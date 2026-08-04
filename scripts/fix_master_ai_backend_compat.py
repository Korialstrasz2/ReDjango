from pathlib import Path
import re


def sub_once(path: str, pattern: str, replacement: str) -> None:
    file = Path(path)
    content = file.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, replacement, content, count=1, flags=re.MULTILINE)
    if count == 0:
        if replacement.strip() in content:
            return
        raise SystemExit(f"Pattern not found in {path}: {pattern[:100]}")
    file.write_text(updated, encoding="utf-8")


sub_once(
    "backend/ai/master_runtime.py",
    r'(?P<indent>        )mode = resolved_mode\(agent_mode\)\n(?P=indent)if not tool_is_available\(tool, user, giocatore, agent_mode=mode\):\n(?P=indent)    return json\.dumps\(\{"errore": f"Strumento non autorizzato nella modalità \{mode\}: \{name\}"\}, ensure_ascii=False\), True',
    '''        mode = resolved_mode(agent_mode)
        if not tool_is_available(tool, user, giocatore, agent_mode=mode):
            from backend.core.security import effective_role, has_minimum_role

            if not has_minimum_role(effective_role(user, giocatore), tool.minimum_role):
                return json.dumps({"errore": f"Permessi insufficienti per usare lo strumento: {name}"}, ensure_ascii=False), True
            return json.dumps({"errore": f"Strumento non autorizzato nella modalità {mode}: {name}"}, ensure_ascii=False), True''',
)
sub_once(
    "backend/ai/apps.py",
    r'        def ask_assistant\(user, giocatore, payload, \*, budget=None, progress=None\):\n            return original_ask_assistant\(',
    '''        def ask_assistant(user, giocatore, payload, *, budget=None, progress=None):
            if not str((payload or {}).get("message") or "").strip():
                raise ApiError("ai.message_required", "Scrivi una domanda per l'assistente.", "message")
            return original_ask_assistant(''',
)
sub_once(
    "backend/ai/test_question_coverage.py",
    r'    def test_every_tool_is_declared_read_only\(self\):\n        non_read_only = \[tool\.name for tool in AI_TOOLS if not tool\.read_only\]\n        self\.assertEqual\(non_read_only, \[\]\)',
    '''    def test_tool_mutability_is_explicit(self):
        ordinary_non_read_only = [
            tool.name for tool in AI_TOOLS
            if not getattr(tool, "proposal_only", False) and not tool.read_only
        ]
        proposal_declared_read_only = [
            tool.name for tool in AI_TOOLS
            if getattr(tool, "proposal_only", False) and tool.read_only
        ]
        self.assertEqual(ordinary_non_read_only, [])
        self.assertEqual(proposal_declared_read_only, [])''',
)
sub_once(
    "backend/ai/tests.py",
    r'        failures = \[\]\n        for tool in AI_TOOLS:\n            kwargs = required_arguments\.get\(tool\.name, \{\}\)\n            try:\n                tool\.run\(self\.user, self\.giocatore, \*\*kwargs\)',
    '''        failures = []
        for tool in AI_TOOLS:
            if getattr(tool, "proposal_only", False):
                continue
            kwargs = required_arguments.get(tool.name, {})
            try:
                tool.run(self.user, self.giocatore, **kwargs)''',
)
