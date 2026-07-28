"""Import the Sanguine campaign's factions, reputation history, and lore
characters from The Elder Django's ``LoreCampagna`` JSON blob.

The source stored one live snapshot (``felicita``) recomputed from
``felicita_base`` by replaying ``fazioni_modifier_events`` in timestamp order —
the same single-hop, delta-times-coefficient propagation this app's own
``backend.lore.services`` implements. Because only the *current* reaction
grid was ever persisted, not a history of it, replaying old events against
ReDjango's engine would silently use today's coefficients for yesterday's
events. Instead this importer copies each event's already-resolved per-faction
deltas verbatim, so history is preserved exactly as Elder recorded it.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from django.core.files import File
from django.core.management.base import CommandError
from django.db import transaction

from backend.core.models import DatiCampagna
from backend.media_library.models import ImageCategory, UploadedImage

from .models import (
    EffettoEventoReputazione,
    EventoReputazione,
    Fazione,
    PersonaggioLore,
    RelazioneFazione,
    clamp_reputation,
)

SOURCE_PROJECT = "the_elder_django"
DEFAULT_SOURCE_ROOT = Path(r"C:\Users\alexo\PycharmProjects\firstDjango\the_elder_django")
SOURCE_CAMPAIGN_NAME = "Sanguine"

# The source LoreCampagna JSON stores a stale filename for this portrait; the
# file on disk (and the catalog entry already imported by
# import_legacy_images) uses the name without the upload de-duplication
# suffix. Verified by hand: same character, same image.
KNOWN_IMAGE_PATH_FIXES = {
    "uploaded_images/priapo-tricax_Jlz6AEa.png": "uploaded_images/priapo-tricax.png",
}


def _connect_read_only(database: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _legacy_relative_path(raw: str) -> str:
    """``/media/uploaded_images/x.png`` -> ``uploaded_images/x.png``."""
    value = (raw or "").strip().lstrip("/")
    if value.startswith("media/"):
        value = value[len("media/"):]
    return value


class LoreImporter:
    def __init__(self, source_root: Path):
        self.source_root = source_root
        self.connection = _connect_read_only(source_root / "db.sqlite3")
        self.warnings: list[dict[str, Any]] = []
        self.campaign = DatiCampagna.objects.filter(nome=SOURCE_CAMPAIGN_NAME, archived_at__isnull=True).first()
        if self.campaign is None:
            raise CommandError(
                f"Campagna '{SOURCE_CAMPAIGN_NAME}' non trovata in ReDjango. "
                "Importa prima la campagna con import_elder_characters."
            )

    def close(self) -> None:
        self.connection.close()

    # -- source reading ---------------------------------------------------

    def _source_lore(self) -> sqlite3.Row:
        campaign_row = self.connection.execute(
            "SELECT id FROM django_slim_daticampagna WHERE nome = ?",
            (SOURCE_CAMPAIGN_NAME,),
        ).fetchone()
        if campaign_row is None:
            raise CommandError(f"Campagna Elder '{SOURCE_CAMPAIGN_NAME}' non trovata nel database sorgente.")
        lore_row = self.connection.execute(
            "SELECT * FROM django_slim_lorecampagna WHERE campagna_id = ?",
            (campaign_row["id"],),
        ).fetchone()
        if lore_row is None:
            raise CommandError(f"Nessun LoreCampagna Elder collegato a '{SOURCE_CAMPAIGN_NAME}'.")
        return lore_row

    def _json_field(self, lore_row: sqlite3.Row, column: str, default):
        import json

        raw = lore_row[column]
        if not raw:
            return default
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            return default

    # -- media --------------------------------------------------------

    def _resolve_image(self, legacy_path: str, *, title: str, group: str) -> UploadedImage | None:
        relative = _legacy_relative_path(legacy_path)
        if not relative:
            return None
        relative = KNOWN_IMAGE_PATH_FIXES.get(relative, relative)
        existing = UploadedImage.objects.filter(metadata__legacyImagePath=relative).first()
        if existing is not None:
            return existing
        file_path = self.source_root / "media" / relative
        if not file_path.is_file():
            self.warnings.append({"type": "missing_image", "path": relative})
            return None
        category = ImageCategory.objects.filter(slug="personaggi", is_active=True).first()
        asset = UploadedImage(
            title=title[:180],
            folder="personaggi",
            usage_type="character_portrait",
            category=category,
            group=group[:160],
            source=SOURCE_PROJECT,
            metadata={
                "sourceProject": SOURCE_PROJECT,
                "sourceType": "lore_portrait",
                "legacyImagePath": relative,
            },
        )
        with file_path.open("rb") as handle:
            asset.file.save(file_path.name, File(handle), save=False)
        asset.save()
        return asset

    # -- preview --------------------------------------------------------

    def preview(self) -> dict[str, Any]:
        lore_row = self._source_lore()
        fazioni = self._json_field(lore_row, "fazioni", [])
        relazioni = self._json_field(lore_row, "relazioni_fazioni", {})
        eventi = self._json_field(lore_row, "fazioni_modifier_events", [])
        personaggi = self._json_field(lore_row, "personaggi", [])

        def _existing_source_ids(queryset) -> set[str]:
            # SQLite's JSON extraction returns a number for a numeric-looking
            # key, even though it was stored as a string, so every id is
            # compared as text on both sides.
            return {str(value) for value in queryset.exclude(metadata__sourceId__isnull=True).values_list("metadata__sourceId", flat=True)}

        existing_factions = _existing_source_ids(Fazione.objects.filter(campagna=self.campaign, archived_at__isnull=True))
        existing_events = _existing_source_ids(EventoReputazione.objects.filter(campagna=self.campaign))
        existing_npcs = _existing_source_ids(PersonaggioLore.objects.filter(campagna=self.campaign, archived_at__isnull=True))
        relation_pairs = sum(
            1 for targets in relazioni.values() if isinstance(targets, dict)
            for coefficient in targets.values() if coefficient
        )
        return {
            "mode": "dry-run",
            "campaign": self.campaign.nome,
            "factions": {"total": len(fazioni), "alreadyImported": len(existing_factions & {str(f.get("id")) for f in fazioni})},
            "relations": relation_pairs,
            "events": {"total": len(eventi), "alreadyImported": len(existing_events & {str(e.get("id")) for e in eventi})},
            "characters": {"total": len(personaggi), "alreadyImported": len(existing_npcs & {str(p.get("id")) for p in personaggi})},
        }

    # -- apply --------------------------------------------------------

    @transaction.atomic
    def apply(self) -> dict[str, Any]:
        lore_row = self._source_lore()
        fazioni = self._json_field(lore_row, "fazioni", [])
        relazioni = self._json_field(lore_row, "relazioni_fazioni", {})
        eventi = self._json_field(lore_row, "fazioni_modifier_events", [])
        personaggi = self._json_field(lore_row, "personaggi", [])

        faction_by_source_id = self._import_factions(fazioni, eventi)
        relation_count = self._import_relations(relazioni, faction_by_source_id)
        event_count = self._import_events(eventi, faction_by_source_id)
        character_count = self._import_characters(personaggi, faction_by_source_id)

        return {
            "mode": "apply",
            "campaign": self.campaign.nome,
            "factions": len(faction_by_source_id),
            "relations": relation_count,
            "events": event_count,
            "characters": character_count,
            "warnings": self.warnings,
        }

    def _import_factions(self, fazioni: list[dict], eventi: list[dict]) -> dict[str, Fazione]:
        # Elder's stored `felicita_base` turned out to be a later, event-less
        # manual override (edited straight through the faction editor) that
        # never actually fed the replay: Elder's own recompute takes each
        # event's cached `result` verbatim, so for any faction touched by at
        # least one event `felicita_base` is dead data. The authoritative
        # current value is `felicita`. To seed ReDjango's engine — which
        # really does replay base + every imported delta — the base is
        # reverse-derived as felicita minus the sum of every delta the
        # faction ever received, so replaying those same deltas reproduces
        # Elder's real current standing instead of drifting from a stale base.
        total_delta_by_source_id: dict[str, int] = {}
        for event in eventi:
            if not isinstance(event, dict):
                continue
            for effect in event.get("effects") or []:
                if not isinstance(effect, dict) or not effect.get("id"):
                    continue
                try:
                    delta = int(effect.get("delta", 0))
                except (TypeError, ValueError):
                    delta = 0
                fid = str(effect["id"])
                total_delta_by_source_id[fid] = total_delta_by_source_id.get(fid, 0) + delta

        by_source_id: dict[str, Fazione] = {}
        for order, entry in enumerate(fazioni):
            if not isinstance(entry, dict) or not entry.get("id"):
                continue
            source_id = str(entry["id"])
            faction = Fazione.objects.filter(campagna=self.campaign, metadata__sourceId=source_id).first()
            if faction is None:
                faction = Fazione.objects.filter(
                    campagna=self.campaign,
                    nome__iexact=str(entry.get("nome") or ""),
                    archived_at__isnull=True,
                ).first()
            if faction is None:
                faction = Fazione(campagna=self.campaign)
            faction.nome = str(entry.get("nome") or "").strip()[:160] or faction.nome or "Fazione"
            faction.descrizione = str(entry.get("descrizione") or "")
            current_value = entry.get("felicita", entry.get("felicita_base", 0)) or 0
            try:
                current_value = int(current_value)
            except (TypeError, ValueError):
                current_value = 0
            faction.reputazione_base = clamp_reputation(current_value - total_delta_by_source_id.get(source_id, 0))
            faction.ordine = order
            image_path = str(entry.get("immagine") or "")
            if image_path:
                faction.emblema = self._resolve_image(image_path, title=faction.nome, group="Fazioni")
            faction.metadata = {**(faction.metadata or {}), "sourceProject": SOURCE_PROJECT, "sourceId": source_id}
            faction.save()
            by_source_id[source_id] = faction
        return by_source_id

    def _import_relations(self, relazioni: dict, faction_by_source_id: dict[str, Fazione]) -> int:
        RelazioneFazione.objects.filter(origine__in=faction_by_source_id.values()).delete()
        rows = []
        for source_id, targets in relazioni.items():
            origin = faction_by_source_id.get(str(source_id))
            if origin is None or not isinstance(targets, dict):
                continue
            for target_id, coefficient in targets.items():
                destination = faction_by_source_id.get(str(target_id))
                if destination is None or destination.id == origin.id:
                    continue
                try:
                    value = round(float(coefficient), 3)
                except (TypeError, ValueError):
                    continue
                if not value:
                    continue
                rows.append(RelazioneFazione(origine=origin, destinazione=destination, coefficiente=value))
        RelazioneFazione.objects.bulk_create(rows)
        return len(rows)

    def _import_events(self, eventi: list[dict], faction_by_source_id: dict[str, Fazione]) -> int:
        ordered = sorted(
            (event for event in eventi if isinstance(event, dict) and event.get("id")),
            key=lambda event: event.get("timestamp") or "",
        )
        imported = 0
        for event in ordered:
            source_id = str(event["id"])
            if EventoReputazione.objects.filter(campagna=self.campaign, metadata__sourceId=source_id).exists():
                continue
            raw_effects = event.get("effects")
            if not isinstance(raw_effects, list) or not raw_effects:
                continue
            record = EventoReputazione.objects.create(
                campagna=self.campaign,
                titolo="",
                motivo=str(event.get("reason") or "").strip() or "(motivo non registrato)",
                modalita=EventoReputazione.MODE_ADJUST,
                giorno_campagna=0,
                ora_campagna="",
                visibile_ai_giocatori=True,
                registrato_da="Importato da The Elder Django",
                metadata={
                    "sourceProject": SOURCE_PROJECT,
                    "sourceId": source_id,
                    "sourceTimestamp": event.get("timestamp") or "",
                },
            )
            authored_source = str(event.get("source") or "")
            effect_rows = []
            for index, effect in enumerate(raw_effects):
                if not isinstance(effect, dict) or not effect.get("id"):
                    continue
                faction = faction_by_source_id.get(str(effect["id"]))
                if faction is None:
                    self.warnings.append({"type": "unknown_faction_in_event", "eventId": source_id, "factionId": effect["id"]})
                    continue
                try:
                    delta = int(effect.get("delta", 0))
                except (TypeError, ValueError):
                    delta = 0
                effect_rows.append(EffettoEventoReputazione(
                    evento=record,
                    fazione=faction,
                    delta=delta,
                    valore_assoluto=None,
                    propagato=str(effect["id"]) != authored_source,
                    ordine=index,
                ))
            if not effect_rows:
                record.delete()
                continue
            EffettoEventoReputazione.objects.bulk_create(effect_rows)
            imported += 1
        return imported

    def _import_characters(self, personaggi: list[dict], faction_by_source_id: dict[str, Fazione]) -> int:
        faction_by_name = {faction.nome.casefold(): faction for faction in faction_by_source_id.values()}
        imported = 0
        for order, entry in enumerate(personaggi):
            if not isinstance(entry, dict) or not entry.get("id"):
                continue
            source_id = str(entry["id"])
            npc = PersonaggioLore.objects.filter(campagna=self.campaign, metadata__sourceId=source_id).first()
            if npc is None:
                npc = PersonaggioLore.objects.filter(
                    campagna=self.campaign,
                    nome__iexact=str(entry.get("nome") or ""),
                    archived_at__isnull=True,
                ).first()
            if npc is None:
                npc = PersonaggioLore(campagna=self.campaign)
            npc.nome = str(entry.get("nome") or "").strip()[:180] or npc.nome or "Personaggio"
            npc.descrizione = str(entry.get("dati") or "")
            npc.visibile_ai_giocatori = True
            npc.ordine = order

            references = entry.get("riferimenti") if isinstance(entry.get("riferimenti"), list) else []
            faction_mentions = [
                ref.split(":", 1)[1].strip()
                for ref in references
                if isinstance(ref, str) and ref.lower().startswith("fazione:")
            ]
            resolved_faction = None
            if len(faction_mentions) == 1:
                resolved_faction = faction_by_name.get(faction_mentions[0].casefold())
                if resolved_faction is None:
                    self.warnings.append({"type": "unresolved_faction_reference", "character": npc.nome, "faction": faction_mentions[0]})
            elif len(faction_mentions) > 1:
                self.warnings.append({"type": "ambiguous_faction_reference", "character": npc.nome, "candidates": faction_mentions})
            npc.fazione = resolved_faction

            image_path = str(entry.get("immagine") or "")
            if image_path:
                npc.ritratto = self._resolve_image(image_path, title=npc.nome, group="Lore")

            npc.metadata = {
                **(npc.metadata or {}),
                "sourceProject": SOURCE_PROJECT,
                "sourceId": source_id,
                "hofId": entry.get("hof_id"),
                "imageCaption": entry.get("immagine_nome") or "",
                "references": references,
            }
            npc.save()
            imported += 1
        return imported


__all__ = ["DEFAULT_SOURCE_ROOT", "LoreImporter", "SOURCE_CAMPAIGN_NAME"]
