from __future__ import annotations

from django.db import transaction

from backend.core.api import ApiError

from ..models import NOTE_SECTION_FIELDS, Note, Personaggio


MAX_SECTION_LENGTH = 30000


@transaction.atomic
def update_note_section(personaggio_id: int, section: str, content: str) -> Personaggio:
    if section not in NOTE_SECTION_FIELDS:
        raise ApiError("notes.invalid_section", "La sezione delle note non è valida.", "section")

    content = str(content)
    if len(content) > MAX_SECTION_LENGTH:
        raise ApiError(
            "notes.section_too_long",
            f"La sezione non può superare {MAX_SECTION_LENGTH:,} caratteri.".replace(",", "."),
            "content",
        )

    try:
        personaggio = Personaggio.objects.select_for_update().select_related("note").get(pk=personaggio_id)
    except Personaggio.DoesNotExist as exc:
        raise ApiError("character.not_found", "Personaggio non trovato.", status=404) from exc

    note = personaggio.note
    if note is None:
        note = Note.objects.create(nome=f"Note di {personaggio.nome}")
        personaggio.note = note
        personaggio.save(update_fields=["note", "updated_at"])
    else:
        note = Note.objects.select_for_update().get(pk=note.pk)

    if getattr(note, section) != content:
        setattr(note, section, content)
        note.save(update_fields=[section, "updated_at"])
    personaggio.note = note
    return personaggio
