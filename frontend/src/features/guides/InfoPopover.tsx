import { type ReactNode, useCallback, useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

type Props = {
  /** Testo del richiamo mostrato nella pagina. */
  label: ReactNode;
  /** Titolo della nota aperta. */
  title: string;
  children: ReactNode;
  /** Descrizione accessibile del comando, quando l'etichetta è solo un simbolo. */
  hint?: string;
  className?: string;
};

const NOTE_WIDTH = 340;
const VIEWPORT_MARGIN = 12;

/** Nota consultabile ancorata al richiamo che l'ha aperta.
 *
 * Il portale su `body` la tiene sopra la finestra della scheda oggetto, che
 * altrimenti ne taglierebbe il contesto di impilamento; la posizione viene
 * ricalcolata a ogni scorrimento perché il richiamo vive in un pannello che
 * scorre con la pagina.
 */
export function InfoPopover({ label, title, children, hint, className = "" }: Props) {
  const [open, setOpen] = useState(false);
  const [placement, setPlacement] = useState<{ top: number; left: number } | null>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const noteRef = useRef<HTMLDivElement>(null);
  const noteId = useId();

  const reposition = useCallback(() => {
    const trigger = triggerRef.current;
    if (!trigger) return;
    const anchor = trigger.getBoundingClientRect();
    const height = noteRef.current?.offsetHeight ?? 0;
    const left = Math.max(
      VIEWPORT_MARGIN,
      Math.min(anchor.left, window.innerWidth - NOTE_WIDTH - VIEWPORT_MARGIN),
    );
    // Sotto il richiamo quando c'è spazio, sopra quando la nota uscirebbe dallo schermo.
    const below = anchor.bottom + 9;
    const preferred = height && below + height > window.innerHeight - VIEWPORT_MARGIN
      ? anchor.top - height - 9
      : below;
    // Il richiamo può essere appena fuori dall'area visibile mentre la pagina
    // scorre: la nota resta comunque interamente leggibile.
    const top = Math.max(
      VIEWPORT_MARGIN,
      Math.min(preferred, window.innerHeight - height - VIEWPORT_MARGIN),
    );
    setPlacement({ top, left });
  }, []);

  useLayoutEffect(() => {
    if (!open) {
      setPlacement(null);
      return;
    }
    reposition();
  }, [open, reposition]);

  // Il fuoco si sposta sulla nota solo dopo che è stata collocata, così la
  // lettura da tastiera parte dal contenuto invece che dal richiamo. La
  // dipendenza è il solo "è collocata", non la posizione: lo scorrimento
  // ricalcola le coordinate senza riprendersi il fuoco. Nessun riferimento
  // mutabile fa da guardia, perché StrictMode esegue gli effetti due volte e
  // una guardia del genere resterebbe alzata dopo la passata scartata.
  const placed = placement !== null;
  useEffect(() => {
    const note = noteRef.current;
    if (!open || !placed || !note || note.contains(document.activeElement)) return;
    note.focus();
  }, [open, placed]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.stopPropagation();
      setOpen(false);
      triggerRef.current?.focus();
    };
    const onPointerDown = (event: PointerEvent) => {
      const target = event.target as Node;
      if (noteRef.current?.contains(target) || triggerRef.current?.contains(target)) return;
      setOpen(false);
    };
    window.addEventListener("keydown", onKeyDown, true);
    window.addEventListener("pointerdown", onPointerDown, true);
    window.addEventListener("resize", reposition);
    window.addEventListener("scroll", reposition, true);
    return () => {
      window.removeEventListener("keydown", onKeyDown, true);
      window.removeEventListener("pointerdown", onPointerDown, true);
      window.removeEventListener("resize", reposition);
      window.removeEventListener("scroll", reposition, true);
    };
  }, [open, reposition]);

  return <>
    <button
      ref={triggerRef}
      type="button"
      className={`codex-link ${className}`.trim()}
      data-component-type="button"
      data-theme="gold"
      aria-expanded={open}
      aria-controls={open ? noteId : undefined}
      aria-label={hint}
      title={hint || `Apri la nota: ${title}`}
      onClick={() => setOpen((value) => !value)}
    >{label}</button>
    {open && createPortal(
      <div
        ref={noteRef}
        id={noteId}
        className="codex-note"
        data-component-type="panel"
        data-theme="parchment"
        role="note"
        tabIndex={-1}
        // La nota viene misurata prima di sapere dove sta: resta trasparente per
        // un fotogramma, non nascosta, perché `visibility: hidden` impedirebbe
        // di darle il fuoco da tastiera.
        style={{ top: placement?.top ?? 0, left: placement?.left ?? 0, opacity: placement ? 1 : 0 }}
      >
        <header>
          <strong>{title}</strong>
          <button type="button" className="icon-button" aria-label="Chiudi la nota" onClick={() => { setOpen(false); triggerRef.current?.focus(); }}>×</button>
        </header>
        <div className="codex-note-body">{children}</div>
      </div>,
      document.body,
    )}
  </>;
}
