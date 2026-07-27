from .models import NOTE_SECTION_FIELDS, Note, Personaggio


def note_sections_payload(note: Note | None) -> dict[str, str]:
    return {
        section: getattr(note, section, "") if note else ""
        for section in NOTE_SECTION_FIELDS
    }


def character_notes_payload(personaggio: Personaggio) -> dict:
    note = personaggio.note
    return {
        "characterId": personaggio.id,
        "characterName": personaggio.nome,
        "noteId": note.id if note else None,
        "sections": note_sections_payload(note),
        "updatedAt": note.updated_at.isoformat() if note and note.updated_at else None,
    }
