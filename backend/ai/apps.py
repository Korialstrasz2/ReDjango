from collections import defaultdict

from django.apps import AppConfig


_READY_INSTALLED = False


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
        from . import selectors, services, tools

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
