from django.db import models

from backend.core.models import Giocatore, V2Model

from .crypto import decrypt_secret, encrypt_secret


class AIProvider(V2Model):
    """Un endpoint configurato per la chat o per le immagini.

    Il segreto vive solo in `secret_ciphertext`, cifrato a riposo, e non entra mai
    in un payload dell'API: l'interfaccia riceve soltanto `hasSecret`.

    `auth_strategy` esiste perché oggi l'unica via praticabile per un'applicazione
    multiutente è la chiave API. Se un provider pubblicherà un flusso device-code
    utilizzabile da terze parti, diventerà una nuova strategia e non una riscrittura.
    """

    PURPOSE_CHAT = "chat"
    PURPOSE_IMAGE = "image"
    PURPOSE_CHOICES = [
        (PURPOSE_CHAT, "Chat"),
        (PURPOSE_IMAGE, "Immagini"),
    ]

    KIND_ANTHROPIC = "anthropic"
    KIND_OPENAI_RESPONSES = "openai_responses"
    KIND_OPENAI_COMPATIBLE = "openai_compatible"
    KIND_OPENAI_IMAGE = "openai_image"
    KIND_STABLE_DIFFUSION = "stable_diffusion"
    KIND_CHOICES = [
        (KIND_ANTHROPIC, "Anthropic Messages"),
        (KIND_OPENAI_RESPONSES, "OpenAI Responses"),
        (KIND_OPENAI_COMPATIBLE, "Compatibile OpenAI"),
        (KIND_OPENAI_IMAGE, "Immagini OpenAI"),
        (KIND_STABLE_DIFFUSION, "Stable Diffusion locale"),
    ]

    AUTH_API_KEY = "api_key"
    AUTH_NONE = "none"
    AUTH_CHOICES = [
        (AUTH_API_KEY, "Chiave API"),
        (AUTH_NONE, "Nessuna autenticazione"),
    ]

    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=120, unique=True)
    purpose = models.CharField(max_length=16, choices=PURPOSE_CHOICES, default=PURPOSE_CHAT)
    kind = models.CharField(max_length=32, choices=KIND_CHOICES, default=KIND_ANTHROPIC)
    auth_strategy = models.CharField(max_length=32, choices=AUTH_CHOICES, default=AUTH_API_KEY)
    base_url = models.CharField(max_length=300, blank=True)
    model = models.CharField(max_length=160, blank=True)
    secret_ciphertext = models.TextField(blank=True, editable=False)
    options = models.JSONField(default=dict, blank=True)
    is_enabled = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["purpose", "order", "name"]
        verbose_name = "provider AI"
        verbose_name_plural = "provider AI"
        indexes = [models.Index(fields=["purpose", "is_enabled", "order"])]

    def __str__(self) -> str:
        return f"{self.name} ({self.get_purpose_display()})"

    @property
    def has_secret(self) -> bool:
        return bool(self.secret_ciphertext)

    def set_secret(self, value: str) -> None:
        self.secret_ciphertext = encrypt_secret(str(value or "").strip())

    def read_secret(self) -> str:
        return decrypt_secret(self.secret_ciphertext)


class AIAgentProfile(V2Model):
    """Policy configurabile per un agente di sola lettura."""

    ROUTING_OFF = "off"
    ROUTING_AUTO = "auto"
    ROUTING_CHOICES = [
        (ROUTING_OFF, "Disattivato"),
        (ROUTING_AUTO, "Automatico"),
    ]

    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    instructions = models.TextField(blank=True)
    minimum_role = models.CharField(
        max_length=20,
        choices=Giocatore.ROLE_CHOICES,
        default=Giocatore.ROLE_USER,
    )
    provider = models.ForeignKey(
        AIProvider,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="agent_profiles",
        limit_choices_to={"purpose": AIProvider.PURPOSE_CHAT},
    )
    allowed_tools = models.JSONField(default=list, blank=True)
    max_iterations = models.PositiveSmallIntegerField(default=6)
    routing_mode = models.CharField(
        max_length=8,
        choices=ROUTING_CHOICES,
        default=ROUTING_AUTO,
        help_text="Con «Automatico», una domanda con molti strumenti disponibili viene prima instradata a un sottoinsieme pertinente.",
    )
    is_enabled = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]
        verbose_name = "profilo agente AI"
        verbose_name_plural = "profili agente AI"
        indexes = [models.Index(fields=["is_enabled", "minimum_role", "order"])]

    def __str__(self) -> str:
        return self.name
