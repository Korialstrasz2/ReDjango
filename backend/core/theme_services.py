import re
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from backend.media_library.models import UploadedImage

from .api import ApiError
from .models import Giocatore, Theme, ThemeBackground
from .security import effective_role, has_minimum_role
from .theme_selectors import (
    THEME_BLANKABLE_COLOR_FIELDS,
    THEME_COLOR_FIELD_NAMES,
    serialize_managed_theme,
    themes_management_payload,
)
from .theme_surfaces import THEME_SURFACE_KEY_SET


COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
BACKGROUND_POSITION_RE = re.compile(r"^[a-z0-9%.\s-]{1,80}$", re.IGNORECASE)


def require_theme_admin(user, giocatore: Giocatore) -> None:
    if not has_minimum_role(effective_role(user, giocatore), Giocatore.ROLE_ADMIN):
        raise ApiError(
            "management.themes.forbidden",
            "Solo gli amministratori possono gestire i temi.",
            status=403,
        )


def _get_theme(theme_id) -> Theme:
    try:
        return Theme.objects.get(pk=int(theme_id), archived_at__isnull=True)
    except (Theme.DoesNotExist, TypeError, ValueError) as exc:
        raise ApiError("management.themes.not_found", "Il tema richiesto non esiste.", "themeId", 404) from exc


def _clean_color(field_name: str, raw_value) -> str:
    value = str(raw_value or "").strip().lower()
    if not value:
        if field_name in THEME_BLANKABLE_COLOR_FIELDS:
            return ""
        raise ApiError(
            "management.themes.color_required",
            "Questo colore è obbligatorio: solo principale, dorato e menu laterale possono restare vuoti.",
            field_name,
        )
    if not COLOR_RE.fullmatch(value):
        raise ApiError(
            "management.themes.color_invalid",
            "Usa un colore esadecimale nel formato #RRGGBB.",
            field_name,
        )
    return value


def _decimal_opacity(raw_value) -> Decimal:
    """DecimalField(decimal_places=2) rifiuta i float binari: normalizza sempre a due cifre."""
    return Decimal(f"{round(float(raw_value), 2):.2f}")


def _clean_opacity(field_name: str, raw_value, current) -> Decimal:
    if raw_value is None:
        return _decimal_opacity(current)
    try:
        value = _decimal_opacity(raw_value)
    except (TypeError, ValueError) as exc:
        raise ApiError("management.themes.opacity_invalid", "L'opacità deve essere un numero.", field_name) from exc
    if not 0 <= value <= 1:
        raise ApiError("management.themes.opacity_range", "L'opacità deve essere compresa tra 0 e 1.", field_name)
    return value


def _clean_background_image(surface_key: str, raw_value) -> UploadedImage | None:
    if raw_value in (None, "", 0):
        return None
    try:
        return UploadedImage.objects.get(pk=int(raw_value), archived_at__isnull=True)
    except (UploadedImage.DoesNotExist, TypeError, ValueError) as exc:
        raise ApiError(
            "management.themes.background_not_found",
            "L'immagine scelta non esiste più nell'Archivio.",
            surface_key,
            404,
        ) from exc


def _clean_backgrounds(payload: dict) -> dict:
    """Le superfici toccate dal payload: chiave della superficie → immagine o None."""
    raw = payload.get("backgrounds")
    if not isinstance(raw, dict):
        return {}
    cleaned = {}
    for surface_key, raw_value in raw.items():
        if surface_key not in THEME_SURFACE_KEY_SET:
            raise ApiError(
                "management.themes.surface_unknown",
                "Questa superficie non fa parte dell'elenco dei temi.",
                surface_key,
            )
        cleaned[surface_key] = _clean_background_image(surface_key, raw_value)
    return cleaned


def _write_backgrounds(theme: Theme, cleaned: dict) -> None:
    """Scrive una riga per superficie. Nessuna superficie eredita da un'altra:
    togliere l'immagine lascia semplicemente quella schermata senza sfondo."""
    emptied = [surface_key for surface_key, image in cleaned.items() if image is None]
    if emptied:
        ThemeBackground.objects.filter(theme=theme, surface_key__in=emptied).delete()
    for surface_key, image in cleaned.items():
        if image is not None:
            ThemeBackground.objects.update_or_create(
                theme=theme,
                surface_key=surface_key,
                defaults={"image": image},
            )


def _unique_slug(name: str, exclude_pk=None) -> str:
    base = slugify(name)[:70] or "tema"
    candidate = base
    index = 2
    while Theme.objects.filter(slug=candidate).exclude(pk=exclude_pk).exists():
        candidate = f"{base}-{index}"[:80]
        index += 1
    return candidate


def _apply_payload(theme: Theme, payload: dict, *, partial: bool) -> Theme:
    if "name" in payload or not partial:
        name = str(payload.get("name") or "").strip()
        if not name:
            raise ApiError("management.themes.name_required", "Inserisci il nome del tema.", "name")
        theme.name = name[:120]
    if "description" in payload:
        theme.description = str(payload.get("description") or "").strip()
    if "order" in payload:
        try:
            theme.order = max(0, int(payload.get("order") or 0))
        except (TypeError, ValueError) as exc:
            raise ApiError("management.themes.order_invalid", "L'ordine deve essere un numero intero.", "order") from exc

    colors = payload.get("colors")
    if isinstance(colors, dict):
        for field_name in THEME_COLOR_FIELD_NAMES:
            if field_name in colors:
                setattr(theme, field_name, _clean_color(field_name, colors[field_name]))

    theme.overlay_opacity = _clean_opacity("overlayOpacity", payload.get("overlayOpacity"), theme.overlay_opacity)
    theme.panel_opacity = _clean_opacity("panelOpacity", payload.get("panelOpacity"), theme.panel_opacity)
    if "backgroundPosition" in payload:
        position = str(payload["backgroundPosition"] or "").strip() or "center center"
        if not BACKGROUND_POSITION_RE.fullmatch(position):
            raise ApiError(
                "management.themes.position_invalid",
                "Usa una posizione CSS semplice, per esempio «center center» oppure «50% 20%».",
                "backgroundPosition",
            )
        theme.background_position = position
    if "backgroundBlur" in payload:
        try:
            blur = int(payload["backgroundBlur"])
        except (TypeError, ValueError) as exc:
            raise ApiError("management.themes.blur_invalid", "La sfocatura deve essere un numero intero.", "backgroundBlur") from exc
        if not 0 <= blur <= 20:
            raise ApiError("management.themes.blur_range", "La sfocatura può andare da 0 a 20 pixel.", "backgroundBlur")
        theme.background_blur = blur

    # Gli sfondi sono righe figlie: si scrivono dopo il salvataggio, quando il
    # tema ha una chiave primaria (vedi _write_backgrounds).

    if "isActive" in payload:
        is_active = bool(payload["isActive"])
        if not is_active and theme.is_default:
            raise ApiError(
                "management.themes.default_must_stay_active",
                "Il tema predefinito deve restare attivo: designane un altro come predefinito prima di disattivarlo.",
                "isActive",
            )
        theme.is_active = is_active
    return theme


@transaction.atomic
def save_theme(user, giocatore: Giocatore, theme_id, payload: dict) -> dict:
    require_theme_admin(user, giocatore)
    if not isinstance(payload, dict):
        raise ApiError("management.themes.invalid_payload", "I dati del tema non sono validi.", "theme")
    theme = _get_theme(theme_id)
    backgrounds = _clean_backgrounds(payload)
    _apply_payload(theme, payload, partial=True)
    theme.full_clean(exclude=["slug"])
    theme.save()
    _write_backgrounds(theme, backgrounds)
    theme.refresh_from_db()
    return {"theme": serialize_managed_theme(theme), **themes_management_payload()}


@transaction.atomic
def create_theme(user, giocatore: Giocatore, payload: dict) -> dict:
    require_theme_admin(user, giocatore)
    if not isinstance(payload, dict):
        raise ApiError("management.themes.invalid_payload", "I dati del tema non sono validi.", "theme")

    source_id = payload.get("duplicateOfId")
    if source_id:
        source = _get_theme(source_id)
        theme = Theme.objects.get(pk=source.pk)
        theme.pk = None
        theme._state.adding = True
        theme.is_default = False
        theme.metadata = {"seed_kind": "theme_custom", "duplicated_from": source.slug}
        payload = {"name": payload.get("name") or f"{source.name} (copia)", **payload}
    else:
        theme = Theme(metadata={"seed_kind": "theme_custom"})
        theme.is_default = False

    _apply_payload(theme, payload, partial=False)
    theme.is_active = bool(payload.get("isActive", True))
    theme.slug = _unique_slug(theme.name)
    if not theme.order:
        highest = Theme.objects.order_by("-order").values_list("order", flat=True).first() or 0
        theme.order = highest + 10
    theme.full_clean()
    theme.save()
    return {"theme": serialize_managed_theme(theme), **themes_management_payload()}


@transaction.atomic
def set_default_theme(user, giocatore: Giocatore, theme_id) -> dict:
    require_theme_admin(user, giocatore)
    theme = _get_theme(theme_id)
    if not theme.is_active:
        raise ApiError(
            "management.themes.default_must_be_active",
            "Attiva il tema prima di renderlo predefinito.",
            "themeId",
        )
    # Il vincolo one_default_theme ammette una sola riga con is_default=True.
    Theme.objects.filter(is_default=True).exclude(pk=theme.pk).update(is_default=False)
    theme.is_default = True
    theme.save(update_fields=["is_default", "updated_at"])
    return {"theme": serialize_managed_theme(theme), **themes_management_payload()}


@transaction.atomic
def archive_theme(user, giocatore: Giocatore, theme_id) -> dict:
    require_theme_admin(user, giocatore)
    theme = _get_theme(theme_id)
    if theme.is_default:
        raise ApiError(
            "management.themes.default_not_archivable",
            "Non puoi archiviare il tema predefinito: designane prima un altro.",
            "themeId",
        )
    if (theme.metadata or {}).get("seed_kind") == "theme":
        raise ApiError(
            "management.themes.seeded_not_archivable",
            "I temi di serie non si archiviano: puoi disattivarli per nasconderli dalle Impostazioni.",
            "themeId",
        )
    theme.archived_at = timezone.now()
    theme.is_active = False
    theme.save(update_fields=["archived_at", "is_active", "updated_at"])
    return themes_management_payload()
