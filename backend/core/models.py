from django.conf import settings as django_settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models

from .theme_surfaces import THEME_SURFACE_KEY_SET


V2_SCHEMA_VERSION = "1.2"

HEX_COLOR_VALIDATOR = RegexValidator(
    regex=r"^#[0-9a-fA-F]{6}$",
    message="Inserisci un colore esadecimale nel formato #RRGGBB.",
)


class V2Model(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        abstract = True


class ReagenteAlchemico(V2Model):
    COLOR_RED = "rosso"
    COLOR_GREEN = "verde"
    COLOR_BLUE = "blu"
    COLOR_CHOICES = [
        (COLOR_RED, "Rosso"),
        (COLOR_GREEN, "Verde"),
        (COLOR_BLUE, "Blu"),
    ]

    nome = models.CharField(max_length=160, unique=True)
    colore = models.CharField(max_length=12, choices=COLOR_CHOICES)
    livello = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(4)],
    )
    attivo = models.BooleanField(default=True)
    ordine = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["ordine", "livello", "nome"]
        verbose_name = "reagente alchemico"
        verbose_name_plural = "reagenti alchemici"
        indexes = [models.Index(fields=["attivo", "colore", "livello"])]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(livello__gte=1, livello__lte=4),
                name="alchemy_reagent_level_1_to_4",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.nome} · {self.get_colore_display()} L{self.livello}"


class Giocatore(V2Model):
    ROLE_USER = "user"
    ROLE_MASTER = "master"
    ROLE_ADMIN = "admin"
    ROLE_CHOICES = [
        (ROLE_USER, "Giocatore"),
        (ROLE_MASTER, "Master"),
        (ROLE_ADMIN, "Amministratore"),
    ]
    ROLE_RANKS = {ROLE_USER: 10, ROLE_MASTER: 20, ROLE_ADMIN: 30}

    user = models.OneToOneField(
        django_settings.AUTH_USER_MODEL,
        verbose_name="account Django",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="redjango_giocatore",
    )
    nome = models.CharField(max_length=120, unique=True)
    display_name = models.CharField(max_length=120, blank=True)
    password_hash = models.CharField(max_length=255, blank=True)
    role = models.CharField("livello di accesso", max_length=20, choices=ROLE_CHOICES, default=ROLE_USER)
    active_character = models.ForeignKey(
        "characters.Personaggio",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="active_for_giocatori",
    )
    active_campaign = models.ForeignKey(
        "DatiCampagna",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="active_for_giocatori",
    )
    character_ids = models.JSONField(default=list, blank=True)
    dice_profile = models.CharField(max_length=120, blank=True)
    settings = models.JSONField(default=dict, blank=True)
    notes = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["nome"]
        indexes = [models.Index(fields=["role", "nome"])]

    def __str__(self) -> str:
        return self.display_name or self.nome

    def has_role(self, required_role: str) -> bool:
        return self.ROLE_RANKS.get(self.role, 0) >= self.ROLE_RANKS.get(required_role, 0)


class LoginThrottle(models.Model):
    """Cross-process login failure counter without storing usernames or IPs."""

    key = models.CharField(max_length=64, primary_key=True)
    failures = models.PositiveSmallIntegerField(default=0)
    window_started_at = models.DateTimeField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "limite tentativi di accesso"
        verbose_name_plural = "limiti tentativi di accesso"
        indexes = [
            models.Index(
                fields=["updated_at"],
                name="core_logint_updated_744393_idx",
            )
        ]


class CharacterAssignmentRequest(V2Model):
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [
        (STATUS_PENDING, "In attesa"),
        (STATUS_APPROVED, "Approvata"),
        (STATUS_REJECTED, "Rifiutata"),
    ]

    giocatore = models.ForeignKey(
        Giocatore,
        verbose_name="giocatore",
        on_delete=models.CASCADE,
        related_name="character_assignment_requests",
    )
    personaggio = models.ForeignKey(
        "characters.Personaggio",
        verbose_name="personaggio richiesto",
        on_delete=models.CASCADE,
        related_name="assignment_requests",
    )
    status = models.CharField("stato", max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    message = models.TextField("messaggio del giocatore", blank=True)
    admin_note = models.TextField("nota amministrativa", blank=True)
    reviewed_at = models.DateTimeField("esaminata il", null=True, blank=True)

    class Meta:
        ordering = ["status", "-created_at"]
        verbose_name = "richiesta di assegnazione personaggio"
        verbose_name_plural = "richieste di assegnazione personaggi"
        constraints = [
            models.UniqueConstraint(
                fields=["giocatore", "personaggio"],
                name="unique_character_request_per_player",
            )
        ]
        indexes = [models.Index(fields=["status", "created_at"])]

    def __str__(self) -> str:
        return f"{self.giocatore} → {self.personaggio}"


class SettingDefinition(V2Model):
    TYPE_BOOL = "bool"
    TYPE_INT = "int"
    TYPE_STRING = "string"
    TYPE_COLOR = "color"
    TYPE_SELECT = "select"
    TYPE_JSON = "json"
    VALUE_TYPE_CHOICES = [
        (TYPE_BOOL, "Sì/No"),
        (TYPE_INT, "Numero intero"),
        (TYPE_STRING, "Testo"),
        (TYPE_COLOR, "Colore"),
        (TYPE_SELECT, "Scelta"),
        (TYPE_JSON, "JSON"),
    ]

    key = models.CharField("chiave", max_length=160, unique=True)
    label = models.CharField("etichetta", max_length=180)
    category = models.CharField("categoria", max_length=80)
    description = models.TextField("descrizione", blank=True)
    minimum_role = models.CharField(
        "livello minimo",
        max_length=20,
        choices=Giocatore.ROLE_CHOICES,
        default=Giocatore.ROLE_USER,
    )
    value_type = models.CharField(
        "tipo di valore",
        max_length=20,
        choices=VALUE_TYPE_CHOICES,
        default=TYPE_STRING,
    )
    default_value = models.JSONField("valore predefinito", default=dict, blank=True)
    value = models.JSONField("valore globale", null=True, blank=True)
    choices = models.JSONField("scelte disponibili", default=list, blank=True)
    user_customizable = models.BooleanField("modificabile dal giocatore", default=False)
    master_customizable = models.BooleanField("modificabile dal master", default=False)
    ui_token = models.CharField("token dell'interfaccia", max_length=80, blank=True)
    active = models.BooleanField("attiva", default=True)
    order = models.PositiveIntegerField("ordine", default=0)

    class Meta:
        ordering = ["category", "order", "key"]
        verbose_name = "definizione di impostazione"
        verbose_name_plural = "definizioni delle impostazioni"
        indexes = [
            models.Index(
                fields=["category", "minimum_role", "order"],
                name="core_settin_categor_f4cfd9_idx",
            )
        ]

    def __str__(self) -> str:
        return self.label

    @property
    def base_value(self):
        return self.default_value if self.value is None else self.value


class SettingOverride(V2Model):
    setting = models.ForeignKey(
        SettingDefinition,
        verbose_name="impostazione",
        on_delete=models.CASCADE,
        related_name="overrides",
    )
    giocatore = models.ForeignKey(
        Giocatore,
        verbose_name="giocatore",
        on_delete=models.CASCADE,
        related_name="setting_overrides",
    )
    value = models.JSONField("valore personale")

    class Meta:
        ordering = ["giocatore__nome", "setting__category", "setting__order"]
        verbose_name = "preferenza personale"
        verbose_name_plural = "preferenze personali"
        constraints = [
            models.UniqueConstraint(
                fields=["setting", "giocatore"],
                name="unique_setting_override_per_giocatore",
            )
        ]
        indexes = [
            models.Index(
                fields=["giocatore", "setting"],
                name="core_settin_giocato_38af41_idx",
            )
        ]

    def __str__(self) -> str:
        return f"{self.giocatore}: {self.setting.key}"


class Theme(V2Model):
    slug = models.SlugField("identificatore", max_length=80, unique=True)
    name = models.CharField("nome", max_length=120)
    description = models.TextField("descrizione", blank=True)
    is_active = models.BooleanField("attivo", default=True)
    is_default = models.BooleanField("predefinito", default=False)
    order = models.PositiveIntegerField("ordine", default=0)

    background_color = models.CharField("colore di sfondo", max_length=7, default="#f4f2ec", validators=[HEX_COLOR_VALIDATOR])
    panel_color = models.CharField("colore dei pannelli", max_length=7, default="#ffffff", validators=[HEX_COLOR_VALIDATOR])
    panel_strong_color = models.CharField("colore dei pannelli in rilievo", max_length=7, default="#f9faf8", validators=[HEX_COLOR_VALIDATOR])
    text_color = models.CharField("colore del testo", max_length=7, default="#202521", validators=[HEX_COLOR_VALIDATOR])
    muted_text_color = models.CharField("colore del testo secondario", max_length=7, default="#6e746e", validators=[HEX_COLOR_VALIDATOR])
    line_color = models.CharField("colore dei bordi", max_length=7, default="#d8ddd3", validators=[HEX_COLOR_VALIDATOR])
    # Lasciando vuoti accent/gold/sidebar il tema eredita i colori globali di riserva
    # definiti in Impostazioni (appearance.accent_color, gold_color, sidebar_color).
    accent_color = models.CharField("colore principale", max_length=7, default="#2f6f62", blank=True, validators=[HEX_COLOR_VALIDATOR])
    accent_strong_color = models.CharField("colore principale intenso", max_length=7, default="#214f47", validators=[HEX_COLOR_VALIDATOR])
    gold_color = models.CharField("colore dorato", max_length=7, default="#af7d2f", blank=True, validators=[HEX_COLOR_VALIDATOR])
    sidebar_color = models.CharField("colore del menu laterale", max_length=7, default="#1f2a27", blank=True, validators=[HEX_COLOR_VALIDATOR])
    health_color = models.CharField("colore punti ferita", max_length=7, default="#a63d40", validators=[HEX_COLOR_VALIDATOR])
    mana_color = models.CharField("colore mana", max_length=7, default="#3f6fa9", validators=[HEX_COLOR_VALIDATOR])
    energy_color = models.CharField("colore energia", max_length=7, default="#4f8a58", validators=[HEX_COLOR_VALIDATOR])
    power_color = models.CharField("colore potere", max_length=7, default="#7653a6", validators=[HEX_COLOR_VALIDATOR])
    valid_slot_color = models.CharField("colore slot compatibile", max_length=7, default="#4f8a58", validators=[HEX_COLOR_VALIDATOR])
    invalid_slot_color = models.CharField("colore slot incompatibile", max_length=7, default="#a63d40", validators=[HEX_COLOR_VALIDATOR])
    overlay_opacity = models.DecimalField(
        "opacità del velo sugli sfondi",
        max_digits=3,
        decimal_places=2,
        default=0.72,
        help_text="Valore compreso tra 0 e 1. Più è alto, più lo sfondo risulta attenuato.",
    )
    panel_opacity = models.DecimalField(
        "opacità dei pannelli",
        max_digits=3,
        decimal_places=2,
        default=0.94,
        help_text="Valore compreso tra 0 e 1.",
    )
    background_position = models.CharField(
        "posizione degli sfondi",
        max_length=80,
        default="center center",
        help_text="Per esempio: center center, top center oppure 50% 20%.",
    )
    background_blur = models.PositiveSmallIntegerField(
        "sfocatura degli sfondi (px)",
        default=0,
        validators=[MaxValueValidator(20)],
    )

    # Gli sfondi vivono in ThemeBackground, una riga per superficie: vedi
    # core/theme_surfaces.py per l'elenco di pagine, modali e strumenti.

    class Meta:
        ordering = ["order", "name"]
        verbose_name = "tema"
        verbose_name_plural = "temi"
        constraints = [
            models.UniqueConstraint(
                fields=["is_default"],
                condition=models.Q(is_default=True),
                name="one_default_theme",
            ),
            models.CheckConstraint(
                condition=models.Q(overlay_opacity__gte=0, overlay_opacity__lte=1),
                name="theme_overlay_opacity_between_zero_and_one",
            ),
            models.CheckConstraint(
                condition=models.Q(panel_opacity__gte=0, panel_opacity__lte=1),
                name="theme_panel_opacity_between_zero_and_one",
            ),
        ]

    def clean(self):
        super().clean()
        if self.is_default and not self.is_active:
            raise ValidationError({"is_active": "Il tema predefinito deve essere attivo."})
        if self.is_default and Theme.objects.exclude(pk=self.pk).filter(is_default=True).exists():
            raise ValidationError({"is_default": "Esiste già un tema predefinito."})

    def __str__(self) -> str:
        return self.name

    def background_map(self) -> dict:
        """Immagine scelta per ogni superficie, senza ereditarietà fra superfici."""
        return {row.surface_key: row.image for row in self.backgrounds.all()}


class ThemeBackground(V2Model):
    """Lo sfondo che un tema assegna a una singola superficie.

    Una riga per coppia (tema, superficie). Le superfici non sono una colonna
    ma una chiave testuale definita in core/theme_surfaces.py, così aggiungere
    una pagina o una modale non richiede una migrazione.
    """

    theme = models.ForeignKey(
        Theme,
        verbose_name="tema",
        on_delete=models.CASCADE,
        related_name="backgrounds",
    )
    surface_key = models.CharField("superficie", max_length=64)
    image = models.ForeignKey(
        "media_library.UploadedImage",
        verbose_name="immagine",
        on_delete=models.CASCADE,
        related_name="theme_backgrounds",
    )

    class Meta:
        ordering = ["theme__order", "surface_key"]
        verbose_name = "sfondo del tema"
        verbose_name_plural = "sfondi dei temi"
        constraints = [
            models.UniqueConstraint(
                fields=["theme", "surface_key"],
                name="one_background_per_theme_surface",
            )
        ]
        indexes = [
            models.Index(fields=["theme", "surface_key"], name="core_themebg_theme_surf_idx"),
        ]

    def clean(self):
        super().clean()
        if self.surface_key not in THEME_SURFACE_KEY_SET:
            raise ValidationError({"surface_key": "Superficie sconosciuta."})

    def __str__(self) -> str:
        return f"{self.theme.name}: {self.surface_key}"


class DatiCampagna(V2Model):
    nome = models.CharField(max_length=160)
    attiva = models.BooleanField(default=False)
    monete_condivise = models.PositiveIntegerField(default=0)
    meteo = models.TextField(blank=True)
    ora_corrente = models.CharField(max_length=80, blank=True)
    giorni_da_inizio = models.IntegerField(default=0)
    note_condivise = models.TextField(blank=True)
    risorse_speciali = models.JSONField(default=dict, blank=True)
    default_global_map = models.ForeignKey(
        "media_library.UploadedImage",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="default_for_campaigns",
    )
    state = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-attiva", "nome"]
        indexes = [models.Index(fields=["attiva", "nome"])]
        constraints = [
            models.UniqueConstraint(
                fields=["attiva"],
                condition=models.Q(attiva=True),
                name="one_active_campaign",
            ),
        ]

    def __str__(self) -> str:
        return self.nome

    def save(self, *args, **kwargs):
        if self.attiva:
            DatiCampagna.objects.exclude(pk=self.pk).filter(attiva=True).update(attiva=False)
        super().save(*args, **kwargs)


class GlobalModifiers(V2Model):
    name = models.CharField(max_length=120, unique=True)
    value_float = models.JSONField(default=dict, blank=True)
    value_string = models.JSONField(default=dict, blank=True)
    rule_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Effetto(V2Model):
    tipo = models.CharField(max_length=80, blank=True)
    nome = models.CharField(max_length=180, unique=True)
    descrizione = models.TextField(blank=True)
    effect_payload = models.JSONField(default=dict, blank=True)
    durata_turni = models.IntegerField(null=True, blank=True)
    stacking_rule = models.CharField(max_length=80, blank=True)
    icona = models.CharField(max_length=160, blank=True)
    origine_tipo = models.CharField(max_length=80, blank=True)
    origine_nome = models.CharField(max_length=180, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["tipo", "nome"]
        indexes = [
            models.Index(fields=["tipo", "nome"]),
            models.Index(fields=["origine_tipo", "origine_nome"]),
        ]

    def __str__(self) -> str:
        return self.nome


class GruppoFamiglieSkill(V2Model):
    nome = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    ordine = models.IntegerField(default=0)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["ordine", "nome"]

    def __str__(self) -> str:
        return self.nome


class FamigliaSkill(V2Model):

    nome = models.CharField(max_length=160, unique=True)
    gruppo = models.ForeignKey(
        GruppoFamiglieSkill,
        on_delete=models.PROTECT,
        related_name="famiglie",
    )
    ordine = models.IntegerField(default=0)
    is_classe = models.BooleanField(default=False)
    is_religione = models.BooleanField(default=False)
    is_perk = models.BooleanField(default=False)
    note = models.TextField(blank=True)
    note_addizionali = models.TextField(blank=True)
    immagine = models.ForeignKey(
        "media_library.UploadedImage",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="famiglie_skill",
    )

    class Meta:
        ordering = ["ordine", "nome"]

    def __str__(self) -> str:
        return self.nome


class Skill(V2Model):
    XP_TYPE_CHOICES = [
        ("all", "Tutti"),
        ("general", "Generali"),
        ("red", "Rossi"),
        ("green", "Verdi"),
        ("blue", "Blu"),
    ]

    nome = models.CharField(max_length=180, unique=True)
    slug = models.SlugField(max_length=180, unique=True)
    numero = models.IntegerField(unique=True)
    famiglia = models.ForeignKey(FamigliaSkill, on_delete=models.PROTECT, related_name="skills")
    prerequisiti = models.ManyToManyField("self", symmetrical=False, blank=True, related_name="sblocca_skills")
    ordine_famiglia = models.IntegerField(default=0)
    costo_pe = models.IntegerField(default=0)
    tipo_pe = models.CharField(max_length=40, choices=XP_TYPE_CHOICES, default="all")
    costo_testuale = models.CharField(max_length=255, blank=True)
    descrizione = models.TextField(blank=True)
    requisiti = models.TextField(blank=True)
    profile_tags = models.JSONField(default=dict, blank=True)
    profile_notes = models.TextField(blank=True)
    effetti_passivi = models.JSONField(default=list, blank=True)
    azioni_attive = models.JSONField(default=list, blank=True)
    icona = models.CharField(max_length=80, default="runa", blank=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["famiglia__ordine", "ordine_famiglia", "numero", "nome"]
        indexes = [
            models.Index(fields=["tipo_pe"]),
            models.Index(fields=["famiglia", "ordine_famiglia"]),
        ]

    def __str__(self) -> str:
        return self.nome


class SpellDefinition(V2Model):
    TIER_BASE = "base"
    TIER_APPRENTICE = "apprentice"
    TIER_MASTER = "master"
    TIER_CHOICES = [
        (TIER_BASE, "Base"),
        (TIER_APPRENTICE, "Apprendista"),
        (TIER_MASTER, "Maestro"),
    ]
    ROUNDING_NONE = "none"
    ROUNDING_FLOOR = "floor"
    ROUNDING_CEIL = "ceil"
    ROUNDING_NEAREST = "nearest"
    ROUNDING_CHOICES = [
        (ROUNDING_NONE, "Nessun arrotondamento"),
        (ROUNDING_FLOOR, "Per difetto"),
        (ROUNDING_CEIL, "Per eccesso"),
        (ROUNDING_NEAREST, "Al più vicino"),
    ]

    skill = models.OneToOneField(Skill, on_delete=models.CASCADE, related_name="spell_definition")
    tier = models.CharField(max_length=24, choices=TIER_CHOICES, default=TIER_BASE)
    range_text = models.CharField(max_length=160, blank=True)
    effect_unit = models.CharField(max_length=120, default="Effetto")
    # Mana fisso pagato a ogni lancio, indipendente dall'intensità: è la parte
    # "15 Mana" di una formula come "15 Mana più 3 Mana per effetto". Concorre
    # alla conversione in Energia e PA esattamente come il Mana variabile.
    base_mana = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    effect_per_mana = models.DecimalField(max_digits=12, decimal_places=6, default=1)
    minimum_mana = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    # Costi fissi in altre risorse (pf, energia, potere, pa, stanchezza) pagati a
    # ogni lancio e sommati ai costi convertiti dal Mana, senza essere riconvertiti.
    fixed_costs = models.JSONField(default=dict, blank=True)
    rounding = models.CharField(max_length=24, choices=ROUNDING_CHOICES, default=ROUNDING_NONE)
    legacy_formula = models.CharField(max_length=255, blank=True)
    cost_notes = models.TextField(blank=True)
    combat_configuration = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["skill__famiglia__ordine", "tier", "skill__ordine_famiglia", "skill__nome"]

    def __str__(self) -> str:
        return f"Incantesimo: {self.skill.nome}"


class EffettiSkill(V2Model):
    SOURCE_CHOICES = [
        ("skill", "Skill"),
        ("razza", "Razza"),
        ("subrazza", "Subrazza"),
        ("manuale", "Manuale"),
        ("unit", "Unit"),
        ("oggetto", "Oggetto"),
    ]
    TYPE_CHOICES = [
        ("passivo", "Passivo"),
        ("attivabile", "Attivabile"),
        ("ibrido", "Ibrido"),
    ]

    skill = models.ForeignKey(Skill, on_delete=models.SET_NULL, null=True, blank=True, related_name="effetti")
    nome = models.CharField(max_length=180)
    fonte_tipo = models.CharField(max_length=40, choices=SOURCE_CHOICES, default="skill")
    fonte_nome = models.CharField(max_length=180, blank=True)
    tipo = models.CharField(max_length=40, choices=TYPE_CHOICES, default="passivo")
    descrizione = models.TextField(blank=True)
    note_proposte = models.TextField(blank=True)
    costi = models.JSONField(default=dict, blank=True)
    durata_turni = models.IntegerField(null=True, blank=True)
    messaggi = models.JSONField(default=dict, blank=True)
    icona = models.CharField(max_length=160, blank=True)
    effect_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["nome"]
        indexes = [models.Index(fields=["fonte_tipo", "tipo", "nome"])]

    def __str__(self) -> str:
        return self.nome


class EffettiEMalattie(V2Model):
    tipo = models.CharField(max_length=80, blank=True)
    nome = models.CharField(max_length=180, unique=True)
    descrizione = models.TextField(blank=True)
    effect_payload = models.JSONField(default=dict, blank=True)
    default_duration_turns = models.IntegerField(null=True, blank=True)
    stacking_rule = models.CharField(max_length=80, blank=True)
    icon = models.CharField(max_length=160, blank=True)

    class Meta:
        ordering = ["tipo", "nome"]

    def __str__(self) -> str:
        return self.nome


class Competenze(V2Model):
    nome = models.CharField(max_length=160, unique=True)
    descrizione = models.TextField(blank=True)
    mapping_tag = models.JSONField(default=dict, blank=True)
    ordine = models.IntegerField(default=0)
    categoria = models.CharField(max_length=80, blank=True)

    class Meta:
        ordering = ["ordine", "nome"]

    def __str__(self) -> str:
        return self.nome


class TipoArma(V2Model):
    nome = models.CharField(max_length=120, unique=True)
    lunghezza = models.CharField(max_length=80, blank=True)
    potenza = models.CharField(max_length=80, blank=True)
    bonus_1 = models.CharField(max_length=160, blank=True)
    bonus_2 = models.CharField(max_length=160, blank=True)
    rules = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["nome"]

    def __str__(self) -> str:
        return self.nome


class OpzioneTipoOggetto(V2Model):
    POSIZIONE_CHOICES = [
        (1, "Tipo 1"),
        (2, "Tipo 2"),
        (3, "Tipo 3"),
        (4, "Tipo 4"),
    ]

    posizione = models.PositiveSmallIntegerField(choices=POSIZIONE_CHOICES)
    valore = models.CharField(max_length=80)
    etichetta = models.CharField(max_length=120, blank=True)
    attiva = models.BooleanField(default=True)
    ordine = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["posizione", "ordine", "etichetta", "valore"]
        verbose_name = "opzione tipo oggetto"
        verbose_name_plural = "opzioni tipo oggetto"
        constraints = [
            models.UniqueConstraint(
                fields=["posizione", "valore"],
                name="unique_item_type_option_per_position",
            ),
        ]
        indexes = [models.Index(fields=["posizione", "attiva", "ordine"])]

    @property
    def label(self) -> str:
        return self.etichetta or self.valore

    def clean(self):
        super().clean()
        self.valore = self.valore.strip()
        self.etichetta = self.etichetta.strip()
        if not self.valore:
            raise ValidationError({"valore": "Il valore del tipo è obbligatorio."})
        duplicate = OpzioneTipoOggetto.objects.filter(
            posizione=self.posizione,
            valore__iexact=self.valore,
        ).exclude(pk=self.pk)
        if duplicate.exists():
            raise ValidationError(
                {"valore": "Esiste già un'opzione con questo valore, anche usando maiuscole diverse."}
            )

    def __str__(self) -> str:
        return f"{self.get_posizione_display()} · {self.label}"


class Oggetto(V2Model):
    class Rarita(models.IntegerChoices):
        UNICO = 0, "Unico"
        UNO = 1, "1"
        DUE = 2, "2"
        TRE = 3, "3"
        QUATTRO = 4, "4"
        CINQUE = 5, "5"

    nome = models.CharField(max_length=180, unique=True)
    modello = models.BooleanField(default=True)
    temporaneo = models.BooleanField(default=False)
    archiviato = models.BooleanField(default=False)
    speciale = models.BooleanField(
        default=False,
        help_text="Contrassegna oggetti legacy anomali o che richiedono regole/revisione speciali.",
    )
    numero_ordine = models.IntegerField(null=True, blank=True)
    icona = models.CharField(max_length=160, blank=True)
    tipo_1 = models.CharField(max_length=80, blank=True)
    tipo_2 = models.CharField(max_length=80, blank=True)
    tipo_3 = models.CharField(max_length=80, blank=True)
    tipo_4 = models.CharField(max_length=80, blank=True)
    descrizione = models.TextField(blank=True)
    valore = models.IntegerField(null=True, blank=True)
    peso = models.FloatField(null=True, blank=True)
    rarita = models.IntegerField(
        choices=Rarita.choices,
        validators=[MinValueValidator(0), MaxValueValidator(5)],
        null=True,
        blank=True,
    )
    lv_loot = models.CharField(max_length=80, blank=True)
    regione_loot = models.CharField(max_length=120, blank=True)
    peso_regione = models.FloatField(null=True, blank=True)
    tipo_arma = models.ForeignKey(TipoArma, on_delete=models.SET_NULL, null=True, blank=True, related_name="oggetti")
    pa_per_attacco = models.IntegerField(null=True, blank=True)
    effetto_1 = models.CharField("effetto Elder 1", max_length=255, blank=True)
    effetto_2 = models.CharField("effetto Elder 2", max_length=255, blank=True)
    effetto_3 = models.CharField("effetto Elder 3", max_length=255, blank=True)
    effetto_4 = models.CharField("effetto Elder 4", max_length=255, blank=True)
    effetto_5 = models.CharField("effetto Elder 5", max_length=255, blank=True)
    effetto_6 = models.CharField("effetto Elder 6", max_length=255, blank=True)
    effetto_7 = models.CharField("effetto Elder 7", max_length=255, blank=True)
    effetto_8 = models.CharField("effetto Elder 8", max_length=255, blank=True)
    regole_speciali = models.TextField(
        "regole speciali",
        blank=True,
        help_text=(
            "Regole leggibili al tavolo per gli effetti che il sistema non sa calcolare. "
            "Compilarle dichiara riviste le voci Elder descrittive attualmente presenti, "
            "così l'oggetto smette di essere marcato speciale per quel motivo."
        ),
    )
    effects = models.JSONField(default=list, blank=True)
    weapon_profile = models.JSONField(default=dict, blank=True)
    alchemy_profile = models.JSONField(default=dict, blank=True)
    crafting_profile = models.JSONField(default=dict, blank=True)
    media = models.ForeignKey(
        "media_library.UploadedImage",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="oggetti",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["numero_ordine", "nome"]
        indexes = [
            models.Index(fields=["modello", "archiviato"]),
            models.Index(fields=["speciale", "archiviato"], name="core_oggett_special_b95562_idx"),
            models.Index(fields=["tipo_1", "tipo_2"]),
            models.Index(fields=["regione_loot", "rarita"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(rarita__isnull=True) | models.Q(rarita__gte=0, rarita__lte=5),
                name="item_rarity_unique_or_1_to_5",
            ),
        ]

    @property
    def effetti_elder(self) -> list[str]:
        return [getattr(self, f"effetto_{index}") for index in range(1, 9)]

    def __str__(self) -> str:
        return self.nome


class AccessoryProfile(V2Model):
    key = models.SlugField(max_length=80, unique=True)
    nome = models.CharField(max_length=120, unique=True)
    descrizione = models.TextField(blank=True)
    rules = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["nome"]

    def __str__(self) -> str:
        return self.nome


class Unit(V2Model):
    nome = models.CharField(max_length=180, unique=True)
    categoria = models.CharField(max_length=80, blank=True)
    archetipo_tags = models.JSONField(default=dict, blank=True)
    archetipo_descrizione = models.TextField(blank=True)
    profilo_competenze = models.JSONField(default=dict, blank=True)
    levels = models.JSONField(default=list, blank=True)
    equipment_profiles = models.JSONField(default=dict, blank=True)
    stat_profiles = models.JSONField(default=dict, blank=True)
    skill_actions = models.JSONField(default=list, blank=True)
    skill_unlocks = models.JSONField(default=list, blank=True)
    lore_description = models.TextField(blank=True)
    lore_image = models.ForeignKey(
        "media_library.UploadedImage",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="unit_lore",
    )
    generation_rules = models.JSONField(default=dict, blank=True)
    accessory_profile = models.ForeignKey(
        AccessoryProfile,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="units",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["categoria", "nome"]
        indexes = [models.Index(fields=["categoria"])]

    def __str__(self) -> str:
        return self.nome


class Negozio(V2Model):
    nome = models.CharField(max_length=180)
    proprietario = models.CharField(max_length=180, blank=True)
    categoria = models.CharField(max_length=80, blank=True)
    livello = models.IntegerField(default=1)
    regione_nome = models.CharField(max_length=120, blank=True)
    regione_descrizione = models.TextField(blank=True)
    regione_immagine = models.ForeignKey(
        "media_library.UploadedImage",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="negozi_regione",
    )
    citta_nome = models.CharField(max_length=120, blank=True)
    citta_descrizione = models.TextField(blank=True)
    citta_immagine = models.ForeignKey(
        "media_library.UploadedImage",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="negozi_citta",
    )
    immagine_sfondo = models.ForeignKey(
        "media_library.UploadedImage",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="negozi_sfondo",
    )
    lista_oggetti = models.JSONField(default=list, blank=True)
    generation_seed = models.CharField(max_length=120, blank=True)
    generation_profile_key = models.CharField(max_length=80, blank=True)
    descrizione = models.TextField(blank=True)
    location_key = models.CharField(max_length=200, blank=True, db_index=True)
    stock_revision = models.PositiveIntegerField(default=0)
    last_restocked_at = models.DateTimeField(null=True, blank=True)
    in_evidenza = models.BooleanField(default=False)
    price_modifier_percent = models.IntegerField(default=0)

    class Meta:
        ordering = ["regione_nome", "citta_nome", "nome"]
        indexes = [models.Index(fields=["regione_nome", "citta_nome", "categoria"])]

    def __str__(self) -> str:
        return self.nome


class Guida(V2Model):
    nome = models.CharField(max_length=180, unique=True)
    contenuto = models.TextField(blank=True)
    immagine_sfondo = models.ForeignKey(
        "media_library.UploadedImage",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="guide",
    )
    categoria = models.CharField(max_length=80, blank=True)
    ordine = models.IntegerField(default=0)

    class Meta:
        ordering = ["ordine", "nome"]

    def __str__(self) -> str:
        return self.nome


class Curiosita(V2Model):
    nome = models.CharField(max_length=180, unique=True)
    descrizione = models.TextField(blank=True)
    categoria = models.CharField(max_length=80, blank=True)
    visibile = models.BooleanField(default=True)

    class Meta:
        ordering = ["categoria", "nome"]

    def __str__(self) -> str:
        return self.nome


class TimelineEvent(V2Model):
    # Dedicated exclusively to Lore > Timeline. Do not reuse this model for
    # reputation changes, campaign audit logs, quests, or Hall of Fame data.
    nome = models.CharField(max_length=180)
    data_evento = models.CharField(max_length=80, blank=True)
    ordine_cronologico = models.IntegerField(
        default=0,
        help_text="Chiave numerica usata soltanto per ordinare gli eventi nella Timeline del Lore.",
    )
    immagine = models.ForeignKey(
        "media_library.UploadedImage",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="timeline_events",
    )
    descrizione = models.TextField(blank=True)
    campagna = models.ForeignKey(DatiCampagna, on_delete=models.SET_NULL, null=True, blank=True, related_name="timeline")
    tags = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["ordine_cronologico", "created_at", "id"]
        indexes = [
            models.Index(
                fields=["campagna", "archived_at", "ordine_cronologico"],
                name="core_timeline_campaign_idx",
            )
        ]

    def __str__(self) -> str:
        return self.nome


class HallOfFameCharacter(V2Model):
    nome = models.CharField(max_length=180)
    immagine = models.ForeignKey(
        "media_library.UploadedImage",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="hall_of_fame_entries",
    )
    campaign = models.CharField(max_length=160, blank=True)
    personaggio = models.ForeignKey(
        "characters.Personaggio",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="hall_of_fame_entries",
    )
    descrizione = models.TextField(blank=True)
    ordine = models.IntegerField(default=0)

    class Meta:
        ordering = ["ordine", "nome"]

    def __str__(self) -> str:
        return self.nome


class CampaignLoreEntry(V2Model):
    STATUS_CANON = "canon"
    STATUS_CHOICES = [
        (STATUS_CANON, "Canon"),
        ("rumor", "Rumor"),
        ("deprecated", "Deprecated"),
        ("draft", "Draft"),
        ("contradicted", "Contradicted"),
    ]
    VISIBILITY_CHOICES = [
        ("dm", "DM only"),
        ("player", "Player visible"),
        ("mixed", "Mixed"),
    ]

    campagna = models.ForeignKey(DatiCampagna, on_delete=models.CASCADE, related_name="lore_entries")
    tipo = models.CharField(max_length=80, blank=True)
    slug = models.SlugField(max_length=180)
    nome = models.CharField(max_length=180)
    sommario = models.TextField(blank=True)
    contenuto = models.JSONField(default=dict, blank=True)
    tags = models.JSONField(default=list, blank=True)
    aliases = models.JSONField(default=list, blank=True)
    stato = models.CharField(max_length=40, choices=STATUS_CHOICES, default=STATUS_CANON)
    visibilita = models.CharField(max_length=40, choices=VISIBILITY_CHOICES, default="dm")
    image = models.ForeignKey(
        "media_library.UploadedImage",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lore_entries",
    )

    class Meta:
        ordering = ["tipo", "nome"]
        constraints = [
            models.UniqueConstraint(fields=["campagna", "slug"], name="unique_lore_slug_per_campaign"),
        ]
        indexes = [models.Index(fields=["campagna", "tipo", "stato"])]

    def __str__(self) -> str:
        return self.nome


class CampaignLoreRelation(V2Model):
    campagna = models.ForeignKey(DatiCampagna, on_delete=models.CASCADE, related_name="lore_relations")
    source = models.ForeignKey(CampaignLoreEntry, on_delete=models.CASCADE, related_name="outgoing_relations")
    target = models.ForeignKey(CampaignLoreEntry, on_delete=models.CASCADE, related_name="incoming_relations")
    relation_type = models.CharField(max_length=80)
    relevance = models.IntegerField(default=0)
    activation_context = models.JSONField(default=dict, blank=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["-relevance", "relation_type"]
        indexes = [models.Index(fields=["campagna", "relation_type", "relevance"])]

    def __str__(self) -> str:
        return f"{self.source} -> {self.target} ({self.relation_type})"


class Messaggio(V2Model):
    campagna = models.ForeignKey(DatiCampagna, on_delete=models.SET_NULL, null=True, blank=True, related_name="messaggi")
    sender = models.ForeignKey(Giocatore, on_delete=models.CASCADE, related_name="sent_messages")
    recipient = models.ForeignKey(
        Giocatore,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="received_messages",
    )
    thread_key = models.CharField(max_length=120, blank=True)
    content = models.TextField()
    read_at = models.DateTimeField(null=True, blank=True)
    message_type = models.CharField(max_length=40, default="chat")

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["campagna", "thread_key", "created_at"])]

    def __str__(self) -> str:
        return f"{self.message_type}: {self.sender}"


class NomiRazzeInfo(V2Model):
    name = models.CharField(max_length=160, unique=True)
    race = models.CharField(max_length=120, blank=True)
    names_male = models.JSONField(default=list, blank=True)
    names_female = models.JSONField(default=list, blank=True)
    surnames = models.JSONField(default=list, blank=True)
    description = models.TextField(blank=True)
    # La razza non ha una tabella propria: è una colonna di testo su questa. Il
    # ritratto di razza viene quindi ripetuto su tutte le culture della stessa
    # razza, così il selettore lo legge da qualunque riga senza un modello in più.
    immagine_razza = models.ForeignKey(
        "media_library.UploadedImage",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="razze_come_ritratto",
    )
    immagine_maschile = models.ForeignKey(
        "media_library.UploadedImage",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="culture_come_ritratto_maschile",
    )
    immagine_femminile = models.ForeignKey(
        "media_library.UploadedImage",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="culture_come_ritratto_femminile",
    )
    clip_maschile = models.ForeignKey(
        "media_library.VideoClip",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="culture_come_clip_maschile",
    )
    clip_femminile = models.ForeignKey(
        "media_library.VideoClip",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="culture_come_clip_femminile",
    )

    class Meta:
        ordering = ["race", "name"]

    def __str__(self) -> str:
        return self.name
