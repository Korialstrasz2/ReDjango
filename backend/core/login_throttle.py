import hashlib
from dataclasses import dataclass
from datetime import timedelta

from django.db import IntegrityError, models
from django.utils import timezone

from .models import LoginThrottle
from .request_security import client_ip


LOGIN_FAILURE_LIMIT = 5
LOGIN_FAILURE_WINDOW_SECONDS = 300


@dataclass(frozen=True)
class ThrottleState:
    limited: bool
    retry_after: int


def _key(request, username: str) -> str:
    normalized = username.strip().casefold()
    material = f"{client_ip(request)}\0{normalized}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def throttle_state(request, username: str) -> ThrottleState:
    now = timezone.now()
    cutoff = now - timedelta(seconds=LOGIN_FAILURE_WINDOW_SECONDS)
    bucket = LoginThrottle.objects.filter(key=_key(request, username)).first()
    if bucket is None or bucket.window_started_at <= cutoff:
        return ThrottleState(False, 0)
    elapsed = max(0, int((now - bucket.window_started_at).total_seconds()))
    retry_after = max(1, LOGIN_FAILURE_WINDOW_SECONDS - elapsed)
    return ThrottleState(bucket.failures >= LOGIN_FAILURE_LIMIT, retry_after)


def register_login_failure(request, username: str) -> ThrottleState:
    key = _key(request, username)
    now = timezone.now()
    cutoff = now - timedelta(seconds=LOGIN_FAILURE_WINDOW_SECONDS)

    def increment_existing() -> int:
        return LoginThrottle.objects.filter(key=key).update(
            failures=models.Case(
                models.When(window_started_at__lte=cutoff, then=models.Value(1)),
                models.When(failures__gte=65535, then=models.Value(65535)),
                default=models.F("failures") + 1,
                output_field=models.PositiveSmallIntegerField(),
            ),
            window_started_at=models.Case(
                models.When(window_started_at__lte=cutoff, then=models.Value(now)),
                default=models.F("window_started_at"),
                output_field=models.DateTimeField(),
            ),
            updated_at=now,
        )

    if increment_existing() == 0:
        try:
            LoginThrottle.objects.create(
                key=key,
                failures=1,
                window_started_at=now,
            )
        except IntegrityError:
            # Another worker created this bucket between UPDATE and INSERT.
            increment_existing()
    return throttle_state(request, username)


def clear_login_failures(request, username: str) -> None:
    LoginThrottle.objects.filter(key=_key(request, username)).delete()
