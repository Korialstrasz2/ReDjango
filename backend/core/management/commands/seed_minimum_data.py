from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from backend.characters.models import BorsaReagenti, Character, Equip, Faretra, Note, Personaggio, Zaino
from backend.core.defaults import (
    DEFAULT_CAMPAIGN_NAME,
    LOCAL_PLAYER_NAME,
    V2_EFFECT_CATEGORY_DEFAULTS,
    V2_EMPTY_OBJECT_NAMES,
    V2_GLOBAL_MODIFIERS_DEFAULTS,
    V2_PLACEHOLDER_ITEMS,
    V2_SKILL_FAMILY_DEFAULTS,
)
from backend.core.models import DatiCampagna, EffettiEMalattie, FamigliaSkill, Giocatore, GlobalModifiers, Oggetto


class Command(BaseCommand):
    help = "Create the local user and a tiny playable data seed."

    def _seed_global_modifiers(self) -> int:
        touched = 0
        for modifier_defaults in V2_GLOBAL_MODIFIERS_DEFAULTS:
            modifier, created = GlobalModifiers.objects.get_or_create(
                name=modifier_defaults["name"],
                defaults={
                    "value_float": modifier_defaults["value_float"],
                    "value_string": modifier_defaults["value_string"],
                    "rule_notes": modifier_defaults["rule_notes"],
                },
            )
            if created:
                touched += 1
                continue

            value_float = modifier.value_float or {}
            value_string = modifier.value_string or {}
            changed = False
            for key, value in modifier_defaults["value_float"].items():
                if key not in value_float:
                    value_float[key] = value
                    changed = True
            for key, value in modifier_defaults["value_string"].items():
                if key not in value_string:
                    value_string[key] = value
                    changed = True
            if not modifier.rule_notes:
                modifier.rule_notes = modifier_defaults["rule_notes"]
                changed = True
            if changed:
                modifier.value_float = value_float
                modifier.value_string = value_string
                modifier.save(update_fields=["value_float", "value_string", "rule_notes", "updated_at"])
                touched += 1
        return touched

    def _seed_skill_families(self) -> int:
        touched = 0
        for family in V2_SKILL_FAMILY_DEFAULTS:
            _, created = FamigliaSkill.objects.get_or_create(
                nome=family["nome"],
                defaults={
                    "gruppo": family.get("gruppo", ""),
                    "ordine": family.get("ordine", 0),
                    "is_classe": family.get("is_classe", False),
                    "is_religione": family.get("is_religione", False),
                    "is_perk": family.get("is_perk", False),
                    "note": "Seed category for v2 skill organization.",
                },
            )
            touched += int(created)
        return touched

    def _seed_effect_categories(self) -> int:
        touched = 0
        for category in V2_EFFECT_CATEGORY_DEFAULTS:
            _, created = EffettiEMalattie.objects.get_or_create(
                nome=category["nome"],
                defaults={
                    "tipo": category["tipo"],
                    "descrizione": "Seed category placeholder for v2 effect organization.",
                    "effect_payload": {"seed_category": True},
                    "stacking_rule": "category",
                    "icon": category["icon"],
                    "metadata": {"seed_kind": "effect_category"},
                },
            )
            touched += int(created)
        return touched

    def _seed_placeholder_items(self) -> int:
        touched = 0
        for item in V2_PLACEHOLDER_ITEMS:
            _, created = Oggetto.objects.get_or_create(
                nome=item["nome"],
                defaults={
                    "modello": True,
                    "temporaneo": False,
                    "archiviato": True,
                    "icona": item.get("icona", ""),
                    "tipo_1": item.get("tipo_1", ""),
                    "tipo_2": item.get("tipo_2", ""),
                    "descrizione": "Seed placeholder item for empty/default equipment states.",
                    "metadata": {"seed_kind": "placeholder_item"},
                },
            )
            touched += int(created)
        return touched

    def _seed_empty_character_objects(self) -> int:
        touched = 0
        names = V2_EMPTY_OBJECT_NAMES
        zaino, created = Zaino.objects.get_or_create(nome=names["zaino"])
        touched += int(created)
        faretra, created = Faretra.objects.get_or_create(nome=names["faretra"])
        touched += int(created)
        equip, created = Equip.objects.get_or_create(nome=names["equip"])
        touched += int(created)
        note, created = Note.objects.get_or_create(
            nome=names["note"],
            defaults={
                "personaggio": {"seed": "empty"},
                "appunti": {"seed": "empty"},
                "note_combat": {"seed": "empty"},
                "note_skill": {"seed": "empty"},
                "crafting": {"seed": "empty"},
                "alchimia": {"seed": "empty"},
            },
        )
        touched += int(created)
        borsa, created = BorsaReagenti.objects.get_or_create(
            nome=names["borsa_reagenti"],
            defaults={"slot_max_reagenti": 0, "ingredienti": {}, "moltiplicatori": {}},
        )
        touched += int(created)
        personaggio, created = Personaggio.objects.get_or_create(
            nome_interno=names["personaggio_internal"],
            defaults={
                "nome": names["personaggio"],
                "tipologia": "altro",
                "razza_1": "",
                "livello": 1,
                "equip": equip,
                "zaino": zaino,
                "note": note,
                "borsa_reagenti": borsa,
                "faretra": faretra,
                "metadata": {"seed_kind": "empty_personaggio_template"},
            },
        )
        touched += int(created)

        changed = False
        if personaggio.equip_id is None:
            personaggio.equip = equip
            changed = True
        if personaggio.zaino_id is None:
            personaggio.zaino = zaino
            changed = True
        if personaggio.note_id is None:
            personaggio.note = note
            changed = True
        if personaggio.borsa_reagenti_id is None:
            personaggio.borsa_reagenti = borsa
            changed = True
        if personaggio.faretra_id is None:
            personaggio.faretra = faretra
            changed = True
        if changed:
            personaggio.save(update_fields=["equip", "zaino", "note", "borsa_reagenti", "faretra", "updated_at"])
            touched += 1

        if note.personaggio_ref_id is None:
            note.personaggio_ref = personaggio
            note.save(update_fields=["personaggio_ref", "updated_at"])
            touched += 1
        if borsa.personaggio_id is None:
            borsa.personaggio = personaggio
            borsa.save(update_fields=["personaggio", "updated_at"])
            touched += 1
        return touched

    def handle(self, *args, **options):
        User = get_user_model()
        user, created = User.objects.get_or_create(
            username=LOCAL_PLAYER_NAME,
            defaults={"is_staff": True, "is_superuser": False},
        )
        if created:
            user.set_unusable_password()
            user.save(update_fields=["password"])

        Giocatore.objects.get_or_create(
            nome=LOCAL_PLAYER_NAME,
            defaults={"display_name": "Local Master", "role": Giocatore.ROLE_DM},
        )
        DatiCampagna.objects.get_or_create(
            nome=DEFAULT_CAMPAIGN_NAME,
            defaults={"attiva": True},
        )
        touched = 0
        touched += self._seed_global_modifiers()
        touched += self._seed_skill_families()
        touched += self._seed_effect_categories()
        touched += self._seed_placeholder_items()
        touched += self._seed_empty_character_objects()

        if not Character.objects.filter(owner=user).exists():
            Character.objects.create(
                owner=user,
                name="Elyra",
                ancestry="Human",
                archetype="Wayfarer",
                level=1,
                stats={"might": 2, "agility": 3, "mind": 2, "spirit": 3},
                resources={"health": 10, "stamina": 8, "mana": 6},
                notes="Starter character for the minimum rebuild.",
            )
            Character.objects.create(
                owner=user,
                name="Borin",
                ancestry="Dwarf",
                archetype="Guardian",
                level=1,
                stats={"might": 4, "agility": 1, "mind": 2, "spirit": 2},
                resources={"health": 14, "stamina": 7, "mana": 2},
                notes="A sturdy sample character for testing the character menu.",
            )
            self.stdout.write(self.style.SUCCESS(f"Seeded local user, sample characters, and {touched} v2 defaults."))
            return

        self.stdout.write(f"Minimum data already present. V2 defaults touched: {touched}.")
