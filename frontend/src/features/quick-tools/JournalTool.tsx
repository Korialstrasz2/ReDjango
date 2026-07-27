import { useEffect, useState } from "react";

import type { CampaignData, NoteSection } from "../../lib/types";
import { CampaignSharedNoteEditor } from "../notes/CampaignSharedNoteEditor";
import { NOTE_SECTIONS, NoteSectionEditor } from "../notes/NoteSectionEditor";

type JournalSection = NoteSection | "condivise";
const JOURNAL_SECTIONS = [
  ...NOTE_SECTIONS,
  { id: "condivise" as const, label: "Condivise", description: "Note comuni alla campagna selezionata.", glyph: "◎" },
];

type Props = { characterId: number | null; campaign: CampaignData | null; notify: (message: string, kind?: "success" | "error" | "info") => void };

export function JournalTool({ characterId, campaign, notify }: Props) {
  const [section, setSection] = useState<JournalSection>(characterId ? "appunti" : "condivise");
  useEffect(() => {
    if (!characterId && campaign) setSection("condivise");
  }, [campaign, characterId]);

  if (!characterId && !campaign) return <div className="journal-empty"><span aria-hidden="true">⌑</span><h3>Scegli una campagna</h3><p>Il diario condiviso segue la campagna selezionata.</p></div>;

  return <div className="journal-tool" data-component-type="panel" data-theme="parchment">
    <aside className="journal-sections" aria-label="Sezioni del diario">
      {JOURNAL_SECTIONS.map((entry) => <button type="button" key={entry.id} disabled={entry.id !== "condivise" && !characterId} className={section === entry.id ? "active" : ""} onClick={() => setSection(entry.id)} aria-pressed={section === entry.id}>
        <span aria-hidden="true">{entry.glyph}</span><strong>{entry.label}</strong>
      </button>)}
    </aside>
    <section className="journal-book">
      <div className="journal-page-heading">
        <span aria-hidden="true">{JOURNAL_SECTIONS.find((entry) => entry.id === section)?.glyph}</span>
        <div><p className="eyebrow">Diario di viaggio</p><h2>{JOURNAL_SECTIONS.find((entry) => entry.id === section)?.label}</h2></div>
      </div>
      {section === "condivise" && campaign
        ? <CampaignSharedNoteEditor key={campaign.id} campaign={campaign} notify={notify} rows={22} />
        : characterId && <NoteSectionEditor key={section} characterId={characterId} section={section as NoteSection} notify={notify} rows={22} minimal />}
    </section>
  </div>;
}
