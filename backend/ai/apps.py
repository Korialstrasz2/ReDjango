from django.apps import AppConfig


class AiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.ai"
    verbose_name = "Intelligenza artificiale"

    def ready(self) -> None:
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
