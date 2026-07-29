import { type CSSProperties, type ChangeEvent, type FormEvent, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { command, getData, uploadMedia } from "../../lib/api";
import type { DiceSet, DiceSetsData, DiceTexture } from "../../lib/types";
import { DiceVisual } from "./DiceVisual";

const SIDES = [4, 6, 8, 10, 12, 20, 100];
const EMPTY = {
  name: "",
  description: "",
  dice: SIDES,
  surfaceColor: "#7f2434",
  accentColor: "#d0a95b",
  textColor: "#fff4d6",
  isActive: true,
  isDefault: false,
  order: 50
};

type Draft = typeof EMPTY;
type TextureDraft = DiceTexture & { file?: File; previewUrl?: string };
type TextureMap = Record<number, TextureDraft>;
type Props = { notify: (message: string, kind?: "success" | "error" | "info") => void; compact?: boolean };

function textureMap(textures: DiceTexture[]): TextureMap {
  return Object.fromEntries(textures.map((texture) => [texture.sides, { ...texture }]));
}

function TextureWorkshop({ side, texture, colors, onChange, onFile, onRemove }: {
  side: number;
  texture?: TextureDraft;
  colors: Pick<Draft, "surfaceColor" | "accentColor" | "textColor">;
  onChange: (values: Partial<TextureDraft>) => void;
  onFile: (event: ChangeEvent<HTMLInputElement>) => void;
  onRemove: () => void;
}) {
  const visualTexture = texture ? { ...texture, imageUrl: texture.previewUrl || texture.imageUrl } : null;
  const palette = {
    "--dice-surface": colors.surfaceColor,
    "--dice-accent": colors.accentColor,
    "--dice-text": colors.textColor
  } as CSSProperties;

  return <article className="texture-workshop" style={palette}>
    <header><div><span>Texture d{side}</span><small>{texture?.imageName || "Nessuna immagine"}</small></div></header>
    <div className="texture-final-preview">
      <DiceVisual sides={side} value={side} texture={visualTexture} className="dice-texture-preview" />
      <small>Anteprima finale del dado</small>
    </div>
    <div className="texture-upload-row">
      <label className="button secondary">{texture ? "Sostituisci immagine" : "Carica immagine"}<input className="sr-only" type="file" accept="image/png,image/jpeg,image/webp" onChange={onFile} /></label>
      {texture && <button type="button" className="texture-remove" onClick={onRemove}>Rimuovi</button>}
    </div>
    {texture && <div className="texture-controls">
      <label>Scala <output>{texture.scale}%</output><input type="range" min={50} max={300} value={texture.scale} onChange={(event) => onChange({ scale: Number(event.target.value) })} /></label>
      <label>Orizzontale <output>{texture.offsetX}</output><input type="range" min={-100} max={100} value={texture.offsetX} onChange={(event) => onChange({ offsetX: Number(event.target.value) })} /></label>
      <label>Verticale <output>{texture.offsetY}</output><input type="range" min={-100} max={100} value={texture.offsetY} onChange={(event) => onChange({ offsetY: Number(event.target.value) })} /></label>
      <label>Rotazione <output>{texture.rotation}°</output><input type="range" min={-180} max={180} value={texture.rotation} onChange={(event) => onChange({ rotation: Number(event.target.value) })} /></label>
    </div>}
  </article>;
}

export function DiceSetManager({ notify, compact = false }: Props) {
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["diceSets", "admin"], queryFn: () => getData<DiceSetsData>("/api/v1/dice-sets?include_inactive=true") });
  const [selectedId, setSelectedId] = useState<number | "new">("new");
  const selected = query.data?.diceSets.find((entry) => entry.id === selectedId);
  const [draft, setDraft] = useState<Draft>(EMPTY);
  const [textures, setTextures] = useState<TextureMap>({});
  const [textureSide, setTextureSide] = useState(20);

  useEffect(() => {
    if (!selected) {
      setDraft(EMPTY);
      setTextures({});
      setTextureSide(20);
      return;
    }
    setDraft({
      name: selected.name,
      description: selected.description,
      dice: selected.dice,
      surfaceColor: selected.surfaceColor,
      accentColor: selected.accentColor,
      textColor: selected.textColor,
      isActive: selected.isActive,
      isDefault: selected.isDefault,
      order: selected.order
    });
    setTextures(textureMap(selected.textures));
    setTextureSide(selected.dice.includes(20) ? 20 : selected.dice[0]);
  }, [selected]);

  const sync = async (data: DiceSetsData) => {
    queryClient.setQueryData(["diceSets", "admin"], data);
    queryClient.setQueryData(["diceSets", "active"], { ...data, diceSets: data.diceSets.filter((entry) => entry.isActive) });
    await queryClient.invalidateQueries({ queryKey: ["settings"] });
  };

  const save = useMutation({
    mutationFn: async () => {
      const preparedTextures: DiceTexture[] = [];
      for (const side of draft.dice) {
        const texture = textures[side];
        if (!texture) continue;
        if (texture.file) {
          const uploaded = await uploadMedia(texture.file, `${draft.name || "Set di dadi"} · d${side}`, `Texture preparata nella forgia per d${side}.`, "dice_texture", undefined, "Dadi");
          preparedTextures.push({ ...texture, imageId: uploaded.data.asset.id, imageUrl: uploaded.data.asset.url, imageName: uploaded.data.asset.originalName });
        } else {
          preparedTextures.push(texture);
        }
      }
      const values = {
        ...draft,
        textures: preparedTextures.map(({ sides, imageId, offsetX, offsetY, scale, rotation }) => ({ sides, imageId, offsetX, offsetY, scale, rotation }))
      };
      return selected
        ? command<{ diceSets: DiceSetsData }>("diceSets.update", { diceSetId: selected.id, values }, "dice")
        : command<{ diceSets: DiceSetsData }>("diceSets.create", { values }, "dice");
    },
    onSuccess: async (result) => {
      await sync(result.data.diceSets);
      const saved = result.data.diceSets.diceSets.find((entry) => entry.name === draft.name);
      if (saved) {
        setSelectedId(saved.id);
        setTextures(textureMap(saved.textures));
      }
      notify(selected ? "Set di dadi aggiornato." : "Set di dadi creato e reso disponibile nelle impostazioni.");
    },
    onError: (error: Error) => notify(error.message, "error")
  });
  const archive = useMutation({
    mutationFn: (diceSet: DiceSet) => command<{ diceSets: DiceSetsData }>("diceSets.archive", { diceSetId: diceSet.id }, "dice"),
    onSuccess: async (result) => { await sync(result.data.diceSets); setSelectedId("new"); notify("Set di dadi archiviato."); },
    onError: (error: Error) => notify(error.message, "error")
  });
  const duplicate = useMutation({
    mutationFn: (diceSet: DiceSet) => command<{ diceSets: DiceSetsData }>("diceSets.duplicate", { diceSetId: diceSet.id }, "dice"),
    onSuccess: async (result) => {
      await sync(result.data.diceSets);
      // The copy starts inactive so it cannot reach players before it is ready.
      const copy = result.data.diceSets.diceSets.find((entry) => !entry.isActive && entry.name.startsWith("Copia di "));
      if (copy) setSelectedId(copy.id);
      notify("Set duplicato: la copia è una bozza finché non la attivi.");
    },
    onError: (error: Error) => notify(error.message, "error")
  });

  const previewStyle = useMemo(() => ({
    "--dice-surface": draft.surfaceColor,
    "--dice-accent": draft.accentColor,
    "--dice-text": draft.textColor
  } as CSSProperties), [draft]);

  const updateTexture = (side: number, values: Partial<TextureDraft>) => setTextures((current) => ({ ...current, [side]: { ...current[side], ...values } }));
  const chooseTexture = (side: number, event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    if (!file.type.startsWith("image/")) return notify("Scegli un file immagine PNG, JPEG o WebP.", "error");
    if (file.size > 10 * 1024 * 1024) return notify("La texture deve essere più piccola di 10 MB.", "error");
    const previewUrl = URL.createObjectURL(file);
    setTextures((current) => ({
      ...current,
      [side]: {
        sides: side,
        imageId: current[side]?.imageId || 0,
        imageUrl: current[side]?.imageUrl || "",
        imageName: file.name,
        offsetX: current[side]?.offsetX || 0,
        offsetY: current[side]?.offsetY || 0,
        scale: current[side]?.scale || 100,
        rotation: current[side]?.rotation || 0,
        file,
        previewUrl
      }
    }));
  };
  const removeTexture = (side: number) => setTextures((current) => {
    const next = { ...current };
    if (next[side]?.previewUrl) URL.revokeObjectURL(next[side].previewUrl!);
    delete next[side];
    return next;
  });
  const toggleSide = (side: number) => setDraft((current) => {
    const included = current.dice.includes(side);
    const dice = included ? current.dice.filter((value) => value !== side) : [...current.dice, side].sort((a, b) => a - b);
    if (!included) setTextureSide(side);
    else if (textureSide === side && dice.length) setTextureSide(dice[0]);
    return { ...current, dice };
  });
  const submit = (event: FormEvent) => { event.preventDefault(); save.mutate(); };

  return <section className={`dice-set-manager ${compact ? "compact" : ""}`} data-component-type="panel" data-theme="arcane">
    <header><div><p className="eyebrow">Solo amministratori</p><h3>Forgia dei set</h3><p>Crea una collezione fantasy, assegna una texture a ciascun dado e controllane la resa con le sagome guida.</p></div></header>
    {query.isLoading ? <p className="empty-copy">Caricamento dei set…</p> : <div className="dice-set-manager-layout">
      <div className="dice-set-list" role="listbox" aria-label="Set di dadi">
        <button type="button" className={selectedId === "new" ? "active" : ""} onClick={() => setSelectedId("new")}><strong>＋ Nuovo set</strong><span>Crea da zero</span></button>
        {query.data?.diceSets.map((entry) => <button type="button" key={entry.id} className={selectedId === entry.id ? "active" : ""} onClick={() => setSelectedId(entry.id)}>
          <i style={{ background: entry.surfaceColor, borderColor: entry.accentColor }} /><strong>{entry.name}</strong><span>{entry.isDefault ? "Predefinito" : entry.isActive ? "Attivo" : "Bozza"}</span><em className="dice-set-coverage" data-state={entry.untexturedDice.length ? "partial" : "complete"}>{entry.dice.length - entry.untexturedDice.length}/{entry.dice.length} texture</em>
        </button>)}
      </div>
      <form className="dice-set-form" onSubmit={submit}>
        <div className="dice-set-preview" style={previewStyle}>
          <DiceVisual sides={textureSide} value={textureSide} texture={textures[textureSide] ? { ...textures[textureSide], imageUrl: textures[textureSide].previewUrl || textures[textureSide].imageUrl } : null} />
          <div><strong>{draft.name || "Nuovo set"}</strong><small>{textures[textureSide] ? `Texture d${textureSide} pronta` : "Materiale base senza texture"}</small></div>
        </div>
        <label>Nome<input value={draft.name} maxLength={120} required onChange={(event) => setDraft((current) => ({ ...current, name: event.target.value }))} /></label>
        <label>Descrizione<textarea value={draft.description} rows={compact ? 2 : 3} maxLength={1000} onChange={(event) => setDraft((current) => ({ ...current, description: event.target.value }))} /></label>
        <fieldset><legend>Dadi inclusi</legend><div className="dice-side-checks">{SIDES.map((side) => <label key={side}><input type="checkbox" checked={draft.dice.includes(side)} onChange={() => toggleSide(side)} />d{side}</label>)}</div></fieldset>
        <div className="dice-color-grid"><label>Materiale<input type="color" value={draft.surfaceColor} onChange={(event) => setDraft((current) => ({ ...current, surfaceColor: event.target.value }))} /></label><label>Bordo<input type="color" value={draft.accentColor} onChange={(event) => setDraft((current) => ({ ...current, accentColor: event.target.value }))} /></label><label>Numeri<input type="color" value={draft.textColor} onChange={(event) => setDraft((current) => ({ ...current, textColor: event.target.value }))} /></label></div>
        <fieldset className="texture-forge"><legend>Texture individuali</legend>
          <nav aria-label="Scegli il dado da decorare">{draft.dice.map((side) => <button type="button" key={side} className={textureSide === side ? "active" : ""} onClick={() => setTextureSide(side)}>d{side}{textures[side] && <span>●</span>}</button>)}</nav>
          {draft.dice.length ? <TextureWorkshop side={textureSide} texture={textures[textureSide]} colors={draft} onChange={(values) => updateTexture(textureSide, values)} onFile={(event) => chooseTexture(textureSide, event)} onRemove={() => removeTexture(textureSide)} /> : <p className="form-error">Scegli almeno un dado per preparare le texture.</p>}
        </fieldset>
        <div className="check-row"><label><input type="checkbox" checked={draft.isActive} onChange={(event) => setDraft((current) => ({ ...current, isActive: event.target.checked }))} />Attivo</label><label><input type="checkbox" checked={draft.isDefault} onChange={(event) => setDraft((current) => ({ ...current, isDefault: event.target.checked, isActive: event.target.checked || current.isActive }))} />Predefinito</label></div>
        {selected && selected.untexturedDice.length > 0 && <p className="form-warning">Senza texture: {selected.untexturedDice.map((side) => `d${side}`).join(", ")}. Questi dadi usano solo il colore del materiale.</p>}
        <div className="button-row"><button className="button primary" disabled={save.isPending || draft.dice.length === 0}>{save.isPending ? "Preparazione…" : selected ? "Salva set" : "Crea set"}</button>{selected && <button className="button secondary" type="button" disabled={duplicate.isPending} onClick={() => duplicate.mutate(selected)}>{duplicate.isPending ? "Copia…" : "Duplica"}</button>}{selected && <button className="button danger" type="button" disabled={archive.isPending} onClick={() => archive.mutate(selected)}>Archivia</button>}</div>
      </form>
    </div>}
  </section>;
}
