from django.conf import settings
from django.db import models

from backend.core.models import V2Model


DEFAULT_STATS = {"might": 1, "agility": 1, "mind": 1, "spirit": 1}
DEFAULT_RESOURCES = {"health": 10, "stamina": 5, "mana": 0}


class ItemSlot50Mixin(models.Model):
    slot_1 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    slot_2 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    slot_3 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    slot_4 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    slot_5 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    slot_6 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    slot_7 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    slot_8 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    slot_9 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    slot_10 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    slot_11 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    slot_12 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    slot_13 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    slot_14 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    slot_15 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    slot_16 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    slot_17 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    slot_18 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    slot_19 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    slot_20 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    slot_21 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    slot_22 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    slot_23 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    slot_24 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    slot_25 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    slot_26 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    slot_27 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    slot_28 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    slot_29 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    slot_30 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    slot_31 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    slot_32 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    slot_33 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    slot_34 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    slot_35 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    slot_36 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    slot_37 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    slot_38 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    slot_39 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    slot_40 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    slot_41 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    slot_42 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    slot_43 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    slot_44 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    slot_45 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    slot_46 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    slot_47 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    slot_48 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    slot_49 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    slot_50 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")

    class Meta:
        abstract = True


class Zaino(V2Model, ItemSlot50Mixin):
    nome = models.CharField(max_length=160)

    class Meta:
        ordering = ["nome"]

    def __str__(self) -> str:
        return self.nome


class Faretra(V2Model, ItemSlot50Mixin):
    nome = models.CharField(max_length=160)

    class Meta:
        ordering = ["nome"]

    def __str__(self) -> str:
        return self.nome


class Equip(V2Model):
    nome = models.CharField(max_length=160)
    arma = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    armatura = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    scudo = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    chainmail = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    veste = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    anello_1 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    anello_2 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    anello_3 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    anello_4 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    anello_5 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    anello_6 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    anello_7 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    anello_8 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    orecchino_1 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    orecchino_2 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    orecchino_3 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    orecchino_4 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    orecchino_5 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    orecchino_6 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    spilla = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    fascia = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    amuleto = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    cintura = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    vestiti = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    mantello = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    borsello = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    sacco_1 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    sacco_2 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    sacco_3 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    faretra_1 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    faretra_2 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    extra_slot_1 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    extra_slot_2 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    extra_slot_3 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    extra_slot_4 = models.ForeignKey("core.Oggetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")

    class Meta:
        ordering = ["nome"]

    def __str__(self) -> str:
        return self.nome


class BorsaReagenti(V2Model):
    nome = models.CharField(max_length=160)
    personaggio = models.ForeignKey(
        "Personaggio",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="borse_reagenti",
    )
    slot_max_reagenti = models.IntegerField(default=0)
    ingredienti = models.JSONField(default=dict, blank=True)
    moltiplicatori = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["nome"]

    def __str__(self) -> str:
        return self.nome


class Note(V2Model):
    personaggio_ref = models.ForeignKey(
        "Personaggio",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="personaggio_id",
        related_name="note_sets",
    )
    nome = models.CharField(max_length=160)
    personaggio = models.JSONField(default=dict, blank=True)
    appunti = models.JSONField(default=dict, blank=True)
    note_combat = models.JSONField(default=dict, blank=True)
    note_skill = models.JSONField(default=dict, blank=True)
    crafting = models.JSONField(default=dict, blank=True)
    alchimia = models.JSONField(default=dict, blank=True)
    background = models.TextField(blank=True)
    tracker_config = models.JSONField(default=dict, blank=True)
    tracker_state = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["nome"]

    def __str__(self) -> str:
        return self.nome


class Personaggio(V2Model):
    TYPE_CHOICES = [
        ("giocabile", "Giocabile"),
        ("npc", "NPC"),
        ("nemico", "Nemico"),
        ("evocazione", "Evocazione"),
        ("altro", "Altro"),
    ]

    nome = models.CharField(max_length=180)
    tipologia = models.CharField(max_length=40, choices=TYPE_CHOICES, default="npc")
    nome_interno = models.CharField(max_length=180, unique=True)
    razza_1 = models.CharField(max_length=120, blank=True)
    razza_2 = models.CharField(max_length=120, blank=True)
    razza_3 = models.CharField(max_length=120, blank=True)
    livello = models.IntegerField(default=1)
    eta = models.IntegerField(null=True, blank=True)
    sesso = models.CharField(max_length=80, blank=True)
    monete = models.IntegerField(default=0)
    dettagli_personaggio = models.TextField(blank=True)
    danno = models.IntegerField(default=0)
    mana_speso = models.IntegerField(default=0)
    energia_spesa = models.IntegerField(default=0)
    potere_speso = models.IntegerField(default=0)
    mana_in_sifone = models.IntegerField(default=0)
    competenze = models.JSONField(default=dict, blank=True)
    pe_generali = models.IntegerField(default=0)
    pe_rossi = models.IntegerField(default=0)
    pe_verdi = models.IntegerField(default=0)
    pe_blu = models.IntegerField(default=0)
    pe_abilita = models.IntegerField(default=0)
    equip = models.ForeignKey(Equip, on_delete=models.SET_NULL, null=True, blank=True, related_name="personaggi")
    zaino = models.ForeignKey(Zaino, on_delete=models.SET_NULL, null=True, blank=True, related_name="personaggi")
    note = models.ForeignKey(Note, on_delete=models.SET_NULL, null=True, blank=True, related_name="personaggi")
    borsa_reagenti = models.ForeignKey(
        BorsaReagenti,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="personaggi",
    )
    faretra = models.ForeignKey(Faretra, on_delete=models.SET_NULL, null=True, blank=True, related_name="personaggi")
    abilita = models.JSONField(default=dict, blank=True)
    abilita_desiderate = models.JSONField(default=dict, blank=True)
    act = models.JSONField(default=dict, blank=True)
    extra = models.JSONField(default=dict, blank=True)
    bottoni = models.JSONField(default=dict, blank=True)
    crit_min = models.CharField(max_length=40, blank=True)
    crit_nor = models.CharField(max_length=40, blank=True)
    crit_mag = models.CharField(max_length=40, blank=True)
    custom_overrides = models.JSONField(default=dict, blank=True)
    stanchezza_tot = models.FloatField(default=0)
    modificatore_generale_tot = models.FloatField(default=0)
    fortuna_tot = models.FloatField(default=0)
    forza_tot = models.FloatField(default=0)
    resistenza_tot = models.FloatField(default=0)
    velocita_tot = models.FloatField(default=0)
    agilita_tot = models.FloatField(default=0)
    intelligenza_tot = models.FloatField(default=0)
    concentrazione_tot = models.FloatField(default=0)
    personalita_tot = models.FloatField(default=0)
    saggezza_tot = models.FloatField(default=0)
    pf_tot = models.FloatField(default=0)
    mana_tot = models.FloatField(default=0)
    energia_tot = models.FloatField(default=0)
    potere_tot = models.FloatField(default=0)
    pa_tot = models.FloatField(default=0)
    attacco_tot = models.FloatField(default=0)
    difesa_tot = models.FloatField(default=0)
    attacco_npc = models.FloatField(default=0)
    difesa_npc = models.FloatField(default=0)
    rd_fis_tot = models.FloatField(default=0)
    res_contundente_tot = models.FloatField(default=0)
    res_taglio_tot = models.FloatField(default=0)
    res_perforante_tot = models.FloatField(default=0)
    res_fuoco_tot = models.FloatField(default=0)
    res_gelo_tot = models.FloatField(default=0)
    res_elettro_tot = models.FloatField(default=0)
    rd_fuoco_tot = models.FloatField(default=0)
    rd_gelo_tot = models.FloatField(default=0)
    rd_elettro_tot = models.FloatField(default=0)
    ap_tot = models.FloatField(default=0)
    ap_percento_tot = models.FloatField(default=0)
    slot_magici_tot = models.FloatField(default=0)
    slot_non_magici_tot = models.FloatField(default=0)
    monete_per_slot_tot = models.FloatField(default=0)
    tier_tot = models.FloatField(default=0)
    sifone_di_mana_tot = models.FloatField(default=0)
    en_per_mana_ordine_tot = models.FloatField(default=0)
    pa_per_mana_ordine_tot = models.FloatField(default=0)
    en_per_mana_caos_tot = models.FloatField(default=0)
    pa_per_mana_caos_tot = models.FloatField(default=0)
    ogni_en_x_mana_ordine_tot = models.FloatField(default=0)
    ogni_pa_x_mana_ordine_tot = models.FloatField(default=0)
    ogni_en_x_mana_caos_tot = models.FloatField(default=0)
    ogni_pa_x_mana_caos_tot = models.FloatField(default=0)
    sconto_mana_per_potere_tot = models.FloatField(default=0)
    sconto_pa_per_potere_tot = models.FloatField(default=0)
    mod_carico_tot = models.FloatField(default=0)
    mod_peso_equip_tot = models.FloatField(default=0)
    orecchini_max_tot = models.FloatField(default=0)
    anelli_max_tot = models.FloatField(default=0)
    sacchi_max_tot = models.FloatField(default=0)
    atk_skill_taglio_tot = models.FloatField(default=0)
    atk_skill_contundente_tot = models.FloatField(default=0)
    atk_skill_perforante_tot = models.FloatField(default=0)

    class Meta:
        ordering = ["nome"]
        indexes = [
            models.Index(fields=["tipologia", "nome"]),
            models.Index(fields=["nome_interno"]),
        ]

    def __str__(self) -> str:
        return self.nome


class Character(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="redjango_characters")
    name = models.CharField(max_length=120)
    ancestry = models.CharField(max_length=80, blank=True)
    archetype = models.CharField(max_length=80, blank=True)
    level = models.PositiveIntegerField(default=1)
    stats = models.JSONField(default=dict, blank=True)
    resources = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)
    portrait = models.ForeignKey(
        "media_library.UserMediaAsset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="portrait_characters",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["owner", "name"]),
        ]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        self.stats = {**DEFAULT_STATS, **(self.stats or {})}
        self.resources = {**DEFAULT_RESOURCES, **(self.resources or {})}
        super().save(*args, **kwargs)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "ancestry": self.ancestry,
            "archetype": self.archetype,
            "level": self.level,
            "stats": self.stats,
            "resources": self.resources,
            "notes": self.notes,
            "portrait": self.portrait.to_dict() if self.portrait_id else None,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }
