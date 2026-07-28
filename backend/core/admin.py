from django import forms
from django.contrib import admin

from .models import (
    CampaignLoreEntry,
    CampaignLoreRelation,
    CharacterAssignmentRequest,
    Competenze,
    Curiosita,
    DatiCampagna,
    Effetto,
    EffettiEMalattie,
    EffettiSkill,
    FamigliaSkill,
    Giocatore,
    GlobalModifiers,
    GruppoFamiglieSkill,
    Guida,
    HallOfFameCharacter,
    Messaggio,
    Negozio,
    NomiRazzeInfo,
    Oggetto,
    OpzioneTipoOggetto,
    ReagenteAlchemico,
    Skill,
    SkillMigrationReview,
    SpellDefinition,
    SettingDefinition,
    SettingOverride,
    Theme,
    TimelineEvent,
    TipoArma,
    Unit,
)
from .defaults import (
    QUICK_STAT_ADJUSTMENT_CONFIG_KEY,
    QUICK_STAT_ADJUSTMENT_DEFAULTS,
    QUICK_STAT_ADJUSTMENT_TARGET_CHOICES,
    SKILL_PRICING_CONFIG_KEY,
    SKILL_PRICING_DEFAULTS,
)
from .settings_services import approve_character_assignment, reject_character_assignment
from backend.market.config import (
    GENERATOR_RULES_KEY,
    LOCATION_KEY,
    SHOP_TYPES_KEY,
    resolve_location,
    validate_generator_rules,
    validate_market_locations,
    validate_shop_types,
)
from backend.market.services import regenerate_shop


admin.site.site_header = "Amministrazione ReDjango"
admin.site.site_title = "Amministrazione ReDjango"
admin.site.index_title = "Configurazione del mondo di gioco"


@admin.action(description="Approva e assegna i personaggi selezionati")
def approve_assignment_requests(_modeladmin, _request, queryset):
    for assignment in queryset.select_related("giocatore", "personaggio"):
        approve_character_assignment(assignment)


@admin.action(description="Rifiuta le richieste selezionate")
def reject_assignment_requests(_modeladmin, _request, queryset):
    for assignment in queryset:
        reject_character_assignment(assignment)


@admin.register(CharacterAssignmentRequest)
class CharacterAssignmentRequestAdmin(admin.ModelAdmin):
    list_display = ("giocatore", "personaggio", "status", "created_at", "reviewed_at")
    list_filter = ("status", "created_at", "reviewed_at")
    search_fields = ("giocatore__nome", "giocatore__display_name", "personaggio__nome", "message")
    readonly_fields = ("created_at", "updated_at", "reviewed_at")
    actions = (approve_assignment_requests, reject_assignment_requests)


class V2Admin(admin.ModelAdmin):
    readonly_fields = ("created_at", "updated_at")
    list_filter = ("archived_at",)

    def get_list_display(self, request):
        field_names = {field.name for field in self.model._meta.fields}
        preferred = (
            "nome",
            "name",
            "title",
            "categoria",
            "tipo",
            "role",
            "attiva",
            "updated_at",
        )
        display = tuple(field for field in preferred if field in field_names)
        return display or ("id",)

    def get_search_fields(self, request):
        field_names = {field.name for field in self.model._meta.fields}
        preferred = (
            "nome",
            "name",
            "title",
            "descrizione",
            "description",
            "contenuto",
            "content",
            "slug",
        )
        return tuple(field for field in preferred if field in field_names)


class OggettoAdminForm(forms.ModelForm):
    tipo_1 = forms.ChoiceField(label="Tipo 1", required=False)
    tipo_2 = forms.ChoiceField(label="Tipo 2", required=False)
    tipo_3 = forms.ChoiceField(label="Tipo 3", required=False)
    tipo_4 = forms.ChoiceField(label="Tipo 4", required=False)

    class Meta:
        model = Oggetto
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for posizione in range(1, 5):
            field_name = f"tipo_{posizione}"
            current = str(getattr(self.instance, field_name, "") or "")
            options = list(
                OpzioneTipoOggetto.objects.filter(posizione=posizione, attiva=True).order_by(
                    "ordine", "etichetta", "valore"
                )
            )
            choices = [("", "---------"), *[(option.valore, option.label) for option in options]]
            if current and current not in {value for value, _label in choices}:
                choices.append((current, f"{current} (non attivo o non configurato)"))
            self.fields[field_name].choices = choices


@admin.register(Oggetto)
class OggettoAdmin(V2Admin):
    form = OggettoAdminForm
    list_display = ("nome", "tipo_1", "tipo_2", "rarita", "speciale", "archiviato", "updated_at")
    list_filter = ("tipo_1", "tipo_2", "rarita", "speciale", "archiviato", "archived_at")
    search_fields = ("nome", "descrizione", "tipo_1", "tipo_2", "tipo_3", "tipo_4")
    fieldsets = (
        (
            "Identità",
            {
                "fields": (
                    "nome", "modello", "temporaneo", "archiviato", "numero_ordine",
                    "icona", "descrizione", "media",
                )
            },
        ),
        ("Classificazione", {"fields": ("tipo_1", "tipo_2", "tipo_3", "tipo_4", "tipo_arma")}),
        (
            "Economia e bottino",
            {"fields": ("valore", "peso", "rarita", "lv_loot", "regione_loot", "peso_regione")},
        ),
        (
            "Effetti Elder conservati",
            {
                "description": (
                    "Testo originale predisposto per l'importazione. Questi campi non modificano "
                    "automaticamente i calcoli finché non vengono convertiti negli effetti strutturati."
                ),
                "fields": (
                    "effetto_1", "effetto_2", "effetto_3", "effetto_4",
                    "effetto_5", "effetto_6", "effetto_7", "effetto_8",
                ),
            },
        ),
        (
            "Regole strutturate",
            {
                "fields": (
                    "pa_per_attacco", "speciale", "effects", "weapon_profile", "alchemy_profile", "crafting_profile",
                )
            },
        ),
        ("Note", {"fields": ("notes",)}),
        (
            "Informazioni di sistema",
            {"fields": ("created_at", "updated_at", "archived_at", "metadata"), "classes": ("collapse",)},
        ),
    )


@admin.register(OpzioneTipoOggetto)
class OpzioneTipoOggettoAdmin(V2Admin):
    list_display = ("posizione", "valore", "etichetta", "attiva", "ordine", "updated_at")
    list_editable = ("etichetta", "attiva", "ordine")
    list_filter = ("posizione", "attiva", "archived_at")
    search_fields = ("valore", "etichetta")
    ordering = ("posizione", "ordine", "etichetta", "valore")


class GlobalModifiersAdminForm(forms.ModelForm):
    fatigue_percent_per_point = forms.DecimalField(
        label="Malus stanchezza per punto (%)",
        min_value=0,
        max_value=100,
        decimal_places=2,
        help_text="Ogni punto di Stanchezza riduce di questa percentuale le statistiche selezionate.",
    )
    fatigue_fixed_per_point = forms.DecimalField(
        label="Malus fisso per Stanchezza",
        min_value=0,
        decimal_places=2,
        help_text="Valore fisso sottratto dopo la percentuale per ogni punto di Stanchezza.",
    )
    general_modifier_percent_per_point = forms.DecimalField(
        label="Effetto modificatore generale per punto (%)",
        min_value=0,
        max_value=100,
        decimal_places=2,
        help_text="Un valore positivo aumenta, uno negativo riduce le statistiche selezionate.",
    )
    general_modifier_fixed_per_point = forms.DecimalField(
        label="Bonus fisso per Modificatore generale",
        min_value=0,
        decimal_places=2,
        help_text="Valore fisso aggiunto dopo la percentuale per ogni punto di Modificatore generale.",
    )
    quick_stat_targets = forms.MultipleChoiceField(
        label="Statistiche influenzate",
        choices=QUICK_STAT_ADJUSTMENT_TARGET_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )
    skill_price_modifier_base = forms.DecimalField(
        label="Divisore base del rincaro Skill",
        min_value=0.01,
        decimal_places=3,
        help_text="Valore iniziale del divisore: il costo base della Skill viene sommato a questo numero.",
    )
    skill_price_modifier_max = forms.DecimalField(
        label="Divisore massimo del rincaro Skill",
        min_value=0.01,
        decimal_places=3,
        help_text="Limite superiore del divisore usato per contenere la crescita del prezzo.",
    )
    skill_price_scaling_factor = forms.DecimalField(
        label="Fattore livello per il prezzo Skill",
        min_value=0,
        decimal_places=4,
        help_text="Quanto il livello del personaggio contribuisce al rincaro.",
    )
    skill_price_scaling_divisor = forms.DecimalField(
        label="Divisore livello per il prezzo Skill",
        min_value=0.01,
        decimal_places=4,
        help_text="Riduce o amplifica l'incidenza del livello sul prezzo finale.",
    )
    skill_price_spent_xp_discount_cap = forms.DecimalField(
        label="PE spesi per azzerare il rincaro",
        min_value=0.01,
        decimal_places=2,
        help_text="Raggiunta questa spesa nel colore pertinente, resta soltanto il costo base.",
    )

    class Meta:
        model = GlobalModifiers
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        value_string = self.instance.value_string if isinstance(self.instance.value_string, dict) else {}
        configured = value_string.get(QUICK_STAT_ADJUSTMENT_CONFIG_KEY, {})
        if not isinstance(configured, dict):
            configured = {}
        self.fields["fatigue_percent_per_point"].initial = configured.get(
            "fatigue_percent_per_point",
            QUICK_STAT_ADJUSTMENT_DEFAULTS["fatigue_percent_per_point"],
        )
        self.fields["fatigue_fixed_per_point"].initial = configured.get(
            "fatigue_fixed_per_point",
            QUICK_STAT_ADJUSTMENT_DEFAULTS["fatigue_fixed_per_point"],
        )
        self.fields["general_modifier_percent_per_point"].initial = configured.get(
            "general_modifier_percent_per_point",
            QUICK_STAT_ADJUSTMENT_DEFAULTS["general_modifier_percent_per_point"],
        )
        self.fields["general_modifier_fixed_per_point"].initial = configured.get(
            "general_modifier_fixed_per_point",
            QUICK_STAT_ADJUSTMENT_DEFAULTS["general_modifier_fixed_per_point"],
        )
        self.fields["quick_stat_targets"].initial = configured.get(
            "targets",
            QUICK_STAT_ADJUSTMENT_DEFAULTS["targets"],
        )
        pricing = value_string.get(SKILL_PRICING_CONFIG_KEY, {})
        if not isinstance(pricing, dict):
            pricing = {}
        for field_name, config_key in (
            ("skill_price_modifier_base", "modifier_base"),
            ("skill_price_modifier_max", "modifier_max"),
            ("skill_price_scaling_factor", "scaling_factor"),
            ("skill_price_scaling_divisor", "scaling_divisor"),
            ("skill_price_spent_xp_discount_cap", "spent_xp_discount_cap"),
        ):
            self.fields[field_name].initial = pricing.get(config_key, SKILL_PRICING_DEFAULTS[config_key])

    def clean(self):
        cleaned_data = super().clean()
        value_string = cleaned_data.get("value_string")
        value_string = dict(value_string) if isinstance(value_string, dict) else {}
        value_string[QUICK_STAT_ADJUSTMENT_CONFIG_KEY] = {
            "fatigue_percent_per_point": float(cleaned_data.get("fatigue_percent_per_point") or 0),
            "fatigue_fixed_per_point": float(cleaned_data.get("fatigue_fixed_per_point") or 0),
            "general_modifier_percent_per_point": float(
                cleaned_data.get("general_modifier_percent_per_point") or 0
            ),
            "general_modifier_fixed_per_point": float(
                cleaned_data.get("general_modifier_fixed_per_point") or 0
            ),
            "targets": cleaned_data.get("quick_stat_targets") or [],
        }
        modifier_base = cleaned_data.get("skill_price_modifier_base")
        modifier_max = cleaned_data.get("skill_price_modifier_max")
        if modifier_base is not None and modifier_max is not None and modifier_max < modifier_base:
            self.add_error(
                "skill_price_modifier_max",
                "Il divisore massimo non può essere inferiore al divisore base.",
            )
        value_string[SKILL_PRICING_CONFIG_KEY] = {
            "modifier_base": float(modifier_base or 0),
            "modifier_max": float(modifier_max or 0),
            "scaling_factor": float(cleaned_data.get("skill_price_scaling_factor") or 0),
            "scaling_divisor": float(cleaned_data.get("skill_price_scaling_divisor") or 0),
            "spent_xp_discount_cap": float(
                cleaned_data.get("skill_price_spent_xp_discount_cap") or 0
            ),
        }
        cleaned_data["value_string"] = value_string
        return cleaned_data


@admin.register(GlobalModifiers)
class GlobalModifiersAdmin(V2Admin):
    form = GlobalModifiersAdminForm
    list_display = ("name", "updated_at")
    search_fields = ("name",)
    fieldsets = (
        ("Profilo", {"fields": ("name",)}),
        (
            "Influenza di Stanchezza e Modificatore generale",
            {
                "description": (
                    "Formula applicata: 100% - Stanchezza × malus + Modificatore generale × effetto. "
                    "Le modifiche diventano visibili nella scheda al successivo uso dei pulsanti +/- ."
                ),
                "fields": (
                    "fatigue_percent_per_point",
                    "fatigue_fixed_per_point",
                    "general_modifier_percent_per_point",
                    "general_modifier_fixed_per_point",
                    "quick_stat_targets",
                ),
            },
        ),
        (
            "Prezzo dinamico delle Skill",
            {
                "description": (
                    "Il catalogo mostra un prezzo calcolato dal costo base, dal livello del personaggio "
                    "e dai PE già spesi nel colore pertinente. Nell'editor Skill il costo resta sempre quello base."
                ),
                "fields": (
                    "skill_price_modifier_base",
                    "skill_price_modifier_max",
                    "skill_price_scaling_factor",
                    "skill_price_scaling_divisor",
                    "skill_price_spent_xp_discount_cap",
                ),
            },
        ),
        (
            "Configurazione avanzata",
            {
                "fields": ("value_float", "value_string", "rule_notes"),
                "classes": ("collapse",),
            },
        ),
        ("Informazioni di sistema", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )


admin.site.register(
    [
        CampaignLoreEntry,
        CampaignLoreRelation,
        Competenze,
        Curiosita,
        DatiCampagna,
        Effetto,
        EffettiEMalattie,
        EffettiSkill,
        FamigliaSkill,
        GruppoFamiglieSkill,
        Giocatore,
        Guida,
        HallOfFameCharacter,
        Messaggio,
        NomiRazzeInfo,
        ReagenteAlchemico,
        Skill,
        SkillMigrationReview,
        SpellDefinition,
        TipoArma,
        Unit,
    ],
    V2Admin,
)


@admin.register(TimelineEvent)
class TimelineEventAdmin(V2Admin):
    """Administrative fallback for the Lore > Timeline content type."""

    list_display = (
        "nome",
        "data_evento",
        "ordine_cronologico",
        "campagna",
        "immagine",
        "archived_at",
        "updated_at",
    )
    list_filter = ("campagna", "archived_at")
    search_fields = ("nome", "data_evento", "descrizione")
    ordering = ("ordine_cronologico", "created_at", "id")
    autocomplete_fields = ("immagine",)


class NegozioAdminForm(forms.ModelForm):
    location = forms.ChoiceField(label="Località", required=False)

    class Meta:
        model = Negozio
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            from backend.market.config import get_market_locations, get_shop_type_definitions
            choices = [("", "---------")]
            for region in get_market_locations()["regions"]:
                choices.extend((f"{region['key']}/{place['key']}", f"{region['label']} — {place['label']}") for place in region["places"])
            self.fields["location"].choices = choices
            self.fields["location"].initial = self.instance.location_key
            category_choices = [(item["key"], item["label"]) for item in get_shop_type_definitions()["types"]]
            self.fields["categoria"].widget = forms.Select(choices=[("", "---------"), *category_choices])
        except ValidationError:
            pass

    def clean(self):
        cleaned = super().clean()
        location_key = cleaned.get("location") or self.instance.location_key
        if location_key:
            try:
                location = resolve_location(location_key)
            except ValidationError as exc:
                self.add_error("location", exc.messages[0])
            else:
                cleaned["location_key"] = location["key"]
                cleaned["regione_nome"] = location["regionLabel"]
                cleaned["citta_nome"] = location["placeLabel"]
        return cleaned


@admin.action(description="Rigenera lo stock dei negozi selezionati")
def regenerate_stock_action(modeladmin, request, queryset):
    from backend.core.security import get_or_create_giocatore_for_user
    giocatore = get_or_create_giocatore_for_user(request.user)
    for shop in queryset:
        regenerate_shop(request.user, giocatore, shop.id)


@admin.register(Negozio)
class NegozioAdmin(V2Admin):
    form = NegozioAdminForm
    list_display = ("nome", "location_display", "categoria", "livello", "proprietario", "stock_count", "last_restocked_at", "archived_at")
    list_filter = ("categoria", "livello", "archived_at")
    search_fields = ("nome", "proprietario", "regione_nome", "citta_nome", "location_key")
    readonly_fields = ("stock_revision", "last_restocked_at", "created_at", "updated_at")
    actions = (regenerate_stock_action,)
    save_as = True
    fieldsets = (("Negozio", {"fields": ("nome", "proprietario", "location", "categoria", "livello", "descrizione", "immagine_sfondo", "generation_seed", "generation_profile_key")}), ("Stock", {"fields": ("stock_revision", "last_restocked_at", "lista_oggetti"), "classes": ("collapse",)}), ("Archivio legacy", {"fields": ("regione_nome", "citta_nome", "regione_descrizione", "citta_descrizione", "regione_immagine", "citta_immagine", "metadata", "archived_at"), "classes": ("collapse",)}), ("Sistema", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}))

    @admin.display(description="Località")
    def location_display(self, obj): return obj.location_key or f"{obj.regione_nome} — {obj.citta_nome}"

    @admin.display(description="Pezzi")
    def stock_count(self, obj):
        stock = obj.lista_oggetti if isinstance(obj.lista_oggetti, dict) else {}
        return sum(int(entry.get("quantity", 0) or 0) for entry in stock.get("entries", []) if isinstance(entry, dict))


class SettingDefinitionAdminForm(forms.ModelForm):
    class Meta:
        model = SettingDefinition
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()
        validator = {LOCATION_KEY: validate_market_locations, SHOP_TYPES_KEY: validate_shop_types, GENERATOR_RULES_KEY: validate_generator_rules}.get(cleaned.get("key"))
        if validator:
            for field in ("default_value", "value"):
                value = cleaned.get(field)
                if value is not None:
                    try: cleaned[field] = validator(value)
                    except ValidationError as exc: self.add_error(field, exc.messages[0])
        return cleaned


@admin.register(SettingDefinition)
class SettingDefinitionAdmin(admin.ModelAdmin):
    form = SettingDefinitionAdminForm
    list_display = (
        "key",
        "label",
        "category",
        "minimum_role",
        "value_type",
        "user_customizable",
        "master_customizable",
        "active",
        "updated_at",
    )
    list_filter = ("minimum_role", "category", "value_type", "active")
    search_fields = ("key", "label", "description")
    readonly_fields = ("created_at", "updated_at")


@admin.register(SettingOverride)
class SettingOverrideAdmin(admin.ModelAdmin):
    list_display = ("setting", "giocatore", "value", "updated_at")
    list_filter = ("setting__category", "setting__minimum_role")
    search_fields = ("setting__key", "giocatore__nome", "giocatore__display_name")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Theme)
class ThemeAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "is_default", "order", "updated_at")
    list_editable = ("is_active", "order")
    list_filter = ("is_active", "is_default")
    search_fields = ("name", "slug", "description")
    readonly_fields = ("created_at", "updated_at")

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name.endswith("_color"):
            kwargs["widget"] = forms.TextInput(attrs={"type": "color"})
        return super().formfield_for_dbfield(db_field, request, **kwargs)
    fieldsets = (
        (
            "Identità",
            {
                "fields": (
                    "name",
                    "slug",
                    "description",
                    "is_active",
                    "is_default",
                    "order",
                )
            },
        ),
        (
            "Colori",
            {
                "fields": (
                    "background_color",
                    "panel_color",
                    "panel_strong_color",
                    "text_color",
                    "muted_text_color",
                    "line_color",
                    "accent_color",
                    "accent_strong_color",
                    "gold_color",
                    "sidebar_color",
                    "health_color",
                    "mana_color",
                    "energy_color",
                    "power_color",
                    "valid_slot_color",
                    "invalid_slot_color",
                )
            },
        ),
        (
            "Trasparenze e disposizione",
            {
                "fields": (
                    "overlay_opacity",
                    "panel_opacity",
                    "background_position",
                    "background_blur",
                )
            },
        ),
        (
            "Sfondi delle schermate",
            {
                "description": (
                    "Le immagini provengono dall'Archivio immagini. È possibile riusarle tra più schermate "
                    "oppure assegnarne una diversa a ogni area."
                ),
                "fields": (
                    "dashboard_background",
                    "characters_background",
                    "personaggio_background",
                    "media_background",
                    "guide_background",
                    "settings_background",
                    "dice_background",
                    "journal_background",
                    "lore_background",
                    "market_background",
                ),
            },
        ),
        ("Informazioni di sistema", {"fields": ("created_at", "updated_at", "metadata"), "classes": ("collapse",)}),
    )
