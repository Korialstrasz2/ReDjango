from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from backend.core.models import HEX_COLOR_VALIDATOR, V2Model


ALLOWED_DICE_SIDES = (4, 6, 8, 10, 12, 20, 100)


def validate_dice_sides(value):
    if not isinstance(value, list) or not value:
        raise ValidationError("Scegli almeno un dado per il set.")
    normalized = []
    for raw_side in value:
        if isinstance(raw_side, bool):
            raise ValidationError("Il set contiene un dado non valido.")
        try:
            side = int(raw_side)
        except (TypeError, ValueError) as exc:
            raise ValidationError("Il set contiene un dado non valido.") from exc
        if side not in ALLOWED_DICE_SIDES:
            raise ValidationError(f"d{side} non è supportato.")
        if side not in normalized:
            normalized.append(side)


class DiceSet(V2Model):
    slug = models.SlugField("identificatore", max_length=80, unique=True)
    name = models.CharField("nome", max_length=120)
    description = models.TextField("descrizione", blank=True)
    dice = models.JSONField("dadi disponibili", default=list, validators=[validate_dice_sides])
    surface_color = models.CharField("colore dado", max_length=7, default="#7f2434", validators=[HEX_COLOR_VALIDATOR])
    accent_color = models.CharField("colore bordo", max_length=7, default="#d0a95b", validators=[HEX_COLOR_VALIDATOR])
    text_color = models.CharField("colore simboli", max_length=7, default="#fff4d6", validators=[HEX_COLOR_VALIDATOR])
    is_active = models.BooleanField("attivo", default=True)
    is_default = models.BooleanField("predefinito", default=False)
    order = models.PositiveIntegerField("ordine", default=0)

    class Meta:
        ordering = ["order", "name"]
        verbose_name = "set di dadi"
        verbose_name_plural = "set di dadi"
        indexes = [models.Index(fields=["is_active", "order", "name"], name="dice_set_active_order_idx")]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        validate_dice_sides(self.dice)
        if self.is_default and not self.is_active:
            raise ValidationError({"is_default": "Il set predefinito deve essere attivo."})


class DiceTexture(V2Model):
    dice_set = models.ForeignKey(
        DiceSet,
        verbose_name="set di dadi",
        on_delete=models.CASCADE,
        related_name="textures",
    )
    sides = models.PositiveSmallIntegerField("facce del dado")
    image = models.ForeignKey(
        "media_library.UploadedImage",
        verbose_name="immagine texture",
        on_delete=models.CASCADE,
        related_name="dice_textures",
    )
    offset_x = models.SmallIntegerField(
        "spostamento orizzontale",
        default=0,
        validators=[MinValueValidator(-100), MaxValueValidator(100)],
    )
    offset_y = models.SmallIntegerField(
        "spostamento verticale",
        default=0,
        validators=[MinValueValidator(-100), MaxValueValidator(100)],
    )
    scale = models.PositiveSmallIntegerField(
        "scala percentuale",
        default=100,
        validators=[MinValueValidator(50), MaxValueValidator(300)],
    )
    rotation = models.SmallIntegerField(
        "rotazione",
        default=0,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )

    class Meta:
        ordering = ["sides"]
        verbose_name = "texture dado"
        verbose_name_plural = "texture dadi"
        constraints = [
            models.UniqueConstraint(
                fields=["dice_set", "sides"],
                name="unique_texture_per_die_in_set",
            )
        ]

    def clean(self):
        super().clean()
        if self.sides not in ALLOWED_DICE_SIDES:
            raise ValidationError({"sides": f"d{self.sides} non è supportato."})
        if self.dice_set_id and self.sides not in [int(value) for value in self.dice_set.dice]:
            raise ValidationError({"sides": "Il dado deve essere incluso nel set."})

    def __str__(self):
        return f"{self.dice_set} · d{self.sides}"


class DiceRollRecord(V2Model):
    SOURCE_QUICK = "quick"
    SOURCE_COMPETENCE = "competence"
    SOURCE_CHOICES = [
        (SOURCE_QUICK, "Dadi"),
        (SOURCE_COMPETENCE, "Competenza"),
    ]

    giocatore = models.ForeignKey(
        "core.Giocatore",
        verbose_name="giocatore",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dice_roll_records",
    )
    player_name = models.CharField("nome giocatore", max_length=120)
    personaggio = models.ForeignKey(
        "characters.Personaggio",
        verbose_name="personaggio",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dice_roll_records",
    )
    character_name = models.CharField("nome personaggio", max_length=160, blank=True)
    source = models.CharField("origine", max_length=24, choices=SOURCE_CHOICES)
    label = models.CharField("contesto", max_length=180, blank=True)
    notation = models.CharField("notazione", max_length=80)
    rolls = models.JSONField("risultati dei dadi", default=list)
    modifier = models.IntegerField("modificatore", default=0)
    total = models.IntegerField("totale")
    dice_set_name = models.CharField("set di dadi", max_length=120, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = "tiro di dado registrato"
        verbose_name_plural = "tiri di dado registrati"
        indexes = [
            models.Index(fields=["created_at"], name="dice_roll_created_idx"),
            models.Index(fields=["giocatore", "created_at"], name="dice_roll_player_idx"),
            models.Index(fields=["personaggio", "created_at"], name="dice_roll_character_idx"),
        ]

    def __str__(self):
        owner = self.character_name or self.player_name
        return f"{owner} · {self.notation}: {self.total}"
