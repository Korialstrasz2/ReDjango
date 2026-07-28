import { type ChangeEvent, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { useApp } from "../App";
import { ITEM_ICON_SIZE, deleteItemSpecialIcon, uploadItemSpecialIcon } from "../lib/api";

type Props = {
  itemId: number | null;
  itemName: string;
  imageUrl: string;
};

/**
 * Uploads a dedicated icon for one item. The picked file is centre-cropped to a
 * square and re-encoded as a 128x128 WebP before it leaves the browser.
 */
export function ItemSpecialIconField({ itemId, itemName, imageUrl }: Props) {
  const { notify } = useApp();
  const queryClient = useQueryClient();
  const fileInput = useRef<HTMLInputElement>(null);
  const [preview, setPreview] = useState("");

  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["item-search"] }),
      queryClient.invalidateQueries({ queryKey: ["item-catalog-config"] }),
      queryClient.invalidateQueries({ queryKey: ["character-sheet"] }),
    ]);
  };

  const uploadMutation = useMutation({
    mutationFn: (file: File) => uploadItemSpecialIcon(itemId as number, file),
    onSuccess: async (response) => {
      setPreview(`${response.data.item.imageUrl}?t=${Date.now()}`);
      await refresh();
      notify(response.events[0]?.message || "Icona dedicata aggiornata.");
    },
    onError: (error: Error) => notify(error.message, "error"),
  });

  const removeMutation = useMutation({
    mutationFn: () => deleteItemSpecialIcon(itemId as number),
    onSuccess: async (response) => {
      setPreview(`${response.data.item.imageUrl}?t=${Date.now()}`);
      await refresh();
      notify(response.events[0]?.message || "Icona dedicata rimossa.");
    },
    onError: (error: Error) => notify(error.message, "error"),
  });

  const pick = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (file) uploadMutation.mutate(file);
  };

  const busy = uploadMutation.isPending || removeMutation.isPending;
  return <div className="item-special-icon-field">
    <div className="item-special-icon-preview">
      {(preview || imageUrl)
        ? <img src={preview || imageUrl} alt={`Icona di ${itemName || "oggetto"}`} width={ITEM_ICON_SIZE} height={ITEM_ICON_SIZE} />
        : <span aria-hidden="true">◇</span>}
    </div>
    <div className="item-special-icon-controls">
      <strong>Icona dedicata</strong>
      <small>
        {itemId
          ? `Ritagliata al centro in quadrato e salvata come WebP ${ITEM_ICON_SIZE}×${ITEM_ICON_SIZE}. Senza icona dedicata l'oggetto usa quella della sua categoria.`
          : "Salva prima l'oggetto: l'icona dedicata si carica solo su un oggetto esistente."}
      </small>
      <input ref={fileInput} className="sr-only" type="file" accept="image/*" onChange={pick} disabled={!itemId || busy} />
      <div className="item-special-icon-buttons">
        <button className="button secondary small" type="button" disabled={!itemId || busy} onClick={() => fileInput.current?.click()}>
          {uploadMutation.isPending ? "Caricamento…" : "Carica icona"}
        </button>
        <button className="button secondary small" type="button" disabled={!itemId || busy} onClick={() => removeMutation.mutate()}>
          {removeMutation.isPending ? "Rimozione…" : "Rimuovi"}
        </button>
      </div>
    </div>
  </div>;
}
