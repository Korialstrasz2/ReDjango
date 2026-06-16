# AGENTS.md

This project is **ReDjango**, a minimum usable rebuild seed for **The Elder Django**.

## Origin

ReDjango was created from the rebuild analysis of the original project at:

```text
C:\Users\alexo\PycharmProjects\firstDjango\the_elder_django
```

The original project, usually called `the_elder_django`, is a large Django tabletop/game-master workstation with characters, combat, items, inventory, maps, lore, shops, crafting, AI tools, media, and orchestration features. ReDjango is not a direct copy. It is the clean rebuild seed where those features should be reintroduced gradually, deliberately, and with stronger architecture.

Treat the original project as historical context and a source of data/domain knowledge. Do not mutate the original project from inside ReDjango work unless the user explicitly asks for that.

## First Documents To Read

Before changing code or creating content in this repository, read:

1. `README.md` for the current runnable project shape.
2. `best_build_practices.md` for architecture, naming, UI, API, and content conventions.

If the original project is available, the most important context file is:

```text
C:\Users\alexo\PycharmProjects\firstDjango\the_elder_django\REBUILD_ANALYSIS_AND_GUIDE.md
```

That file explains why ReDjango should stay database-preserving, modular, single-page-oriented, and API-driven.

## Current Philosophy

ReDjango must stay small, coherent, and resource efficient while it grows.

- Django remains the source of truth.
- The frontend remains a single-page application served by Django.
- Backend/frontend communication should converge on one consistent AJAX contract.
- Features should be added as clean vertical slices: model, service/selector, API action, frontend component, and minimal verification.
- UI components must be identifiable by `componentType` and `theme` so global visual rules can be applied consistently.
- Avoid copying the old monolith shape. Rebuild features through services, selectors, typed payloads, and reusable UI patterns.

## Working Rules For Agents

- Read before editing. Preserve the structure already present unless there is a clear reason to improve it.
- Keep changes scoped. Do not port large original systems in one pass.
- Prefer additive migrations and import scripts over destructive database changes.
- Keep one-page navigation: add views/panels to the app shell instead of adding unrelated template pages.
- Use `best_build_practices.md` as the local law for naming, component structure, API shape, content creation, and folder placement.
- Update the practices document when a new convention becomes real and repeated.

## Run Command

Use:

```bat
start_server.bat
```

The project should run at:

```text
http://127.0.0.1:8003/
```
