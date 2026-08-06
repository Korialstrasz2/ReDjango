import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { getData } from "../../lib/api";
import { useResponsiveLayout } from "../../lib/responsive";
import { matchesShortcut, quickToolShortcutTargets, shortcutValue } from "../../lib/shortcuts";
import type { ShellNavigationItem } from "../../lib/navigation";
import type { BootstrapData, CampaignData, SettingsData } from "../../lib/types";
import { AITool } from "../ai/AITool";
import { AudioMiniPlayer } from "../audio/AudioMiniPlayer";
import { AudioTool } from "../audio/AudioTool";
import { CampaignStatus } from "../campaign/CampaignStatus";
import { MobileNavigation, type MobileTool } from "../mobile/MobileNavigation";
import { pendingSpecialResourceCount } from "../notes/specialResourceState";
import { DiceTool } from "./DiceTool";
import { JournalTool } from "./JournalTool";
import { NameTool } from "./NameTool";
import { TheftTool } from "./TheftTool";
import { ToolDrawer } from "./ToolDrawer";

type Tool = MobileTool | null;

type Props = {
  characterId: number | null;
  characterName: string;
  campaign: CampaignData | null;
  settings: SettingsData;
  navigation: ShellNavigationItem[];
  notify: (message: string, kind?: "success" | "error" | "info") => void;
};

export function QuickTools({ characterId, characterName, campaign, settings, navigation, notify }: Props) {
  const queryClient = useQueryClient();
  const { isPhone } = useResponsiveLayout();
  const [tool, setTool] = useState<Tool>(null);
  const journalShortcut = shortcutValue(settings.ui, "journal");
  const diceShortcut = shortcutValue(settings.ui, "dice");
  const theftShortcut = shortcutValue(settings.ui, "theft");
  const audioShortcut = shortcutValue(settings.ui, "audio");
  const aiShortcut = shortcutValue(settings.ui, "ai");
  const namesShortcut = shortcutValue(settings.ui, "names");
  const pendingJournalCount = pendingSpecialResourceCount(campaign);
  const journalClassName = [tool === "journal" ? "active" : "", pendingJournalCount > 0 ? "pending-review-glow" : ""].filter(Boolean).join(" ");
  const toggleTool = (target: MobileTool) => setTool((current) => current === target ? null : target);

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

  useEffect(() => {
    if (!settings.security.canManageGameData) return;
    const refreshApprovals = () => {
      if (document.visibilityState !== "visible") return;
      void getData<BootstrapData>("/api/bootstrap/")
        .then((latest) => queryClient.setQueryData(["bootstrap"], latest))
        .catch(() => undefined);
    };
    const timer = window.setInterval(refreshApprovals, 15_000);
    window.addEventListener("focus", refreshApprovals);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("focus", refreshApprovals);
    };
  }, [queryClient, settings.security.canManageGameData]);

  return <>
    {isPhone && <MobileNavigation
      characterName={characterName}
      campaignName={campaign?.name || ""}
      canManageGameData={settings.security.canManageGameData}
      navigation={navigation}
      activeTool={tool}
      onSelectTool={toggleTool}
    />}
    <div className="quick-tools-bar" aria-label="Strumenti rapidi" data-component-type="toolbar" data-theme="dark">
      <CampaignStatus campaign={campaign} settings={settings} notify={notify} />
      <AudioMiniPlayer onOpen={() => setTool("audio")} />
      <div className="quick-tools-actions">
        <span>Strumenti rapidi</span>
        <button type="button" className={journalClassName} onClick={() => toggleTool("journal")} aria-expanded={tool === "journal"} aria-keyshortcuts={journalShortcut || undefined} title={pendingJournalCount > 0 ? `Diario · ${pendingJournalCount} richieste Risorse speciali in attesa` : journalShortcut ? `Diario (${journalShortcut.replace("+", " + ")})` : "Diario"}>
          <span aria-hidden="true">⌑</span><strong>Diario</strong>
          {pendingJournalCount > 0 && <em className="quick-tool-pending-count" aria-label={`${pendingJournalCount} richieste in attesa`}>{pendingJournalCount}</em>}
        </button>
        <button type="button" className={tool === "dice" ? "active" : ""} onClick={() => toggleTool("dice")} aria-expanded={tool === "dice"} aria-keyshortcuts={diceShortcut || undefined} title={diceShortcut ? `Dadi (${diceShortcut.replace("+", " + ")})` : "Dadi"}>
          <span aria-hidden="true">◆</span><strong>Dadi</strong>
        </button>
        <button type="button" className={tool === "ai" ? "active" : ""} onClick={() => toggleTool("ai")} aria-expanded={tool === "ai"} aria-keyshortcuts={aiShortcut || undefined} title={aiShortcut ? `AI (${aiShortcut.replace("+", " + ")})` : "AI"}>
          <span aria-hidden="true">✳</span><strong>AI</strong>
        </button>
        <button type="button" className={tool === "audio" ? "active" : ""} onClick={() => toggleTool("audio")} aria-expanded={tool === "audio"} aria-keyshortcuts={audioShortcut || undefined} title={audioShortcut ? `Audio (${audioShortcut.replace("+", " + ")})` : "Audio"}>
          <span aria-hidden="true">♪</span><strong>Audio</strong>
        </button>
        <button type="button" className={tool === "theft" ? "active" : ""} onClick={() => toggleTool("theft")} aria-expanded={tool === "theft"} aria-keyshortcuts={theftShortcut || undefined} title={theftShortcut ? `Furto (${theftShortcut.replace("+", " + ")})` : "Furto"}>
          <span aria-hidden="true">⚿</span><strong>Furto</strong>
        </button>
        <button type="button" className={tool === "names" ? "active" : ""} onClick={() => toggleTool("names")} aria-expanded={tool === "names"} aria-keyshortcuts={namesShortcut || undefined} title={namesShortcut ? `Nomi (${namesShortcut.replace("+", " + ")})` : "Nomi"}>
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
