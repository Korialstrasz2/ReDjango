import mimetypes
import os
import secrets
import socket
from ipaddress import ip_network
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured


mimetypes.add_type("image/webp", ".webp")

BASE_DIR = Path(__file__).resolve().parent.parent

ACCESS_MODES = {"locked", "lan", "online"}
ACCESS_MODE_STATE_FILE = BASE_DIR / ".redjango-access-mode"
configured_access_mode = os.environ.get("REDJANGO_ACCESS_MODE", "").strip().lower()
if not configured_access_mode and ACCESS_MODE_STATE_FILE.exists():
    configured_access_mode = ACCESS_MODE_STATE_FILE.read_text(encoding="utf-8").strip().lower()
REDJANGO_ACCESS_MODE = configured_access_mode or "locked"
if REDJANGO_ACCESS_MODE not in ACCESS_MODES:
    raise ImproperlyConfigured("REDJANGO_ACCESS_MODE deve essere locked, lan oppure online.")


def _environment_list(name: str) -> list[str]:
    return [value.strip() for value in os.environ.get(name, "").split(",") if value.strip()]


configured_secret_key = os.environ.get("REDJANGO_SECRET_KEY", "").strip()
if REDJANGO_ACCESS_MODE == "online" and (
    len(configured_secret_key) < 50
    or configured_secret_key == "dev-only-redjango-secret-key"
):
    raise ImproperlyConfigured(
        "La modalità online richiede REDJANGO_SECRET_KEY con almeno 50 caratteri."
    )
if configured_secret_key:
    SECRET_KEY = configured_secret_key
else:
    local_state_directory = BASE_DIR / ".redjango"
    local_secret_path = local_state_directory / "django-secret-key"
    stored_local_secret = ""
    if local_secret_path.is_file():
        stored_local_secret = local_secret_path.read_text(encoding="utf-8").strip()
    if len(stored_local_secret) >= 50:
        SECRET_KEY = stored_local_secret
    else:
        local_state_directory.mkdir(parents=True, exist_ok=True)
        SECRET_KEY = secrets.token_urlsafe(64)
        temporary_secret_path = local_secret_path.with_name(
            f"{local_secret_path.name}.{os.getpid()}.tmp"
        )
        temporary_secret_path.write_text(f"{SECRET_KEY}\n", encoding="utf-8")
        temporary_secret_path.replace(local_secret_path)

# Debug pages disclose settings, SQL and local variables. They are opt-in in
# every access mode, including LAN.
DEBUG = os.environ.get("REDJANGO_DEBUG", "0") == "1"

configured_hosts = _environment_list("REDJANGO_ALLOWED_HOSTS")
if configured_hosts:
    ALLOWED_HOSTS = configured_hosts
elif REDJANGO_ACCESS_MODE == "online":
    raise ImproperlyConfigured("La modalità online richiede REDJANGO_ALLOWED_HOSTS.")
else:
    local_hosts = {"127.0.0.1", "localhost", "::1"}
    if REDJANGO_ACCESS_MODE == "lan":
        hostname = socket.gethostname()
        local_hosts.add(hostname)
        try:
            local_hosts.update(
                address[4][0]
                for address in socket.getaddrinfo(hostname, None)
                if address[4] and address[4][0]
            )
        except socket.gaierror:
            pass
    ALLOWED_HOSTS = sorted(local_hosts)

CSRF_TRUSTED_ORIGINS = _environment_list("REDJANGO_CSRF_TRUSTED_ORIGINS")
if REDJANGO_ACCESS_MODE == "locked":
    CSRF_TRUSTED_ORIGINS.extend([
        "http://127.0.0.1:8003",
        "http://localhost:8003",
    ])
elif REDJANGO_ACCESS_MODE == "lan":
    CSRF_TRUSTED_ORIGINS.extend(
        f"https://{host}:8003"
        for host in ALLOWED_HOSTS
        if ":" not in host
    )

configured_trusted_proxies = _environment_list("REDJANGO_TRUSTED_PROXIES")
if not configured_trusted_proxies and REDJANGO_ACCESS_MODE == "online":
    configured_trusted_proxies = ["127.0.0.0/8", "::1/128"]
try:
    REDJANGO_TRUSTED_PROXIES = [
        str(ip_network(value, strict=False))
        for value in configured_trusted_proxies
    ]
except ValueError as exc:
    raise ImproperlyConfigured(
        "REDJANGO_TRUSTED_PROXIES deve contenere indirizzi o reti CIDR validi."
    ) from exc

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "backend.core",
    "backend.media_library",
    "backend.characters",
    "backend.dice_tools",
    "backend.combat",
    "backend.lore",
]

MIDDLEWARE = [
    "backend.core.middleware.TrustedProxyHeadersMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "backend.core.middleware.LockedModeMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "backend.core.middleware.AdminLoginThrottleMiddleware",
    "backend.core.middleware.AccessControlMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "redjango.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "frontend" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "redjango.wsgi.application"
ASGI_APPLICATION = "redjango.asgi.application"

configured_database_name = os.environ.get("REDJANGO_DATABASE_NAME", "").strip()
database_name = Path(configured_database_name) if configured_database_name else BASE_DIR / "db.sqlite3"
if not database_name.is_absolute():
    database_name = BASE_DIR / database_name

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": database_name,
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "it"
TIME_ZONE = "Europe/Rome"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "frontend" / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "whitenoise.storage.CompressedManifestStaticFilesStorage"
            if REDJANGO_ACCESS_MODE == "online"
            else "django.contrib.staticfiles.storage.StaticFilesStorage"
        )
    },
}
WHITENOISE_USE_FINDERS = REDJANGO_ACCESS_MODE != "online"
WHITENOISE_AUTOREFRESH = DEBUG

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Keep uploads bounded before they are parsed or persisted. The image service
# applies a stricter per-file limit.
DATA_UPLOAD_MAX_MEMORY_SIZE = 12 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/login/"

SESSION_COOKIE_NAME = "redjango_sessionid"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = REDJANGO_ACCESS_MODE in {"lan", "online"}
CSRF_COOKIE_SECURE = REDJANGO_ACCESS_MODE in {"lan", "online"}
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_COOKIE_AGE = 60 * 60 * 12

if REDJANGO_ACCESS_MODE == "online":
    SECURE_SSL_REDIRECT = os.environ.get("REDJANGO_SECURE_SSL_REDIRECT", "1") == "1"
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    USE_X_FORWARDED_HOST = os.environ.get("REDJANGO_USE_X_FORWARDED_HOST", "0") == "1"
    SECURE_HSTS_SECONDS = int(os.environ.get("REDJANGO_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
