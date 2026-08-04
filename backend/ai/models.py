import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q

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
    model_catalog = models.JSONField(default=list, blank=True)
    model_catalog_refreshed_at = models.DateTimeField(null=True, blank=True)
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
        constraints = [
            models.UniqueConstraint(
                fields=["purpose", "is_default"],
                condition=Q(is_default=True, archived_at__isnull=True),
                name="ai_one_default_provider_per_purpose",
            ),
        ]

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
    """Policy configurabile per un agente AI."""

    MODE_READ_ONLY = "read_only"
    MODE_PROPOSER = "proposer"
    MODE_CHOICES = [
        (MODE_READ_ONLY, "Sola lettura"),
        (MODE_PROPOSER, "Proposte di modifica"),
    ]

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
    mode = models.CharField(max_length=16, choices=MODE_CHOICES, default=MODE_READ_ONLY)
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
        constraints = [
            models.UniqueConstraint(
                fields=["is_default"],
                condition=Q(is_default=True, archived_at__isnull=True),
                name="ai_one_default_agent",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class AIConversation(V2Model):
    """Una delle tre conversazioni recenti conservate per account."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ai_conversations",
    )
    agent = models.ForeignKey(
        AIAgentProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="conversations",
    )
    title = models.CharField(max_length=120)
    history = models.JSONField(default=list, blank=True)
    transcript = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["-updated_at", "-id"]
        indexes = [models.Index(fields=["user", "-updated_at"])]
        verbose_name = "conversazione AI"
        verbose_name_plural = "conversazioni AI"

    def __str__(self) -> str:
        return f"{self.user}: {self.title}"


class AIExecutionRun(V2Model):
    """Stato transitorio di una richiesta AI eseguita fuori dal ciclo HTTP."""

    KIND_CHAT = "chat"
    KIND_IMAGE = "image"
    KIND_CHOICES = [(KIND_CHAT, "Chat"), (KIND_IMAGE, "Immagine")]

    STATUS_QUEUED = "queued"
    STATUS_RUNNING = "running"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_QUEUED, "In coda"),
        (STATUS_RUNNING, "In esecuzione"),
        (STATUS_COMPLETED, "Completata"),
        (STATUS_FAILED, "Non riuscita"),
        (STATUS_CANCELLED, "Annullata"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ai_execution_runs",
    )
    conversation = models.ForeignKey(
        AIConversation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="runs",
    )
    agent = models.ForeignKey(
        AIAgentProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="runs",
    )
    provider = models.ForeignKey(
        AIProvider,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="runs",
    )
    kind = models.CharField(max_length=12, choices=KIND_CHOICES)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_QUEUED)
    progress = models.CharField(max_length=180, blank=True)
    request_payload = models.JSONField(default=dict, blank=True)
    result = models.JSONField(default=dict, blank=True)
    error = models.JSONField(default=dict, blank=True)
    cancel_requested = models.BooleanField(default=False)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    tool_calls = models.PositiveSmallIntegerField(default=0)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status", "-created_at"]),
            models.Index(fields=["status", "created_at"]),
        ]
        verbose_name = "esecuzione AI"
        verbose_name_plural = "esecuzioni AI"
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=Q(status__in=["queued", "running"], archived_at__isnull=True),
                name="ai_one_active_run_per_user",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.kind} {self.id} · {self.status}"


class AIChangeSet(V2Model):
    STATUS_DRAFT = "draft"
    STATUS_READY = "ready"
    STATUS_APPLIED = "applied"
    STATUS_DISCARDED = "discarded"
    STATUS_EXPIRED = "expired"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Bozza"),
        (STATUS_READY, "Pronta"),
        (STATUS_APPLIED, "Applicata"),
        (STATUS_DISCARDED, "Scartata"),
        (STATUS_EXPIRED, "Scaduta"),
    ]
    EDITABLE_STATUSES = {STATUS_DRAFT, STATUS_READY}
    IMMUTABLE_STATUSES = {STATUS_APPLIED, STATUS_DISCARDED, STATUS_EXPIRED}

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ai_change_sets",
    )
    conversation = models.ForeignKey(
        AIConversation,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="change_sets",
    )
    agent = models.ForeignKey(
        AIAgentProfile,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="change_sets",
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    title = models.CharField(max_length=160, blank=True)
    request_text = models.TextField(blank=True)
    context = models.JSONField(default=dict, blank=True)
    revision = models.PositiveIntegerField(default=1)
    validation_summary = models.JSONField(default=dict, blank=True)
    validation_token = models.TextField(blank=True)
    validated_at = models.DateTimeField(null=True, blank=True)
    applied_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="applied_ai_change_sets",
    )
    applied_at = models.DateTimeField(null=True, blank=True)
    discarded_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "proposta AI"
        verbose_name_plural = "proposte AI"
        indexes = [
            models.Index(fields=["user", "status", "-updated_at"], name="ai_changeset_user_status_idx"),
            models.Index(fields=["conversation", "status"], name="ai_changeset_conversation_idx"),
            models.Index(fields=["status", "expires_at"], name="ai_changeset_expiry_idx"),
        ]

    def __str__(self) -> str:
        return self.title or f"Proposta {self.id}"


class AIChangeOperation(V2Model):
    ACTION_CREATE = "create"
    ACTION_UPDATE = "update"
    ACTION_ARCHIVE = "archive"
    ACTION_CHOICES = [
        (ACTION_CREATE, "Crea"),
        (ACTION_UPDATE, "Modifica"),
        (ACTION_ARCHIVE, "Archivia"),
    ]

    STATUS_PROPOSED = "proposed"
    STATUS_VALID = "valid"
    STATUS_INVALID = "invalid"
    STATUS_APPLIED = "applied"
    STATUS_SKIPPED = "skipped"
    STATUS_CHOICES = [
        (STATUS_PROPOSED, "Proposta"),
        (STATUS_VALID, "Valida"),
        (STATUS_INVALID, "Non valida"),
        (STATUS_APPLIED, "Applicata"),
        (STATUS_SKIPPED, "Saltata"),
    ]

    change_set = models.ForeignKey(
        AIChangeSet,
        on_delete=models.CASCADE,
        related_name="operations",
    )
    position = models.PositiveSmallIntegerField(default=0)
    entity_type = models.CharField(max_length=32)
    action = models.CharField(max_length=16, choices=ACTION_CHOICES)
    target_id = models.PositiveBigIntegerField(null=True, blank=True)
    source_id = models.PositiveBigIntegerField(null=True, blank=True)
    display_label = models.CharField(max_length=200, blank=True)
    selected = models.BooleanField(default=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PROPOSED)
    original_snapshot = models.JSONField(default=dict, blank=True)
    proposed_values = models.JSONField(default=dict, blank=True)
    edited_values = models.JSONField(default=dict, blank=True)
    field_schema = models.JSONField(default=list, blank=True)
    base_updated_at = models.DateTimeField(null=True, blank=True)
    base_digest = models.CharField(max_length=64, blank=True)
    validation_errors = models.JSONField(default=list, blank=True)
    validation_warnings = models.JSONField(default=list, blank=True)
    application_result = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["position", "id"]
        verbose_name = "operazione proposta AI"
        verbose_name_plural = "operazioni proposte AI"
        constraints = [
            models.UniqueConstraint(
                fields=["change_set", "position"],
                name="ai_change_operation_unique_position",
            ),
            models.CheckConstraint(
                condition=Q(action__in=["create", "update", "archive"]),
                name="ai_change_operation_valid_action",
            ),
            models.CheckConstraint(
                condition=(
                    Q(action="create", target_id__isnull=True)
                    | Q(action__in=["update", "archive"], target_id__isnull=False)
                ),
                name="ai_change_operation_target_shape",
            ),
        ]

    @property
    def effective_values(self) -> dict:
        if isinstance(self.edited_values, dict) and self.edited_values:
            return self.edited_values
        return self.proposed_values if isinstance(self.proposed_values, dict) else {}

    def __str__(self) -> str:
        return f"{self.change_set_id} · {self.position} · {self.entity_type}:{self.action}"
