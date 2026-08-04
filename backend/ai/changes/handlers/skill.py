from __future__ import annotations

from typing import Any

from django.db.models import Max, Q

from backend.characters.services.custom_effects import EFFECT_ICONS
from backend.core.api import ApiError
from backend.core.management_services import require_game_manager
from backend.core.models import FamigliaSkill, Giocatore, Skill, SpellDefinition
from backend.core.skill_selectors import serialize_skill
from backend.core.skill_services import archive_skill, create_skill, update_skill, validate_skill_values
from backend.core.spell_services import validate_spell_values

from ..contracts import PreparedChange
from .base import canonical_digest, json_safe


class SkillChangeHandler:
    entity_type = "skill"
    label = "Abilità"
    minimum_role = Giocatore.ROLE_MASTER
    supported_actions = frozenset({"create", "update", "archive"})

    EDITABLE_FIELDS = frozenset(
        {
            "name",
            "slug",
            "number",
            "familyId",
            "familyOrder",
            "prerequisiteIds",
            "baseXpCost",
            "xpType",
            "rulesCost",
            "requirementsText",
            "description",
            "profileTags",
            "profileNotes",
            "passiveEffects",
            "activeReminders",
            "magic",
            "spell",
            "icon",
            "notes",
        }
    )

    def require_access(self, user, giocatore, action: str) -> None:
        if action not in self.supported_actions:
            raise ApiError("ai.change_action_unsupported", "Azione proposta non supportata.", "action")
        require_game_manager(user, giocatore)

    def _families(self):
        return FamigliaSkill.objects.filter(
            archived_at__isnull=True,
            gruppo__archived_at__isnull=True,
        ).select_related("gruppo").order_by("gruppo__ordine", "ordine", "nome")

    def _skill_choices(self, *, exclude_id: int | None = None) -> list[dict[str, Any]]:
        queryset = Skill.objects.filter(archived_at__isnull=True).order_by("nome")
        if exclude_id:
            queryset = queryset.exclude(pk=exclude_id)
        return [{"value": skill.id, "label": skill.nome} for skill in queryset[:500]]

    def field_schema(self, user, giocatore, *, action: str, instance=None) -> list[dict[str, Any]]:
        self.require_access(user, giocatore, action)
        family_choices = [
            {"value": family.id, "label": f"{family.gruppo.nome} · {family.nome}"}
            for family in self._families()
        ]
        xp_choices = [{"value": value, "label": label} for value, label in Skill.XP_TYPE_CHOICES]
        icon_choices = [
            {"value": value, "label": label}
            for value, label, _category, _keywords in EFFECT_ICONS
        ]
        fields = [
            self._field("name", "Nome", "text", "Identità", required=True),
            self._field("slug", "Slug", "text", "Identità", help="Se vuoto viene derivato dal nome."),
            self._field("number", "Numero", "integer", "Identità", required=True, ui={"minimum": 1}),
            self._field("icon", "Icona", "choice", "Identità", choices=icon_choices),
            self._field("familyId", "Famiglia", "relation", "Struttura", required=True, choices=family_choices),
            self._field("familyOrder", "Ordine nella famiglia", "integer", "Struttura", ui={"minimum": 0}),
            self._field(
                "prerequisiteIds",
                "Prerequisiti",
                "multiRelation",
                "Struttura",
                choices=self._skill_choices(exclude_id=getattr(instance, "id", None)),
                ui={"widget": "skillPrerequisites"},
            ),
            self._field("baseXpCost", "Costo PE base", "integer", "Economia e regole", ui={"minimum": 0}),
            self._field("xpType", "Tipo PE", "choice", "Economia e regole", required=True, choices=xp_choices),
            self._field("rulesCost", "Costo testuale", "text", "Economia e regole"),
            self._field("requirementsText", "Requisiti", "longText", "Economia e regole"),
            self._field("description", "Descrizione", "longText", "Descrizione e profilo"),
            self._field("profileTags", "Tag profilo", "structured", "Descrizione e profilo", ui={"widget": "json"}),
            self._field("profileNotes", "Note profilo", "longText", "Descrizione e profilo"),
            self._field("notes", "Note", "longText", "Descrizione e profilo"),
            self._field(
                "passiveEffects",
                "Effetti passivi",
                "structured",
                "Comportamento",
                ui={"widget": "skillPassiveEffects"},
            ),
            self._field(
                "activeReminders",
                "Azioni attive",
                "structured",
                "Comportamento",
                ui={"widget": "skillActiveReminders"},
            ),
            self._field("magic", "Magia", "boolean", "Magia"),
            self._field("spell", "Definizione incantesimo", "structured", "Magia", nullable=True, ui={"widget": "spellDefinition"}),
        ]
        return fields

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
        help: str = "",
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
            "help": help,
            "choices": choices or [],
            "ui": {"widget": kind, "width": "full" if kind in {"longText", "structured", "multiRelation"} else "half", **(ui or {})},
        }

    def _queryset(self, *, for_update: bool = False):
        queryset = Skill.objects.select_related(
            "famiglia",
            "famiglia__gruppo",
            "spell_definition",
        ).prefetch_related("prerequisiti")
        if for_update:
            queryset = queryset.select_for_update()
        return queryset

    def _load(self, object_id: int, *, for_update: bool = False) -> Skill:
        try:
            return self._queryset(for_update=for_update).get(pk=int(object_id))
        except (TypeError, ValueError, Skill.DoesNotExist) as exc:
            raise ApiError("skills.not_found", "Abilità non trovata.", status=404) from exc

    def _values_for(self, skill: Skill) -> dict[str, Any]:
        serialized = serialize_skill(skill)
        return {
            "name": serialized["name"],
            "slug": serialized["slug"],
            "number": serialized["number"],
            "familyId": serialized["familyId"],
            "familyOrder": serialized["familyOrder"],
            "prerequisiteIds": list(serialized["unlock"].get("prerequisiteIds") or []),
            "baseXpCost": serialized["baseXpCost"],
            "xpType": serialized["xpType"],
            "rulesCost": serialized["rulesCost"],
            "requirementsText": serialized["requirementsText"],
            "description": serialized["description"],
            "profileTags": serialized["profileTags"],
            "profileNotes": serialized["profileNotes"],
            "passiveEffects": serialized["passiveEffects"],
            "activeReminders": serialized["activeReminders"],
            "magic": serialized["magic"],
            "spell": serialized["spell"],
            "icon": serialized["icon"],
            "notes": serialized["notes"],
        }

    def _snapshot_for(self, skill: Skill) -> dict[str, Any]:
        values = json_safe(self._values_for(skill))
        digest = canonical_digest({"id": skill.id, "entityType": self.entity_type, "values": values})
        return {
            "id": skill.id,
            "entityType": self.entity_type,
            "label": skill.nome,
            "updatedAt": skill.updated_at.isoformat() if skill.updated_at else None,
            "values": values,
            "display": {
                "family": skill.famiglia.nome,
                "group": skill.famiglia.gruppo.nome,
                "magic": bool(values["magic"]),
            },
            "digest": digest,
        }

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
                | Q(descrizione__icontains=text)
                | Q(famiglia__nome__icontains=text)
            )
        return [
            {
                "id": skill.id,
                "label": skill.nome,
                "description": skill.descrizione[:280],
                "meta": {
                    "family": skill.famiglia.nome,
                    "group": skill.famiglia.gruppo.nome,
                    "magic": hasattr(skill, "spell_definition"),
                },
            }
            for skill in queryset.order_by("nome")[:cap]
        ]

    def _default_spell(self) -> dict[str, Any]:
        return {
            "tier": SpellDefinition.TIER_BASE,
            "range": "",
            "effectUnit": "Effetto",
            "baseMana": 0,
            "effectPerMana": 1,
            "minimumMana": 0,
            "fixedCosts": {},
            "rounding": SpellDefinition.ROUNDING_NONE,
            "legacyFormula": "",
            "costNotes": "",
            "combatConfiguration": {},
        }

    def _default_values(self) -> dict[str, Any]:
        family = self._families().first()
        highest_number = Skill.objects.aggregate(value=Max("numero"))["value"] or 0
        return {
            "name": "",
            "slug": "",
            "number": highest_number + 1,
            "familyId": family.id if family else None,
            "familyOrder": 0,
            "prerequisiteIds": [],
            "baseXpCost": 0,
            "xpType": "general",
            "rulesCost": "",
            "requirementsText": "",
            "description": "",
            "profileTags": {},
            "profileNotes": "",
            "passiveEffects": [],
            "activeReminders": [],
            "magic": False,
            "spell": None,
            "icon": "runa",
            "notes": "",
        }

    def _filter_values(self, values: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(values, dict):
            raise ApiError("ai.change_values_invalid", "I valori proposti devono essere un oggetto JSON.", "values")
        unknown = sorted(set(values) - self.EDITABLE_FIELDS)
        if unknown:
            raise ApiError("ai.change_field_unknown", f"Campi non modificabili: {', '.join(unknown)}.", "values")
        return dict(values)

    def _normalise_spell(self, raw: Any) -> dict[str, Any]:
        validated = validate_spell_values(raw)
        return json_safe(
            {
                "tier": validated["tier"],
                "range": validated["range_text"],
                "effectUnit": validated["effect_unit"],
                "baseMana": validated["base_mana"],
                "effectPerMana": validated["effect_per_mana"],
                "minimumMana": validated["minimum_mana"],
                "fixedCosts": validated["fixed_costs"],
                "rounding": validated["rounding"],
                "legacyFormula": validated["legacy_formula"],
                "costNotes": validated["cost_notes"],
                "combatConfiguration": validated["combat_configuration"],
            }
        )

    def _validate_values(self, values: dict[str, Any], *, instance: Skill | None) -> dict[str, Any]:
        filtered = self._filter_values(values)
        if filtered.get("magic"):
            filtered["spell"] = self._normalise_spell(filtered.get("spell") or self._default_spell())
        else:
            filtered["spell"] = None
        validated = validate_skill_values(filtered, instance=instance)
        fields = validated["fields"]
        return json_safe(
            {
                "name": fields["nome"],
                "slug": fields["slug"],
                "number": fields["numero"],
                "familyId": fields["famiglia"].id,
                "familyOrder": fields["ordine_famiglia"],
                "prerequisiteIds": [skill.id for skill in validated["prerequisites"]],
                "baseXpCost": fields["costo_pe"],
                "xpType": fields["tipo_pe"],
                "rulesCost": fields["costo_testuale"],
                "requirementsText": fields["requisiti"],
                "description": fields["descrizione"],
                "profileTags": fields["profile_tags"],
                "profileNotes": fields["profile_notes"],
                "passiveEffects": fields["effetti_passivi"],
                "activeReminders": fields["azioni_attive"],
                "magic": validated["magic"],
                "spell": filtered["spell"] if validated["magic"] else None,
                "icon": fields["icona"],
                "notes": fields["note"],
            }
        )

    def prepare_create(self, user, giocatore, values: dict[str, Any], source_id: int | None = None) -> PreparedChange:
        self.require_access(user, giocatore, "create")
        original: dict[str, Any] = {}
        base_updated_at = None
        base_digest = ""
        materialized = self._default_values()
        if source_id is not None:
            source = self._load(source_id)
            original = self._snapshot_for(source)
            materialized.update(original["values"])
            materialized["name"] = ""
            materialized["slug"] = ""
            materialized["number"] = self._default_values()["number"]
            base_updated_at = source.updated_at
            base_digest = original["digest"]
        materialized.update(self._filter_values(values))
        normalized = self._validate_values(materialized, instance=None)
        return PreparedChange(
            values=normalized,
            original_snapshot=original,
            field_schema=self.field_schema(user, giocatore, action="create"),
            display_label=normalized["name"],
            base_updated_at=base_updated_at,
            base_digest=base_digest,
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
        skill = self._load(object_id, for_update=for_update)
        original = self._snapshot_for(skill)
        materialized = {**original["values"], **self._filter_values(values)}
        normalized = self._validate_values(materialized, instance=skill)
        return PreparedChange(
            values=normalized,
            original_snapshot=original,
            field_schema=self.field_schema(user, giocatore, action="update", instance=skill),
            display_label=normalized["name"],
            base_updated_at=skill.updated_at,
            base_digest=original["digest"],
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
        skill = self._load(object_id, for_update=for_update)
        if skill.archived_at:
            raise ApiError("skills.already_archived", "L'abilità è già archiviata.", status=409)
        original = self._snapshot_for(skill)
        return PreparedChange(
            values=original["values"],
            original_snapshot=original,
            field_schema=[],
            display_label=skill.nome,
            base_updated_at=skill.updated_at,
            base_digest=original["digest"],
        )

    def apply_create(self, user, giocatore, values: dict[str, Any]) -> dict[str, Any]:
        skill = create_skill(user, giocatore, values)
        return {"id": skill.id, "label": skill.nome, "action": "create", "entityType": self.entity_type}

    def apply_update(self, user, giocatore, object_id: int, values: dict[str, Any]) -> dict[str, Any]:
        skill = update_skill(user, giocatore, object_id, values)
        return {"id": skill.id, "label": skill.nome, "action": "update", "entityType": self.entity_type}

    def apply_archive(self, user, giocatore, object_id: int) -> dict[str, Any]:
        skill = archive_skill(user, giocatore, object_id)
        return {"id": skill.id, "label": skill.nome, "action": "archive", "entityType": self.entity_type}


class SpellChangeHandler(SkillChangeHandler):
    entity_type = "spell"
    label = "Incantesimo"

    def _queryset(self, *, for_update: bool = False):
        return super()._queryset(for_update=for_update).filter(
            spell_definition__isnull=False,
            spell_definition__archived_at__isnull=True,
        )

    def _default_values(self) -> dict[str, Any]:
        return {**super()._default_values(), "magic": True, "spell": self._default_spell()}

    def _validate_values(self, values: dict[str, Any], *, instance: Skill | None) -> dict[str, Any]:
        return super()._validate_values({**values, "magic": True}, instance=instance)

    def field_schema(self, user, giocatore, *, action: str, instance=None) -> list[dict[str, Any]]:
        fields = super().field_schema(user, giocatore, action=action, instance=instance)
        for field in fields:
            if field["name"] == "magic":
                field["readOnly"] = True
                field["help"] = "Gli incantesimi sono sempre Skill magiche."
        return fields
