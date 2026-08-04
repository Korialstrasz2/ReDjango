from collections import Counter, defaultdict
import logging
from time import monotonic

from django.apps import AppConfig


_READY_INSTALLED = False
logger = logging.getLogger("backend.ai.master_ai")


class AiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.ai"
    verbose_name = "Intelligenza artificiale"

    def ready(self) -> None:
        global _READY_INSTALLED
        if _READY_INSTALLED:
            return
        _READY_INSTALLED = True

        from .master_runtime import install

        install()

        # The original modules import these registry objects by name. Rebind the
        # expanded registry after installation so agent validation and selector
        # serialization see proposal tools as well as read-only tools.
        from . import execution, selectors, services, tools

        services.AI_TOOLS_BY_NAME = tools.AI_TOOLS_BY_NAME
        original_serialize_agent = selectors.serialize_agent

        def serialize_agent(agent, user, giocatore, *, management=False):
            payload = original_serialize_agent(agent, user, giocatore, management=management)
            configured = set(agent.allowed_tools if isinstance(agent.allowed_tools, list) else [])
            payload["toolNames"] = [
                tool.name
                for tool in tools.AI_TOOLS
                if tool.name in configured
                and selectors.tool_is_available(tool, user, giocatore, agent_mode=agent.mode)
            ]
            return payload

        selectors.serialize_agent = serialize_agent

        # Skill and Spell are two public entity names for the same authoring root.
        # Cross-operation checks therefore share their target and name namespace.
        from .changes import services as change_services
        from .models import AIChangeOperation

        def root_entity(entity_type: str) -> str:
            return "skill" if entity_type in {"skill", "spell"} else entity_type

        def append_error(operation, error):
            errors = list(operation.validation_errors or [])
            errors.append(error)
            operation.validation_errors = errors
            operation.status = AIChangeOperation.STATUS_INVALID

        def cross_operation_checks(operations):
            target_groups = defaultdict(list)
            create_names = defaultdict(list)
            for operation in operations:
                if not operation.selected:
                    continue
                root = root_entity(operation.entity_type)
                if operation.action in {AIChangeOperation.ACTION_UPDATE, AIChangeOperation.ACTION_ARCHIVE} and operation.target_id:
                    target_groups[(root, operation.target_id)].append(operation)
                if operation.action == AIChangeOperation.ACTION_CREATE:
                    values = operation.effective_values
                    name = str(values.get("name") or values.get("nome") or "").strip().casefold()
                    if name:
                        create_names[(root, name)].append(operation)
            for group in target_groups.values():
                if len(group) > 1:
                    for operation in group:
                        append_error(
                            operation,
                            {"code": "ai.change_target_conflict", "message": "Più operazioni selezionate agiscono sullo stesso record."},
                        )
            for group in create_names.values():
                if len(group) > 1:
                    for operation in group:
                        append_error(
                            operation,
                            {
                                "code": "ai.change_create_name_conflict",
                                "message": "Due creazioni selezionate usano lo stesso nome.",
                                "field": "name" if operation.entity_type in {"skill", "spell", "theme"} else "nome",
                            },
                        )

        change_services._cross_operation_checks = cross_operation_checks

        # Preserve the current domain rule during dry validation: a default
        # Theme cannot be deactivated before another Theme becomes the default.
        from backend.core.api import ApiError

        from .changes.handlers.theme import ThemeChangeHandler

        original_theme_validate = ThemeChangeHandler._validate_values

        def validate_theme_values(handler, values, *, instance):
            if instance is not None and instance.is_default and "isActive" in values and not bool(values.get("isActive")):
                raise ApiError(
                    "management.themes.default_must_stay_active",
                    "Il tema predefinito deve restare attivo: designane un altro come predefinito prima di disattivarlo.",
                    "isActive",
                )
            return original_theme_validate(handler, values, instance=instance)

        ThemeChangeHandler._validate_values = validate_theme_values

        # Contextual launch parameters are hints only. Validate them before they
        # enter a run or proposal, then let normal handlers/tools resolve the data
        # again. This prevents a URL or raw payload from becoming an authorization
        # shortcut.
        from backend.core.security import get_or_create_giocatore_for_user

        from .changes.context import validate_change_context

        def sanitized_payload(user, giocatore, payload):
            safe = dict(payload or {})
            safe["context"] = validate_change_context(user, giocatore, safe.get("context"))
            return safe

        original_start_chat_run = execution.start_chat_run

        def start_chat_run(user, giocatore, payload):
            return original_start_chat_run(user, giocatore, sanitized_payload(user, giocatore, payload))

        execution.start_chat_run = start_chat_run

        original_ask_assistant = services.ask_assistant

        def ask_assistant(user, giocatore, payload, *, budget=None, progress=None):
            if not str((payload or {}).get("message") or "").strip():
                raise ApiError("ai.message_required", "Scrivi una domanda per l'assistente.", "message")
            return original_ask_assistant(
                user,
                giocatore,
                sanitized_payload(user, giocatore, payload),
                budget=budget,
                progress=progress,
            )

        services.ask_assistant = ask_assistant
        execution.ask_assistant = ask_assistant

        original_create_change_set = change_services.create_change_set

        def create_change_set(user, giocatore, **kwargs):
            kwargs["context"] = validate_change_context(user, giocatore, kwargs.get("context"))
            return original_create_change_set(user, giocatore, **kwargs)

        change_services.create_change_set = create_change_set

        original_update_change_set = change_services.update_change_set

        def update_change_set(user, change_set_id, values):
            safe_values = dict(values or {})
            if "context" in safe_values:
                giocatore = get_or_create_giocatore_for_user(user)
                safe_values["context"] = validate_change_context(user, giocatore, safe_values.get("context"))
            return original_update_change_set(user, change_set_id, safe_values)

        change_services.update_change_set = update_change_set

        # Operational logs intentionally contain IDs, counts, outcomes and
        # duration only. Prompts, snapshots, descriptions, values and secrets are
        # never emitted.
        def operation_counts(change_set):
            counts = Counter(
                f"{operation.entity_type}:{operation.action}"
                for operation in change_set.operations.all()
                if operation.selected
            )
            return dict(sorted(counts.items()))

        original_validate_change_set = change_services.validate_change_set

        def validate_change_set(user, giocatore, change_set_id):
            started = monotonic()
            try:
                change_set = original_validate_change_set(user, giocatore, change_set_id)
            except ApiError as error:
                logger.warning(
                    "master_ai_validation_failed",
                    extra={
                        "change_set_id": str(change_set_id),
                        "user_id": user.id,
                        "error_code": error.code,
                        "duration_ms": round((monotonic() - started) * 1000),
                    },
                )
                raise
            logger.info(
                "master_ai_validation_completed",
                extra={
                    "change_set_id": str(change_set.id),
                    "user_id": user.id,
                    "agent_id": change_set.agent_id,
                    "status": change_set.status,
                    "operation_counts": operation_counts(change_set),
                    "error_count": int((change_set.validation_summary or {}).get("errorCount", 0)),
                    "warning_count": int((change_set.validation_summary or {}).get("warningCount", 0)),
                    "duration_ms": round((monotonic() - started) * 1000),
                },
            )
            return change_set

        change_services.validate_change_set = validate_change_set

        original_apply_change_set = change_services.apply_change_set

        def apply_change_set(user, giocatore, change_set_id, token):
            started = monotonic()
            try:
                change_set = original_apply_change_set(user, giocatore, change_set_id, token)
            except ApiError as error:
                logger.warning(
                    "master_ai_apply_failed",
                    extra={
                        "change_set_id": str(change_set_id),
                        "user_id": user.id,
                        "error_code": error.code,
                        "stale_conflict": error.status == 409 and "stale" in error.code,
                        "duration_ms": round((monotonic() - started) * 1000),
                    },
                )
                raise
            logger.info(
                "master_ai_apply_completed",
                extra={
                    "change_set_id": str(change_set.id),
                    "user_id": user.id,
                    "agent_id": change_set.agent_id,
                    "operation_counts": operation_counts(change_set),
                    "duration_ms": round((monotonic() - started) * 1000),
                },
            )
            return change_set

        change_services.apply_change_set = apply_change_set

        original_discard_change_set = change_services.discard_change_set

        def discard_change_set(user, change_set_id):
            change_set = original_discard_change_set(user, change_set_id)
            logger.info(
                "master_ai_proposal_discarded",
                extra={
                    "change_set_id": str(change_set.id),
                    "user_id": user.id,
                    "agent_id": change_set.agent_id,
                    "operation_counts": operation_counts(change_set),
                },
            )
            return change_set

        change_services.discard_change_set = discard_change_set

        # Views import service callables by name. Rebind them so manual API calls
        # receive the same context validation and safe operational logging as the
        # agent runtime.
        from . import change_views

        change_views.create_change_set = create_change_set
        change_views.update_change_set = update_change_set
        change_views.validate_change_set = validate_change_set
        change_views.apply_change_set = apply_change_set
        change_views.discard_change_set = discard_change_set
