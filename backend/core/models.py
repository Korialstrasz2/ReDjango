from django.db import models


V2_SCHEMA_VERSION = "0.1"


class V2Model(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        abstract = True


class Giocatore(V2Model):
    ROLE_DM = "dm"
    ROLE_PLAYER = "player"
    ROLE_GUEST = "guest"
    ROLE_CHOICES = [
        (ROLE_DM, "DM"),
        (ROLE_PLAYER, "Player"),
        (ROLE_GUEST, "Guest"),
    ]

    nome = models.CharField(max_length=120, unique=True)
    display_name = models.CharField(max_length=120, blank=True)
    password_hash = models.CharField(max_length=255, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_PLAYER)
    active_character = models.ForeignKey(
        "characters.Personaggio",
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


class DatiCampagna(V2Model):
    nome = models.CharField(max_length=160)
    attiva = models.BooleanField(default=False)
    meteo = models.CharField(max_length=120, blank=True)
    ora_corrente = models.CharField(max_length=80, blank=True)
    giorni_da_inizio = models.IntegerField(default=0)
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

    def __str__(self) -> str:
        return self.nome


class GlobalModifiers(V2Model):
    name = models.CharField(max_length=120, unique=True)
    value_float = models.JSONField(default=dict, blank=True)
    value_string = models.JSONField(default=dict, blank=True)
    rule_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class FamigliaSkill(V2Model):
    nome = models.CharField(max_length=160, unique=True)
    gruppo = models.CharField(max_length=80, blank=True)
    ordine = models.IntegerField(default=0)
    is_classe = models.BooleanField(default=False)
    is_religione = models.BooleanField(default=False)
    is_perk = models.BooleanField(default=False)
    note = models.TextField(blank=True)
    note_addizionali = models.TextField(blank=True)

    class Meta:
        ordering = ["ordine", "nome"]

    def __str__(self) -> str:
        return self.nome


class Skill(V2Model):
    nome = models.CharField(max_length=180, unique=True)
    numero = models.IntegerField(unique=True)
    famiglia = models.ForeignKey(FamigliaSkill, on_delete=models.PROTECT, related_name="skills")
    ordine_famiglia = models.IntegerField(default=0)
    magia = models.BooleanField(default=False)
    costo_pe = models.IntegerField(default=0)
    tipo_pe = models.CharField(max_length=40, blank=True)
    costo_testuale = models.CharField(max_length=255, blank=True)
    descrizione = models.TextField(blank=True)
    requisiti = models.TextField(blank=True)
    livello_magia = models.CharField(max_length=80, blank=True)
    raggio = models.CharField(max_length=120, blank=True)
    formula_effetto = models.CharField(max_length=255, blank=True)
    profile_tags = models.JSONField(default=dict, blank=True)
    profile_notes = models.TextField(blank=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["famiglia__ordine", "ordine_famiglia", "numero", "nome"]
        indexes = [
            models.Index(fields=["magia", "tipo_pe"]),
            models.Index(fields=["famiglia", "ordine_famiglia"]),
        ]

    def __str__(self) -> str:
        return self.nome


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


class Oggetto(V2Model):
    nome = models.CharField(max_length=180, unique=True)
    modello = models.BooleanField(default=True)
    temporaneo = models.BooleanField(default=False)
    archiviato = models.BooleanField(default=False)
    numero_ordine = models.IntegerField(null=True, blank=True)
    icona = models.CharField(max_length=160, blank=True)
    tipo_1 = models.CharField(max_length=80, blank=True)
    tipo_2 = models.CharField(max_length=80, blank=True)
    tipo_3 = models.CharField(max_length=80, blank=True)
    tipo_4 = models.CharField(max_length=80, blank=True)
    tipo_5 = models.CharField(max_length=80, blank=True)
    tipo_6 = models.CharField(max_length=80, blank=True)
    descrizione = models.TextField(blank=True)
    valore = models.IntegerField(null=True, blank=True)
    peso = models.FloatField(null=True, blank=True)
    rarita = models.IntegerField(null=True, blank=True)
    lv_loot = models.CharField(max_length=80, blank=True)
    regione_loot = models.CharField(max_length=120, blank=True)
    peso_regione = models.FloatField(null=True, blank=True)
    tipo_arma = models.ForeignKey(TipoArma, on_delete=models.SET_NULL, null=True, blank=True, related_name="oggetti")
    pa_per_attacco = models.IntegerField(null=True, blank=True)
    effects = models.JSONField(default=list, blank=True)
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
            models.Index(fields=["tipo_1", "tipo_2"]),
            models.Index(fields=["regione_loot", "rarita"]),
        ]

    def __str__(self) -> str:
        return self.nome


class Unit(V2Model):
    nome = models.CharField(max_length=180, unique=True)
    razza = models.CharField(max_length=120, blank=True)
    categoria = models.CharField(max_length=80, blank=True)
    archetipo_key = models.CharField(max_length=120, blank=True)
    archetipo_tags = models.JSONField(default=dict, blank=True)
    archetipo_descrizione = models.TextField(blank=True)
    profilo_equip = models.CharField(max_length=160, blank=True)
    profilo_competenze = models.JSONField(default=dict, blank=True)
    levels = models.JSONField(default=list, blank=True)
    preset = models.CharField(max_length=80, blank=True)
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
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["categoria", "razza", "nome"]
        indexes = [models.Index(fields=["categoria", "razza"])]

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
    descrizione = models.TextField(blank=True)

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
    nome = models.CharField(max_length=180)
    data_evento = models.CharField(max_length=80, blank=True)
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
        ordering = ["data_evento", "nome"]
        indexes = [models.Index(fields=["campagna", "data_evento"])]

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

    class Meta:
        ordering = ["race", "name"]

    def __str__(self) -> str:
        return self.name
