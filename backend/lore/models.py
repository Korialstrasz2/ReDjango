from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from backend.core.models import V2Model

REPUTATION_MIN = -100
REPUTATION_MAX = 100


def clamp_reputation(value: int) -> int:
    return max(REPUTATION_MIN, min(REPUTATION_MAX, int(value)))


class Fazione(V2Model):
    campagna = models.ForeignKey(
        "core.DatiCampagna",
        on_delete=models.CASCADE,
        related_name="fazioni",
    )
    nome = models.CharField(max_length=160)
    descrizione = models.TextField(blank=True, default="")
    emblema = models.ForeignKey(
        "media_library.UploadedImage",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="fazioni_emblema",
    )
    # Starting standing towards the party. The current value is never stored:
    # it is replayed from this base through the reputation event log.
    reputazione_base = models.IntegerField(
        default=0,
        validators=[MinValueValidator(REPUTATION_MIN), MaxValueValidator(REPUTATION_MAX)],
    )
    ordine = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["ordine", "nome"]
        constraints = [
            # Archived factions stay readable in the event history, so they must
            # not reserve their name forever.
            models.UniqueConstraint(
                fields=["campagna", "nome"],
                condition=models.Q(archived_at__isnull=True),
                name="unique_faction_name_per_campaign",
            ),
        ]
        indexes = [models.Index(fields=["campagna", "ordine"])]

    def __str__(self) -> str:
        return self.nome


class RelazioneFazione(V2Model):
    """One directed cell of the reaction grid.

    ``coefficiente`` is how much ``destinazione`` moves for every point
    ``origine`` gains or loses: 0.2 means +1 for every +5.
    The grid is deliberately asymmetric, so origine->destinazione and
    destinazione->origine are independent rows.
    """

    origine = models.ForeignKey(
        Fazione,
        on_delete=models.CASCADE,
        related_name="relazioni_uscenti",
    )
    destinazione = models.ForeignKey(
        Fazione,
        on_delete=models.CASCADE,
        related_name="relazioni_entranti",
    )
    coefficiente = models.FloatField(default=0.0)

    class Meta:
        ordering = ["origine__ordine", "destinazione__ordine"]
        constraints = [
            models.UniqueConstraint(fields=["origine", "destinazione"], name="unique_faction_relation_pair"),
            models.CheckConstraint(
                check=~models.Q(origine=models.F("destinazione")),
                name="faction_relation_not_self",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.origine_id} -> {self.destinazione_id}: {self.coefficiente}"


class EventoReputazione(V2Model):
    MODE_ADJUST = "adjust"
    MODE_SET = "set"
    MODE_CHOICES = [
        (MODE_ADJUST, "Aggiungi o sottrai"),
        (MODE_SET, "Imposta valore"),
    ]

    campagna = models.ForeignKey(
        "core.DatiCampagna",
        on_delete=models.CASCADE,
        related_name="eventi_reputazione",
    )
    titolo = models.CharField(max_length=200, blank=True, default="")
    motivo = models.TextField()
    modalita = models.CharField(max_length=16, choices=MODE_CHOICES, default=MODE_ADJUST)
    # Campaign day the event belongs to. It is the primary replay key, so a
    # back-dated event is inserted where it belongs in the story.
    giorno_campagna = models.IntegerField(default=0)
    # Free narrative time ("Mattino", "14:30"). Display only, never a sort key.
    ora_campagna = models.CharField(max_length=80, blank=True, default="")
    visibile_ai_giocatori = models.BooleanField(default=True)
    registrato_da = models.CharField(max_length=180, blank=True, default="")

    class Meta:
        ordering = ["giorno_campagna", "created_at", "id"]
        indexes = [models.Index(fields=["campagna", "giorno_campagna"])]

    def __str__(self) -> str:
        return self.titolo or self.motivo[:60]


class EffettoEventoReputazione(models.Model):
    """One faction's share of a reputation event.

    ``propagato`` separates what the master authored from what the reaction
    grid added. Propagation is single hop: a propagated effect never seeds
    further propagation.
    """

    evento = models.ForeignKey(
        EventoReputazione,
        on_delete=models.CASCADE,
        related_name="effetti",
    )
    fazione = models.ForeignKey(
        Fazione,
        on_delete=models.CASCADE,
        related_name="effetti_reputazione",
    )
    # Used when the parent event is an adjustment.
    delta = models.IntegerField(default=0)
    # Used when the parent event sets an absolute value.
    valore_assoluto = models.IntegerField(null=True, blank=True)
    propagato = models.BooleanField(default=False)
    ordine = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["ordine", "id"]
        constraints = [
            models.UniqueConstraint(fields=["evento", "fazione"], name="unique_faction_per_reputation_event"),
        ]

    def __str__(self) -> str:
        return f"{self.fazione_id}: {self.delta if self.valore_assoluto is None else self.valore_assoluto}"


class PersonaggioLore(V2Model):
    """Lightweight narrative NPC.

    Deliberately independent from ``characters.Personaggio``: a lore record
    describes who somebody is in the campaign, not their sheet.
    """

    campagna = models.ForeignKey(
        "core.DatiCampagna",
        on_delete=models.CASCADE,
        related_name="lore_personaggi",
    )
    nome = models.CharField(max_length=180)
    ruolo = models.CharField(max_length=160, blank=True, default="")
    descrizione = models.TextField(blank=True, default="")
    ritratto = models.ForeignKey(
        "media_library.UploadedImage",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lore_personaggi_ritratto",
    )
    fazione = models.ForeignKey(
        Fazione,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="personaggi",
    )
    visibile_ai_giocatori = models.BooleanField(default=True)
    ordine = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["ordine", "nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["campagna", "nome"],
                condition=models.Q(archived_at__isnull=True),
                name="unique_lore_character_name_per_campaign",
            ),
        ]
        indexes = [models.Index(fields=["campagna", "ordine"])]

    def __str__(self) -> str:
        return self.nome
