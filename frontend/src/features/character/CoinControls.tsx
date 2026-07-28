import { type KeyboardEvent, useEffect, useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { useApp } from "../../App";
import { command } from "../../lib/api";
import type { CharacterSheet } from "../../lib/types";

type ActionData = { character?: CharacterSheet | null };

type CoinMutation = {
  coins: number;
  expectedCoins: number;
  transferOverflow?: boolean;
  expectedSharedCoins?: number;
};

function parsedBalance(value: string): number | null {
  if (!/^\d+$/.test(value.trim())) return null;
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) && parsed >= 0 && parsed <= 2_147_483_647 ? parsed : null;
}

export function coinDraftPreview(
  draft: string,
  storage: CharacterSheet["coinStorage"],
): { value: number | null; requiredSlots: number | null; overflow: boolean; overflowCoins: number } {
  const value = parsedBalance(draft);
  const requiredSlots = value == null ? null : value === 0 ? 0 : Math.ceil(value / storage.coinsPerSlot);
  const overflow = requiredSlots != null && requiredSlots > storage.availableSlots;
  return {
    value,
    requiredSlots,
    overflow,
    overflowCoins: value == null ? 0 : Math.max(0, value - storage.maxCarryableCoins),
  };
}

function useSyncedDraft(savedValue: number) {
  const [draft, setDraft] = useState(String(savedValue));
  const previousSaved = useRef(savedValue);
  useEffect(() => {
    setDraft((current) => current === String(previousSaved.current) ? String(savedValue) : current);
    previousSaved.current = savedValue;
  }, [savedValue]);
  return [draft, setDraft] as const;
}

export function CarriedCoinsControl({ character, onUpdate }: {
  character: CharacterSheet;
  onUpdate: (character: CharacterSheet) => void;
}) {
  const { notify } = useApp();
  const [draft, setDraft] = useSyncedDraft(character.coins);
  const storage = character.coinStorage;
  const { value, requiredSlots, overflow, overflowCoins } = coinDraftPreview(draft, storage);
  const dirty = value !== character.coins;

  const mutation = useMutation({
    mutationFn: (payload: CoinMutation) => command<ActionData>("character.updateCoins", {
      characterId: character.id,
      ...payload,
    }),
    onSuccess: (result, variables) => {
      if (!result.data.character) return;
      onUpdate(result.data.character);
      setDraft((current) => parsedBalance(current) === variables.coins
        ? String(result.data.character!.coins)
        : current);
      const transferred = variables.transferOverflow ? variables.coins - result.data.character.coins : 0;
      notify(transferred > 0
        ? `${transferred} monete trasferite alle risorse condivise.`
        : "Monete trasportate aggiornate.");
    },
    onError: (error: Error) => notify(error.message, "error"),
  });

  const save = (coins: number, transferOverflow = false) => {
    if (mutation.isPending || (!transferOverflow && coins === character.coins)) return;
    mutation.mutate({
      coins,
      expectedCoins: character.coins,
      transferOverflow,
      expectedSharedCoins: transferOverflow ? storage.sharedCoins : undefined,
    });
  };

  useEffect(() => {
    if (value == null || overflow || !dirty || mutation.isPending) return;
    const timer = window.setTimeout(() => save(value), 1000);
    return () => window.clearTimeout(timer);
  }, [dirty, mutation.isPending, overflow, value]);

  const saveOnCommit = () => {
    if (value != null && !overflow) save(value);
  };
  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter") {
      event.preventDefault();
      saveOnCommit();
      event.currentTarget.blur();
    }
  };
  return <div
    className={`carried-coins-control ${dirty ? "dirty" : ""} ${overflow ? "overflow" : ""}`}
    data-component-type="field"
    data-theme={overflow ? "danger" : "gold"}
    data-state={mutation.isPending ? "saving" : overflow ? "invalid" : dirty ? "dirty" : "saved"}
  >
    <label htmlFor="character-carried-coins">Monete</label>
    <input
      id="character-carried-coins"
      type="number"
      min={0}
      max={2_147_483_647}
      step={1}
      inputMode="numeric"
      value={draft}
      aria-invalid={value == null || overflow}
      onChange={(event) => setDraft(event.target.value)}
      onBlur={saveOnCommit}
      onKeyDown={onKeyDown}
    />
    <span className="coin-save-state" aria-live="polite">
      {mutation.isPending ? "salvataggio…" : overflow ? "troppi spazi" : dirty ? "salvataggio automatico" : "salvato"}
    </span>
    {overflow && requiredSlots != null && <div className="coin-overflow-popover" role="alert">
      <strong>Servono {requiredSlots} spazi, disponibili {storage.availableSlots}.</strong>
      <span>Puoi trasportare al massimo {storage.maxCarryableCoins} monete.</span>
      <div>
        <button type="button" disabled={mutation.isPending} onClick={() => {
          setDraft(String(storage.maxCarryableCoins));
          save(storage.maxCarryableCoins);
        }}>
          Imposta il massimo trasportabile
        </button>
        {storage.canTransferToShared && <button
          type="button"
          disabled={mutation.isPending || overflowCoins <= 0}
          onClick={() => value != null && save(value, true)}
        >
          Trasferisci {overflowCoins} alle condivise
        </button>}
      </div>
    </div>}
  </div>;
}

export function SharedCoinsCard({ character, onUpdate }: {
  character: CharacterSheet;
  onUpdate: (character: CharacterSheet) => void;
}) {
  const { notify } = useApp();
  const saved = character.coinStorage.sharedCoins;
  const [draft, setDraft] = useSyncedDraft(saved);
  const value = parsedBalance(draft);
  const dirty = value !== saved;
  const mutation = useMutation({
    mutationFn: (coins: number) => command<ActionData>("campaign.updateSharedCoins", {
      characterId: character.id,
      coins,
      expectedCoins: saved,
    }),
    onSuccess: (result, requested) => {
      if (!result.data.character) return;
      onUpdate(result.data.character);
      setDraft((current) => parsedBalance(current) === requested
        ? String(result.data.character!.coinStorage.sharedCoins)
        : current);
      notify("Monete condivise aggiornate.");
    },
    onError: (error: Error) => notify(error.message, "error"),
  });
  const save = () => {
    if (value != null && dirty && !mutation.isPending) mutation.mutate(value);
  };
  useEffect(() => {
    if (value == null || !dirty || mutation.isPending) return;
    const timer = window.setTimeout(save, 1000);
    return () => window.clearTimeout(timer);
  }, [dirty, mutation.isPending, value]);

  return <article
    className={`shared-coins-card ${dirty ? "dirty" : ""}`}
    data-component-type="card"
    data-theme="gold"
    data-state={mutation.isPending ? "saving" : value == null ? "invalid" : dirty ? "dirty" : "saved"}
  >
    <header><span>Risorsa condivisa</span><em>non occupa spazio</em></header>
    <strong>Monete condivise</strong>
    <input
      aria-label="Monete condivise"
      type="number"
      min={0}
      max={2_147_483_647}
      step={1}
      inputMode="numeric"
      value={draft}
      aria-invalid={value == null}
      onChange={(event) => setDraft(event.target.value)}
      onBlur={save}
      onKeyDown={(event) => {
        if (event.key === "Enter") {
          event.preventDefault();
          save();
          event.currentTarget.blur();
        }
      }}
    />
    <small aria-live="polite">{mutation.isPending ? "Salvataggio…" : dirty ? "Salvataggio automatico" : "Disponibili al gruppo"}</small>
  </article>;
}
