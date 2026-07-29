import { useMemo, useState } from "react";

import { Modal } from "../../components/Modal";
import type { EffectConfiguration, EffectPreset } from "../../lib/types";
import { EffectIcon } from "./EffectIcon";

type Props = {
  configuration: EffectConfiguration;
  onClose: () => void;
  onPick: (preset: EffectPreset) => void;
};

/** Simboli compatti: l'anteprima deve leggersi a colpo d'occhio, senza etichette lunghe. */
const OPERATION_SYMBOL: Record<string, string> = {
  add: "+",
  subtract: "−",
  multiply: "×",
  percent: "%",
  min: "≥",
  max: "≤",
  cap: "≤",
  set: "=",
  strong_set: "≡",
  formula_override: "ƒ",
};

const ALL_CATEGORIES = "Tutti";

/** Una formula lunga diventa "ƒ": nell'anteprima conta il campo toccato, non il calcolo. */
export function shortOperationValue(value: string) {
  const compact = value.trim();
  if (!compact) return "";
  if (/^-?\d+(\.\d+)?$/.test(compact)) return compact;
  return compact.length <= 10 ? compact : "ƒ";
}

export function EffectPresetPicker({ configuration, onClose, onPick }: Props) {
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState(ALL_CATEGORIES);
  const presets = configuration.presets || [];

  const categories = useMemo(
    () => [ALL_CATEGORIES, ...Array.from(new Set(presets.map((preset) => preset.category).filter(Boolean)))],
    [presets],
  );

  const filtered = useMemo(() => {
    const query = search.trim().toLocaleLowerCase("it");
    return presets.filter((preset) => {
      if (category !== ALL_CATEGORIES && preset.category !== category) return false;
      if (!query) return true;
      return [preset.name, preset.description, preset.category].some((value) => (value || "").toLocaleLowerCase("it").includes(query));
    });
  }, [category, presets, search]);

  const targetLabel = (value: string) => configuration.targets.find((target) => target.value === value)?.label || value;

  return <Modal title="Preset effetto" wide className="effect-preset-modal" onClose={onClose}>
    <div className="effect-preset-tools">
      <input
        type="search"
        autoFocus
        value={search}
        onChange={(event) => setSearch(event.target.value)}
        placeholder="Cerca fra i preset: nome, descrizione…"
        aria-label="Cerca un preset"
      />
      <div className="effect-preset-categories" role="tablist" aria-label="Categorie dei preset">
        {categories.map((entry) => <button
          key={entry}
          type="button"
          role="tab"
          aria-selected={category === entry}
          className={category === entry ? "active" : ""}
          onClick={() => setCategory(entry)}
        >{entry}</button>)}
      </div>
      <span className="effect-preset-count">{filtered.length} preset</span>
    </div>

    <div className="effect-preset-grid">
      {filtered.map((preset) => <button
        key={preset.id}
        type="button"
        className="effect-preset-card"
        onClick={() => onPick(preset)}
        title={preset.description || preset.name}
      >
        <span className="effect-preset-card-symbol"><EffectIcon name={preset.icon} assetUrl={preset.iconUrl} /></span>
        <span className="effect-preset-card-body">
          <strong>{preset.name}</strong>
          <small>{preset.description || "Nessuna descrizione."}</small>
          <span className="effect-preset-chips">
            {preset.operations.length
              ? preset.operations.slice(0, 3).map((operation, index) => <em key={index}>
                  {targetLabel(operation.target)} {OPERATION_SYMBOL[operation.operation] || operation.operation}{shortOperationValue(operation.value)}
                </em>)
              : <em className="descriptive">Solo descrittivo</em>}
            {preset.operations.length > 3 && <em>+{preset.operations.length - 3}</em>}
          </span>
        </span>
      </button>)}
      {!filtered.length && <p className="empty-copy">Nessun preset corrisponde alla ricerca.</p>}
    </div>
  </Modal>;
}
