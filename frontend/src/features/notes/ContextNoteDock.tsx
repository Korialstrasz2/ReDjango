import { useState } from "react";
import { createPortal } from "react-dom";

import { Modal } from "../../components/Modal";
import { useResponsiveLayout } from "../../lib/responsive";
import type { NoteSection } from "../../lib/types";
import { NOTE_SECTIONS, NoteSectionEditor } from "./NoteSectionEditor";

type Props = {
  characterId: number;
  characterName: string;
  section: NoteSection;
  notify: (message: string, kind?: "success" | "error" | "info") => void;
};

export function ContextNoteDock({ characterId, characterName, section, notify }: Props) {
  const { isPhone } = useResponsiveLayout();
  const [hovered, setHovered] = useState(false);
  const [focused, setFocused] = useState(false);
  const [pinned, setPinned] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const definition = NOTE_SECTIONS.find((entry) => entry.id === section)!;
  const open = hovered || focused || pinned;

  if (isPhone) {
    return createPortal(
      <section
        className="mobile-context-note"
        data-component-type="context-note"
        data-theme="parchment"
        data-note-section={section}
      >
        <button
          type="button"
          className="mobile-context-note-trigger"
          aria-label={`Note della pagina: ${definition.label}`}
          aria-expanded={mobileOpen}
          onClick={() => setMobileOpen(true)}
        >
          <span aria-hidden="true">{definition.glyph}</span>
          <strong>{definition.label}</strong>
        </button>
        {mobileOpen && <Modal
          title={`Note ${definition.label}`}
          onClose={() => setMobileOpen(false)}
          responsiveMode="sheet"
          closeOnBackdrop={false}
          className="mobile-context-note-modal"
        >
          <div className="mobile-context-note-sheet">
            <header>
              <p className="eyebrow">{characterName}</p>
              <p>{definition.description}</p>
            </header>
            <NoteSectionEditor
              characterId={characterId}
              section={section}
              notify={notify}
              rows={14}
              compact
              minimal
            />
          </div>
        </Modal>}
      </section>,
      document.body,
    );
  }

  return <section
    className={`context-note-dock ${open ? "is-open" : ""} ${pinned ? "is-pinned" : ""}`}
    data-component-type="context-note"
    data-theme="parchment"
    data-note-section={section}
    onMouseEnter={() => setHovered(true)}
    onMouseLeave={() => setHovered(false)}
    onFocus={() => setFocused(true)}
    onBlur={(event) => {
      if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setFocused(false);
    }}
  >
    <button
      type="button"
      className="context-note-trigger"
      aria-label={`Note della pagina: ${definition.label}`}
      aria-expanded={open}
      aria-pressed={pinned}
      onClick={() => setPinned((current) => !current)}
    >
      <span aria-hidden="true">{definition.glyph}</span>
      <span><small>Note della pagina</small><strong>{definition.label}</strong></span>
      <em aria-hidden="true">{pinned ? "●" : "○"}</em>
    </button>
    <aside className="context-note-flyout" aria-label={`Note ${definition.label} di ${characterName}`} aria-hidden={!open} inert={!open}>
      <header>
        <div><p className="eyebrow">{characterName}</p><h2>{definition.label}</h2></div>
        <span>{pinned ? "Fissata" : "Anteprima"}</span>
      </header>
      <NoteSectionEditor characterId={characterId} section={section} notify={notify} rows={10} compact minimal />
    </aside>
  </section>;
}
