import { type ReactNode, useEffect, useMemo, useState } from "react";

import type { CharacterSheet, CharacterSlot as Slot, Item } from "../../lib/types";
import { CharacterSlot } from "./CharacterSlot";

type EquipmentView = "figure" | "grid";

type Props = {
  character: CharacterSheet;
  selectedSlotId: string | null;
  moveSourceId: string | null;
  equipItem: Item | null;
  actionPending: boolean;
  compatibility: (slot: Slot) => "valid" | "invalid" | "neutral";
  onSelect: (slot: Slot) => void;
  onMoveStart: (slot: Slot) => void;
  onEquip: (slot: Slot) => void;
  onEmpty: (slot: Slot) => void;
  onPick: (slot: Slot, anchor: { x: number; y: number }) => void;
  onSwitchPrimary: () => void;
  onActionsEnter: () => void;
  onActionsLeave: () => void;
  coinsControl: ReactNode;
};

type FigureRegion = {
  id: "head" | "torso" | "hands" | "waist" | "utility";
  slotNames: string[];
};

const FIGURE_LEFT_REGIONS: FigureRegion[] = [
  { id: "head", slotNames: ["fascia", "orecchino_1", "orecchino_3", "orecchino_5"] },
  { id: "torso", slotNames: ["spilla", "armatura", "chainmail"] },
  { id: "hands", slotNames: ["scudo", "anello_1", "anello_3", "anello_5", "anello_7"] },
  { id: "utility", slotNames: ["sacco_1", "sacco_3", "faretra_1", "extra_slot_1", "extra_slot_3"] },
];

const FIGURE_RIGHT_REGIONS: FigureRegion[] = [
  { id: "head", slotNames: ["orecchino_2", "orecchino_4", "orecchino_6", "amuleto"] },
  { id: "torso", slotNames: ["mantello", "veste", "vestiti"] },
  { id: "hands", slotNames: ["arma", "anello_2", "anello_4", "anello_6", "anello_8"] },
  { id: "waist", slotNames: ["cintura", "borsello"] },
  { id: "utility", slotNames: ["sacco_2", "faretra_2", "extra_slot_2", "extra_slot_4"] },
];

export function CharacterEquipment({
  character,
  selectedSlotId,
  moveSourceId,
  equipItem,
  actionPending,
  compatibility,
  onSelect,
  onMoveStart,
  onEquip,
  onEmpty,
  onPick,
  onSwitchPrimary,
  onActionsEnter,
  onActionsLeave,
  coinsControl,
}: Props) {
  const [view, setView] = useState<EquipmentView>("figure");
  const [imageUrl, setImageUrl] = useState(character.appearance.imageUrl);
  useEffect(() => setImageUrl(character.appearance.imageUrl), [character.appearance.imageUrl]);

  const figureRegions = useMemo(() => {
    const slotByName = new Map(character.equipment.slots.map((slot) => [slot.slot, slot]));
    const assigned = new Set<string>();
    const takeRegions = (regions: FigureRegion[]) => regions.map((region) => ({
      id: region.id,
      slots: region.slotNames.flatMap((name) => {
        const slot = slotByName.get(name);
        if (!slot) return [];
        assigned.add(name);
        return [slot];
      }),
    }));
    const left = takeRegions(FIGURE_LEFT_REGIONS);
    const right = takeRegions(FIGURE_RIGHT_REGIONS);
    right.find((region) => region.id === "utility")?.slots.push(
      ...character.equipment.slots.filter((slot) => !assigned.has(slot.slot)),
    );
    return { left, right };
  }, [character.equipment.slots]);

  const renderSlot = (slot: Slot, variant: "card" | "figure" = "card") => <CharacterSlot
    key={slot.id}
    slot={slot}
    variant={variant}
    selected={selectedSlotId === slot.id}
    moveSource={moveSourceId === slot.id}
    compatibility={compatibility(slot)}
    equipItem={equipItem}
    actionsVisible={selectedSlotId === slot.id}
    actionPending={actionPending}
    onSelect={onSelect}
    onMoveStart={onMoveStart}
    onEquip={onEquip}
    onEmpty={onEmpty}
    onPick={onPick}
    onActionsEnter={onActionsEnter}
    onActionsLeave={onActionsLeave}
  />;

  const renderFigureRail = (side: "left" | "right") => <div className={`figure-slot-rail figure-slot-rail-${side}`}>
    {figureRegions[side].map((region) => region.slots.length > 0 && <div
      className={`figure-slot-group figure-slot-group-${region.id}`}
      data-figure-region={region.id}
      key={region.id}
    >
      {region.slots.map((slot) => renderSlot(slot, "figure"))}
    </div>)}
  </div>;

  const isPlaceholder = imageUrl === character.appearance.fallbackUrl
    ? character.appearance.fallbackIsPlaceholder
    : character.appearance.isPlaceholder;
  const mainWeapon = character.equipment.slots.find((slot) => slot.slot === "arma")?.item;
  const offhandWeapon = character.equipment.slots.find((slot) => slot.slot === "scudo")?.item;
  return <>
    <div className="equipment-heading-row">
      <h3>Equipaggiamento</h3>
      <div className="equipment-heading-tools">
        <div className="equipment-view-switch" role="tablist" aria-label="Vista equipaggiamento" data-component-type="tabset" data-theme="dark">
          <button type="button" role="tab" aria-selected={view === "figure"} className={view === "figure" ? "active" : ""} data-action="equipment.showFigure" onClick={() => setView("figure")}>Sagoma</button>
          <button type="button" role="tab" aria-selected={view === "grid"} className={view === "grid" ? "active" : ""} data-action="equipment.showGrid" onClick={() => setView("grid")}>Griglia</button>
        </div>
        {coinsControl}
      </div>
    </div>

    {character.equipment.dualWield && <section className="dual-wield-control" data-component-type="toolbar" data-theme="gold"><div><strong>Doppia impugnatura</strong><p><span className={character.equipment.primaryWeaponSlot === "arma" ? "primary" : ""}>{mainWeapon?.name}</span><b>⇄</b><span className={character.equipment.primaryWeaponSlot === "scudo" ? "primary" : ""}>{offhandWeapon?.name}</span></p><small>Conta soltanto l'arma primaria. Il cambio è gratuito.</small></div><button type="button" className="button primary small" disabled={actionPending} onClick={onSwitchPrimary}>Cambia primaria · 0 PA</button></section>}

    {view === "figure" ? <div className="figure-equipment" data-equipment-view="figure">
      <figure className="character-figure" data-component-type="panel" data-theme="arcane" data-placeholder={isPlaceholder ? "true" : "false"}>
        <div className="character-figure-art">
          <span className="figure-rune figure-rune-left" aria-hidden="true">✦</span>
          <img
            src={imageUrl}
            alt={`Sagoma di ${character.name} con armatura equipaggiata`}
            width={500}
            height={800}
            loading="lazy"
            decoding="async"
            onError={() => imageUrl !== character.appearance.fallbackUrl && setImageUrl(character.appearance.fallbackUrl)}
          />
          <span className="figure-rune figure-rune-right" aria-hidden="true">✦</span>
        </div>
        <div className="figure-slot-layer" aria-label="Slot sulla sagoma">
          {renderFigureRail("left")}
          {renderFigureRail("right")}
        </div>
        {isPlaceholder && <figcaption>
          <span>Sagoma segnaposto</span>
          {character.appearance.preferredFilename && <small>Aggiungi {character.appearance.preferredFilename} nella cartella dei personaggi.</small>}
        </figcaption>}
      </figure>
    </div> : <div className="equipment-grid" data-equipment-view="grid">{character.equipment.slots.map((slot) => renderSlot(slot))}</div>}
  </>;
}
