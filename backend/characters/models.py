from django.db import models

from backend.core.models import V2Model


PERSONAGGIO_TOT_KEYS = (
    "stanchezza",
    "modificatore_generale",
    "fortuna",
    "forza",
    "resistenza",
    "velocita",
    "agilita",
    "intelligenza",
    "concentrazione",
    "personalita",
    "saggezza",
    "pf",
    "mana",
    "energia",
    "potere",
    "pa",
    "attacco",
    "difesa",
    "mod_forza",
    "mod_resistenza",
    "mod_velocita",
    "mod_agilita",
    "mod_intelligenza",
    "mod_concentrazione",
    "mod_personalita",
    "mod_saggezza",
    "mod_fortuna",
    "rd_fis",
    "res_contundente",
    "res_taglio",
    "res_perforante",
    "res_fuoco",
    "res_gelo",
    "res_elettro",
    "rd_fuoco",
    "rd_gelo",
    "rd_elettro",
    "ap",
    "ap_percento",
    "slot_magici",
    "slot_non_magici",
    "monete_per_slot",
    "tier",
    "sifone_di_mana",
    "en_per_mana",
    "pa_per_mana",
    "ogni_en_x_mana",
    "ogni_pa_x_mana",
    "sconto_mana_per_potere",
    "sconto_pa_per_potere",
    "malus_carico",
    "mod_carico",
    "mod_peso_equip",
    "orecchini_max",
    "anelli_max",
    "sacchi_max",
    "moltiplicatore_reagenti_rossi",
    "moltiplicatore_reagenti_verdi",
    "moltiplicatore_reagenti_blu",
    "moltiplicatore_reagenti_livello_1",
    "moltiplicatore_reagenti_livello_2",
    "moltiplicatore_reagenti_livello_3",
    "moltiplicatore_reagenti_livello_4",
    "atk_skill_taglio",
    "atk_skill_contundente",
    "atk_skill_perforante",
    "atk_skill_corte",
    "atk_skill_medie1",
    "atk_skill_lunghe",
    "atk_skill_precise",
    "atk_skill_medie2",
    "atk_skill_potenti",
    "atk_skill_maninude",
    "tier_skill_maninude",
    "def_skill_leggera",
    "def_skill_pesante",
    "def_skill_noarmatura",
    "def_skill_scudo",
)

NOTE_SECTION_FIELDS = (
    "zaino",
    "combat",
    "competenze",
    "crafting",
    "viaggio",
    "appunti",
    "missioni",
    "background",
)


def default_personaggio_tot() -> dict:
    return {key: 0 for key in PERSONAGGIO_TOT_KEYS}


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


class EffectSlot50Mixin(models.Model):
    effetto_1 = models.ForeignKey("core.Effetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    effetto_2 = models.ForeignKey("core.Effetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    effetto_3 = models.ForeignKey("core.Effetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    effetto_4 = models.ForeignKey("core.Effetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    effetto_5 = models.ForeignKey("core.Effetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    effetto_6 = models.ForeignKey("core.Effetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    effetto_7 = models.ForeignKey("core.Effetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    effetto_8 = models.ForeignKey("core.Effetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    effetto_9 = models.ForeignKey("core.Effetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    effetto_10 = models.ForeignKey("core.Effetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    effetto_11 = models.ForeignKey("core.Effetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    effetto_12 = models.ForeignKey("core.Effetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    effetto_13 = models.ForeignKey("core.Effetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    effetto_14 = models.ForeignKey("core.Effetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    effetto_15 = models.ForeignKey("core.Effetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    effetto_16 = models.ForeignKey("core.Effetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    effetto_17 = models.ForeignKey("core.Effetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    effetto_18 = models.ForeignKey("core.Effetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    effetto_19 = models.ForeignKey("core.Effetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    effetto_20 = models.ForeignKey("core.Effetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    effetto_21 = models.ForeignKey("core.Effetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    effetto_22 = models.ForeignKey("core.Effetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    effetto_23 = models.ForeignKey("core.Effetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    effetto_24 = models.ForeignKey("core.Effetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    effetto_25 = models.ForeignKey("core.Effetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    effetto_26 = models.ForeignKey("core.Effetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    effetto_27 = models.ForeignKey("core.Effetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    effetto_28 = models.ForeignKey("core.Effetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    effetto_29 = models.ForeignKey("core.Effetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    effetto_30 = models.ForeignKey("core.Effetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    effetto_31 = models.ForeignKey("core.Effetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    effetto_32 = models.ForeignKey("core.Effetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    effetto_33 = models.ForeignKey("core.Effetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    effetto_34 = models.ForeignKey("core.Effetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    effetto_35 = models.ForeignKey("core.Effetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    effetto_36 = models.ForeignKey("core.Effetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    effetto_37 = models.ForeignKey("core.Effetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    effetto_38 = models.ForeignKey("core.Effetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    effetto_39 = models.ForeignKey("core.Effetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    effetto_40 = models.ForeignKey("core.Effetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    effetto_41 = models.ForeignKey("core.Effetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    effetto_42 = models.ForeignKey("core.Effetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    effetto_43 = models.ForeignKey("core.Effetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    effetto_44 = models.ForeignKey("core.Effetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    effetto_45 = models.ForeignKey("core.Effetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    effetto_46 = models.ForeignKey("core.Effetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    effetto_47 = models.ForeignKey("core.Effetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    effetto_48 = models.ForeignKey("core.Effetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    effetto_49 = models.ForeignKey("core.Effetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    effetto_50 = models.ForeignKey("core.Effetto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")

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


class ContenitoreInventario(V2Model):
    SCOPE_PERSONAL = "personal"
    SCOPE_CAMPAIGN = "campaign"
    SCOPE_CHOICES = [
        (SCOPE_PERSONAL, "Personale"),
        (SCOPE_CAMPAIGN, "Campagna"),
    ]

    nome = models.CharField(max_length=160)
    scope = models.CharField(max_length=16, choices=SCOPE_CHOICES)
    personaggio = models.ForeignKey(
        "Personaggio",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="contenitori_inventario",
    )
    campagna = models.ForeignKey(
        "core.DatiCampagna",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="contenitori_inventario",
    )
    capacita = models.PositiveSmallIntegerField(default=15)
    senza_peso = models.BooleanField(default=True)

    class Meta:
        ordering = ["scope", "nome"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(scope="personal", personaggio__isnull=False, campagna__isnull=True)
                    | models.Q(scope="campaign", personaggio__isnull=True, campagna__isnull=False)
                ),
                name="inventory_container_owner_matches_scope",
            ),
            models.UniqueConstraint(
                fields=["personaggio"],
                condition=models.Q(scope="personal"),
                name="one_personal_inventory_container",
            ),
            models.UniqueConstraint(
                fields=["campagna"],
                condition=models.Q(scope="campaign"),
                name="one_campaign_inventory_container",
            ),
        ]

    def __str__(self) -> str:
        return self.nome


class VoceContenitoreInventario(V2Model):
    contenitore = models.ForeignKey(
        ContenitoreInventario,
        on_delete=models.CASCADE,
        related_name="voci",
    )
    slot = models.PositiveSmallIntegerField()
    oggetto = models.ForeignKey(
        "core.Oggetto",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="voci_contenitore",
    )
    reagent_stock_key = models.CharField(max_length=8, blank=True)
    quantita = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["slot"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(oggetto__isnull=False, reagent_stock_key="")
                    | (models.Q(oggetto__isnull=True) & ~models.Q(reagent_stock_key=""))
                ),
                name="inventory_entry_has_one_content",
            ),
            models.CheckConstraint(
                condition=models.Q(quantita__gte=1),
                name="inventory_entry_quantity_positive",
            ),
            models.UniqueConstraint(
                fields=["contenitore", "slot"],
                name="unique_inventory_entry_slot",
            ),
            models.UniqueConstraint(
                fields=["contenitore", "oggetto"],
                condition=models.Q(oggetto__isnull=False),
                name="unique_item_stack_per_inventory_container",
            ),
            models.UniqueConstraint(
                fields=["contenitore", "reagent_stock_key"],
                condition=~models.Q(reagent_stock_key=""),
                name="unique_reagent_stack_per_inventory_container",
            ),
        ]

    def __str__(self) -> str:
        content = self.oggetto.nome if self.oggetto_id else self.reagent_stock_key
        return f"{self.contenitore.nome} · {self.slot}: {content} × {self.quantita}"


class EffettiPersonaggio(V2Model, EffectSlot50Mixin):
    nome = models.CharField(max_length=160)

    class Meta:
        ordering = ["nome"]

    def __str__(self) -> str:
        return self.nome


class Equip(V2Model):
    nome = models.CharField(max_length=160)
    arma_primaria_slot = models.CharField(max_length=12, default="arma")
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


class Note(V2Model):
    nome = models.CharField(max_length=160)
    zaino = models.TextField(blank=True, default="")
    combat = models.TextField(blank=True, default="")
    competenze = models.TextField(blank=True, default="")
    crafting = models.TextField(blank=True, default="")
    viaggio = models.TextField(blank=True, default="")
    appunti = models.TextField(blank=True, default="")
    missioni = models.TextField(blank=True, default="")
    background = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["nome"]

    def __str__(self) -> str:
        return self.nome


class Personaggio(V2Model):
    TYPE_CHOICES = [
        ("giocabile", "Giocabile"),
        ("automatico", "Automatico"),
        ("npc", "NPC"),
        ("nemico", "Nemico"),
        ("evocazione", "Evocazione"),
        ("altro", "Altro"),
    ]

    nome = models.CharField(max_length=180)
    tipologia = models.CharField(max_length=40, choices=TYPE_CHOICES, default="npc")
    nome_interno = models.CharField(max_length=180, unique=True)
    campagna = models.ForeignKey(
        "core.DatiCampagna",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="personaggi",
    )
    portrait = models.ForeignKey(
        "media_library.UploadedImage",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="personaggi_ritratto",
    )
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
    stanchezza_accumulata = models.IntegerField(default=0)
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
    faretra = models.ForeignKey(Faretra, on_delete=models.SET_NULL, null=True, blank=True, related_name="personaggi")
    effetti = models.ForeignKey(
        EffettiPersonaggio,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="personaggi",
    )
    abilita = models.JSONField(default=dict, blank=True)
    abilita_desiderate = models.JSONField(default=dict, blank=True)
    effetti_finali = models.JSONField(default=dict, blank=True)
    extra = models.JSONField(default=dict, blank=True)
    bottoni = models.JSONField(default=dict, blank=True)
    crit_min = models.CharField(max_length=40, blank=True)
    crit_nor = models.CharField(max_length=40, blank=True)
    crit_mag = models.CharField(max_length=40, blank=True)
    custom_overrides = models.JSONField(default=dict, blank=True)
    tot = models.JSONField(default=default_personaggio_tot, blank=True)

    class Meta:
        ordering = ["nome"]
        indexes = [
            models.Index(fields=["tipologia", "nome"]),
            models.Index(fields=["campagna", "tipologia", "nome"]),
            models.Index(fields=["nome_interno"]),
        ]

    def __str__(self) -> str:
        return self.nome


class BottoneCombat(V2Model):
    """Modificatori d'attacco configurati e posseduti da un personaggio."""

    personaggio = models.ForeignKey(
        Personaggio,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bottoni_combat",
    )
    nome = models.CharField(max_length=80)
    testo_da_mostrare = models.TextField(blank=True, max_length=1000)
    bonus_attacco = models.SmallIntegerField(default=0)
    bonus_danno = models.SmallIntegerField(default=0)
    bonus_tier = models.SmallIntegerField(default=0)
    perforazione = models.SmallIntegerField(default=0)
    perforazione_percentuale = models.SmallIntegerField(default=0)
    pubblico = models.BooleanField(default=False)
    attivo = models.BooleanField(default=True)
    tieni_attivo_in_combat = models.BooleanField(default=False)
    ordine = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["ordine", "id"]
        indexes = [
            models.Index(fields=["personaggio", "attivo", "ordine"]),
            models.Index(fields=["pubblico", "ordine"]),
        ]

    def __str__(self) -> str:
        proprietario = self.personaggio.nome if self.personaggio_id else "senza personaggio"
        return f"{self.nome} — {proprietario}"


class SkillPersonaggio(V2Model):
    """Acquisto di una Skill da parte di un personaggio e prova della spesa effettuata."""

    personaggio = models.ForeignKey(
        Personaggio,
        on_delete=models.CASCADE,
        related_name="skill_sbloccate",
    )
    skill = models.ForeignKey(
        "core.Skill",
        on_delete=models.PROTECT,
        related_name="personaggi_sbloccati",
    )
    spesa_pe = models.JSONField(default=dict, blank=True)
    passivi_accettati = models.JSONField(default=list, blank=True)
    configurazione_azioni = models.JSONField(default=dict, blank=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["skill__famiglia__ordine", "skill__ordine_famiglia", "skill__nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["personaggio", "skill"],
                name="unique_skill_per_personaggio",
            )
        ]
        indexes = [models.Index(fields=["personaggio", "skill"])]

    def __str__(self) -> str:
        return f"{self.skill.nome} — {self.personaggio.nome}"


class TiroCompetenza(V2Model):
    """A competence check and its possible rank-seven rerolls."""

    TECHNIQUE_CHOICES = [
        ("standard", "Standard"),
        ("focus", "Impulso +1"),
        ("amplify", "Impulso maggiore +2"),
    ]

    personaggio = models.ForeignKey(
        Personaggio,
        on_delete=models.CASCADE,
        related_name="tiri_competenze",
    )
    competenza = models.ForeignKey(
        "core.Competenze",
        on_delete=models.PROTECT,
        related_name="tiri",
    )
    competence_key = models.CharField(max_length=80)
    technique = models.CharField(max_length=24, choices=TECHNIQUE_CHOICES, default="standard")
    die_sides = models.PositiveSmallIntegerField(default=6)
    base_rank = models.SmallIntegerField(default=0)
    manual_extra = models.SmallIntegerField(default=0)
    linked_extra = models.SmallIntegerField(default=0)
    modifier = models.SmallIntegerField(default=0)
    focus_bonus = models.SmallIntegerField(default=0)
    multiplier = models.PositiveSmallIntegerField(default=1)
    energy_spent = models.PositiveSmallIntegerField(default=0)
    rolls = models.JSONField(default=list, blank=True)
    total = models.IntegerField(default=0)
    rerolls_used = models.PositiveSmallIntegerField(default=0)
    daily_marker = models.CharField(max_length=120)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["personaggio", "competence_key", "daily_marker"]),
            models.Index(fields=["personaggio", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.personaggio.nome} · {self.competenza.nome}: {self.total}"


class EffettoPersonalizzato(models.Model):
    """Effetto attivo appartenente a un solo personaggio, senza template o stato temporale."""

    personaggio = models.ForeignKey(
        Personaggio,
        on_delete=models.CASCADE,
        related_name="effetti_personalizzati",
    )
    nome = models.CharField(max_length=180)
    descrizione = models.TextField(blank=True)
    origine = models.CharField(max_length=180, blank=True)
    icona = models.CharField(max_length=80, default="runa")
    temporaneo = models.BooleanField(default=False)
    ordine = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["ordine", "nome", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["personaggio", "nome"],
                name="unique_custom_effect_name_per_character",
            )
        ]
        indexes = [models.Index(fields=["personaggio", "ordine", "nome"])]

    def __str__(self) -> str:
        return f"{self.nome} — {self.personaggio.nome}"


class OperazioneEffettoPersonalizzato(models.Model):
    OPERATION_CHOICES = [
        ("add", "Aggiungi"),
        ("subtract", "Sottrai"),
        ("multiply", "Moltiplica"),
        ("percent", "Percentuale"),
        ("min", "Valore minimo"),
        ("max", "Valore massimo"),
        ("cap", "Limite massimo"),
        ("set", "Imposta"),
        ("strong_set", "Imposta forte"),
        ("formula_override", "Sostituisci formula"),
    ]

    effetto = models.ForeignKey(
        EffettoPersonalizzato,
        on_delete=models.CASCADE,
        related_name="operazioni",
    )
    ordine = models.PositiveIntegerField(default=0)
    bersaglio = models.CharField(max_length=80)
    operazione = models.CharField(max_length=32, choices=OPERATION_CHOICES, default="add")
    valore = models.TextField()
    condizione = models.TextField(blank=True)

    class Meta:
        ordering = ["ordine", "id"]
        indexes = [models.Index(fields=["effetto", "ordine"])]

    def __str__(self) -> str:
        return f"{self.bersaglio} {self.operazione} {self.valore}"
