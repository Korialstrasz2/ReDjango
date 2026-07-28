import re
import secrets

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .access import (
    ACCESS_MODE_ONLINE,
    ACCESS_MODE_SETTING_KEY,
    online_configuration_errors,
    persist_access_mode,
)
from .api import ApiError
from .models import CharacterAssignmentRequest, Giocatore, SettingDefinition, SettingOverride, Theme
from .security import effective_role, has_minimum_role, role_rank
from .settings_selectors import (
    ADMIN_MANAGED_SETTING_KEYS,
    GLOBAL_EDITABLE_SETTING_KEYS,
    can_edit_setting,
    global_setting_value,
    setting_base_value,
)


COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
ROLE_CODE_KEYS = {
    Giocatore.ROLE_MASTER: "security.game_master_access_code",
    Giocatore.ROLE_ADMIN: "security.game_admin_access_code",
}


def _choice_values(setting: SettingDefinition) -> list:
    if setting.key == "appearance.theme":
        return list(
            Theme.objects.filter(is_active=True, archived_at__isnull=True).values_list("slug", flat=True)
        )
    if setting.key == "dice.default_set":
        from backend.dice_tools.models import DiceSet

        return list(DiceSet.objects.filter(is_active=True, archived_at__isnull=True).values_list("slug", flat=True))
    values = []
    for choice in setting.choices if isinstance(setting.choices, list) else []:
        values.append(choice.get("value") if isinstance(choice, dict) else choice)
    return values


def validate_setting_value(setting: SettingDefinition, raw_value):
    if setting.value_type == SettingDefinition.TYPE_BOOL:
        if not isinstance(raw_value, bool):
            raise ApiError("settings.boolean_required", f"{setting.label}: scegli Sì oppure No.", setting.key)
        return raw_value

    if setting.value_type == SettingDefinition.TYPE_INT:
        if isinstance(raw_value, bool):
            raise ApiError("settings.integer_required", f"{setting.label}: inserisci un numero intero.", setting.key)
        try:
            value = int(raw_value)
        except (TypeError, ValueError) as exc:
            raise ApiError("settings.integer_required", f"{setting.label}: inserisci un numero intero.", setting.key) from exc
        metadata = setting.metadata if isinstance(setting.metadata, dict) else {}
        minimum = metadata.get("minimum")
        maximum = metadata.get("maximum")
        if minimum is not None and value < int(minimum):
            raise ApiError("settings.below_minimum", f"{setting.label}: il valore minimo è {minimum}.", setting.key)
        if maximum is not None and value > int(maximum):
            raise ApiError("settings.above_maximum", f"{setting.label}: il valore massimo è {maximum}.", setting.key)
        return value

    if setting.value_type == SettingDefinition.TYPE_COLOR:
        value = str(raw_value or "").strip()
        if not COLOR_RE.fullmatch(value):
            raise ApiError("settings.color_required", f"{setting.label}: usa un colore esadecimale di sei cifre.", setting.key)
        return value.lower()

    if setting.value_type == SettingDefinition.TYPE_SELECT:
        if raw_value not in _choice_values(setting):
            raise ApiError("settings.invalid_choice", f"La scelta per {setting.label} non è valida.", setting.key)
        return raw_value

    if setting.value_type == SettingDefinition.TYPE_STRING:
        return str(raw_value or "").strip()[:240]

    return raw_value


@transaction.atomic
def save_setting_overrides(user, giocatore: Giocatore, submitted: dict) -> None:
    if not isinstance(submitted, dict):
        raise ApiError("settings.invalid_payload", "Le impostazioni devono essere un oggetto.", "settings")

    role = effective_role(user, giocatore)
    definitions = {
        setting.key: setting
        for setting in SettingDefinition.objects.filter(key__in=submitted.keys(), active=True, archived_at__isnull=True)
    }
    prepared_values: list[tuple[SettingDefinition, object]] = []
    for key, raw_value in submitted.items():
        if key in ADMIN_MANAGED_SETTING_KEYS:
            raise ApiError(
                "settings.admin_managed",
                "Questa impostazione globale si modifica soltanto dal pannello Django Admin.",
                key,
                403,
            )
        setting = definitions.get(key)
        if setting is None:
            raise ApiError("settings.unknown", f"Impostazione sconosciuta o non attiva: {key}.", key, 404)
        if not has_minimum_role(role, setting.minimum_role) or not can_edit_setting(role, setting):
            raise ApiError("settings.forbidden", f"Non hai il permesso di modificare {setting.label}.", key, 403)

        value = None if raw_value is None else validate_setting_value(setting, raw_value)
        if setting.key == ACCESS_MODE_SETTING_KEY and value == ACCESS_MODE_ONLINE:
            missing = online_configuration_errors()
            if missing:
                raise ApiError(
                    "security.online_configuration_incomplete",
                    "Prima di attivare il server online configura "
                    + " e ".join(missing)
                    + " nell'ambiente del launcher.",
                    setting.key,
                    409,
                )
        prepared_values.append((setting, value))

    shortcut_definitions = list(
        SettingDefinition.objects.filter(
            key__startswith="shortcuts.",
            active=True,
            archived_at__isnull=True,
        )
    )
    shortcut_definitions = [
        setting
        for setting in shortcut_definitions
        if has_minimum_role(role, setting.minimum_role)
    ]
    shortcut_overrides = {
        override.setting_id: override.value
        for override in SettingOverride.objects.filter(
            giocatore=giocatore,
            setting__in=shortcut_definitions,
        )
    }
    effective_shortcuts = {
        setting.key: shortcut_overrides.get(setting.id, setting_base_value(setting))
        for setting in shortcut_definitions
    }
    for setting, value in prepared_values:
        if setting.key.startswith("shortcuts."):
            effective_shortcuts[setting.key] = setting_base_value(setting) if value is None else value

    shortcut_owners: dict[str, str] = {}
    for key, value in effective_shortcuts.items():
        shortcut = str(value or "")
        if not shortcut:
            continue
        conflict = shortcut_owners.get(shortcut)
        if conflict:
            raise ApiError(
                "settings.shortcut_conflict",
                f"{shortcut.replace('+', ' + ')} è già assegnata a un'altra azione.",
                key,
            )
        shortcut_owners[shortcut] = key

    for setting, value in prepared_values:
        if setting.key in GLOBAL_EDITABLE_SETTING_KEYS:
            SettingOverride.objects.filter(setting=setting).delete()
            setting.value = value
            setting.save(update_fields=["value", "updated_at"])
            if setting.key == ACCESS_MODE_SETTING_KEY:
                transaction.on_commit(lambda selected=value: persist_access_mode(selected))
            continue
        if value is None:
            SettingOverride.objects.filter(setting=setting, giocatore=giocatore).delete()
            continue
        SettingOverride.objects.update_or_create(
            setting=setting,
            giocatore=giocatore,
            defaults={"value": value},
        )


@transaction.atomic
def update_player_alias(giocatore: Giocatore, alias: object) -> Giocatore:
    normalized = str(alias or "").strip()
    if not normalized:
        raise ApiError("player.alias_required", "Inserisci un alias.", "alias")
    if len(normalized) > 120:
        raise ApiError("player.alias_too_long", "L'alias può contenere al massimo 120 caratteri.", "alias")
    giocatore = Giocatore.objects.select_for_update().get(pk=giocatore.pk)
    giocatore.display_name = normalized
    giocatore.save(update_fields=["display_name", "updated_at"])
    return giocatore


@transaction.atomic
def request_character_assignments(giocatore: Giocatore, character_ids: object, message: object = "") -> int:
    from backend.characters.models import Personaggio

    if not isinstance(character_ids, list) or not character_ids:
        raise ApiError("player.characters_required", "Seleziona almeno un personaggio.", "characterIds")
    try:
        requested_ids = list(dict.fromkeys(int(value) for value in character_ids))
    except (TypeError, ValueError) as exc:
        raise ApiError("player.characters_invalid", "La selezione dei personaggi non è valida.", "characterIds") from exc
    if len(requested_ids) > 50:
        raise ApiError("player.characters_too_many", "Puoi richiedere al massimo 50 personaggi alla volta.", "characterIds")

    assigned_ids = {
        int(value)
        for value in (giocatore.character_ids if isinstance(giocatore.character_ids, list) else [])
        if str(value).isdigit()
    }
    characters = list(
        Personaggio.objects.filter(id__in=requested_ids, archived_at__isnull=True)
        .filter(
            Q(metadata__seed_kind__isnull=True)
            | ~Q(metadata__seed_kind="empty_personaggio_template")
        )
    )
    if len(characters) != len(requested_ids):
        raise ApiError("player.character_not_found", "Uno dei personaggi selezionati non è disponibile.", "characterIds", 404)

    normalized_message = str(message or "").strip()[:1000]
    created = 0
    for character in characters:
        if character.id in assigned_ids:
            continue
        assignment, was_created = CharacterAssignmentRequest.objects.update_or_create(
            giocatore=giocatore,
            personaggio=character,
            defaults={
                "status": CharacterAssignmentRequest.STATUS_PENDING,
                "message": normalized_message,
                "admin_note": "",
                "reviewed_at": None,
                "archived_at": None,
            },
        )
        created += int(was_created or assignment.status == CharacterAssignmentRequest.STATUS_PENDING)
    if not created:
        raise ApiError("player.characters_already_assigned", "I personaggi selezionati sono già assegnati.", "characterIds")
    return created


@transaction.atomic
def approve_character_assignment(assignment: CharacterAssignmentRequest) -> CharacterAssignmentRequest:
    assignment = CharacterAssignmentRequest.objects.select_for_update().select_related("giocatore").get(pk=assignment.pk)
    giocatore = assignment.giocatore
    assigned_ids = [
        int(value)
        for value in (giocatore.character_ids if isinstance(giocatore.character_ids, list) else [])
        if str(value).isdigit()
    ]
    if assignment.personaggio_id not in assigned_ids:
        assigned_ids.append(assignment.personaggio_id)
    giocatore.character_ids = assigned_ids
    if giocatore.active_character_id is None:
        giocatore.active_character_id = assignment.personaggio_id
    giocatore.save(update_fields=["character_ids", "active_character", "updated_at"])
    assignment.status = CharacterAssignmentRequest.STATUS_APPROVED
    assignment.reviewed_at = timezone.now()
    assignment.save(update_fields=["status", "reviewed_at", "updated_at"])
    return assignment


@transaction.atomic
def reject_character_assignment(assignment: CharacterAssignmentRequest) -> CharacterAssignmentRequest:
    assignment = CharacterAssignmentRequest.objects.select_for_update().get(pk=assignment.pk)
    assignment.status = CharacterAssignmentRequest.STATUS_REJECTED
    assignment.reviewed_at = timezone.now()
    assignment.save(update_fields=["status", "reviewed_at", "updated_at"])
    return assignment


@transaction.atomic
def redeem_role_code(user, giocatore: Giocatore, target_role: object, submitted_code: object) -> Giocatore:
    target = str(target_role or "")
    setting_key = ROLE_CODE_KEYS.get(target)
    if setting_key is None:
        raise ApiError("player.role_invalid", "Il livello di accesso richiesto non è valido.", "targetRole")
    configured_code = str(global_setting_value(setting_key, "") or "").strip()
    candidate = str(submitted_code or "").strip()
    if not configured_code:
        raise ApiError("player.role_code_unavailable", "Questo codice non è ancora stato configurato dall'amministratore Django.", "code", 409)
    if not candidate or not secrets.compare_digest(candidate, configured_code):
        raise ApiError("player.role_code_invalid", "Il codice inserito non è valido.", "code", 403)

    giocatore = Giocatore.objects.select_for_update().get(pk=giocatore.pk)
    current_role = effective_role(user, giocatore)
    if role_rank(target) > role_rank(current_role):
        giocatore.role = target
        giocatore.save(update_fields=["role", "updated_at"])
    return giocatore


@transaction.atomic
def select_game_role(user, giocatore: Giocatore, target_role: object, submitted_code: object = "") -> Giocatore:
    """Select the in-game role without changing Django staff/superuser privileges."""
    target = str(target_role or "")
    if target not in Giocatore.ROLE_RANKS:
        raise ApiError("player.role_invalid", "Il livello di accesso richiesto non è valido.", "targetRole")

    giocatore = Giocatore.objects.select_for_update().get(pk=giocatore.pk)
    current_role = effective_role(user, giocatore)
    if target == current_role:
        return giocatore

    if user.is_staff or user.is_superuser:
        giocatore.role = target
        giocatore.save(update_fields=["role", "updated_at"])
        return giocatore

    if role_rank(target) < role_rank(current_role):
        giocatore.role = target
        giocatore.save(update_fields=["role", "updated_at"])
        return giocatore

    return redeem_role_code(user, giocatore, target, submitted_code)
