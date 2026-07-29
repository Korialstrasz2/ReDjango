from __future__ import annotations

import json
import math
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from backend.characters.models import (
    PERSONAGGIO_TOT_KEYS,
    ContenitoreInventario,
    EffettiPersonaggio,
    EffettoPersonalizzato,
    Equip,
    Faretra,
    Note,
    OperazioneEffettoPersonalizzato,
    Personaggio,
    SkillPersonaggio,
    VoceContenitoreInventario,
    Zaino,
)
from backend.characters.services.custom_effects import EFFECT_ICONS
from backend.characters.services.refresh_personaggio import (
    DEFAULT_PROFILE_NAME,
    normalize_stat_key,
    refresh_personaggio,
)
from backend.core.models import DatiCampagna, Giocatore, GlobalModifiers, Oggetto, Skill
from backend.core.skill_services import _create_passive_instances
from backend.core.spell_economy_repair import redundant_manual_operation, skill_derived_spell_economy
from backend.media_library.models import DatiMappa, ImageCategory, UploadedImage


SOURCE_PROJECT = "the_elder_django"
SOURCE_CHARACTER_IDS = (88, 111, 149, 153, 211)
DEFAULT_SOURCE_ROOT = Path(r"C:\Users\alexo\PycharmProjects\firstDjango\the_elder_django")
PORTRAIT_FILES = {
    88: "Master.png",
    111: "Illaoi Karanen.png",
    149: "Rhyss Arcane.png",
    153: "Ra'Zirr.png",
    211: "Mog gro-Ghor.png",
}
APPEARANCE_KEYS = {88: "master", 111: "illaoi", 149: "rhyss", 153: "razirr", 211: "mog"}
SENTINELS = {"", "none", "null", "vuoto", "empty", "assente", "false"}
NOTE_REPORT_START = "[Rapporto importazione Elder Django — INIZIO]"
NOTE_REPORT_END = "[Rapporto importazione Elder Django — FINE]"
# Elder's Ordine/Caos ratio pairs collapse onto a single ReDjango target, so the
# two halves are merged into one operation instead of being applied twice.
# en_per_mana/pa_per_mana are deliberately absent: Elder deleted their formulas in
# migration 0118 and nothing has read them since.
COLLAPSED_MAGIC_TARGETS = {
    "ogni_en_x_mana_ordine": "ogni_en_x_mana",
    "ogni_en_x_mana_caos": "ogni_en_x_mana",
    "ogni_pa_x_mana_ordine": "ogni_pa_x_mana",
    "ogni_pa_x_mana_caos": "ogni_pa_x_mana",
}
# Per-character starting values Elder stored on the NPC itself. The Ordine and Caos
# halves are averaged, matching how their bonuses collapse onto one unified ratio.
MAGIC_BASE_FIELDS = {
    "ogni_en_x_mana": ("ogni_en_x_mana_ordine_base", "ogni_en_x_mana_caos_base"),
    "ogni_pa_x_mana": ("ogni_pa_x_mana_ordine_base", "ogni_pa_x_mana_caos_base"),
    "sconto_mana_per_potere": ("sconto_mana_per_potere_base",),
    "sconto_pa_per_potere": ("sconto_pa_per_potere_base",),
}
ALCHEMY_MULTIPLIER_TARGETS = {
    "moltiplicatore_rossi": "moltiplicatore_reagenti_rossi",
    "moltiplicatore_verdi": "moltiplicatore_reagenti_verdi",
    "moltiplicatore_blu": "moltiplicatore_reagenti_blu",
    "moltiplicatore_lv_1": "moltiplicatore_reagenti_livello_1",
    "moltiplicatore_lv_2": "moltiplicatore_reagenti_livello_2",
    "moltiplicatore_lv_3": "moltiplicatore_reagenti_livello_3",
    "moltiplicatore_lv_4": "moltiplicatore_reagenti_livello_4",
}
EQUIP_SLOTS = (
    "arma", "armatura", "scudo", "chainmail", "veste",
    *(f"anello_{index}" for index in range(1, 9)),
    *(f"orecchino_{index}" for index in range(1, 7)),
    "spilla", "fascia", "amuleto", "cintura", "vestiti", "mantello", "borsello",
    *(f"sacco_{index}" for index in range(1, 4)),
    *(f"faretra_{index}" for index in range(1, 3)),
    *(f"extra_slot_{index}" for index in range(1, 5)),
)
ALLOWED_EFFECT_ICONS = {entry[0] for entry in EFFECT_ICONS}


def _json(value: Any, fallback: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value or "")
    except (TypeError, ValueError, json.JSONDecodeError):
        return fallback


def _meaningful(value: Any) -> str:
    text = str(value or "").strip()
    return "" if text.casefold() in SENTINELS else text


def _integer(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _normalize_competenze(value: Any) -> dict[str, dict[str, int]]:
    source = _json(value, {})
    if not isinstance(source, dict):
        return {}
    result = {}
    for key, raw_tracks in source.items():
        tracks = raw_tracks if isinstance(raw_tracks, dict) else {}
        result[str(key)] = {
            "barra1": _integer(tracks.get("barra1")),
            "barra2": _integer(tracks.get("barra2")),
            "extra": _integer(tracks.get("extra")),
        }
    return result


def _merge_note_fields(row: sqlite3.Row | None, fields: Iterable[str]) -> str:
    if row is None:
        return ""
    return "\n".join(text for field in fields if (text := _meaningful(row[field])))


def _converted_expression(value: Any) -> str:
    text = str(value if value is not None else "0").strip().replace("(f)", "")

    def replace_personaggio(match: re.Match) -> str:
        field = normalize_stat_key(match.group(1))
        if field == "livello":
            return "personaggio.livello"
        if field in PERSONAGGIO_TOT_KEYS:
            return f"final.{field}"
        return f"personaggio.{field}"

    return re.sub(r"Personaggio\.([A-Za-z0-9_]+)", replace_personaggio, text, flags=re.IGNORECASE)


def _average_expressions(values: list[str]) -> str:
    if len(values) == 1 or len(set(values)) == 1:
        return values[0]
    numeric = [_number(value) for value in values]
    if all(value is not None for value in numeric):
        average = sum(value for value in numeric if value is not None) / len(numeric)
        return str(int(average)) if average.is_integer() else str(round(average, 8))
    return f"({' + '.join(f'({value})' for value in values)}) / {len(values)}"


def converted_effect_operations(effect: dict[str, Any]) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    operations: list[dict[str, str]] = []
    collapsed: dict[tuple[str, str], list[str]] = defaultdict(list)
    skipped: list[dict[str, Any]] = []
    operation_map = {"+": "add", "-": "subtract"}
    for raw in effect.get("effetti", []) if isinstance(effect.get("effetti"), list) else []:
        if not isinstance(raw, dict):
            skipped.append({"reason": "operation_not_object", "value": raw})
            continue
        raw_target = normalize_stat_key(raw.get("name"))
        target = COLLAPSED_MAGIC_TARGETS.get(raw_target, raw_target)
        operation = operation_map.get(str(raw.get("operation") or "").strip())
        if target not in PERSONAGGIO_TOT_KEYS or operation is None:
            skipped.append({"reason": "unsupported_target_or_operation", "value": raw})
            continue
        expression = _converted_expression(raw.get("value"))
        if raw_target in COLLAPSED_MAGIC_TARGETS:
            collapsed[(target, operation)].append(expression)
        else:
            operations.append({"target": target, "operation": operation, "value": expression})
    for (target, operation), values in collapsed.items():
        operations.append({"target": target, "operation": operation, "value": _average_expressions(values)})
    return operations, skipped


def normalized_elder_totals(raw_totals: Any) -> dict[str, float]:
    source = _json(raw_totals, {})
    if not isinstance(source, dict):
        return {}
    result: dict[str, float] = {}
    collapsed: dict[str, list[float]] = defaultdict(list)
    for raw_key, raw_value in source.items():
        value = _number(raw_value)
        if value is None:
            continue
        normalized = normalize_stat_key(raw_key)
        if normalized in COLLAPSED_MAGIC_TARGETS:
            collapsed[COLLAPSED_MAGIC_TARGETS[normalized]].append(value)
        elif normalized in PERSONAGGIO_TOT_KEYS:
            result[normalized] = value
    for key, values in collapsed.items():
        result[key] = sum(values) / len(values)
    return result


class ElderCharacterImporter:
    def __init__(self, source_root: Path):
        self.source_root = source_root
        self.connection = sqlite3.connect(f"file:{source_root / 'db.sqlite3'}?mode=ro", uri=True)
        self.connection.row_factory = sqlite3.Row
        self.warnings: list[dict[str, Any]] = []
        self.skipped_operations: list[dict[str, Any]] = []
        self.item_by_source_id = {
            int(metadata["sourceId"]): item
            for item in Oggetto.objects.filter(archived_at__isnull=True)
            if isinstance((metadata := item.metadata), dict)
            and metadata.get("sourceProject") == SOURCE_PROJECT
            and isinstance(metadata.get("sourceId"), int)
        }
        self.skill_by_name = {
            skill.nome.strip().casefold(): skill
            for skill in Skill.objects.filter(archived_at__isnull=True).select_related("famiglia")
        }
        self.source_item_names: dict[int, str] = {}

    def close(self):
        self.connection.close()

    def row(self, table: str, row_id: int | None) -> sqlite3.Row | None:
        if not row_id:
            return None
        return self.connection.execute(f"SELECT * FROM {table} WHERE id = ?", (row_id,)).fetchone()

    def selected_characters(self) -> list[sqlite3.Row]:
        placeholders = ",".join("?" for _ in SOURCE_CHARACTER_IDS)
        rows = self.connection.execute(
            f"SELECT * FROM django_slim_npc WHERE id IN ({placeholders}) ORDER BY id",
            SOURCE_CHARACTER_IDS,
        ).fetchall()
        found = {row["id"] for row in rows}
        missing = sorted(set(SOURCE_CHARACTER_IDS) - found)
        if missing:
            raise CommandError(f"Personaggi Elder mancanti: {missing}")
        return rows

    def source_item_name(self, source_id: int) -> str:
        if source_id not in self.source_item_names:
            row = self.row("django_slim_oggetto", source_id)
            self.source_item_names[source_id] = str(row["nome"] if row else "")
        return self.source_item_names[source_id]

    def target_item(self, source_id: int | None, *, context: str) -> Oggetto | None:
        if not source_id:
            return None
        item = self.item_by_source_id.get(int(source_id))
        if item:
            return item
        name = self.source_item_name(int(source_id))
        if _meaningful(name) and name.casefold() not in {"no mantello", "no borsello"}:
            self.warnings.append({"type": "missing_item", "sourceId": source_id, "name": name, "context": context})
        return None

    def resolve_media_path(self, stored_name: str) -> Path:
        normalized = stored_name.replace("/", "\\")
        candidates = (self.source_root / "media" / normalized, self.source_root / normalized)
        return next((path for path in candidates if path.is_file()), candidates[0])

    def imported_image(
        self,
        *,
        source_type: str,
        source_key: str,
        title: str,
        path: Path,
        usage_type: str,
        category_slug: str,
        folder: str,
        group: str,
        campaign: DatiCampagna | None,
    ) -> UploadedImage:
        if not path.is_file():
            raise CommandError(f"Immagine Elder non trovata: {path}")
        metadata_filter = {
            "metadata__sourceProject": SOURCE_PROJECT,
            "metadata__sourceType": source_type,
            "metadata__sourceKey": source_key,
        }
        asset = UploadedImage.objects.filter(**metadata_filter).first()
        category = ImageCategory.objects.filter(slug=category_slug, is_active=True).first()
        metadata = {
            "sourceProject": SOURCE_PROJECT,
            "sourceType": source_type,
            "sourceKey": source_key,
            "sourcePath": str(path),
        }
        if asset is None:
            asset = UploadedImage(
                title=title[:180],
                usage_type=usage_type,
                category=category,
                folder=folder,
                group=group,
                campagna=campaign,
                source=SOURCE_PROJECT,
                metadata=metadata,
            )
            with path.open("rb") as handle:
                asset.file.save(path.name, File(handle), save=False)
            asset.save()
        else:
            asset.title = title[:180]
            asset.usage_type = usage_type
            asset.category = category
            asset.folder = folder
            asset.group = group
            asset.campagna = campaign
            asset.source = SOURCE_PROJECT
            asset.metadata = {**(asset.metadata or {}), **metadata}
            asset.save()
        return asset

    def import_campaign_and_maps(self) -> tuple[DatiCampagna, int]:
        source = self.connection.execute(
            "SELECT * FROM django_slim_daticampagna WHERE nome = ? ORDER BY id LIMIT 1",
            ("Sanguine",),
        ).fetchone()
        if source is None:
            raise CommandError("La campagna Elder Sanguine non esiste.")
        campaign = DatiCampagna.objects.filter(
            metadata__sourceProject=SOURCE_PROJECT,
            metadata__sourceTable="django_slim_daticampagna",
            metadata__sourceId=source["id"],
        ).first() or DatiCampagna.objects.filter(nome="Sanguine").first()
        if campaign is None:
            campaign = DatiCampagna(nome="Sanguine")
        campaign.nome = "Sanguine"
        campaign.meteo = str(source["meteo"] or "")
        campaign.ora_corrente = str(source["ore"] or "")
        campaign.giorni_da_inizio = _integer(source["giorni_da_inizio"])
        campaign.risorse_speciali = {}
        campaign.state = {}
        campaign.attiva = True
        campaign.metadata = {
            **(campaign.metadata or {}),
            "sourceProject": SOURCE_PROJECT,
            "sourceTable": "django_slim_daticampagna",
            "sourceId": source["id"],
        }
        campaign.save()

        altro = _json(source["altro"], {})
        default_name = str(altro.get("global_map_default_name") or "") if isinstance(altro, dict) else ""
        imported_maps = 0
        default_image = None
        for source_map in self.connection.execute(
            "SELECT * FROM django_slim_globalimage WHERE campagna_id = ? ORDER BY id",
            (source["id"],),
        ):
            image_path = self.resolve_media_path(str(source_map["image"] or ""))
            image = self.imported_image(
                source_type="global_map",
                source_key=str(source_map["id"]),
                title=str(source_map["nome"] or image_path.stem),
                path=image_path,
                usage_type="map",
                category_slug="mappe",
                folder="mappe/Sanguine",
                group="Mappe globali",
                campaign=campaign,
            )
            map_record = DatiMappa.objects.filter(
                metadata__sourceProject=SOURCE_PROJECT,
                metadata__sourceTable="django_slim_globalimage",
                metadata__sourceId=source_map["id"],
            ).first()
            source_grid = _json(source_map["grid_data"], {})
            source_effects = source_grid.pop("hex_effects", {})
            source_markers = source_grid.pop("markers", [])
            if isinstance(source_effects, dict):
                source_effects = {
                    key: effect
                    for key, effect in source_effects.items()
                    if isinstance(effect, dict)
                    and (effect.get("black") or effect.get("bw") or (_number(effect.get("blur")) or 0) > 0)
                }
            if map_record is None:
                map_record = DatiMappa()
            map_record.nome = str(source_map["nome"] or image.title)
            map_record.campagna = campaign
            map_record.image = image
            map_record.tipo = "globale"
            map_record.grid_data = source_grid
            if not map_record.hex_effects and isinstance(source_effects, dict):
                map_record.hex_effects = source_effects
            if not map_record.markers and isinstance(source_markers, list):
                map_record.markers = source_markers
            map_record.default_for_campaign = map_record.nome == default_name
            map_record.metadata = {
                **(map_record.metadata or {}),
                "sourceProject": SOURCE_PROJECT,
                "sourceTable": "django_slim_globalimage",
                "sourceId": source_map["id"],
            }
            map_record.save()
            imported_maps += 1
            if map_record.default_for_campaign:
                default_image = image
        campaign.default_global_map = default_image
        campaign.save(update_fields=["default_global_map", "updated_at"])
        return campaign, imported_maps

    def _upsert_container(self, character: Personaggio | None, field: str, model, name: str):
        existing = getattr(character, field, None) if character else None
        if existing is not None and existing.personaggi.exclude(pk=character.pk).exists():
            existing = None
        return existing or model.objects.create(nome=name[:160])

    def import_inventory(self, source: sqlite3.Row, character: Personaggio | None) -> dict[str, Any]:
        character_name = str(source["nome"])
        equip = self._upsert_container(character, "equip", Equip, f"Equip di {character_name}")
        source_equip = self.row("django_slim_equip", source["equip_id"])
        for slot in EQUIP_SLOTS:
            source_item_id = source_equip[f"{slot}_id"] if source_equip else None
            setattr(equip, slot, self.target_item(source_item_id, context=f"{character_name}.equip.{slot}"))
        equip.metadata = {**(equip.metadata or {}), "sourceProject": SOURCE_PROJECT, "sourceTable": "django_slim_equip", "sourceId": source["equip_id"]}
        equip.save()

        result: dict[str, Any] = {"equip": equip}
        for field, model, table, source_field in (
            ("zaino", Zaino, "django_slim_zaino", "zaino_id"),
            ("faretra", Faretra, "django_slim_faretra", "faretra_id"),
        ):
            container = self._upsert_container(character, field, model, f"{model._meta.verbose_name.title()} di {character_name}")
            source_container = self.row(table, source[source_field])
            for index in range(1, 51):
                source_item_id = source_container[f"slot_{index}_id"] if source_container else None
                setattr(container, f"slot_{index}", self.target_item(source_item_id, context=f"{character_name}.{field}.{index}"))
            container.metadata = {**(container.metadata or {}), "sourceProject": SOURCE_PROJECT, "sourceTable": table, "sourceId": source[source_field]}
            container.save()
            result[field] = container

        note = self._upsert_container(character, "note", Note, f"Note di {character_name}")
        source_note = self.row("django_slim_note", source["note_id"])
        note.zaino = _merge_note_fields(source_note, (f"note_zaino_{index}" for index in range(1, 5)))
        note.combat = _merge_note_fields(source_note, (f"appunti_{index}" for index in range(27, 31)))
        note.competenze = _merge_note_fields(source_note, (f"appunti_{index}" for index in range(25, 27)))
        note.crafting = _merge_note_fields(source_note, (f"note_crafting_{index}" for index in range(1, 5)))
        note.viaggio = _merge_note_fields(source_note, (f"note_viaggio_{index}" for index in range(1, 3)))
        note.appunti = _merge_note_fields(source_note, (f"appunti_{index}" for index in range(1, 25)))
        note.missioni = _merge_note_fields(source_note, (f"note_finestra_principale_{index}" for index in range(1, 11)))
        note.background = _meaningful(source_note["background"] if source_note else "")
        note.metadata = {
            **(note.metadata or {}),
            "sourceProject": SOURCE_PROJECT,
            "sourceTable": "django_slim_note",
            "sourceId": source["note_id"],
            "legacyTracker": {
                "config": _json(source_note["tracker_config"], {}) if source_note else {},
                "state": _json(source_note["tracker_state"], {}) if source_note else {},
            },
        }
        note.save()
        result["note"] = note

        source_alchemy = self.row("django_slim_alchimia", source["alchimia_id"])
        ingredients = {}
        for color, short in (("rossi", "r"), ("verdi", "v"), ("blu", "b")):
            for level in range(1, 5):
                value = _integer(source_alchemy[f"ingredienti_{color}_{level}"] if source_alchemy else 0)
                if value:
                    ingredients[f"{short}{level}"] = value
        result["reagent_values"] = {
            "capacity": max(15, _integer(source_alchemy["slot_max_reagenti"] if source_alchemy else 0)),
            "ingredients": ingredients,
            "metadata": {
                "sourceProject": SOURCE_PROJECT,
                "sourceTable": "django_slim_alchimia",
                "sourceId": source["alchimia_id"],
            },
        }
        result["source_alchemy"] = source_alchemy

        effects = getattr(character, "effetti", None) if character else None
        if effects is not None and effects.personaggi.exclude(pk=character.pk).exists():
            effects = None
        result["effetti"] = effects or EffettiPersonaggio.objects.create(nome=f"Effetti di {character_name}"[:160])
        return result

    def portrait_for(self, source: sqlite3.Row, campaign: DatiCampagna) -> UploadedImage:
        filename = PORTRAIT_FILES[source["id"]]
        path = self.source_root / "django_slim" / "static" / "media" / "images" / "pgs" / filename
        return self.imported_image(
            source_type="character_portrait",
            source_key=str(source["id"]),
            title=str(source["nome"]),
            path=path,
            usage_type="character_portrait",
            category_slug="personaggi",
            folder="personaggi/Sanguine",
            group="Personaggi Sanguine",
            campaign=campaign,
        )

    def import_character(self, source: sqlite3.Row, campaign: DatiCampagna) -> tuple[Personaggio, dict[str, Any]]:
        character = Personaggio.objects.filter(
            metadata__sourceProject=SOURCE_PROJECT,
            metadata__sourceTable="django_slim_npc",
            metadata__sourceId=source["id"],
        ).first()
        if character is None:
            collision = Personaggio.objects.filter(nome_interno=source["nome_interno"]).first()
            if collision:
                raise CommandError(f"Nome interno già in uso: {source['nome_interno']}")
            character = Personaggio(nome=str(source["nome"]), nome_interno=str(source["nome_interno"]), campagna=campaign)

        inventory = self.import_inventory(source, character if character.pk else None)
        character.nome = str(source["nome"])
        character.nome_interno = str(source["nome_interno"])
        character.tipologia = "giocabile" if _meaningful(source["nome"]) else "automatico"
        character.campagna = campaign
        character.portrait = self.portrait_for(source, campaign)
        character.razza_1 = _meaningful(source["razza_1"])
        character.razza_2 = _meaningful(source["razza_2"])
        character.razza_3 = _meaningful(source["razza_3"])
        character.livello = _integer(source["livello"])
        character.eta = _integer(source["eta"]) if source["eta"] is not None else None
        character.sesso = _meaningful(source["sesso"])
        character.monete = _integer(source["monete"])
        character.dettagli_personaggio = str(source["dettagli_personaggio"] or "")
        character.danno = _integer(source["danno"])
        character.mana_speso = _integer(source["mana_speso"])
        character.energia_spesa = _integer(source["energia_spesa"])
        character.potere_speso = _integer(source["potere_speso"])
        character.stanchezza_accumulata = _integer(source["stanchezza_base"])
        character.mana_in_sifone = _integer(source["mana_in_sifone"])
        character.competenze = _normalize_competenze(source["competenze"])
        character.pe_generali = _integer(source["pe_generali"])
        character.pe_rossi = _integer(source["pe_rossi"])
        character.pe_verdi = _integer(source["pe_verdi"])
        character.pe_blu = _integer(source["pe_blu"])
        character.pe_abilita = _integer(source["pe_abilita"])
        character.equip = inventory["equip"]
        character.zaino = inventory["zaino"]
        character.faretra = inventory["faretra"]
        character.note = inventory["note"]
        character.effetti = inventory["effetti"]
        character.abilita = {}
        character.abilita_desiderate = {}
        character.extra = {}
        character.bottoni = {}
        character.crit_min = str(source["crit_min"] or "")
        character.crit_nor = str(source["crit_nor"] or "")
        character.crit_mag = str(source["crit_mag"] or "")
        character.metadata = {
            **(character.metadata or {}),
            "sourceProject": SOURCE_PROJECT,
            "sourceTable": "django_slim_npc",
            "sourceId": source["id"],
            "appearanceKey": APPEARANCE_KEYS[source["id"]],
            "importScope": "sanguine-five",
        }
        character.save()
        reagent_values = inventory["reagent_values"]
        container, _ = ContenitoreInventario.objects.update_or_create(
            scope=ContenitoreInventario.SCOPE_PERSONAL,
            personaggio=character,
            defaults={
                "nome": f"Alchimia&Contenitori · {character.nome}"[:160],
                "capacita": reagent_values["capacity"],
                "senza_peso": True,
                "metadata": reagent_values["metadata"],
            },
        )
        container.voci.exclude(reagent_stock_key="").delete()
        required_capacity = container.voci.count() + len(reagent_values["ingredients"])
        if required_capacity > container.capacita:
            container.capacita = required_capacity
            container.save(update_fields=["capacita", "updated_at"])
        used_slots = set(container.voci.values_list("slot", flat=True))
        for stock_key, quantity in sorted(reagent_values["ingredients"].items()):
            slot = next(
                candidate
                for candidate in range(1, container.capacita + 1)
                if candidate not in used_slots
            )
            VoceContenitoreInventario.objects.create(
                contenitore=container,
                slot=slot,
                reagent_stock_key=stock_key,
                quantita=quantity,
            )
            used_slots.add(slot)
        return character, inventory

    def import_skills(self, source: sqlite3.Row, character: Personaggio) -> int:
        source_skills = _json(source["abilita"], {})
        if not isinstance(source_skills, dict):
            return 0
        imported = 0
        for source_name, raw_cost in source_skills.items():
            skill = self.skill_by_name.get(str(source_name).strip().casefold())
            if skill is None:
                self.warnings.append({"type": "missing_skill", "character": character.nome, "name": source_name})
                continue
            cost = raw_cost if isinstance(raw_cost, dict) else {}
            spend = {
                "red": _integer(cost.get("rossi")),
                "green": _integer(cost.get("verdi")),
                "blue": _integer(cost.get("blu")),
                "general": _integer(cost.get("generali")),
            }
            ownership, created = SkillPersonaggio.objects.get_or_create(
                personaggio=character,
                skill=skill,
                defaults={"spesa_pe": spend},
            )
            metadata = dict(ownership.metadata or {})
            passive_ids = metadata.get("passive_effect_ids", [])
            if created and skill.effetti_passivi:
                passive_ids = _create_passive_instances(character, skill)
            ownership.spesa_pe = spend
            ownership.passivi_accettati = [
                str(passive["id"])
                for passive in skill.effetti_passivi
                if isinstance(passive, dict) and passive.get("id")
            ] if isinstance(skill.effetti_passivi, list) else []
            ownership.note = f"Nota spesa Elder: {_meaningful(cost.get('testo'))}" if _meaningful(cost.get("testo")) else ""
            ownership.metadata = {
                **metadata,
                "sourceProject": SOURCE_PROJECT,
                "sourceCharacterId": source["id"],
                "sourceSkillName": source_name,
                "sourceSpend": cost,
                "passive_effect_ids": passive_ids,
            }
            ownership.save()
            imported += 1
        return imported

    def _available_effect_name(self, character: Personaggio, desired: str, current: EffettoPersonalizzato | None) -> str:
        base = (desired or "Effetto Elder")[:180]
        candidate = base
        suffix = 2
        while EffettoPersonalizzato.objects.filter(personaggio=character, nome=candidate).exclude(pk=current.pk if current else None).exists():
            candidate = f"{base[:170]} ({suffix})"
            suffix += 1
        return candidate

    def upsert_custom_effect(
        self,
        character: Personaggio,
        *,
        marker: str,
        name: str,
        description: str,
        source_origin: str,
        icon: str,
        operations: list[dict[str, str]],
        order: int,
    ) -> EffettoPersonalizzato:
        origin = f"{marker} · {source_origin}"[:180]
        effect = EffettoPersonalizzato.objects.filter(personaggio=character, origine__startswith=marker).first()
        if effect is None:
            effect = EffettoPersonalizzato(personaggio=character)
        effect.nome = self._available_effect_name(character, _meaningful(name) or "Effetto Elder", effect if effect.pk else None)
        effect.descrizione = str(description or "")
        effect.origine = origin
        effect.icona = icon if icon in ALLOWED_EFFECT_ICONS else "runa"
        effect.temporaneo = bool(re.search(r"(?:^|\s)\(t\)(?:\s|$)", effect.descrizione, re.IGNORECASE))
        effect.ordine = order
        effect.save()
        effect.operazioni.all().delete()
        OperazioneEffettoPersonalizzato.objects.bulk_create([
            OperazioneEffettoPersonalizzato(
                effetto=effect,
                ordine=index,
                bersaglio=operation["target"],
                operazione=operation["operation"],
                valore=operation["value"],
            )
            for index, operation in enumerate(operations)
        ])
        return effect

    def magic_base_operations(self, source: sqlite3.Row) -> list[dict[str, str]]:
        """Carry over per-character magic bases that differ from the ReD global base.

        Elder let every character override the starting value of its magic ratios;
        ReDjango derives them from one shared profile. The difference is imported as
        an explicit effect so the cast cost still matches the original character.
        """
        global_base = _json(
            GlobalModifiers.objects.filter(name=DEFAULT_PROFILE_NAME).values_list("value_float", flat=True).first(),
            {},
        )
        operations = []
        for target, source_fields in MAGIC_BASE_FIELDS.items():
            values = [value for field in source_fields if (value := _number(source[field])) is not None]
            if not values:
                continue
            elder_base = sum(values) / len(values)
            red_base = _number(global_base.get(target)) or 0
            delta = round(elder_base - red_base, 8)
            if delta:
                operations.append({
                    "target": target,
                    "operation": "add" if delta > 0 else "subtract",
                    "value": str(abs(delta)),
                })
        return operations

    def import_effects(self, source: sqlite3.Row, character: Personaggio, source_alchemy: sqlite3.Row | None) -> int:
        active = _json(source["act"], {})
        raw_effects = active.get("effetti_extra", []) if isinstance(active, dict) else []
        imported = 0
        used_markers = set()
        # Elder had no automatic skill passives, so players tracked their magic
        # bonuses with a hand-written effect summing every tier. ReDjango derives
        # those from the owned skills; re-importing the manual copy would count
        # them twice, so an operation matching the skill total is dropped.
        skill_totals = skill_derived_spell_economy(character)
        for index, raw_effect in enumerate(raw_effects if isinstance(raw_effects, list) else [], start=1):
            if not isinstance(raw_effect, dict):
                continue
            marker = f"Elder Django #{index:03d}"
            operations, skipped = converted_effect_operations(raw_effect)
            self.skipped_operations.extend(
                {"character": character.nome, "effect": raw_effect.get("nome"), **entry}
                for entry in skipped
            )
            kept = [
                operation
                for operation in operations
                if not redundant_manual_operation(
                    operation["target"], operation["operation"], operation["value"], skill_totals
                )
            ]
            if operations and not kept:
                self.warnings.append({
                    "type": "manual_effect_already_granted_by_skills",
                    "character": character.nome,
                    "effect": raw_effect.get("nome"),
                })
                continue
            operations = kept
            used_markers.add(marker)
            self.upsert_custom_effect(
                character,
                marker=marker,
                name=str(raw_effect.get("nome") or "Effetto Elder"),
                description=str(raw_effect.get("descrizione") or ""),
                source_origin=str(raw_effect.get("origine") or "Manuale Elder"),
                icon=str(raw_effect.get("icona") or "runa"),
                operations=operations,
                order=500 + index,
            )
            imported += 1
        for stale in EffettoPersonalizzato.objects.filter(personaggio=character, origine__startswith="Elder Django #"):
            marker = stale.origine.split(" · ", 1)[0]
            if marker not in used_markers:
                stale.delete()

        alchemy_operations = []
        if source_alchemy:
            for source_field, target in ALCHEMY_MULTIPLIER_TARGETS.items():
                value = _number(source_alchemy[source_field]) or 0
                if value:
                    alchemy_operations.append({"target": target, "operation": "add", "value": str(value)})
        if alchemy_operations:
            self.upsert_custom_effect(
                character,
                marker="Elder Django · alchimia",
                name="Alchimia Elder Django",
                description="Moltiplicatori alchemici personali importati come bonus alle statistiche ReD.",
                source_origin="Alchimia",
                icon="alchimia",
                operations=alchemy_operations,
                order=700,
            )
            imported += 1
        else:
            EffettoPersonalizzato.objects.filter(personaggio=character, origine__startswith="Elder Django · alchimia").delete()

        base_operations = self.magic_base_operations(source)
        if base_operations:
            self.upsert_custom_effect(
                character,
                marker="Elder Django · basi magiche",
                name="Basi magiche Elder Django",
                description=(
                    "Scarto fra le basi magiche personali del personaggio Elder e la base globale ReD, "
                    "senza il quale il costo degli incantesimi non coincide con quello originario."
                ),
                source_origin="Basi personaggio",
                icon="runa",
                operations=base_operations,
                order=702,
            )
            imported += 1
        else:
            EffettoPersonalizzato.objects.filter(
                personaggio=character, origine__startswith="Elder Django · basi magiche"
            ).delete()

        npc_operations = []
        for source_field, target in (("attacco_npc", "attacco"), ("difesa_npc", "difesa")):
            value = _number(source[source_field]) or 0
            if value:
                npc_operations.append({"target": target, "operation": "add", "value": str(value)})
        if npc_operations:
            self.upsert_custom_effect(
                character,
                marker="Elder Django · modificatori NPC",
                name="Modificatori NPC Elder Django",
                description="Bonus NPC conservati dal personaggio Elder.",
                source_origin="Statistiche NPC",
                icon="runa",
                operations=npc_operations,
                order=701,
            )
            imported += 1

        EffettoPersonalizzato.objects.filter(
            personaggio=character,
            nome__startswith="Allineamento totali Elder Django",
        ).delete()
        return imported

    def reconcile(self, source: sqlite3.Row, character: Personaggio) -> dict[str, Any]:
        elder = normalized_elder_totals(source["tot"])
        red = character.tot if isinstance(character.tot, dict) else {}
        stats = []
        for key in sorted(elder):
            red_value = _number(red.get(key))
            elder_value = elder[key]
            delta = red_value - elder_value if red_value is not None else None
            stats.append({
                "stat": key,
                "elder": elder_value,
                "redjango": red_value,
                "delta": delta,
                "matches": delta is not None and abs(delta) < 1e-6,
            })
        return {
            "sourceId": source["id"],
            "characterId": character.id,
            "name": character.nome,
            "stats": stats,
            "matchingStats": sum(1 for stat in stats if stat["matches"]),
            "differentStats": sum(1 for stat in stats if not stat["matches"]),
        }

    def preview(self) -> dict[str, Any]:
        characters = self.selected_characters()
        skill_names = []
        effect_count = 0
        formula_count = 0
        for source in characters:
            abilities = _json(source["abilita"], {})
            skill_names.extend(abilities.keys() if isinstance(abilities, dict) else [])
            active = _json(source["act"], {})
            for effect in active.get("effetti_extra", []) if isinstance(active, dict) else []:
                effect_count += 1
                formula_count += sum(
                    1 for operation in effect.get("effetti", [])
                    if isinstance(operation, dict) and "(f)" in str(operation.get("value") or "")
                )
        missing_skills = sorted({name for name in skill_names if str(name).strip().casefold() not in self.skill_by_name})
        source_campaign = self.connection.execute("SELECT id FROM django_slim_daticampagna WHERE nome = 'Sanguine'").fetchone()
        map_count = self.connection.execute(
            "SELECT COUNT(*) FROM django_slim_globalimage WHERE campagna_id = ?",
            (source_campaign["id"],),
        ).fetchone()[0]
        missing_portraits = [
            filename for filename in PORTRAIT_FILES.values()
            if not (self.source_root / "django_slim" / "static" / "media" / "images" / "pgs" / filename).is_file()
        ]
        return {
            "mode": "dry-run",
            "source": str(self.source_root),
            "campaign": "Sanguine",
            "characters": [{"id": row["id"], "name": row["nome"]} for row in characters],
            "skills": {"references": len(skill_names), "missing": missing_skills},
            "manualEffects": effect_count,
            "formulaEffectOperations": formula_count,
            "globalMaps": map_count,
            "missingPortraits": missing_portraits,
            "ignored": ["LoreCampagna", "lore entries", "campaign buttons", "character buttons", "timeline", "Hall of Fame", "altro.info_*", "altro.sr_staging", "Elder formulas"],
        }

    def apply(self) -> dict[str, Any]:
        campaign, map_count = self.import_campaign_and_maps()
        character_reports = []
        total_skills = 0
        total_effects = 0
        for source in self.selected_characters():
            character, inventory = self.import_character(source, campaign)
            total_skills += self.import_skills(source, character)
            total_effects += self.import_effects(source, character, inventory["source_alchemy"])
            refresh_personaggio(character)
            character.refresh_from_db()
            character_reports.append(self.reconcile(source, character))

        Giocatore.objects.update(active_campaign=campaign, active_character=None, updated_at=timezone.now())
        total_stats = sum(len(report["stats"]) for report in character_reports)
        matching_stats = sum(report["matchingStats"] for report in character_reports)
        different_stats = total_stats - matching_stats
        summary = (
            f"Importazione completata: 5 personaggi, {total_skills} abilità, {total_effects} effetti, "
            f"5 ritratti e {map_count} mappe globali. Contenitori di inventario, note e alchimia "
            "sono stati clonati per personaggio.\n"
            f"Confronto finale: {matching_stats}/{total_stats} statistiche coincidono con i totali Elder; "
            f"{different_stats} restano differenti e seguono le formule ReD senza effetti di allineamento Imposta forte. "
            f"Operazioni effetto scartate: {len(self.skipped_operations)}. "
            f"Riferimenti non importati: {len(self.warnings)}.\n"
            "Non importati per scelta: lore, bottoni, formule Elder, timeline/Hall of Fame e stato altro.info/sr_staging."
        )
        report_block = f"{NOTE_REPORT_START}\n{summary}\n{NOTE_REPORT_END}"
        existing = campaign.note_condivise or ""
        pattern = re.compile(re.escape(NOTE_REPORT_START) + r".*?" + re.escape(NOTE_REPORT_END), re.DOTALL)
        campaign.note_condivise = pattern.sub(report_block, existing) if pattern.search(existing) else "\n\n".join(filter(None, (existing.strip(), report_block)))
        campaign.save(update_fields=["note_condivise", "updated_at"])
        return {
            "mode": "apply",
            "campaignId": campaign.id,
            "campaign": campaign.nome,
            "characters": character_reports,
            "importedSkills": total_skills,
            "importedEffects": total_effects,
            "importedMaps": map_count,
            "warnings": self.warnings,
            "skippedEffectOperations": self.skipped_operations,
            "summary": {
                "totalStats": total_stats,
                "matchingStats": matching_stats,
                "differentStats": different_stats,
            },
        }


class Command(BaseCommand):
    help = "Importa i cinque personaggi concordati e la campagna Sanguine da The Elder Django."

    def add_arguments(self, parser):
        parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE_ROOT)
        parser.add_argument("--apply", action="store_true", help="Applica l'importazione. Senza questo flag esegue solo il dry-run.")
        parser.add_argument("--report", type=Path, help="Scrive il rapporto JSON completo nel percorso indicato.")

    def handle(self, *args, **options):
        source_root = options["source"].resolve()
        if not (source_root / "db.sqlite3").is_file():
            raise CommandError(f"Database Elder non trovato in {source_root}")
        importer = ElderCharacterImporter(source_root)
        try:
            if not options["apply"]:
                report = importer.preview()
            else:
                with transaction.atomic():
                    report = importer.apply()
        finally:
            importer.close()

        if options.get("report"):
            report_path = options["report"]
            if not report_path.is_absolute():
                report_path = Path(settings.BASE_DIR) / report_path
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            report["reportPath"] = str(report_path)
        self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
        if options["apply"]:
            self.stdout.write(self.style.SUCCESS("Importazione Elder completata."))
