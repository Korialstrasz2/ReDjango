import { type FormEvent, useMemo, useState } from "react";

import { Modal } from "../../components/Modal";
import { ImagePickerModal } from "../../components/ImagePickerModal";
import { ItemSpecialIconField } from "../../components/ItemSpecialIconField";
import type { Item, ItemCatalog, MediaAsset } from "../../lib/types";

type EffectDraft = { target: string; operation: string; value: string; source?: string };
type WeaponProfile = {
  heaviness?: string; length?: string; power?: string; damageType?: string;
  materialFamily?: string; material?: string; materialTier?: number; costBand?: string;
  combatMode?: string; handling?: string; baseRangeMeters?: number;
  ammunitionType?: string; magazineSize?: number; reloadBaseCost?: number; reloadPerProjectileCost?: number;
  specialRules?: string[]; bonusNotes?: string[];
};
type WeaponOption = { value: string; label: string; modifiers?: Record<string, number>; effects?: Record<string, number>; paPerAttacco?: number; skill?: string };
type WeaponConfiguration = {
  axes: Record<string, { label: string; options: WeaponOption[] }>;
  materials: Array<{ family: string; modifiers: Record<string, number>; tiers: Array<{ tier: number; name: string }> }>;
  costBands: Array<{ value: string; label: string; weight: number; prices: Record<string, number[]> }>;
};

type Props = {
  item: Item | null;
  catalog: ItemCatalog;
  media: MediaAsset[];
  saving: boolean;
  onClose: () => void;
  onSave: (values: Record<string, unknown>) => void;
  onArchive?: () => void;
  clone?: boolean;
};

const operations = ["add", "subtract", "multiply", "percent", "min", "max", "cap", "set"];

function initialEffects(item: Item | null): EffectDraft[] {
  const entries = Array.isArray(item?.effects) ? item.effects : [];
  return entries.map((entry) => ({
    target: String(entry.target || entry.stat || ""),
    operation: String(entry.operation || entry.op || "add"),
    value: String(entry.value ?? entry.amount ?? ""),
    source: String(entry.source || "") || undefined,
  }));
}

function suggestedEffects(profile: WeaponProfile, configuration: WeaponConfiguration): EffectDraft[] {
  const totals = new Map<string, number>();
  const add = (modifiers?: Record<string, number>) => Object.entries(modifiers || {}).forEach(([target, value]) => totals.set(target, (totals.get(target) || 0) + value));
  for (const axis of ["heaviness", "length", "damageType"] as const) {
    const option = configuration.axes[axis]?.options.find((entry) => entry.value === profile[axis]);
    add(option?.modifiers || option?.effects);
  }
  add(configuration.materials.find((entry) => entry.family === profile.materialFamily)?.modifiers);
  return [...totals].filter(([, value]) => value !== 0).map(([target, value]) => ({ target, operation: "add", value: String(value), source: "weapon_builder" }));
}

export function ItemEditorModal({ item, catalog, media, saving, onClose, onSave, onArchive, clone = false }: Props) {
  const [effects, setEffects] = useState<EffectDraft[]>(() => initialEffects(item));
  const [error, setError] = useState("");
  const [itemName, setItemName] = useState(item ? (clone ? `Copia di ${item.name}` : item.name) : "");
  const [selectedMediaId, setSelectedMediaId] = useState<number | null>(item?.mediaId ?? null);
  const [imagePickerOpen, setImagePickerOpen] = useState(false);
  const configuration = catalog.weaponConfiguration as unknown as WeaponConfiguration;
  const storedProfile = (item?.weaponProfile || {}) as WeaponProfile;
  const typeProfile = (catalog.weaponTypes.find((entry) => entry.id === item?.weaponTypeId)?.rules as { profile?: WeaponProfile } | undefined)?.profile;
  const initialProfile = Object.keys(storedProfile).length ? storedProfile : (typeProfile || {});
  const [weaponProfile, setWeaponProfile] = useState<WeaponProfile>(initialProfile);
  const [selectedWeaponTypeId, setSelectedWeaponTypeId] = useState<number | "">(item?.weaponTypeId ?? "");
  const [paCost, setPaCost] = useState<number | "">(item?.actionPointCost ?? "");
  const [itemValue, setItemValue] = useState<number | "">(item?.value ?? "");
  const [itemWeight, setItemWeight] = useState<number | "">(item?.weight ?? "");
  const typeValues = item?.typeValues?.length === 4 ? item.typeValues : [...(item?.types || []), "", "", "", ""].slice(0, 4);
  const elderEffects = item?.elderEffects?.length
    ? [...item.elderEffects, "", "", "", "", "", "", "", ""].slice(0, 8)
    : Array(8).fill("");
  const defaults = useMemo(() => ({
    nome: item?.name || "",
    modello: item?.model ?? true,
    temporaneo: item?.temporary ?? false,
    archiviato: item?.archived ?? false,
    numero_ordine: item?.order ?? "",
    icona: item?.icon || "",
    tipo_1: typeValues[0] || "",
    tipo_2: typeValues[1] || "",
    tipo_3: typeValues[2] || "",
    tipo_4: typeValues[3] || "",
    descrizione: item?.description || "",
    valore: item?.value ?? "",
    peso: item?.weight ?? "",
    rarita: item?.rarity ?? "",
    lv_loot: item?.lootLevel || "",
    regione_loot: item?.region || "",
    peso_regione: item?.regionWeight ?? "",
    tipoArmaId: item?.weaponTypeId ?? "",
    mediaId: item?.mediaId ?? "",
    alchemy_profile: JSON.stringify(item?.alchemyProfile || {}, null, 2),
    crafting_profile: JSON.stringify(item?.craftingProfile || {}, null, 2),
    notes: item?.notes || ""
  }), [item]);

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      const alchemy = JSON.parse(String(form.get("alchemy_profile") || "{}"));
      const crafting = JSON.parse(String(form.get("crafting_profile") || "{}"));
      const normalizedEffects = effects.filter((effect) => effect.target.trim()).map((effect) => ({
        target: effect.target.trim(), operation: effect.operation, value: Number(effect.value),
        ...(effect.source ? { source: effect.source } : {}),
      }));
      if (normalizedEffects.some((effect) => Number.isNaN(effect.value))) throw new Error("Ogni effetto deve avere un valore numerico.");
      onSave({
        nome: String(form.get("nome") || "").trim(),
        modello: form.get("modello") === "on",
        temporaneo: form.get("temporaneo") === "on",
        archiviato: form.get("archiviato") === "on",
        speciale: form.get("speciale") === "on",
        numero_ordine: form.get("numero_ordine") || null,
        icona: form.get("icona"),
        tipo_1: form.get("tipo_1"), tipo_2: form.get("tipo_2"), tipo_3: form.get("tipo_3"),
        tipo_4: form.get("tipo_4"),
        descrizione: form.get("descrizione"),
        valore: itemValue === "" ? null : itemValue,
        peso: itemWeight === "" ? null : itemWeight,
        rarita: form.get("rarita") || null,
        lv_loot: form.get("lv_loot"),
        regione_loot: form.get("regione_loot"),
        peso_regione: form.get("peso_regione") || null,
        tipoArmaId: selectedWeaponTypeId || null,
        pa_per_attacco: paCost === "" ? null : paCost,
        ...Object.fromEntries(Array.from({ length: 8 }, (_, index) => [
          `effetto_${index + 1}`,
          String(form.get(`effetto_${index + 1}`) || "").trim(),
        ])),
        effects: normalizedEffects,
        weapon_profile: weaponProfile,
        alchemy_profile: alchemy,
        crafting_profile: crafting,
        mediaId: selectedMediaId,
        notes: form.get("notes")
      });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Controlla i dati strutturati.");
    }
  };

  const selectedWeaponType = catalog.weaponTypes.find((entry) => entry.id === selectedWeaponTypeId);
  const previewEffects = suggestedEffects(weaponProfile, configuration);
  const lengthOption = configuration.axes.length?.options.find((entry) => entry.value === weaponProfile.length);
  const materialGroup = configuration.materials.find((entry) => entry.family === weaponProfile.materialFamily);
  const costBand = configuration.costBands.find((entry) => entry.value === weaponProfile.costBand);
  const materialPrices = costBand?.prices[weaponProfile.materialFamily || ""] || [];
  const suggestedPrice = weaponProfile.materialTier ? materialPrices[weaponProfile.materialTier - 1] : undefined;
  const setAxis = (axis: keyof WeaponProfile, value: string) => setWeaponProfile((current) => ({
    ...current,
    [axis]: value,
    ...(axis === "length" ? { handling: value === "lunga" ? "two_handed" : "one_handed" } : {}),
  }));
  const chooseWeaponType = (rawId: string) => {
    const id = rawId ? Number(rawId) : "";
    setSelectedWeaponTypeId(id);
    if (!id) return;
    const weaponType = catalog.weaponTypes.find((entry) => entry.id === id);
    const preset = (weaponType?.rules as { profile?: WeaponProfile } | undefined)?.profile;
    if (preset) setWeaponProfile({ ...preset });
  };
  const applySuggestedModifiers = () => {
    setEffects((current) => [...current.filter((entry) => entry.source !== "weapon_builder"), ...previewEffects]);
    if (lengthOption?.paPerAttacco != null) setPaCost(lengthOption.paPerAttacco);
  };

  const selectedMedia = media.find((asset) => asset.id === selectedMediaId) || null;
  return <><Modal title={item ? (clone ? `Clona ${item.name}` : `Modifica ${item.name}`) : "Crea oggetto"} onClose={onClose} wide footer={<><button className="button secondary" type="button" onClick={onClose}>Annulla</button>{item && !clone && onArchive && <button className="button danger" type="button" onClick={onArchive}>Archivia</button>}<button className="button primary" type="submit" form="item-editor-form" disabled={saving}>Salva oggetto</button></>}>
    <form id="item-editor-form" className="item-editor" onSubmit={submit}>
      {error && <p className="form-error">{error}</p>}
      <fieldset><legend>Identità</legend><div className="form-grid three"><label>Nome<input name="nome" value={itemName} onChange={(event) => setItemName(event.target.value)} required /></label><label>Icona<input name="icona" defaultValue={defaults.icona} /></label><label>Ordine<input name="numero_ordine" type="number" defaultValue={defaults.numero_ordine} /></label></div><label>Descrizione<textarea name="descrizione" rows={3} defaultValue={defaults.descrizione} /></label><div className="check-row"><label><input name="modello" type="checkbox" defaultChecked={defaults.modello} /> Modello riutilizzabile</label><label><input name="temporaneo" type="checkbox" defaultChecked={defaults.temporaneo} /> Temporaneo</label><label><input name="archiviato" type="checkbox" defaultChecked={defaults.archiviato} /> Archiviato</label></div></fieldset>
      <fieldset><legend>Controlli importazione</legend><div className="check-row"><label><input name="speciale" type="checkbox" defaultChecked={item?.special ?? false} /> Speciale</label></div><p className="field-hint">Usa Speciale per oggetti anomali o con regole Elder descrittive da verificare.</p>{Boolean(item?.specialReasons?.length) && <aside className="item-special-evidence" data-theme="gold"><strong>Motivi rilevati automaticamente</strong><ul>{item!.specialReasons.map((reason) => <li key={reason.code}><strong>{reason.label}</strong><span>{reason.hint}</span></li>)}</ul></aside>}</fieldset>
      <fieldset><legend>Classificazione</legend><div className="form-grid three">{[1,2,3,4].map((index) => {
        const current = String(defaults[`tipo_${index}` as keyof typeof defaults] || "");
        const options = catalog.typeOptions.filter((option) => option.position === index);
        return <label key={index}>Tipo {index}<select name={`tipo_${index}`} defaultValue={current}><option value="">Nessuno</option>{current && !options.some((option) => option.value === current) && <option value={current}>{current} · non configurato</option>}{options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>;
      })}</div><p className="field-hint">Le opzioni dei quattro menu si configurano nell'Amministrazione Django.</p><label>Tipo arma<select value={selectedWeaponTypeId} onChange={(event) => chooseWeaponType(event.target.value)}><option value="">Nessuno</option>{catalog.weaponTypes.map((weapon) => <option key={weapon.id} value={weapon.id}>{weapon.name} · {weapon.length} · {weapon.power}</option>)}</select></label>{selectedWeaponType && <aside className="weapon-type-notes"><strong>Note Elder del tipo</strong><p>{[selectedWeaponType.bonus1, selectedWeaponType.bonus2].filter(Boolean).join(" · ") || "Nessun bonus speciale."}</p></aside>}</fieldset>
      <fieldset className="weapon-builder"><legend>Creator arma</legend><p className="field-hint">Le quattro griglie sono indipendenti. Cambiare una scelta aggiorna solo questa anteprima: gli effetti salvati non cambiano finché non premi il pulsante di applicazione.</p>
        <div className="weapon-axis-panels">{Object.entries(configuration.axes).map(([axis, group]) => <section key={axis} className="weapon-axis-panel" data-component-type="panel" data-theme="parchment"><header><strong>{group.label}</strong>{axis === "power" && <small>Media → atk_skill_medie2</small>}{axis === "length" && <small>Media → atk_skill_medie1</small>}</header><div className="weapon-option-grid">{group.options.map((option) => <button type="button" key={option.value} className={weaponProfile[axis as keyof WeaponProfile] === option.value ? "active" : ""} onClick={() => setAxis(axis as keyof WeaponProfile, option.value)}><strong>{option.label}</strong><small>{Object.entries(option.modifiers || option.effects || {}).map(([target, value]) => `${target} ${value > 0 ? "+" : ""}${value}`).join(" · ") || option.skill || "nessun modificatore"}{option.paPerAttacco != null ? ` · ${option.paPerAttacco} PA/attacco` : ""}</small></button>)}</div></section>)}</div>
        <div className="form-grid three"><label>Famiglia materiale<select value={weaponProfile.materialFamily || ""} onChange={(event) => setWeaponProfile((current) => ({ ...current, materialFamily: event.target.value, material: undefined, materialTier: undefined }))}><option value="">Nessuna</option>{configuration.materials.map((entry) => <option key={entry.family} value={entry.family}>{entry.family === "leggera" ? "Materiali leggeri (+2 PA, +1 ATK)" : "Materiali pesanti (+2 EN, +1 DMG)"}</option>)}</select></label><label>Materiale<select value={weaponProfile.material || ""} disabled={!materialGroup} onChange={(event) => { const tier = materialGroup?.tiers.find((entry) => entry.name === event.target.value)?.tier; setWeaponProfile((current) => ({ ...current, material: event.target.value, materialTier: tier })); }}><option value="">Nessuno</option>{materialGroup?.tiers.map((entry) => <option key={entry.name} value={entry.name}>Tier {entry.tier} · {entry.name}</option>)}</select></label><label>Banda costo<select value={weaponProfile.costBand || ""} onChange={(event) => setAxis("costBand", event.target.value)}><option value="">Nessuna</option>{configuration.costBands.map((entry) => <option key={entry.value} value={entry.value}>{entry.value} · {entry.label}</option>)}</select></label></div>
        <div className="form-grid three"><label>Uso in combattimento<select value={weaponProfile.combatMode || "melee"} onChange={(event) => { const mode = event.target.value; setWeaponProfile((current) => ({ ...current, combatMode: mode, baseRangeMeters: mode === "throwable" ? 4 : mode === "ranged" ? 9 : undefined })); }}><option value="melee">Mischia</option><option value="throwable">Da lancio</option><option value="ranged">A distanza</option><option value="magic">Magica</option><option value="nature">Natura</option><option value="unarmed">Mani nude</option></select></label>{weaponProfile.combatMode === "ranged" && <><label>Munizione<select value={String(weaponProfile.ammunitionType || "")} onChange={(event) => setWeaponProfile((current) => ({ ...current, ammunitionType: event.target.value }))}><option value="freccia">Freccia</option><option value="dardo">Dardo</option><option value="proiettile">Proiettile</option></select></label><label>Caricatore (0 = arco)<input type="number" min="0" value={Number(weaponProfile.magazineSize || 0)} onChange={(event) => setWeaponProfile((current) => ({ ...current, magazineSize: Number(event.target.value) }))} /></label><label>Costo fisso ricarica<input type="number" min="0" value={Number(weaponProfile.reloadBaseCost || 0)} onChange={(event) => setWeaponProfile((current) => ({ ...current, reloadBaseCost: Number(event.target.value) }))} /></label><label>Costo per munizione<input type="number" min="0" value={Number(weaponProfile.reloadPerProjectileCost || 0)} onChange={(event) => setWeaponProfile((current) => ({ ...current, reloadPerProjectileCost: Number(event.target.value) }))} /></label></>}</div>
        <section className="weapon-suggestion-panel" data-component-type="panel" data-theme="gold"><div><strong>Modificatori suggeriti</strong><p>{previewEffects.map((effect) => `${effect.target} ${Number(effect.value) > 0 ? "+" : ""}${effect.value}`).join(" · ") || "Nessun modificatore numerico"}{lengthOption?.paPerAttacco != null ? ` · ${lengthOption.paPerAttacco} PA/attacco` : ""}</p><small>Vengono sostituite soltanto precedenti voci generate dal creator; gli effetti manuali restano intatti.</small></div><button type="button" className="button primary" onClick={applySuggestedModifiers}>Applica modificatori suggeriti</button></section>
        {costBand && <section className="weapon-cost-guideline"><div><strong>Linea guida Elder, non vincolante</strong><span>Peso {costBand.weight}{suggestedPrice != null ? ` · Valore ${suggestedPrice}` : " · scegli un materiale per il valore"}</span></div><button type="button" className="button secondary small" onClick={() => { setItemWeight(costBand.weight); if (suggestedPrice != null) setItemValue(suggestedPrice); }}>Copia prezzo e peso</button></section>}
      </fieldset>
      <fieldset><legend>Economia, peso e loot</legend><div className="form-grid three"><label>Valore<input name="valore" type="number" min="0" value={itemValue} onChange={(event) => setItemValue(event.target.value === "" ? "" : Number(event.target.value))} /></label><label>Peso<input name="peso" type="number" min="0" step="0.01" value={itemWeight} onChange={(event) => setItemWeight(event.target.value === "" ? "" : Number(event.target.value))} /></label><label>Rarità<select name="rarita" defaultValue={defaults.rarita}><option value="">Non specificata</option>{catalog.rarityChoices.map((choice) => <option key={choice.value} value={choice.value}>{choice.label}</option>)}</select></label><label>Livello loot<input name="lv_loot" defaultValue={defaults.lv_loot} /></label><label>Regione<input name="regione_loot" defaultValue={defaults.regione_loot} /></label><label>Peso regione<input name="peso_regione" type="number" min="0" step="0.1" defaultValue={defaults.peso_regione} /></label><label>PA per attacco<input name="pa_per_attacco" type="number" min="0" value={paCost} onChange={(event) => setPaCost(event.target.value === "" ? "" : Number(event.target.value))} /></label></div></fieldset>
      <fieldset><legend>Effetti Elder conservati</legend><p className="field-hint">Questi otto testi sono conservati senza interpretarli. Solo gli effetti strutturati sotto partecipano ai calcoli.</p><div className="form-grid">{elderEffects.map((value, index) => <label key={index}>Effetto {index + 1}<textarea name={`effetto_${index + 1}`} rows={2} maxLength={255} defaultValue={value} /></label>)}</div></fieldset>
      <fieldset><legend>Effetti</legend>
        <datalist id="item-effect-targets">{catalog.effectConfiguration.targets.map((target) => <option key={target.value} value={target.value}>{target.label}</option>)}</datalist>
        <div className="effect-editor-list">{effects.map((effect, index) => <div className="effect-editor-row" key={index}><input list="item-effect-targets" aria-label="Statistica o competenza" placeholder="Statistica o competenza" value={effect.target} onChange={(event) => setEffects((current) => current.map((entry, i) => i === index ? {...entry, target: event.target.value} : entry))} /><select aria-label="Operazione" value={effect.operation} onChange={(event) => setEffects((current) => current.map((entry, i) => i === index ? {...entry, operation: event.target.value} : entry))}>{operations.map((operation) => <option key={operation}>{operation}</option>)}</select><input aria-label="Valore" type="number" step="0.01" value={effect.value} onChange={(event) => setEffects((current) => current.map((entry, i) => i === index ? {...entry, value: event.target.value} : entry))} /><button type="button" className="icon-button danger" onClick={() => setEffects((current) => current.filter((_, i) => i !== index))} aria-label="Rimuovi effetto">×</button></div>)}</div>
        <p className="field-hint">Le voci “Competenza · … (extra)” restano collegate all'oggetto: il bonus sparisce quando non è equipaggiato.</p>
        <button type="button" className="button secondary small" onClick={() => setEffects((current) => [...current, { target: "", operation: "add", value: "0" }])}>Aggiungi effetto</button>
      </fieldset>
      <fieldset><legend>Profili strutturati</legend><div className="form-grid"><label>Profilo alchimia<textarea name="alchemy_profile" rows={6} defaultValue={defaults.alchemy_profile} spellCheck={false} /></label><label>Profilo crafting<textarea name="crafting_profile" rows={6} defaultValue={defaults.crafting_profile} spellCheck={false} /></label></div></fieldset>
      <fieldset><legend>Media e note</legend><div className="selected-media-field"><div>{selectedMedia ? <><img src={selectedMedia.thumbnailUrl || selectedMedia.url} alt="" /><span><strong>{selectedMedia.title}</strong><small>{selectedMedia.category} · {selectedMedia.group}</small></span></> : <span><strong>Nessuna immagine</strong><small>Scegli o carica un'immagine dall'archivio.</small></span>}</div><button className="button secondary" type="button" onClick={() => setImagePickerOpen(true)}>Scegli dall'archivio</button></div><ItemSpecialIconField itemId={clone ? null : item?.id ?? null} itemName={itemName} imageUrl={clone ? "" : item?.imageUrl || ""} /><label>Note di progettazione<textarea name="notes" rows={4} defaultValue={defaults.notes} /></label>{item?.metadata && <details><summary>Provenienza tecnica</summary><pre>{JSON.stringify(item.metadata, null, 2)}</pre></details>}</fieldset>
    </form>
  </Modal>{imagePickerOpen && <ImagePickerModal selectedId={selectedMediaId} usageType="item_icon" defaultGroup="Oggetti" defaultTitle={itemName || "Nuovo oggetto"} onSelect={(asset) => setSelectedMediaId(asset?.id || null)} onClose={() => setImagePickerOpen(false)} />}</>;
}
