import { useEffect, useState } from "react";

import { matchesShortcut, quickToolShortcutTargets, shortcutValue } from "../../lib/shortcuts";
import type { CampaignData, SettingsData } from "../../lib/types";
import { AITool } from "../ai/AITool";
import { AudioMiniPlayer } from "../audio/AudioMiniPlayer";
import { AudioTool } from "../audio/AudioTool";
import { CampaignStatus } from "../campaign/CampaignStatus";
import { DiceTool } from "./DiceTool";
import { JournalTool } from "./JournalTool";
import { NameTool } from "./NameTool";
import { TheftTool } from "./TheftTool";
import { ToolDrawer } from "./ToolDrawer";

type Tool = "journal" | "dice" | "theft" | "audio" | "ai" | "names" | null;

type Props = {
  characterId: number | null;
  characterName: string;
  campaign: CampaignData | null;
  settings: SettingsData;
  notify: (message: string, kind?: "success" | "error" | "info") => void;
};

export function QuickTools({ characterId, characterName, campaign, settings, notify }: Props) {
  const [tool, setTool] = useState<Tool>(null);
  const journalShortcut = shortcutValue(settings.ui, "journal");
  const diceShortcut = shortcutValue(settings.ui, "dice");
  const theftShortcut = shortcutValue(settings.ui, "theft");
  const audioShortcut = shortcutValue(settings.ui, "audio");
  const aiShortcut = shortcutValue(settings.ui, "ai");
  const namesShortcut = shortcutValue(settings.ui, "names");
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.repeat) return;
      const target = quickToolShortcutTargets.find((entry) => matchesShortcut(event, shortcutValue(settings.ui, entry)));
      if (!target) return;
      event.preventDefault();
      // La stessa combinazione apre e richiude lo strumento.
      setTool((current) => (current === target ? null : target));
    };
    window.addEventListener("keydown", onKeyDown, true);
    return () => window.removeEventListener("keydown", onKeyDown, true);
  }, [settings.ui]);
  return <>
    <div className="quick-tools-bar" aria-label="Strumenti rapidi" data-component-type="toolbar" data-theme="dark">
      <CampaignStatus campaign={campaign} settings={settings} notify={notify} />
      <AudioMiniPlayer onOpen={() => setTool("audio")} />
      <div className="quick-tools-actions">
        <span>Strumenti rapidi</span>
        <button type="button" className={tool === "journal" ? "active" : ""} onClick={() => setTool((current) => current === "journal" ? null : "journal")} aria-expanded={tool === "journal"} aria-keyshortcuts={journalShortcut || undefined} title={journalShortcut ? `Diario (${journalShortcut.replace("+", " + ")})` : "Diario"}>
          <span aria-hidden="true">⌑</span><strong>Diario</strong>
        </button>
        <button type="button" className={tool === "dice" ? "active" : ""} onClick={() => setTool((current) => current === "dice" ? null : "dice")} aria-expanded={tool === "dice"} aria-keyshortcuts={diceShortcut || undefined} title={diceShortcut ? `Dadi (${diceShortcut.replace("+", " + ")})` : "Dadi"}>
          <span aria-hidden="true">◆</span><strong>Dadi</strong>
        </button>
        <button type="button" className={tool === "ai" ? "active" : ""} onClick={() => setTool((current) => current === "ai" ? null : "ai")} aria-expanded={tool === "ai"} aria-keyshortcuts={aiShortcut || undefined} title={aiShortcut ? `AI (${aiShortcut.replace("+", " + ")})` : "AI"}>
          <span aria-hidden="true">✳</span><strong>AI</strong>
        </button>
        <button type="button" className={tool === "audio" ? "active" : ""} onClick={() => setTool((current) => current === "audio" ? null : "audio")} aria-expanded={tool === "audio"} aria-keyshortcuts={audioShortcut || undefined} title={audioShortcut ? `Audio (${audioShortcut.replace("+", " + ")})` : "Audio"}>
          <span aria-hidden="true">♪</span><strong>Audio</strong>
        </button>
        <button type="button" className={tool === "theft" ? "active" : ""} onClick={() => setTool((current) => current === "theft" ? null : "theft")} aria-expanded={tool === "theft"} aria-keyshortcuts={theftShortcut || undefined} title={theftShortcut ? `Furto (${theftShortcut.replace("+", " + ")})` : "Furto"}>
          <span aria-hidden="true">⚿</span><strong>Furto</strong>
        </button>
        <button type="button" className={tool === "names" ? "active" : ""} onClick={() => setTool((current) => current === "names" ? null : "names")} aria-expanded={tool === "names"} aria-keyshortcuts={namesShortcut || undefined} title={namesShortcut ? `Nomi (${namesShortcut.replace("+", " + ")})` : "Nomi"}>
          <span aria-hidden="true">◈</span><strong>Nomi</strong>
        </button>
      </div>
    </div>
    {tool === "journal" && <ToolDrawer title="Diario" eyebrow={characterName || "Nessun personaggio"} onClose={() => setTool(null)} background={settings.theme?.backgrounds?.journal} wide draggable resizable>
      <JournalTool characterId={characterId} campaign={campaign} notify={notify} />
    </ToolDrawer>}
    {tool === "dice" && <ToolDrawer title="Dadi" eyebrow={characterName || "Tiro libero"} onClose={() => setTool(null)} background={settings.theme?.backgrounds?.dice} compact draggable resizable>
      <DiceTool characterId={characterId} settings={settings} notify={notify} />
    </ToolDrawer>}
    {tool === "theft" && <ToolDrawer title="Furto" eyebrow={characterName || "Scasso e borseggio"} onClose={() => setTool(null)} background={settings.theme?.backgrounds?.theft} draggable resizable>
      <TheftTool characterId={characterId} notify={notify} />
    </ToolDrawer>}
    {tool === "audio" && <ToolDrawer title="Audio" eyebrow={campaign?.name || "Colonna sonora"} onClose={() => setTool(null)} background={settings.theme?.backgrounds?.audio} draggable resizable>
      <AudioTool notify={notify} />
    </ToolDrawer>}
    {tool === "ai" && <ToolDrawer title="AI" eyebrow={campaign?.name || "Assistente di campagna"} onClose={() => setTool(null)} background={settings.theme?.backgrounds?.ai} draggable resizable>
      <AITool notify={notify} />
    </ToolDrawer>}
    {tool === "names" && <ToolDrawer title="Nomi" eyebrow={campaign?.name || "Generatore nomi"} onClose={() => setTool(null)} background={settings.theme?.backgrounds?.guide} wide draggable resizable>
      <NameTool notify={notify} />
    </ToolDrawer>}
  </>;
}
