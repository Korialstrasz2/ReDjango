import { describe, expect, it } from "vitest";

import type { CharacterSheet } from "../../lib/types";
import { coinDraftPreview } from "./CoinControls";

const storage: CharacterSheet["coinStorage"] = {
  coinsPerSlot: 300,
  requiredSlots: 0,
  placedSlots: 0,
  availableSlots: 2,
  maxCarryableCoins: 600,
  fits: true,
  coinItemId: null,
  sharedCoins: 0,
  canTransferToShared: true,
};

describe("anteprima monete trasportate", () => {
  it("mostra la carenza di spazi prima del salvataggio", () => {
    expect(coinDraftPreview("700", storage)).toEqual({
      value: 700,
      requiredSlots: 3,
      overflow: true,
      overflowCoins: 100,
    });
  });

  it("calcola un numero enorme senza creare slot virtuali", () => {
    const preview = coinDraftPreview("99999999", storage);
    expect(preview.requiredSlots).toBe(333334);
    expect(preview.overflow).toBe(true);
    expect(preview.overflowCoins).toBe(99_999_399);
  });

  it("rifiuta valori fuori dal limite sicuro", () => {
    expect(coinDraftPreview("2147483648", storage).value).toBeNull();
  });
});
