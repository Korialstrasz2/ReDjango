# ReDjango

A minimum usable rebuild seed for **The Elder Django**.

This project is intentionally small: Django + SQLite, a single-page vanilla JavaScript frontend, and a few clean backend apps. It is meant to be a safe starting point, not a full port of the original monolith.

## What Is Included

- Basic Django 5.2 project using SQLite.
- Single-page app served by Django at `/`.
- Main menu with Dashboard, Characters, and Media Vault sections.
- Character menu with create, select, edit, and delete flows.
- Per-user media database records with local file copies under `media/user_media/`.
- JSON endpoints under `/api/`.
- Organized backend and frontend folders.
- `start_server.bat` for launching on `0.0.0.0:8003`.

## Project Layout

```text
ReDjango/
  manage.py
  requirements.txt
  start_server.bat
  redjango/                 Django project settings and URLs
  backend/
    core/                   SPA shell, health/bootstrap, seed command
    characters/             Character database and JSON API
    media_library/          User-owned media records and uploads
  frontend/
    templates/              Single HTML shell
    static/frontend/        CSS and vanilla JS modules
  media/                    Runtime uploaded media
```

## Quick Start

Run from this folder:

```bat
start_server.bat
```

Then open:

```text
http://127.0.0.1:8003/
```

The batch file uses an existing Python environment when Django is available. If Django is missing, it creates `.venv`, installs `requirements.txt`, runs migrations, seeds a local user and sample characters, then starts Django at `0.0.0.0:8003`.

## API Sketch

```text
GET    /api/health/
GET    /api/bootstrap/
GET    /api/characters/
POST   /api/characters/
GET    /api/characters/<id>/
PATCH  /api/characters/<id>/
DELETE /api/characters/<id>/
GET    /api/media/
POST   /api/media/
GET    /api/media/<id>/
DELETE /api/media/<id>/
```

All unauthenticated local use is assigned to a lightweight `local_master` user. If you later add login, the same models already support normal Django users.

## Next Good Steps

- Import selected read-only data from the original database through explicit scripts.
- Add an `/api/v1/` namespace once the first real feature slice settles.
- Add typed DTOs before porting larger systems like inventory, skills, and combat.
- Keep old media and database imports additive; do not mutate the original project directly.

