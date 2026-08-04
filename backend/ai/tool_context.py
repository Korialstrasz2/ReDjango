from dataclasses import dataclass

from .models import AIChangeSet


@dataclass(frozen=True)
class AIToolExecutionContext:
    """Explicit runtime state available only to tools that declare they need it."""

    change_set: AIChangeSet | None = None
    run_id: str | None = None
    conversation_id: int | None = None
