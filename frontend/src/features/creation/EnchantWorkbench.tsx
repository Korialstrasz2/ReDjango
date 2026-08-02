import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useApp } from "../../App";
import { command, getData } from "../../lib/api";
import { formatNumber, type EnchantData } from "./craftingTypes";

type EnchantTab = "incanta" | "pergamene" | "cariche";
type EnchantActionData = { enchant: EnchantData; enchantResult?: Record<string, unknown> };

function AltarBar({
  data,
  altarId,
  onAltar,
}: {
  data: EnchantData;
  altarId: number | null;
  onAltar: (id: number | null) => void;
}) {
  const altar = data.altars.find((entry) => entry.itemId === altarId) || null;
  return <section className="panel alchemy-set-bar enchant-altar-bar">
    <label>Altare
      <select value={altarId ?? ""} onChange={(event) => onAltar(event.target.value ? Number(event.target.value) : null)}>
        <option value="">Nessun altare · nessun bonus</option>
        {data.altars.map((entry) => <option key={entry.itemId} value={entry.itemId}>
          {entry.name} · +{entry.bonusPercent}% mana
        </option>)}
      </select>
    </label>
    <p className="alchemy-inline-hint">
      {data.altars.length === 0
        ? "Nessun altare nello zaino: si incanta a mani nude, senza bonus al mana."
        : altar
          ? `${altar.name} · +${altar.bonusPercent}% al mana di ogni livello${altar.portable ? " · portatile" : ""}`
          : "Stai incantando senza altare: il mana resta quello base."}
    </p>
  </section>;
}

function Incanta({ data }: { data: EnchantData }) {
  const { notify } = useApp();
  const queryClient = useQueryClient();
  const [targetId, setTargetId] = useState(data.targets[0]?.itemId || 0);
  // Le gemme si tengono per **slot**: due gemme identiche sono la stessa riga
  // di catalogo, quindi sceglierle per id ne selezionerebbe due insieme.
  const [gemSlots, setGemSlots] = useState<number[]>([]);
  const [kind, setKind] = useState("");
  const [altarId, setAltarId] = useState<number | null>(data.altars[0]?.itemId ?? null);
  const [useFatigue, setUseFatigue] = useState(false);

  const target = data.targets.find((entry) => entry.itemId === targetId) || data.targets[0];
  const filledGems = data.gems.filter((gem) => gem.filled);
  const selectedGems = filledGems.filter((gem) => gemSlots.includes(gem.slot));

  // Con Artigiano di anime le gemme si sommano a scalare: la prima intera, la
  // seconda a metà, la terza a un terzo. Senza, vale solo quella scelta.
  const level = useMemo(() => {
    if (!selectedGems.length) return 0;
    if (selectedGems.length === 1) return selectedGems[0].level;
    const ordered = [...selectedGems].sort((a, b) => b.level - a.level);
    const sum = ordered.reduce((total, gem, index) => total + gem.level / (index + 1), 0);
    return Math.min(10, Math.floor(sum));
  }, [selectedGems]);

  const boosted = Math.min(10, level + (useFatigue ? data.capability.fatigueLevelBonus : 0));
  const altar = data.altars.find((entry) => entry.itemId === altarId);
  const mana = Math.round(boosted * data.capability.manaPerLevel * (1 + (altar?.bonus || 0)) * 100) / 100;
  const charges = Math.max(boosted, Math.floor(boosted * (1 + data.capability.chargeBonusPercent / 100)));
  const overCap = boosted > data.capability.maxItemLevel;

  const kindsQuery = useQuery({
    queryKey: ["enchant-kinds", data.character.id, target?.type, boosted],
    queryFn: () =>
      getData<EnchantData>(
        `/api/v1/characters/${data.character.id}/creation/enchant?slotType=${target?.type}&level=${boosted}`,
      ),
    enabled: Boolean(target?.type && boosted > 0),
  });
  const kinds = kindsQuery.data?.preview.kinds || [];
  useEffect(() => {
    if (kinds.length && !kinds.some((entry) => entry.kind === kind)) setKind(kinds[0].kind);
  }, [kind, kinds]);

  const enchant = useMutation({
    mutationFn: () => command<EnchantActionData>("enchant.item", {
      characterId: data.character.id,
      targetItemId: targetId,
      gemSlots,
      kind,
      altarItemId: altarId,
      useFatigue,
    }, "creation"),
    onSuccess: (response) => {
      queryClient.setQueryData(["enchant", data.character.id], response.data.enchant);
      queryClient.invalidateQueries({ queryKey: ["character-sheet", data.character.id] });
      setGemSlots([]);
      notify(response.events[0]?.message || "Oggetto incantato.");
    },
    onError: (error: Error) => notify(error.message, "error"),
  });

  const toggleGem = (slot: number) => {
    setGemSlots((current) => {
      if (current.includes(slot)) return current.filter((entry) => entry !== slot);
      if (!data.capability.canCombineGems) return [slot];
      return [...current, slot];
    });
  };

  if (data.capability.maxItemLevel <= 0) return <section className="panel empty-state">
    <h2>Non sei ancora un incantatore</h2>
    <p>Serve «Incantatore 1» per infondere il primo oggetto. Gioielliere 1–7 alza poi il tetto fino al livello 10.</p>
  </section>;

  return <div className="enchant-workspace">
    <div className="enchant-left-column">
      <AltarBar data={data} altarId={altarId} onAltar={setAltarId} />

      <section className="panel enchant-gem-panel">
        <header className="alchemy-section-heading">
          <div><p className="eyebrow">Gemme dell'anima</p><h2>Il livello lo decide la gemma</h2></div>
          <div className="alchemy-capacity"><strong>{filledGems.length}</strong><span>piene</span></div>
        </header>
        <div className="enchant-gem-grid">
          {data.gems.map((gem) => <button
            type="button"
            key={gem.slot}
            className={`enchant-gem ${gem.filled ? "filled" : "empty"} ${gemSlots.includes(gem.slot) ? "active" : ""}`}
            disabled={!gem.filled}
            onClick={() => toggleGem(gem.slot)}
            title={gem.filled ? `${gem.name}` : `${gem.name} — vuota, serve un'anima`}
          >
            <strong>{gem.level}</strong>
            <small>{gem.filled ? "piena" : "vuota"}</small>
          </button>)}
          {!data.gems.length && <p className="alchemy-inline-hint">Nessuna gemma dell'anima nello zaino.</p>}
        </div>
        {data.capability.canCombineGems && <p className="alchemy-inline-hint">
          «Artigiano di anime»: puoi sommare più gemme — la prima vale intera, la seconda a metà, la terza a un terzo.
        </p>}
      </section>

      <section className="panel enchant-target-panel">
        <header className="alchemy-section-heading">
          <div><p className="eyebrow">Oggetto</p><h2>Cosa infondere</h2></div>
        </header>
        <div className="enchant-target-list">
          {data.targets.map((entry) => <button
            type="button"
            key={entry.itemId}
            className={`enchant-target ${entry.itemId === target?.itemId ? "active" : ""}`}
            onClick={() => setTargetId(entry.itemId)}
          >
            <strong>{entry.name}</strong>
            <small>{entry.type}{entry.existingEffects ? ` · ${entry.existingEffects} effetti` : ""}</small>
          </button>)}
          {!data.targets.length && <p className="alchemy-inline-hint">
            Nessun gioiello, fascia, spilla, cintura o mantello incantabile nello zaino.
          </p>}
        </div>
      </section>
    </div>

    <section className="panel enchant-bench-panel">
      <header className="alchemy-section-heading">
        <div><p className="eyebrow">Banco d'infusione</p><h2>Componi l'incantamento</h2></div>
        <span className="alchemy-step">max livello {data.capability.maxItemLevel}</span>
      </header>

      <div className="alchemy-formula-card enchant-formula">
        <div><span>Livello</span><strong>{boosted || "—"}</strong></div>
        <span aria-hidden="true">×</span>
        <div><span>Mana per livello{altar ? ` +${altar.bonusPercent}%` : ""}</span><strong>{formatNumber(data.capability.manaPerLevel)}</strong></div>
        <span aria-hidden="true">=</span>
        <div className="alchemy-potency">
          <span>Mana</span><strong>{formatNumber(mana)}</strong>
          <small>{charges} cariche</small>
        </div>
      </div>

      {data.capability.fatigueLevelBonus > 0 && <label className="forge-fatigue-toggle">
        <input type="checkbox" checked={useFatigue} onChange={(event) => setUseFatigue(event.target.checked)} />
        <span>Spendi 1 Stanchezza per +1 livello <small>«Mana e anima»</small></span>
      </label>}

      {boosted > 0 && <div className="enchant-kind-picker">
        <label>Effetto
          <select value={kind} onChange={(event) => setKind(event.target.value)} disabled={!kinds.length}>
            {kinds.map((entry) => <option key={entry.kind} value={entry.kind}>{entry.label}</option>)}
          </select>
        </label>
        {kindsQuery.isLoading && <p className="alchemy-inline-hint">Consulto del catalogo…</p>}
        {!kindsQuery.isLoading && !kinds.length && <p className="alchemy-inline-hint">
          Nessun effetto disponibile per questo slot al livello {boosted}.
        </p>}
      </div>}

      {overCap && <p className="alchemy-inline-hint">
        Il livello {boosted} supera il tuo tetto di {data.capability.maxItemLevel}: serve un Gioielliere più alto.
      </p>}

      <button
        className="button primary alchemy-brew-button"
        type="button"
        disabled={enchant.isPending || !gemSlots.length || !kind || !target || overCap}
        onClick={() => enchant.mutate()}
      >
        {enchant.isPending ? "Infusione…" : "Infondi e consuma la gemma"}
      </button>
    </section>
  </div>;
}

function Pergamene({ data }: { data: EnchantData }) {
  const { notify } = useApp();
  const queryClient = useQueryClient();
  const [spellId, setSpellId] = useState(data.spells[0]?.spellId || 0);
  const [mana, setMana] = useState(12);
  const [altarId, setAltarId] = useState<number | null>(data.altars[0]?.itemId ?? null);

  const altar = data.altars.find((entry) => entry.itemId === altarId);
  const boosted = Math.round(mana * (1 + (altar?.bonus || 0)) * 100) / 100;
  const level = data.scrollLadder.reduce((found, threshold, index) => (boosted >= threshold ? index + 1 : found), 0);
  const castEffect = Math.round(boosted * 0.5 * 100) / 100;
  const overCap = level > data.capability.maxScrollLevel;

  const inscribe = useMutation({
    mutationFn: () => command<EnchantActionData>("enchant.scroll", {
      characterId: data.character.id,
      spellId,
      manaSpent: mana,
      altarItemId: altarId,
    }, "creation"),
    onSuccess: (response) => {
      queryClient.setQueryData(["enchant", data.character.id], response.data.enchant);
      notify(response.events[0]?.message || "Pergamena scritta.");
    },
    onError: (error: Error) => notify(error.message, "error"),
  });

  if (data.capability.maxScrollLevel <= 0) return <section className="panel empty-state">
    <h2>Non sai ancora scrivere pergamene</h2>
    <p>Serve «Incantatore 1»; Scriba 1–7 porta poi le pergamene fino al livello 10.</p>
  </section>;
  if (!data.spells.length) return <section className="panel empty-state">
    <h2>Non conosci incantesimi</h2>
    <p>Si imprime solo ciò che si sa lanciare: sblocca un incantesimo dalla pagina Abilità.</p>
  </section>;

  return <div className="enchant-workspace">
    <div className="enchant-left-column">
      <AltarBar data={data} altarId={altarId} onAltar={setAltarId} />
      <section className="panel">
        <header className="alchemy-section-heading">
          <div><p className="eyebrow">Scala delle pergamene</p><h2>Il mana decide il livello</h2></div>
        </header>
        <div className="alchemy-thresholds">
          {data.scrollLadder.map((threshold, index) => <span key={threshold} className={level === index + 1 ? "active" : ""}>
            <small>Lv {index + 1}</small><strong>{threshold}</strong>
          </span>)}
        </div>
        <p className="alchemy-inline-hint">L'effetto della pergamena è la metà del mana impresso.</p>
      </section>
    </div>

    <section className="panel enchant-bench-panel">
      <header className="alchemy-section-heading">
        <div><p className="eyebrow">Scriptorium</p><h2>Imprimi l'incantesimo</h2></div>
        <span className="alchemy-step">max livello {data.capability.maxScrollLevel}</span>
      </header>
      <div className="alchemy-brew-form">
        <label>Incantesimo
          <select value={spellId} onChange={(event) => setSpellId(Number(event.target.value))}>
            {data.spells.map((spell) => <option key={spell.spellId} value={spell.spellId}>
              {spell.name} · {spell.school}
            </option>)}
          </select>
        </label>
        <label>Mana impresso
          <input
            type="number"
            min={1}
            max={400}
            value={mana}
            onChange={(event) => setMana(Math.max(1, Number(event.target.value) || 1))}
          />
        </label>
      </div>

      <div className="alchemy-formula-card enchant-formula">
        <div><span>Impresso{altar ? ` +${altar.bonusPercent}%` : ""}</span><strong>{formatNumber(boosted)}</strong></div>
        <span aria-hidden="true">÷2</span>
        <div><span>Casta con</span><strong>{formatNumber(castEffect)}</strong></div>
        <span aria-hidden="true">=</span>
        <div className="alchemy-potency">
          <span>Pergamena</span><strong>{level || "—"}</strong>
          <small>{level ? `livello ${level}` : "sotto le 12 di mana"}</small>
        </div>
      </div>

      {overCap && <p className="alchemy-inline-hint">
        Con {formatNumber(boosted)} mana uscirebbe una pergamena di livello {level}, oltre il tuo tetto di {data.capability.maxScrollLevel}.
      </p>}

      <button
        className="button primary alchemy-brew-button"
        type="button"
        disabled={inscribe.isPending || !level || overCap}
        onClick={() => inscribe.mutate()}
      >
        {inscribe.isPending ? "Scrittura…" : "Imprimi la pergamena"}
      </button>
    </section>
  </div>;
}

function Cariche({ data }: { data: EnchantData }) {
  const { notify } = useApp();
  const queryClient = useQueryClient();
  const mutate = (action: string) => ({
    mutationFn: (instanceId: number) =>
      command<EnchantActionData>(action, { characterId: data.character.id, instanceId }, "creation"),
    onSuccess: (response: { data: EnchantActionData; events: Array<{ message: string }> }) => {
      queryClient.setQueryData(["enchant", data.character.id], response.data.enchant);
      queryClient.invalidateQueries({ queryKey: ["character-sheet", data.character.id] });
      notify(response.events[0]?.message || "Fatto.");
    },
    onError: (error: Error) => notify(error.message, "error"),
  });
  const recharge = useMutation(mutate("enchant.recharge"));
  const disenchant = useMutation(mutate("enchant.disenchant"));

  if (!data.enchanted.length) return <section className="panel empty-state">
    <h2>Nessun oggetto incantato</h2>
    <p>Gli oggetti che infondi e le pergamene che scrivi compaiono qui con le loro cariche.</p>
  </section>;

  return <section className="panel">
    <header className="alchemy-section-heading">
      <div><p className="eyebrow">Il tuo lavoro</p><h2>Cariche e manutenzione</h2></div>
      <span className="alchemy-step">ricarica manuale</span>
    </header>
    <div className="enchant-inventory">
      {data.enchanted.map((entry) => <article key={entry.instanceId} className="enchant-card">
        <header>
          <strong>{entry.name}</strong>
          <small>{entry.kind === "scroll" ? `Pergamena lv ${entry.scrollLevel} · ${entry.spell}` : entry.type}</small>
        </header>
        {entry.effects.map((effect) => <div className="enchant-charge-row" key={effect.kind}>
          <span>{effect.label} <em>lv {effect.level}</em></span>
          <span className="enchant-charge-pips" aria-label={`${effect.charges} cariche su ${effect.chargesMax}`}>
            {Array.from({ length: effect.chargesMax }, (_, index) => <i key={index} className={index < effect.charges ? "full" : ""} />)}
          </span>
        </div>)}
        {entry.castEffect > 0 && <p className="enchant-card-note">Casta a {formatNumber(entry.castEffect)} mana.</p>}
        <footer>
          {entry.effects.length > 0 && <button type="button" className="button secondary" disabled={recharge.isPending} onClick={() => recharge.mutate(entry.instanceId)}>
            Ricarica
          </button>}
          {data.capability.canDisenchant && entry.effects.length > 0 && <button type="button" className="button ghost" disabled={disenchant.isPending} onClick={() => disenchant.mutate(entry.instanceId)}>
            Disincanta
          </button>}
        </footer>
      </article>)}
    </div>
  </section>;
}

export function EnchantWorkbench({ characterId }: { characterId: number }) {
  const [tab, setTab] = useState<EnchantTab>("incanta");
  const query = useQuery({
    queryKey: ["enchant", characterId],
    queryFn: () => getData<EnchantData>(`/api/v1/characters/${characterId}/creation/enchant`),
    enabled: Boolean(characterId),
  });

  if (query.isLoading) return <section className="panel loading-state">Accensione dell'altare…</section>;
  if (query.isError) return <section className="panel form-error">{(query.error as Error).message}</section>;
  if (!query.data) return null;
  const data = query.data;

  return <div className="crafting-bench">
    <nav className="crafting-subtabs" aria-label="Banchi di incantamento">
      <button type="button" className={tab === "incanta" ? "active" : ""} onClick={() => setTab("incanta")}>Incanta oggetto</button>
      <button type="button" className={tab === "pergamene" ? "active" : ""} onClick={() => setTab("pergamene")}>Pergamene</button>
      <button type="button" className={tab === "cariche" ? "active" : ""} onClick={() => setTab("cariche")}>
        Cariche{data.enchanted.length ? <em>{data.enchanted.length}</em> : null}
      </button>
    </nav>

    {tab === "incanta" && <Incanta data={data} />}
    {tab === "pergamene" && <Pergamene data={data} />}
    {tab === "cariche" && <Cariche data={data} />}

    {data.tableRules.length > 0 && <section className="panel forge-rules-panel">
      <p className="eyebrow">Abilità che il motore non calcola</p>
      <ul>{data.tableRules.map((rule) => <li key={rule.skill}><strong>{rule.skill}</strong> — {rule.text}</li>)}</ul>
    </section>}
  </div>;
}
