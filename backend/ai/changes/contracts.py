from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol


@dataclass(frozen=True)
class PreparedChange:
    values: dict[str, Any]
    original_snapshot: dict[str, Any]
    field_schema: list[dict[str, Any]]
    display_label: str
    base_updated_at: datetime | None = None
    base_digest: str = ""
    warnings: list[dict[str, Any]] = field(default_factory=list)


class ChangeEntityHandler(Protocol):
    entity_type: str
    label: str
    minimum_role: str
    supported_actions: frozenset[str]

    def require_access(self, user, giocatore, action: str) -> None: ...

    def field_schema(self, user, giocatore, *, action: str, instance=None) -> list[dict[str, Any]]: ...

    def search(self, user, giocatore, query: str, limit: int) -> list[dict[str, Any]]: ...

    def snapshot(self, user, giocatore, object_id: int, *, for_update: bool = False) -> dict[str, Any]: ...

    def prepare_create(self, user, giocatore, values: dict[str, Any], source_id: int | None = None) -> PreparedChange: ...

    def prepare_update(
        self,
        user,
        giocatore,
        object_id: int,
        values: dict[str, Any],
        *,
        for_update: bool = False,
    ) -> PreparedChange: ...

    def prepare_archive(
        self,
        user,
        giocatore,
        object_id: int,
        *,
        for_update: bool = False,
    ) -> PreparedChange: ...

    def apply_create(self, user, giocatore, values: dict[str, Any]) -> dict[str, Any]: ...

    def apply_update(self, user, giocatore, object_id: int, values: dict[str, Any]) -> dict[str, Any]: ...

    def apply_archive(self, user, giocatore, object_id: int) -> dict[str, Any]: ...
