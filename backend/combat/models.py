from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

from backend.core.models import HEX_COLOR_VALIDATOR, V2Model


class MapType(V2Model):
    name = models.CharField("nome", max_length=120, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    description = models.TextField("descrizione", blank=True)
    default_orientation = models.CharField(
        max_length=12,
        choices=(("pointy", "Punta in alto"), ("flat", "Lato in alto")),
        default="pointy",
    )
    default_rows = models.PositiveSmallIntegerField(default=24, validators=[MinValueValidator(1)])
    default_columns = models.PositiveSmallIntegerField(default=32, validators=[MinValueValidator(1)])
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "tipo di mappa di combattimento"
        verbose_name_plural = "tipi di mappa di combattimento"

    def __str__(self):
        return self.name


class HexType(V2Model):
    name = models.CharField("nome", max_length=120, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    description = models.TextField("descrizione", blank=True)
    movement_multiplier = models.DecimalField(
        "moltiplicatore movimento",
        max_digits=6,
        decimal_places=2,
        default=Decimal("1.00"),
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    color = models.CharField(max_length=7, default="#76866a", validators=[HEX_COLOR_VALIDATOR])
    impassable = models.BooleanField("intransitabile", default=False)
    active = models.BooleanField(default=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]
        verbose_name = "tipo di esagono"
        verbose_name_plural = "tipi di esagono"

    def __str__(self):
        suffix = " · intransitabile" if self.impassable else f" · x{self.movement_multiplier}"
        return f"{self.name}{suffix}"


class CharacterTemplate(V2Model):
    name = models.CharField("nome", max_length=160, unique=True)
    slug = models.SlugField(max_length=160, unique=True)
    description = models.TextField(blank=True)
    image = models.ForeignKey(
        "media_library.UploadedImage",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="combat_character_templates",
    )
    blueprint = models.JSONField(
        default=dict,
        blank=True,
        help_text="Profilo versionato: attributi, totali, competenze, skill, equipaggiamento, inventario, faretra, effetti e note.",
    )
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "modello di personaggio"
        verbose_name_plural = "modelli di personaggio"

    def __str__(self):
        return self.name


class MapMetadata(V2Model):
    name = models.CharField("nome", max_length=180)
    map_type = models.ForeignKey(MapType, on_delete=models.PROTECT, related_name="maps")
    image = models.ForeignKey(
        "media_library.UploadedImage",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="combat_maps",
    )
    created_by = models.ForeignKey(
        "core.Giocatore",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_combat_maps",
    )
    orientation = models.CharField(
        max_length=12,
        choices=(("pointy", "Punta in alto"), ("flat", "Lato in alto")),
        default="pointy",
    )
    rows = models.PositiveSmallIntegerField(default=24, validators=[MinValueValidator(1)])
    columns = models.PositiveSmallIntegerField(default=32, validators=[MinValueValidator(1)])
    hex_size = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal("34.00"), validators=[MinValueValidator(Decimal("4"))])
    grid_offset_x = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    grid_offset_y = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    image_scale = models.DecimalField(max_digits=7, decimal_places=3, default=Decimal("1.000"), validators=[MinValueValidator(Decimal("0.05"))])
    image_offset_x = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    image_offset_y = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    viewport_scale = models.DecimalField(max_digits=7, decimal_places=3, default=Decimal("1.000"), validators=[MinValueValidator(Decimal("0.05"))])
    viewport_offset_x = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    viewport_offset_y = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    fog_enabled = models.BooleanField(
        "nebbia di guerra attiva",
        default=False,
        help_text="Quando attiva, gli esagoni non rivelati restano nascosti ai giocatori.",
    )
    fog_opacity = models.DecimalField(
        "opacita nebbia",
        max_digits=3,
        decimal_places=2,
        default=Decimal("0.88"),
    )
    active_character = models.ForeignKey(
        "characters.Personaggio",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="active_on_combat_maps",
    )
    revision = models.PositiveIntegerField(default=1)
    is_default = models.BooleanField(default=False)

    class Meta:
        ordering = ["-updated_at", "name"]
        verbose_name = "metadati mappa di combattimento"
        verbose_name_plural = "metadati mappe di combattimento"
        indexes = [models.Index(fields=["is_default", "updated_at"])]

    def __str__(self):
        return self.name


class MapHex(V2Model):
    map = models.ForeignKey(MapMetadata, on_delete=models.CASCADE, related_name="hexes")
    q = models.SmallIntegerField()
    r = models.SmallIntegerField()
    overlay_color = models.CharField(max_length=7, blank=True, validators=[HEX_COLOR_VALIDATOR])
    overlay_opacity = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal("0.35"))
    blocked = models.BooleanField(default=False)
    revealed = models.BooleanField("rivelato ai giocatori", default=False)
    fog_effect = models.BooleanField(
        "effetto nebbia locale",
        default=False,
        help_text="Applica all'esagono un trattamento scuro, desaturato e sfocato senza nasconderlo.",
    )
    terrain_types = models.ManyToManyField(HexType, through="MapHexTerrain", related_name="map_hexes")

    class Meta:
        ordering = ["r", "q"]
        constraints = [models.UniqueConstraint(fields=["map", "q", "r"], name="combat_unique_map_hex")]

    def __str__(self):
        return f"{self.map.name} · {self.q},{self.r}"


class MapHexTerrain(models.Model):
    map_hex = models.ForeignKey(MapHex, on_delete=models.CASCADE, related_name="terrain_links")
    terrain_type = models.ForeignKey(HexType, on_delete=models.PROTECT, related_name="hex_links")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["map_hex", "terrain_type"], name="combat_unique_hex_terrain")]


class MapParticipant(V2Model):
    map = models.ForeignKey(MapMetadata, on_delete=models.CASCADE, related_name="participants")
    character = models.ForeignKey(
        "characters.Personaggio",
        on_delete=models.CASCADE,
        related_name="combat_map_participations",
    )
    active = models.BooleanField(default=True)
    anchor_q = models.SmallIntegerField(default=0)
    anchor_r = models.SmallIntegerField(default=0)
    token_color = models.CharField(max_length=7, default="#d6a64b", validators=[HEX_COLOR_VALIDATOR])
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
        constraints = [models.UniqueConstraint(fields=["map", "character"], name="combat_unique_map_character")]

    def __str__(self):
        return f"{self.character.nome} · {self.map.name}"


class MapParticipantFootprint(models.Model):
    participant = models.ForeignKey(MapParticipant, on_delete=models.CASCADE, related_name="footprint")
    q = models.SmallIntegerField(default=0, help_text="Scostamento assiale dall'ancora")
    r = models.SmallIntegerField(default=0, help_text="Scostamento assiale dall'ancora")

    class Meta:
        ordering = ["r", "q"]
        constraints = [models.UniqueConstraint(fields=["participant", "q", "r"], name="combat_unique_footprint_cell")]


class CombatModifier(V2Model):
    name = models.CharField(max_length=120, unique=True)
    scope = models.CharField(
        max_length=12,
        choices=(("attack", "Attacco"), ("damage", "Danno"), ("both", "Entrambi")),
        default="both",
    )
    attack_bonus = models.SmallIntegerField(default=0)
    damage_bonus = models.SmallIntegerField(default=0)
    penetration_flat = models.SmallIntegerField(default=0)
    penetration_percent = models.SmallIntegerField(default=0)
    description = models.TextField(blank=True)
    color = models.CharField(max_length=7, default="#9c7b45", validators=[HEX_COLOR_VALIDATOR])
    active = models.BooleanField(default=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]
        verbose_name = "modificatore di combattimento"
        verbose_name_plural = "modificatori di combattimento"

    def __str__(self):
        return self.name


class CombatModifierState(models.Model):
    map = models.ForeignKey(MapMetadata, on_delete=models.CASCADE, related_name="modifier_states")
    modifier = models.ForeignKey(CombatModifier, on_delete=models.CASCADE, related_name="states")
    enabled = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["map", "modifier"], name="combat_unique_map_modifier")]


class TurnPlanAction(V2Model):
    map = models.ForeignKey(MapMetadata, on_delete=models.CASCADE, related_name="planned_actions")
    character = models.ForeignKey(
        "characters.Personaggio",
        on_delete=models.CASCADE,
        related_name="combat_planned_actions",
    )
    action_type = models.CharField(
        max_length=16,
        choices=(("movement", "Movimento"), ("attack", "Attacco"), ("cast", "Incantesimo"), ("power", "Potere"), ("other", "Altro")),
        default="other",
    )
    name = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    order = models.PositiveSmallIntegerField(default=0)
    cost_pf = models.PositiveIntegerField(default=0)
    cost_mana = models.PositiveIntegerField(default=0)
    cost_energy = models.PositiveIntegerField(default=0)
    cost_power = models.PositiveIntegerField(default=0)
    cost_ap = models.PositiveIntegerField(default=0)
    cost_fatigue = models.PositiveIntegerField(default=0)
    committed_at = models.DateTimeField(null=True, blank=True)
    source_skill = models.ForeignKey(
        "core.Skill",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="combat_plan_actions",
    )

    class Meta:
        ordering = ["order", "id"]


class TurnPlanStep(models.Model):
    action = models.ForeignKey(TurnPlanAction, on_delete=models.CASCADE, related_name="path")
    order = models.PositiveSmallIntegerField(default=0)
    q = models.SmallIntegerField()
    r = models.SmallIntegerField()

    class Meta:
        ordering = ["order"]
        constraints = [models.UniqueConstraint(fields=["action", "order"], name="combat_unique_plan_step")]


class CombatEvent(models.Model):
    map = models.ForeignKey(MapMetadata, on_delete=models.CASCADE, related_name="events")
    event_type = models.CharField(max_length=80)
    message = models.CharField(max_length=500)
    payload = models.JSONField(default=dict, blank=True)
    actor = models.ForeignKey(
        "characters.Personaggio",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="combat_events",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]
        indexes = [models.Index(fields=["map", "id"])]


class MapSnapshot(models.Model):
    map = models.ForeignKey(MapMetadata, on_delete=models.CASCADE, related_name="snapshots")
    revision = models.PositiveIntegerField()
    label = models.CharField(max_length=180, blank=True)
    state = models.JSONField(default=dict)
    created_by = models.ForeignKey(
        "core.Giocatore",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="combat_map_snapshots",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]
        indexes = [models.Index(fields=["map", "id"])]

    def __str__(self):
        return self.label or f"{self.map.name} - revisione {self.revision}"
