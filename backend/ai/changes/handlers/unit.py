from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from django.db import transaction
from django.db.models import Q

from backend.combat.unit_management_selectors import serialize_managed_unit, unit_management_overview
from backend.combat.unit_management_services import (
    preview_managed_unit,
    require_unit_manager,
    save_managed_unit,
    set_managed_unit_archived,
)
from backend.core.api import ApiError
from backend.core.models import Giocatore, Unit
from backend.media_library.models import UploadedImage

from ..contracts import PreparedChange
from .base import canonical_digest, json_safe


class UnitChangeHandler:
    entity_type = "unit"
    label = "Unit"
    minimum_role = Giocatore.ROLE_MASTER
    supported_actions = frozenset({"create", "update", "archive"})

    EDITABLE_FIELDS = frozenset(
        {
            "name",
            "category",
            "loreImageId",
            "archetypeDescription",
            "loreDescription",
            "notes",
            "generation",
            "archetypeTags",
            "competenceProfile",
            "skillUnlocks",
            "equipmentSlots",
            "equipmentGroups",
            "accessoryCountByLevel",
            "accessoryProfileKey",
            "innateActions",
            "statProfile",
            "levels",
        }
    )
    READ_ONLY_FIELDS = frozenset({"auditPreview"})
    AUDIT_LEVELS = (1, 3, 5, 6, 7, 9, 10, 11, 12, 15, 20)
    AUDIT_REPEAT_LEVELS = (1, 10, 20)
    AUDIT_AUTO_LEVELS = (1, 10, 20)
    AUDIT_AUTO_PER_LEVEL = 3

    def require_access(self, user, giocatore, action: str) -> None:
        if action not in self.supported_actions:
            raise ApiError(
                "ai.change_action_unsupported",
                f"L'azione «{action}» non è supportata per le Unit.",
                "action",
            )
        require_unit_manager(user, giocatore)

    @staticmethod
    def _field(
        name: str,
        label: str,
        kind: str,
        group: str,
        *,
        required: bool = False,
        nullable: bool = False,
        read_only: bool = False,
        help_text: str = "",
        choices: list[dict[str, Any]] | None = None,
        ui: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "name": name,
            "label": label,
            "kind": kind,
            "group": group,
            "required": required,
            "nullable": nullable,
            "readOnly": read_only,
            "help": help_text,
            "choices": choices or [],
            "ui": {
                "widget": kind,
                "width": "full" if kind in {"longText", "structured", "multiRelation"} else "half",
                **(ui or {}),
            },
        }

    @staticmethod
    def _portrait_choices() -> list[dict[str, Any]]:
        choices: list[dict[str, Any]] = []
        queryset = UploadedImage.objects.select_related("category").filter(
            archived_at__isnull=True,
            usage_type="character_portrait",
            category__slug="personaggi",
            group="Unit e NPC",
        ).order_by("title", "id")
        for image in queryset[:500]:
            metadata = image.metadata if isinstance(image.metadata, dict) else {}
            conversion = metadata.get("conversion") if isinstance(metadata.get("conversion"), dict) else {}
            quality = metadata.get("webpQuality", conversion.get("quality"))
            if not image.file or not image.file.name.casefold().endswith(".webp") or quality != 70:
                continue
            choices.append({"value": image.id, "label": image.title})
        return choices

    def field_schema(self, user, giocatore, *, action: str, instance=None) -> list[dict[str, Any]]:
        self.require_access(user, giocatore, action)
        if action == "archive":
            return []
        configuration = unit_management_overview()["configuration"]
        contract = (
            "Contratto Unit LLM: leggere la configurazione live e almeno cinque Unit comparabili; "
            "non inventare ID o valori; scegliere creature/humanoid per meccaniche; creare un DTO completo; "
            "ispezionare Skill, prerequisiti, Item, slot, razze, accessori e Perk; distinguere regole automatiche "
            "da promemoria manuali. La validazione Master AI esegue il generatore reale ai livelli di confine, "
            "ripete varianti nominate e prova varianti automatiche in transazioni annullate."
        )
        return [
            self._field(
                "name",
                "Nome",
                "text",
                "Identità",
                required=True,
                help_text=contract,
                ui={"widget": "unitDefinition", "configuration": configuration, "width": "full"},
            ),
            self._field("category", "Categoria", "text", "Identità"),
            self._field(
                "loreImageId",
                "Ritratto Unit",
                "image",
                "Identità",
                nullable=True,
                choices=self._portrait_choices(),
                ui={"widget": "imagePicker", "width": "full"},
            ),
            self._field("archetypeDescription", "Descrizione archetipo", "longText", "Identità"),
            self._field("loreDescription", "Lore", "longText", "Identità"),
            self._field("notes", "Note di authoring", "longText", "Identità"),
            self._field("generation", "Generazione", "structured", "Contratto", ui={"widget": "unitGeneration"}),
            self._field("archetypeTags", "Tag archetipo", "structured", "Contratto", ui={"widget": "unitTags"}),
            self._field("competenceProfile", "Profilo competenze", "structured", "Contratto", ui={"widget": "unitCompetences"}),
            self._field("skillUnlocks", "Pool Skill", "structured", "Progressione", ui={"widget": "unitSkillUnlocks"}),
            self._field("equipmentSlots", "Slot equipaggiamento", "structured", "Equipaggiamento", ui={"widget": "unitEquipmentSlots"}),
            self._field("equipmentGroups", "Gruppi equipaggiamento", "structured", "Equipaggiamento", ui={"widget": "unitEquipmentGroups"}),
            self._field("accessoryCountByLevel", "Fasce accessori", "structured", "Equipaggiamento", ui={"widget": "unitAccessoryBands"}),
            self._field(
                "accessoryProfileKey",
                "Profilo accessori",
                "choice",
                "Equipaggiamento",
                nullable=True,
                choices=[
                    {"value": entry["value"], "label": entry["label"]}
                    for entry in configuration["accessoryProfiles"]
                ],
            ),
            self._field("innateActions", "Azioni innate", "structured", "Creatura", ui={"widget": "unitInnateActions"}),
            self._field("statProfile", "Profilo statistiche", "structured", "Chassis", ui={"widget": "unitStatProfile"}),
            self._field("levels", "Fasce legacy", "structured", "Chassis", ui={"widget": "unitLegacyLevels"}),
            self._field(
                "auditPreview",
                "Audit generazione",
                "structured",
                "Verifica",
                read_only=True,
                help_text="Risultato delle anteprime rollback-only eseguite dal backend.",
                ui={"widget": "unitAudit", "width": "full"},
            ),
        ]

    def _queryset(self, *, for_update: bool = False):
        queryset = Unit.objects.select_related("accessory_profile", "lore_image")
        if for_update:
            queryset = queryset.select_for_update()
        return queryset

    def _load(self, object_id: int, *, for_update: bool = False) -> Unit:
        try:
            return self._queryset(for_update=for_update).get(pk=int(object_id))
        except (TypeError, ValueError, Unit.DoesNotExist) as exc:
            raise ApiError("management.units.not_found", "Unit non trovata.", status=404) from exc

    @staticmethod
    def _clean_skill_entry(raw: Mapping[str, Any]) -> dict[str, Any]:
        entry = {
            key: raw[key]
            for key in ("skillId", "pool", "weight", "minLevel", "maxLevel", "requiredAtLevel")
            if key in raw
        }
        perk_tier = str(raw.get("perkTier") or "").strip().lower()
        if perk_tier in {"minor", "major"}:
            entry["pool"] = perk_tier
        return entry

    @staticmethod
    def _clean_item_entry(raw: Mapping[str, Any]) -> dict[str, Any]:
        return {
            key: raw[key]
            for key in ("itemId", "minLevel", "maxLevel", "weight", "chance")
            if key in raw
        }

    def _values_for(self, unit: Unit) -> dict[str, Any]:
        serialized = serialize_managed_unit(unit)
        values = {name: deepcopy(serialized.get(name)) for name in self.EDITABLE_FIELDS}
        values["skillUnlocks"] = [
            self._clean_skill_entry(entry)
            for entry in serialized.get("skillUnlocks", [])
            if isinstance(entry, Mapping)
        ]
        values["equipmentSlots"] = [
            {
                "slot": entry.get("slot"),
                **self._clean_item_entry(entry),
            }
            for entry in serialized.get("equipmentSlots", [])
            if isinstance(entry, Mapping)
        ]
        values["equipmentGroups"] = [
            {
                "name": group.get("name", ""),
                "slots": list(group.get("slots") or []),
                "minCount": group.get("minCount", 0),
                "maxCount": group.get("maxCount", 0),
                "emptyChance": group.get("emptyChance", 0),
                "items": [
                    self._clean_item_entry(entry)
                    for entry in group.get("items", [])
                    if isinstance(entry, Mapping)
                ],
            }
            for group in serialized.get("equipmentGroups", [])
            if isinstance(group, Mapping)
        ]
        return json_safe(values)

    def _snapshot_for(self, unit: Unit) -> dict[str, Any]:
        values = self._values_for(unit)
        updated_at = unit.updated_at.isoformat() if unit.updated_at else None
        snapshot = {
            "id": unit.id,
            "entityType": self.entity_type,
            "label": unit.nome,
            "updatedAt": updated_at,
            "values": values,
            "display": {
                "category": unit.categoria,
                "kind": values.get("generation", {}).get("kind") if isinstance(values.get("generation"), dict) else "",
                "archived": unit.archived_at is not None,
                "portrait": unit.lore_image.title if unit.lore_image_id else "",
            },
        }
        snapshot["digest"] = canonical_digest(
            {
                "id": snapshot["id"],
                "entityType": snapshot["entityType"],
                "updatedAt": snapshot["updatedAt"],
                "values": snapshot["values"],
            }
        )
        return snapshot

    def snapshot(self, user, giocatore, object_id: int, *, for_update: bool = False) -> dict[str, Any]:
        self.require_access(user, giocatore, "update")
        return self._snapshot_for(self._load(object_id, for_update=for_update))

    def search(self, user, giocatore, query: str, limit: int) -> list[dict[str, Any]]:
        self.require_access(user, giocatore, "update")
        text = str(query or "").strip()[:160]
        cap = max(1, min(int(limit or 10), 25))
        queryset = self._queryset().filter(archived_at__isnull=True)
        if text:
            queryset = queryset.filter(
                Q(nome__icontains=text)
                | Q(categoria__icontains=text)
                | Q(archetipo_descrizione__icontains=text)
                | Q(lore_description__icontains=text)
            )
        return [
            {
                "id": unit.id,
                "entityType": self.entity_type,
                "label": unit.nome,
                "summary": unit.archetipo_descrizione[:240],
                "meta": {
                    "category": unit.categoria,
                    "kind": (unit.generation_rules or {}).get("kind", "") if isinstance(unit.generation_rules, dict) else "",
                    "updatedAt": unit.updated_at.isoformat() if unit.updated_at else None,
                },
            }
            for unit in queryset.order_by("categoria", "nome")[:cap]
        ]

    @staticmethod
    def _deep_merge(base: dict[str, Any], patch: Mapping[str, Any]) -> dict[str, Any]:
        result = deepcopy(base)
        for key, value in patch.items():
            if isinstance(value, Mapping) and isinstance(result.get(key), dict):
                result[key] = UnitChangeHandler._deep_merge(result[key], value)
            else:
                result[key] = deepcopy(value)
        return result

    def _filter_values(self, values: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(values, dict):
            raise ApiError("ai.change_values_invalid", "I valori proposti devono essere un oggetto JSON.", "values")
        unknown = sorted(set(values) - self.EDITABLE_FIELDS - self.READ_ONLY_FIELDS)
        if unknown:
            raise ApiError(
                "ai.change_field_unknown",
                f"Campi Unit non modificabili: {', '.join(unknown)}.",
                "values",
            )
        return {key: deepcopy(value) for key, value in values.items() if key in self.EDITABLE_FIELDS}

    @staticmethod
    def _default_values() -> dict[str, Any]:
        return {
            "name": "",
            "category": "",
            "loreImageId": None,
            "archetypeDescription": "",
            "loreDescription": "",
            "notes": "",
            "generation": {
                "kind": "humanoid",
                "coreKey": "warrior",
                "coreShare": 0.5,
                "startingXp": 0,
                "xpBase": 20,
                "xpGrowth": 1,
                "competenceStartingXp": 5,
                "competenceXpBase": 15,
                "competenceXpGrowth": 0,
                "finalSpendingPasses": 4,
                "magicPolicy": "none",
                "allowedClassFamilies": [],
                "allowedReligionFamilies": [],
                "allowedRaces": [],
                "allowedSubraces": [],
                "allowHumanoidStatGrowth": False,
            },
            "archetypeTags": {},
            "competenceProfile": {},
            "skillUnlocks": [],
            "equipmentSlots": [],
            "equipmentGroups": [],
            "accessoryCountByLevel": [],
            "accessoryProfileKey": "",
            "innateActions": [],
            "statProfile": {
                "baseModifiers": {},
                "perLevelModifiers": {},
                "milestones": [],
                "curves": [],
            },
            "levels": [],
        }

    @staticmethod
    def _compact_preview(payload: dict[str, Any]) -> dict[str, Any]:
        trace = payload.get("trace") if isinstance(payload.get("trace"), dict) else {}
        skills = trace.get("skills") if isinstance(trace.get("skills"), list) else []
        equipment = payload.get("equipment") if isinstance(payload.get("equipment"), list) else []
        warnings = trace.get("warnings") if isinstance(trace.get("warnings"), list) else []
        return {
            "level": payload.get("level"),
            "totals": payload.get("totals") if isinstance(payload.get("totals"), dict) else {},
            "skills": len(payload.get("skills") or []),
            "coreSkills": sum(1 for entry in skills if isinstance(entry, dict) and entry.get("source") == "core"),
            "archetypeSkills": sum(1 for entry in skills if isinstance(entry, dict) and entry.get("source") == "archetype"),
            "perks": len(trace.get("perks") or []),
            "equipment": len(equipment),
            "innateActions": len(payload.get("innateActions") or []),
            "race": trace.get("race") if isinstance(trace.get("race"), dict) else {},
            "xp": trace.get("xp") if isinstance(trace.get("xp"), dict) else {},
            "competences": trace.get("competences") if isinstance(trace.get("competences"), dict) else {},
            "statCurves": trace.get("statCurves") if isinstance(trace.get("statCurves"), list) else [],
            "warnings": [str(entry) for entry in warnings],
            "digest": canonical_digest(payload),
        }

    def _audit_unit(self, user, giocatore, unit: Unit) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        named: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []
        variant = "master-ai-unit-audit-v1"
        for level in self.AUDIT_LEVELS:
            try:
                payload = preview_managed_unit(user, giocatore, unit.id, level, variant)
            except ApiError as error:
                raise ApiError(
                    "ai.unit_audit_failed",
                    f"Anteprima Unit fallita al livello {level}: {error.message}",
                    "auditPreview",
                    409,
                ) from error
            named.append(self._compact_preview(payload))

        repeats: list[dict[str, Any]] = []
        for level in self.AUDIT_REPEAT_LEVELS:
            first = preview_managed_unit(user, giocatore, unit.id, level, variant)
            second = preview_managed_unit(user, giocatore, unit.id, level, variant)
            stable = canonical_digest(first) == canonical_digest(second)
            repeats.append({"level": level, "stable": stable})
            if not stable:
                raise ApiError(
                    "ai.unit_audit_nondeterministic",
                    f"La variante nominata non è stabile al livello {level}.",
                    "auditPreview",
                    409,
                )

        automatic: list[dict[str, Any]] = []
        for level in self.AUDIT_AUTO_LEVELS:
            rows = [
                self._compact_preview(preview_managed_unit(user, giocatore, unit.id, level, "auto"))
                for _index in range(self.AUDIT_AUTO_PER_LEVEL)
            ]
            unique = len({row["digest"] for row in rows})
            automatic.append({"level": level, "variants": len(rows), "unique": unique, "rows": rows})
            if unique < 2:
                warnings.append(
                    {
                        "code": "ai.unit_audit_low_variation",
                        "message": f"Le varianti automatiche al livello {level} non mostrano variazione osservabile.",
                        "field": "auditPreview",
                    }
                )

        for row in named:
            for message in row["warnings"]:
                warnings.append(
                    {
                        "code": "ai.unit_generation_warning",
                        "message": f"Livello {row['level']}: {message}",
                        "field": "auditPreview",
                    }
                )

        kind = ""
        rules = unit.generation_rules if isinstance(unit.generation_rules, dict) else {}
        kind = str(rules.get("kind") or "")
        level_20 = next((row for row in named if row["level"] == 20), {})
        if kind == "humanoid":
            if int(level_20.get("coreSkills") or 0) < 1:
                raise ApiError(
                    "ai.unit_audit_core_identity_missing",
                    "La generazione di livello 20 non acquista alcuna Skill Core.",
                    "skillUnlocks",
                    409,
                )
            if int(level_20.get("archetypeSkills") or 0) < 1:
                raise ApiError(
                    "ai.unit_audit_archetype_identity_missing",
                    "La generazione di livello 20 non acquista alcuna Skill Archetipo.",
                    "skillUnlocks",
                    409,
                )
            if int(level_20.get("perks") or 0) < 30:
                raise ApiError(
                    "ai.unit_audit_perk_path_incomplete",
                    "La progressione non produce il percorso completo di Perk minori e maggiori entro il livello 20.",
                    "skillUnlocks",
                    409,
                )

        audit = {
            "passed": True,
            "contractVersion": 1,
            "namedVariant": variant,
            "named": named,
            "repeatability": repeats,
            "automatic": automatic,
            "warningCount": len(warnings),
            "levels": list(self.AUDIT_LEVELS),
        }
        return audit, warnings

    def _normalise_and_audit(
        self,
        user,
        giocatore,
        values: dict[str, Any],
        *,
        unit_id: int | None,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        with transaction.atomic():
            unit, _created = save_managed_unit(user, giocatore, values, unit_id=unit_id)
            normalized = self._values_for(unit)
            audit, warnings = self._audit_unit(user, giocatore, unit)
            normalized["auditPreview"] = audit
            transaction.set_rollback(True)
        return normalized, warnings

    def prepare_create(self, user, giocatore, values: dict[str, Any], source_id: int | None = None) -> PreparedChange:
        self.require_access(user, giocatore, "create")
        original: dict[str, Any] = {}
        base_updated_at = None
        base_digest = ""
        materialized = self._default_values()
        if source_id is not None:
            source = self._load(source_id)
            original = self._snapshot_for(source)
            materialized = self._deep_merge(materialized, original["values"])
            materialized["name"] = ""
            base_updated_at = source.updated_at
            base_digest = original["digest"]
        materialized = self._deep_merge(materialized, self._filter_values(values))
        normalized, warnings = self._normalise_and_audit(user, giocatore, materialized, unit_id=None)
        return PreparedChange(
            values=normalized,
            original_snapshot=original,
            field_schema=self.field_schema(user, giocatore, action="create"),
            display_label=str(normalized.get("name") or "Unit"),
            base_updated_at=base_updated_at,
            base_digest=base_digest,
            warnings=warnings,
        )

    def prepare_update(
        self,
        user,
        giocatore,
        object_id: int,
        values: dict[str, Any],
        *,
        for_update: bool = False,
    ) -> PreparedChange:
        self.require_access(user, giocatore, "update")
        unit = self._load(object_id, for_update=for_update)
        original = self._snapshot_for(unit)
        materialized = self._deep_merge(original["values"], self._filter_values(values))
        normalized, warnings = self._normalise_and_audit(user, giocatore, materialized, unit_id=unit.id)
        return PreparedChange(
            values=normalized,
            original_snapshot=original,
            field_schema=self.field_schema(user, giocatore, action="update", instance=unit),
            display_label=str(normalized.get("name") or unit.nome),
            base_updated_at=unit.updated_at,
            base_digest=original["digest"],
            warnings=warnings,
        )

    def prepare_archive(
        self,
        user,
        giocatore,
        object_id: int,
        *,
        for_update: bool = False,
    ) -> PreparedChange:
        self.require_access(user, giocatore, "archive")
        unit = self._load(object_id, for_update=for_update)
        if unit.archived_at is not None:
            raise ApiError("management.units.already_archived", "La Unit è già archiviata.", status=409)
        original = self._snapshot_for(unit)
        return PreparedChange(
            values=original["values"],
            original_snapshot=original,
            field_schema=[],
            display_label=unit.nome,
            base_updated_at=unit.updated_at,
            base_digest=original["digest"],
        )

    @staticmethod
    def _domain_values(values: dict[str, Any]) -> dict[str, Any]:
        return {key: deepcopy(value) for key, value in values.items() if key in UnitChangeHandler.EDITABLE_FIELDS}

    def apply_create(self, user, giocatore, values: dict[str, Any]) -> dict[str, Any]:
        unit, _created = save_managed_unit(user, giocatore, self._domain_values(values))
        return {"id": unit.id, "label": unit.nome, "action": "create", "entityType": self.entity_type}

    def apply_update(self, user, giocatore, object_id: int, values: dict[str, Any]) -> dict[str, Any]:
        unit, _created = save_managed_unit(user, giocatore, self._domain_values(values), unit_id=object_id)
        return {"id": unit.id, "label": unit.nome, "action": "update", "entityType": self.entity_type}

    def apply_archive(self, user, giocatore, object_id: int) -> dict[str, Any]:
        unit = set_managed_unit_archived(user, giocatore, object_id, True)
        return {"id": unit.id, "label": unit.nome, "action": "archive", "entityType": self.entity_type}
