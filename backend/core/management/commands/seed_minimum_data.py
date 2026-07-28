from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files import File
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.text import slugify

from backend.characters.models import (
    ContenitoreInventario,
    EffettiPersonaggio,
    Equip,
    Faretra,
    Note,
    Personaggio,
    SkillPersonaggio,
    VoceContenitoreInventario,
    Zaino,
)
from backend.characters.services.inventory_rules import item_weight
from backend.characters.services.refresh_personaggio import refresh_personaggio
from backend.core.competence_defaults import COMPETENCE_DEFINITIONS, default_competence_state
from backend.core.alchemy_defaults import ALCHEMY_REAGENT_DEFAULTS
from backend.core.defaults import (
    DEFAULT_CAMPAIGN_NAME,
    LOCAL_PLAYER_NAME,
    V2_EFFECT_CATEGORY_DEFAULTS,
    V2_DICE_SET_DEFAULTS,
    V2_EMPTY_OBJECT_NAMES,
    V2_GLOBAL_MODIFIERS_DEFAULTS,
    V2_PLACEHOLDER_ITEMS,
    V2_POC_ABILITA_DEFAULTS,
    V2_POC_EFFECT_DEFAULTS,
    V2_POC_ITEM_DEFAULTS,
    V2_POC_PERSONAGGIO_DEFAULTS,
    V2_POC_SEED_VERSION,
    V2_RETIRED_SETTING_KEYS,
    V2_SKILL_FAMILY_DEFAULTS,
    V2_SETTING_DEFAULTS,
    V2_SETTINGS_SEED_VERSION,
    V2_THEME_DEFAULTS,
    V2_THEME_ASSET_MAPS,
    V2_THEME_PLACEHOLDER_ASSETS,
    V2_THEME_SEED_VERSION,
)
from backend.core.guides_it import V2_GUIDE_DEFAULTS, V2_GUIDE_DEFAULT_VERSION
from backend.combat.defaults import ensure_combat_defaults
from backend.core.models import (
    DatiCampagna,
    Competenze,
    EffettiEMalattie,
    Effetto,
    FamigliaSkill,
    Giocatore,
    GlobalModifiers,
    GruppoFamiglieSkill,
    Guida,
    Oggetto,
    OpzioneTipoOggetto,
    ReagenteAlchemico,
    SettingDefinition,
    Skill,
    Theme,
    TipoArma,
)
from backend.core.weapon_presets import WEAPON_TYPE_PRESETS
from backend.media_library.defaults import DEFAULT_IMAGE_GROUPS, IMAGE_CATEGORY_DEFAULTS
from backend.media_library.models import ImageCategory, UploadedImage
from backend.dice_tools.models import DiceSet


COMPETENCE_SEED_VERSION = "2"


class Command(BaseCommand):
    help = "Crea l'utente locale e i dati minimi utilizzabili."

    def _save_if_changed(self, instance, field_values: dict) -> int:
        changed_fields = []
        for field, value in field_values.items():
            if getattr(instance, field) != value:
                setattr(instance, field, value)
                changed_fields.append(field)
        if not changed_fields:
            return 0
        instance.save(update_fields=[*changed_fields, "updated_at"])
        return 1

    def _seed_competencies(self) -> int:
        touched = 0
        for definition in COMPETENCE_DEFINITIONS:
            metadata = {
                "seed_kind": "competence",
                "seed_version": COMPETENCE_SEED_VERSION,
                "key": definition["key"],
                "attribute": definition["attribute"],
            }
            defaults = {
                "descrizione": definition["description"],
                "mapping_tag": definition["mapping_tag"],
                "ordine": definition["order"],
                "categoria": definition["category"],
                "metadata": metadata,
            }
            competence, created = Competenze.objects.get_or_create(
                nome=definition["name"],
                defaults=defaults,
            )
            touched += int(created)
            current_metadata = competence.metadata if isinstance(competence.metadata, dict) else {}
            if (
                current_metadata.get("seed_kind") == "competence"
                and current_metadata.get("seed_version") != COMPETENCE_SEED_VERSION
            ):
                touched += self._save_if_changed(competence, defaults)
        return touched

    def _seed_alchemy_reagents(self) -> int:
        touched = 0
        for order, (name, color, level) in enumerate(ALCHEMY_REAGENT_DEFAULTS, start=1):
            values = {
                "colore": color,
                "livello": level,
                "attivo": True,
                "ordine": order,
                "metadata": {
                    "seed_kind": "elder_alchemy_reagent",
                    "seed_version": "1",
                },
            }
            reagent, created = ReagenteAlchemico.objects.get_or_create(nome=name, defaults=values)
            touched += int(created)
            if not created:
                current_metadata = reagent.metadata if isinstance(reagent.metadata, dict) else {}
                if current_metadata.get("seed_kind") == "elder_alchemy_reagent":
                    touched += self._save_if_changed(reagent, values)
        return touched

    def _seed_image_categories(self) -> int:
        touched = 0
        for definition in IMAGE_CATEGORY_DEFAULTS:
            _category, created = ImageCategory.objects.get_or_create(
                slug=definition["slug"],
                defaults={
                    **{key: value for key, value in definition.items() if key != "slug"},
                    "is_active": True,
                    "metadata": {"seed_kind": "image_category", "seed_version": "1"},
                },
            )
            touched += int(created)
        return touched

    def _classify_existing_images(self) -> int:
        touched = 0
        categories = list(ImageCategory.objects.filter(is_active=True).order_by("order", "name"))
        for asset in UploadedImage.objects.filter(archived_at__isnull=True):
            category = asset.category
            if category is None:
                category = next(
                    (entry for entry in categories if asset.usage_type in (entry.usage_types or [])),
                    None,
                )
                if category is None:
                    category = next(
                        (entry for entry in categories if "generic" in (entry.usage_types or [])),
                        None,
                    )
            values = {
                "category": category,
                "group": asset.group or DEFAULT_IMAGE_GROUPS.get(asset.usage_type) or "Archivio",
            }
            touched += self._save_if_changed(asset, values)
        return touched

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

    def _seed_settings(self) -> int:
        touched = SettingDefinition.objects.filter(key__in=V2_RETIRED_SETTING_KEYS).count()
        SettingDefinition.objects.filter(key__in=V2_RETIRED_SETTING_KEYS).delete()
        for definition in V2_SETTING_DEFAULTS:
            metadata = {
                "seed_kind": "setting_definition",
                "seed_version": V2_SETTINGS_SEED_VERSION,
                **definition.get("validation", {}),
            }
            managed_fields = {
                key: value
                for key, value in definition.items()
                if key not in {"key", "validation"}
            }
            setting, created = SettingDefinition.objects.get_or_create(
                key=definition["key"],
                defaults={
                    **managed_fields,
                    "value": definition["default_value"],
                    "metadata": metadata,
                },
            )
            if created:
                touched += 1
                continue

            current_metadata = setting.metadata if isinstance(setting.metadata, dict) else {}
            update_values = {
                **managed_fields,
                "metadata": {**current_metadata, **metadata},
            }
            touched += self._save_if_changed(setting, update_values)
        return touched

    def _seed_dice_sets(self) -> int:
        touched = 0
        for definition in V2_DICE_SET_DEFAULTS:
            _dice_set, created = DiceSet.objects.get_or_create(
                slug=definition["slug"],
                defaults={
                    **{key: value for key, value in definition.items() if key != "slug"},
                    "is_active": True,
                    "metadata": {"seed_kind": "dice_set", "seed_version": "1"},
                },
            )
            touched += int(created)
        return touched

    def _seed_themes(self) -> int:
        touched = 0
        theme_category = next(
            (
                category
                for category in ImageCategory.objects.filter(is_active=True).order_by("order", "name")
                if "theme_background" in (category.usage_types or [])
            ),
            None,
        )
        asset_root = settings.BASE_DIR / "frontend" / "static" / "frontend" / "images" / "themes" / "placeholders"
        assets = {}
        asset_titles = {
            "pergamena-menu.webp": "Tema Pergamena - Menu principale",
            "pergamena-personaggi.webp": "Tema Pergamena - Personaggi",
            "pergamena-media.webp": "Tema Pergamena - Archivio multimediale",
            "pergamena-guide.webp": "Tema Pergamena - Guide e impostazioni",
            "notte.webp": "Tema Notte - Osservatorio lunare",
            "arcano.webp": "Tema Arcano - Archivio ametista",
            "skyrim.webp": "Tema Skyrim - Montagne del nord",
            "morrowind.webp": "Tema Morrowind - Terre di cenere",
            "oblivion.webp": "Tema Oblivion - Fortezza d'acciaio",
        }

        filenames = {
            filename
            for theme_assets in V2_THEME_ASSET_MAPS.values()
            for filename in theme_assets.values()
        }
        for filename in sorted(filenames):
            seed_key = f"theme-placeholder:{filename}"
            asset = UploadedImage.objects.filter(metadata__seed_key=seed_key).first()
            created = asset is None
            if asset is None:
                asset = UploadedImage(
                    title=asset_titles.get(filename, filename),
                    folder="themes/placeholders",
                    usage_type="theme_background",
                    category=theme_category,
                    group="Temi",
                    source="generated_placeholder",
                    prompt="Sfondo fantasy originale generato come segnaposto modificabile per i temi di ReDjango.",
                    metadata={
                        "seed_kind": "theme_placeholder",
                        "seed_key": seed_key,
                        "seed_version": V2_THEME_SEED_VERSION,
                    },
                )

            source_path = asset_root / filename
            storage_name = f"v2/images/themes/placeholders/{filename}"
            if source_path.exists() and not default_storage.exists(storage_name):
                try:
                    with source_path.open("rb") as source_file:
                        default_storage.save(storage_name, File(source_file))
                except OSError:
                    # Test and read-only environments can still seed the database contract.
                    # A normal writable launcher run copies the bundled placeholder on the next seed.
                    pass
            if source_path.exists() and asset.file.name != storage_name:
                asset.file.name = storage_name
                asset.save()
                touched += 1
            elif created:
                asset.save()
                touched += 1
            if asset.category_id is None or not asset.group:
                touched += self._save_if_changed(
                    asset,
                    {
                        "category": asset.category or theme_category,
                        "group": asset.group or "Temi",
                    },
                )
            assets[filename] = asset

        for definition in V2_THEME_DEFAULTS:
            image_defaults = {
                field_name: assets.get(filename)
                for field_name, filename in V2_THEME_ASSET_MAPS.get(
                    definition["slug"],
                    V2_THEME_PLACEHOLDER_ASSETS,
                ).items()
            }
            defaults = {
                **definition,
                **image_defaults,
                "metadata": {
                    "seed_kind": "theme",
                    "seed_version": V2_THEME_SEED_VERSION,
                },
            }
            theme, created = Theme.objects.get_or_create(slug=definition["slug"], defaults=defaults)
            if created:
                touched += 1
                continue

            theme_metadata = theme.metadata if isinstance(theme.metadata, dict) else {}
            refresh_seed_images = (
                theme_metadata.get("seed_kind") == "theme"
                and theme_metadata.get("seed_version") != V2_THEME_SEED_VERSION
            )
            theme_updates = {}
            if refresh_seed_images:
                theme_updates = {
                    key: value
                    for key, value in definition.items()
                    if key not in {"slug", "is_active", "is_default"}
                }
            image_updates = {}
            for field_name, asset in image_defaults.items():
                current_asset = getattr(theme, field_name)
                current_metadata = (
                    current_asset.metadata
                    if current_asset and isinstance(current_asset.metadata, dict)
                    else {}
                )
                if asset is not None and (
                    current_asset is None
                    or (refresh_seed_images and current_metadata.get("seed_kind") == "theme_placeholder")
                ):
                    image_updates[field_name] = asset
            update_values = {
                **theme_updates,
                **image_updates,
                "metadata": {
                    **theme_metadata,
                    "seed_kind": "theme",
                    "seed_version": V2_THEME_SEED_VERSION,
                },
            }
            touched += self._save_if_changed(theme, update_values)
        return touched

    def _seed_skill_families_without_art(self) -> int:
        touched = 0
        seed_note = "Categoria iniziale per l'organizzazione delle abilità V2."
        group_names = list(dict.fromkeys(
            family.get("gruppo", "Generali")
            for family in V2_SKILL_FAMILY_DEFAULTS
        ))
        groups = {}
        for index, group_name in enumerate(group_names):
            group, created = GruppoFamiglieSkill.objects.get_or_create(
                nome=group_name,
                defaults={
                    "slug": slugify(group_name),
                    "ordine": index * 10,
                    "metadata": {
                        "seed_kind": "skill_family_group",
                        "seed_version": V2_POC_SEED_VERSION,
                    },
                },
            )
            groups[group_name] = group
            touched += int(created)
        obsolete_flat_families = {
            "Generale", "Combattimento", "Magia", "Crafting", "Sociale",
            "Esplorazione", "Classe", "Religione", "Perk",
        }
        for obsolete in FamigliaSkill.objects.filter(
            nome__in=obsolete_flat_families,
            archived_at__isnull=True,
        ):
            metadata = obsolete.metadata if isinstance(obsolete.metadata, dict) else {}
            if obsolete.note in {seed_note, "Seed category for v2 skill organization."} or metadata.get("seed_kind") == "skill_family":
                obsolete.archived_at = timezone.now()
                obsolete.save(update_fields=["archived_at", "updated_at"])
                touched += 1

        for family in V2_SKILL_FAMILY_DEFAULTS:
            family_record, created = FamigliaSkill.objects.get_or_create(
                nome=family["nome"],
                defaults={
                    "gruppo": groups[family.get("gruppo", "Generali")],
                    "ordine": family.get("ordine", 0),
                    "is_classe": family.get("is_classe", False),
                    "is_religione": family.get("is_religione", False),
                    "is_perk": family.get("is_perk", False),
                    "note": "",
                    "metadata": {"seed_kind": "skill_family", "seed_version": V2_POC_SEED_VERSION},
                },
            )
            touched += int(created)
            metadata = family_record.metadata if isinstance(family_record.metadata, dict) else {}
            if not created and (
                family_record.note in {seed_note, "Seed category for v2 skill organization."}
                or metadata.get("seed_kind") == "skill_family"
            ):
                update_values = {
                    "gruppo": groups[family.get("gruppo", "Generali")],
                    "ordine": family.get("ordine", 0),
                    "is_classe": family.get("is_classe", False),
                    "is_religione": family.get("is_religione", False),
                    "is_perk": family.get("is_perk", False),
                    "archived_at": None,
                    "metadata": {
                        **metadata,
                        "seed_kind": "skill_family",
                        "seed_version": V2_POC_SEED_VERSION,
                    },
                }
                if family_record.note in {seed_note, "Seed category for v2 skill organization."}:
                    update_values["note"] = ""
                touched += self._save_if_changed(
                    family_record,
                    update_values,
                )
        return touched

    def _seed_skill_families(self) -> int:
        touched = self._seed_skill_families_without_art()
        category = ImageCategory.objects.filter(slug="ambientazioni", is_active=True).first()
        asset_root = settings.BASE_DIR / "frontend" / "static" / "frontend" / "images" / "skills" / "families"
        for definition in V2_SKILL_FAMILY_DEFAULTS:
            art_filename = definition.get("art_filename", "")
            if not art_filename:
                continue
            seed_key = f"skill-family-art:{definition['nome'].lower()}"
            artwork = UploadedImage.objects.filter(metadata__seed_key=seed_key).first()
            created = artwork is None
            if artwork is None:
                artwork = UploadedImage(
                    title=f"Famiglia abilità — {definition['nome']}",
                    folder="skills/families",
                    usage_type="skill_family",
                    category=category,
                    group="Famiglie abilità",
                    source="the_elder_django_artwork",
                    metadata={
                        "seed_kind": "skill_family_art",
                        "seed_key": seed_key,
                        "seed_version": "1",
                    },
                )
            source_path = asset_root / art_filename
            storage_name = f"v2/images/skills/families/{art_filename}"
            if source_path.exists() and not default_storage.exists(storage_name):
                try:
                    with source_path.open("rb") as source_file:
                        default_storage.save(storage_name, File(source_file))
                except OSError:
                    pass
            if source_path.exists() and artwork.file.name != storage_name:
                artwork.file.name = storage_name
                artwork.save()
                touched += 1
            elif created:
                artwork.save()
                touched += 1

            family = FamigliaSkill.objects.get(nome=definition["nome"])
            current_metadata = (
                family.immagine.metadata
                if family.immagine_id and isinstance(family.immagine.metadata, dict)
                else {}
            )
            if family.immagine_id is None or current_metadata.get("seed_kind") == "skill_family_art":
                touched += self._save_if_changed(family, {"immagine": artwork})
        return touched

    def _seed_effect_categories(self) -> int:
        touched = 0
        for category in V2_EFFECT_CATEGORY_DEFAULTS:
            _, created = EffettiEMalattie.objects.get_or_create(
                nome=category["nome"],
                defaults={
                    "tipo": category["tipo"],
                    "descrizione": "Categoria iniziale per l'organizzazione degli effetti V2.",
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
                    "descrizione": "Oggetto segnaposto per gli spazi vuoti dell'equipaggiamento.",
                    "metadata": {"seed_kind": "placeholder_item"},
                },
            )
            touched += int(created)
        return touched

    def _seed_guides(self) -> int:
        touched = 0
        for guide_defaults in V2_GUIDE_DEFAULTS:
            guide = Guida.objects.filter(
                metadata__seed_kind="guide",
                ordine=guide_defaults.get("ordine", 0),
            ).first()
            created = guide is None
            if guide is None:
                guide, created = Guida.objects.get_or_create(
                    nome=guide_defaults["nome"],
                    defaults={
                        "categoria": guide_defaults.get("categoria", ""),
                        "ordine": guide_defaults.get("ordine", 0),
                        "contenuto": guide_defaults["contenuto"],
                        "metadata": {
                            "seed_kind": "guide",
                            "seed_version": V2_GUIDE_DEFAULT_VERSION,
                        },
                    },
                )
            if created:
                touched += 1
                continue

            metadata = guide.metadata if isinstance(guide.metadata, dict) else {}
            should_update_seed = (
                metadata.get("seed_kind") == "guide"
                and metadata.get("seed_version") != V2_GUIDE_DEFAULT_VERSION
            )
            if guide.contenuto and not should_update_seed:
                continue

            guide.nome = guide_defaults["nome"]
            guide.categoria = guide_defaults.get("categoria", "")
            guide.ordine = guide_defaults.get("ordine", 0)
            guide.contenuto = guide_defaults["contenuto"]
            guide.metadata = {
                **metadata,
                "seed_kind": "guide",
                "seed_version": V2_GUIDE_DEFAULT_VERSION,
            }
            guide.save(update_fields=["nome", "categoria", "ordine", "contenuto", "metadata", "updated_at"])
            touched += 1
        return touched

    def _seed_poc_items(self) -> tuple[int, dict[str, Oggetto]]:
        touched = 0
        items_by_name = {}
        for item_defaults in V2_POC_ITEM_DEFAULTS:
            source_name = item_defaults["nome"]
            item_name = source_name.removeprefix("POC - ")
            item_values = {key: value for key, value in item_defaults.items() if key not in {"nome", "metadata"}}
            item_metadata = item_defaults.get("metadata") if isinstance(item_defaults.get("metadata"), dict) else {}
            weapon_type = TipoArma.objects.filter(nome__iexact=item_values.get("tipo_1", "")).first()
            defaults = {
                **item_values,
                "modello": True,
                "temporaneo": False,
                "archiviato": False,
                "tipo_arma": weapon_type,
                "metadata": {
                    **item_metadata,
                    "seed_kind": "poc_item",
                    "seed_version": V2_POC_SEED_VERSION,
                    "sourceProject": "the_elder_django",
                    "source": "guide_derived_sample",
                },
            }
            item, created = Oggetto.objects.get_or_create(
                nome=item_name,
                defaults=defaults,
            )
            if created:
                touched += 1
            else:
                current_metadata = item.metadata if isinstance(item.metadata, dict) else {}
                if (
                    current_metadata.get("seed_kind") == "poc_item"
                    and current_metadata.get("seed_version") != V2_POC_SEED_VERSION
                ):
                    update_values = {
                        **defaults,
                        "metadata": {
                            **current_metadata,
                            "seed_kind": "poc_item",
                            "seed_version": V2_POC_SEED_VERSION,
                        },
                    }
                    touched += self._save_if_changed(item, update_values)
            items_by_name[source_name] = item
            items_by_name[item.nome] = item
        return touched, items_by_name

    def _seed_item_type_options(self) -> int:
        touched = 0
        for posizione in range(1, 5):
            values = (
                Oggetto.objects.exclude(**{f"tipo_{posizione}": ""})
                .values_list(f"tipo_{posizione}", flat=True)
                .distinct()
            )
            normalized_values = sorted({str(value).strip() for value in values if value})
            for ordine, value in enumerate(normalized_values, start=10):
                _, created = OpzioneTipoOggetto.objects.get_or_create(
                    posizione=posizione,
                    valore=value,
                    defaults={"etichetta": value, "ordine": ordine},
                )
                touched += int(created)
        return touched

    def _seed_sample_weapon_types(self) -> int:
        touched = 0
        for preset in WEAPON_TYPE_PRESETS:
            weapon_type, created = TipoArma.objects.get_or_create(nome=preset["name"])
            values = {
                "lunghezza": preset["length"],
                "potenza": preset["power"],
                "bonus_1": preset["bonus1"],
                "bonus_2": preset["bonus2"],
                "rules": {
                    **(weapon_type.rules if isinstance(weapon_type.rules, dict) else {}),
                    "source": "the_elder_django",
                    "presetVersion": 1,
                    "profile": preset["profile"],
                },
                "metadata": {
                    **(weapon_type.metadata if isinstance(weapon_type.metadata, dict) else {}),
                    "seed_kind": "elder_weapon_type",
                    "seed_version": "1",
                },
            }
            touched += int(created) if created else self._save_if_changed(weapon_type, values)
        return touched

    def _seed_poc_skills(self) -> tuple[int, dict[str, Skill]]:
        # The skill proof-of-concept catalog is retired. Existing rows are archived
        # by the schema migration and ownership records remain available as history.
        return 0, {}

    def _seed_poc_effects(self) -> tuple[int, dict[str, Effetto]]:
        touched = 0
        effects_by_name = {}
        for effect_defaults in V2_POC_EFFECT_DEFAULTS:
            source_name = effect_defaults["nome"]
            effect_name = source_name.removeprefix("POC - ")
            defaults = {
                "tipo": effect_defaults.get("tipo", ""),
                "descrizione": effect_defaults.get("descrizione", ""),
                "effect_payload": effect_defaults.get("effect_payload", {}),
                "durata_turni": effect_defaults.get("durata_turni"),
                "stacking_rule": effect_defaults.get("stacking_rule", ""),
                "icona": effect_defaults.get("icona", ""),
                "origine_tipo": effect_defaults.get("origine_tipo", ""),
                "origine_nome": effect_defaults.get("origine_nome", ""),
                "notes": "Effetto dimostrativo per le schede dei personaggi attivi.",
                "metadata": {
                    "seed_kind": "poc_effect",
                    "seed_version": V2_POC_SEED_VERSION,
                },
            }
            effect, created = Effetto.objects.get_or_create(nome=effect_name, defaults=defaults)
            if created:
                touched += 1
            else:
                current_metadata = effect.metadata if isinstance(effect.metadata, dict) else {}
                if (
                    current_metadata.get("seed_kind") == "poc_effect"
                    and current_metadata.get("seed_version") != V2_POC_SEED_VERSION
                ):
                    defaults["metadata"] = {
                        **current_metadata,
                        "seed_kind": "poc_effect",
                        "seed_version": V2_POC_SEED_VERSION,
                    }
                    touched += self._save_if_changed(effect, defaults)
            effects_by_name[source_name] = effect
            effects_by_name[effect.nome] = effect
        return touched, effects_by_name

    def _assign_item_slots(self, container, item_names: list[str], items_by_name: dict[str, Oggetto]) -> int:
        item_names = sorted(item_names, key=lambda name: -item_weight(items_by_name.get(name)))
        values = {}
        for index in range(1, 51):
            item = items_by_name.get(item_names[index - 1]) if index <= len(item_names) else None
            values[f"slot_{index}"] = item
        return self._save_if_changed(container, values)

    def _assign_effect_slots(
        self,
        container: EffettiPersonaggio,
        effect_names: list[str],
        effects_by_name: dict[str, Effetto],
    ) -> int:
        values = {}
        for index in range(1, 51):
            effect = effects_by_name.get(effect_names[index - 1]) if index <= len(effect_names) else None
            values[f"effetto_{index}"] = effect
        return self._save_if_changed(container, values)

    def _seed_poc_personaggi(
        self,
        giocatore: Giocatore,
        items_by_name: dict[str, Oggetto],
        skills_by_name: dict[str, Skill],
        effects_by_name: dict[str, Effetto],
    ) -> int:
        touched = 0
        personaggio_ids = []
        active_campaign = DatiCampagna.objects.filter(attiva=True, archived_at__isnull=True).first()
        for personaggio_defaults in V2_POC_PERSONAGGIO_DEFAULTS:
            name = personaggio_defaults["nome"]
            zaino, created = Zaino.objects.get_or_create(
                nome=f"POC - Zaino - {name}",
                defaults={"metadata": {"seed_kind": "poc_related", "seed_version": V2_POC_SEED_VERSION}},
            )
            touched += int(created)
            if created:
                touched += self._assign_item_slots(zaino, personaggio_defaults.get("zaino", []), items_by_name)

            faretra, created = Faretra.objects.get_or_create(
                nome=f"POC - Faretra - {name}",
                defaults={"metadata": {"seed_kind": "poc_related", "seed_version": V2_POC_SEED_VERSION}},
            )
            touched += int(created)
            if created:
                touched += self._assign_item_slots(faretra, personaggio_defaults.get("faretra", []), items_by_name)

            effetti, created = EffettiPersonaggio.objects.get_or_create(
                nome=f"POC - Effetti - {name}",
                defaults={"metadata": {"seed_kind": "poc_related", "seed_version": V2_POC_SEED_VERSION}},
            )
            touched += int(created)
            if created:
                touched += self._assign_effect_slots(effetti, personaggio_defaults.get("effetti", []), effects_by_name)

            equip, created = Equip.objects.get_or_create(
                nome=f"POC - Equip - {name}",
                defaults={"metadata": {"seed_kind": "poc_related", "seed_version": V2_POC_SEED_VERSION}},
            )
            touched += int(created)
            if created:
                equip_values = {field_name: None for field_name in [field.name for field in Equip._meta.fields if field.name != "id"]}
                equip_values.pop("nome", None)
                equip_values.pop("created_at", None)
                equip_values.pop("updated_at", None)
                equip_values.pop("archived_at", None)
                equip_values.pop("metadata", None)
                equip_values["arma_primaria_slot"] = "arma"
                for slot_name, item_name in personaggio_defaults.get("equip", {}).items():
                    equip_values[slot_name] = items_by_name.get(item_name)
                equip_values["metadata"] = {"seed_kind": "poc_related", "seed_version": V2_POC_SEED_VERSION}
                touched += self._save_if_changed(equip, equip_values)

            note_defaults = personaggio_defaults.get("note", {})
            note, created = Note.objects.get_or_create(
                nome=f"POC - Note - {name}",
                defaults={
                    "background": note_defaults.get("background", ""),
                    "zaino": note_defaults.get("zaino", ""),
                    "combat": note_defaults.get("combat", ""),
                    "crafting": note_defaults.get("crafting", ""),
                    "viaggio": note_defaults.get("viaggio", ""),
                    "appunti": note_defaults.get("appunti", ""),
                    "missioni": note_defaults.get("missioni", ""),
                    "metadata": {"seed_kind": "poc_related", "seed_version": V2_POC_SEED_VERSION},
                },
            )
            touched += int(created)

            skill_entries = [
                {
                    "id": skills_by_name[skill_name].id,
                    "nome": skill_name,
                    "numero": skills_by_name[skill_name].numero,
                    "famiglia": skills_by_name[skill_name].famiglia.nome,
                }
                for skill_name in personaggio_defaults.get("skill_names", [])
                if skill_name in skills_by_name
            ]
            personaggio, created = Personaggio.objects.get_or_create(
                nome_interno=personaggio_defaults["nome_interno"],
                defaults={
                    "nome": name,
                    "tipologia": personaggio_defaults.get("tipologia", "giocabile"),
                    "razza_1": personaggio_defaults.get("razza_1", ""),
                    "razza_2": personaggio_defaults.get("razza_2", ""),
                    "livello": personaggio_defaults.get("livello", 1),
                    "equip": equip,
                    "zaino": zaino,
                    "note": note,
                    "faretra": faretra,
                    "effetti": effetti,
                    "metadata": {"seed_kind": "poc_personaggio", "seed_version": V2_POC_SEED_VERSION},
                },
            )
            touched += int(created)
            character_metadata = personaggio.metadata if isinstance(personaggio.metadata, dict) else {}
            refresh_seed_character = created or (
                character_metadata.get("seed_kind") == "poc_personaggio"
                and character_metadata.get("seed_version") != V2_POC_SEED_VERSION
            )
            if refresh_seed_character:
                touched += self._save_if_changed(
                    personaggio,
                    {
                        "nome": name,
                        "tipologia": personaggio_defaults.get("tipologia", "giocabile"),
                        "razza_1": personaggio_defaults.get("razza_1", ""),
                        "razza_2": personaggio_defaults.get("razza_2", ""),
                        "razza_3": personaggio_defaults.get("razza_3", ""),
                        "livello": personaggio_defaults.get("livello", 1),
                        "eta": personaggio_defaults.get("eta"),
                        "sesso": personaggio_defaults.get("sesso", ""),
                        "monete": personaggio_defaults.get("monete", 0),
                        "dettagli_personaggio": personaggio_defaults.get("dettagli_personaggio", ""),
                        "equip": equip,
                        "zaino": zaino,
                        "note": note,
                        "faretra": faretra,
                        "effetti": effetti,
                        "abilita": {
                            "known": V2_POC_ABILITA_DEFAULTS,
                            "skills": skill_entries,
                        },
                        "abilita_desiderate": {
                            "next": ["specializzazione", "talento avanzato"],
                        },
                        "competenze": {
                            **default_competence_state(),
                        },
                        "pe_generali": 12,
                        "pe_rossi": 8,
                        "pe_verdi": 8,
                        "pe_blu": 10,
                        "metadata": {"seed_kind": "poc_personaggio", "seed_version": V2_POC_SEED_VERSION},
                    },
                )
            container, container_created = ContenitoreInventario.objects.get_or_create(
                scope=ContenitoreInventario.SCOPE_PERSONAL,
                personaggio=personaggio,
                defaults={
                    "nome": f"Alchimia&Contenitori · {name}"[:160],
                    "capacita": 15,
                    "senza_peso": True,
                    "metadata": {"seed_kind": "poc_related", "seed_version": V2_POC_SEED_VERSION},
                },
            )
            touched += int(container_created)
            if container_created:
                reagent_defaults = personaggio_defaults.get("alchemy_container", {})
                for slot, (stock_key, quantity) in enumerate(
                    sorted(reagent_defaults.get("ingredienti", {}).items()),
                    start=1,
                ):
                    if int(quantity or 0) > 0:
                        VoceContenitoreInventario.objects.create(
                            contenitore=container,
                            slot=slot,
                            reagent_stock_key=stock_key,
                            quantita=int(quantity),
                        )
            if personaggio.campagna_id is None and active_campaign is not None:
                personaggio.campagna = active_campaign
                personaggio.save(update_fields=["campagna", "updated_at"])
                touched += 1

            refresh_personaggio(personaggio)
            starting_skill = skills_by_name.get("POC - Lama precisa")
            if starting_skill:
                ownership_defaults = {
                    "spesa_pe": {"general": 0, "red": 0, "green": 0, "blue": 0},
                    "passivi_accettati": [],
                    "configurazione_azioni": {
                        "azione-lama-precisa": {"enabled": True, "order": 0, "note": ""},
                    },
                    "metadata": {
                        "seed_kind": "poc_skill_ownership",
                        "seed_version": V2_POC_SEED_VERSION,
                    },
                }
                ownership, ownership_created = SkillPersonaggio.objects.get_or_create(
                    personaggio=personaggio,
                    skill=starting_skill,
                    defaults=ownership_defaults,
                )
                touched += int(ownership_created)
                ownership_metadata = ownership.metadata if isinstance(ownership.metadata, dict) else {}
                if (
                    not ownership_created
                    and ownership_metadata.get("seed_kind") == "poc_skill_ownership"
                    and ownership_metadata.get("seed_version") != V2_POC_SEED_VERSION
                ):
                    touched += self._save_if_changed(ownership, ownership_defaults)
            personaggio_ids.append(personaggio.id)

        existing_ids = giocatore.character_ids if isinstance(giocatore.character_ids, list) else []
        character_ids = [*existing_ids, *(character_id for character_id in personaggio_ids if character_id not in existing_ids)]
        giocatore_values = {"character_ids": character_ids}
        if giocatore.active_character_id not in character_ids:
            giocatore_values["active_character"] = Personaggio.objects.get(id=personaggio_ids[0])
        touched += self._save_if_changed(giocatore, giocatore_values)
        return touched

    def _seed_empty_character_objects(self) -> int:
        touched = 0
        names = V2_EMPTY_OBJECT_NAMES
        zaino, created = Zaino.objects.get_or_create(nome=names["zaino"])
        touched += int(created)
        faretra, created = Faretra.objects.get_or_create(nome=names["faretra"])
        touched += int(created)
        effetti, created = EffettiPersonaggio.objects.get_or_create(nome=names["effetti"])
        touched += int(created)
        equip, created = Equip.objects.get_or_create(nome=names["equip"])
        touched += int(created)
        note, created = Note.objects.get_or_create(
            nome=names["note"],
            defaults={"metadata": {"seed_kind": "empty"}},
        )
        touched += int(created)
        touched += self._save_if_changed(
            note,
            {
                "zaino": "",
                "combat": "",
                "crafting": "",
                "viaggio": "",
                "appunti": "",
                "missioni": "",
                "background": "",
                "metadata": {"seed_kind": "empty"},
            },
        )
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
                "faretra": faretra,
                "effetti": effetti,
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
        if personaggio.faretra_id is None:
            personaggio.faretra = faretra
            changed = True
        if personaggio.effetti_id is None:
            personaggio.effetti = effetti
            changed = True
        if changed:
            personaggio.save(
                update_fields=["equip", "zaino", "note", "faretra", "effetti", "updated_at"]
            )
            touched += 1
        _, container_created = ContenitoreInventario.objects.get_or_create(
            scope=ContenitoreInventario.SCOPE_PERSONAL,
            personaggio=personaggio,
            defaults={
                "nome": f"Alchimia&Contenitori · {personaggio.nome}"[:160],
                "capacita": 15,
                "senza_peso": True,
                "metadata": {"seed_kind": "empty"},
            },
        )
        touched += int(container_created)
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

        giocatore, _ = Giocatore.objects.get_or_create(
            nome=LOCAL_PLAYER_NAME,
            defaults={"user": user, "display_name": "Master locale", "role": Giocatore.ROLE_MASTER},
        )
        if giocatore.user_id is None:
            giocatore.user = user
            giocatore.save(update_fields=["user", "updated_at"])
        if giocatore.display_name == "Local Master":
            giocatore.display_name = "Master locale"
            giocatore.save(update_fields=["display_name", "updated_at"])
        DatiCampagna.objects.get_or_create(
            nome=DEFAULT_CAMPAIGN_NAME,
            defaults={"attiva": True},
        )
        touched = 0
        touched += self._seed_global_modifiers()
        touched += self._seed_image_categories()
        touched += self._classify_existing_images()
        touched += self._seed_themes()
        touched += self._seed_dice_sets()
        touched += self._seed_settings()
        touched += ensure_combat_defaults()
        touched += self._seed_competencies()
        touched += self._seed_alchemy_reagents()
        touched += self._seed_skill_families()
        touched += self._seed_effect_categories()
        touched += self._seed_placeholder_items()
        touched += self._seed_guides()
        touched += self._seed_sample_weapon_types()
        item_count, items_by_name = self._seed_poc_items()
        touched += item_count
        touched += self._seed_item_type_options()
        skill_count, skills_by_name = self._seed_poc_skills()
        touched += skill_count
        effect_count, effects_by_name = self._seed_poc_effects()
        touched += effect_count
        touched += self._seed_poc_personaggi(giocatore, items_by_name, skills_by_name, effects_by_name)
        sample_item_ids = {item.id for item in items_by_name.values()}
        stale_items = Oggetto.objects.filter(metadata__seed_kind="poc_item").exclude(id__in=sample_item_ids)
        stale_item_count = stale_items.count()
        stale_items.delete()
        touched += stale_item_count
        sample_effect_ids = {effect.id for effect in effects_by_name.values()}
        stale_effects = Effetto.objects.filter(metadata__seed_kind="poc_effect").exclude(id__in=sample_effect_ids)
        stale_effect_count = stale_effects.count()
        stale_effects.delete()
        touched += stale_effect_count
        touched += self._seed_empty_character_objects()

        # Base-formula additions must reach existing user characters too, not
        # only the bundled POC records refreshed during their own seed pass.
        for personaggio in Personaggio.objects.all():
            refresh_personaggio(personaggio)

        self.stdout.write(self.style.SUCCESS(f"Dati minimi pronti. Valori V2 aggiornati: {touched}."))
