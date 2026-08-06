import { type CSSProperties, type PointerEvent as ReactPointerEvent, type ReactNode, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { useResponsiveLayout } from "../lib/responsive";
import { useSurfaceBackground } from "../lib/surfaces";

export type ResponsiveMode = "auto" | "dialog" | "sheet" | "fullscreen";

type Props = {
  title: string;
  children: ReactNode;
  footer?: ReactNode;
  onClose: () => void;
  wide?: boolean;
  className?: string;
  resizable?: boolean;
  /** Nasconde intestazione e pulsante di chiusura: il piè di pagina diventa la maniglia di trascinamento. */
  hideHeader?: boolean;
  /** Rende trascinabile anche il corpo: qualsiasi spazio vuoto diventa una maniglia. */
  dragFromBody?: boolean;
  /** Superficie del tema da cui prendere lo sfondo: vedi backend/core/theme_surfaces.py. */
  surface?: string;
  /** Presentazione richiesta sui telefoni. Desktop conserva sempre il dialogo esistente. */
  responsiveMode?: ResponsiveMode;
  /** Mantiene il comportamento storico; i form con stato non salvato possono disabilitarlo esplicitamente. */
  closeOnBackdrop?: boolean;
};

type ResizeEdge = "top" | "right" | "bottom" | "left";
type ModalPresentation = "dialog" | "sheet" | "fullscreen";

const MIN_MODAL_WIDTH = 360;
const MIN_MODAL_HEIGHT = 240;
const FOCUSABLE_SELECTOR = [
  "a[href]",
  "area[href]",
  "button:not([disabled])",
  "input:not([disabled]):not([type='hidden'])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "iframe",
  "object",
  "embed",
  "[contenteditable='true']",
  "[tabindex]:not([tabindex='-1'])",
].join(",");

let mobileBodyLockCount = 0;
let bodyOverflowBeforeMobileLock = "";
let modalSequence = 0;
const modalStack: number[] = [];

function lockBodyScroll(): () => void {
  if (mobileBodyLockCount === 0) {
    bodyOverflowBeforeMobileLock = document.body.style.overflow;
    document.body.style.overflow = "hidden";
  }
  mobileBodyLockCount += 1;
  return () => {
    mobileBodyLockCount = Math.max(0, mobileBodyLockCount - 1);
    if (mobileBodyLockCount === 0) document.body.style.overflow = bodyOverflowBeforeMobileLock;
  };
}

function focusableElements(root: HTMLElement): HTMLElement[] {
  return Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)).filter((element) => {
    if (element.getAttribute("aria-hidden") === "true") return false;
    return element.getClientRects().length > 0;
  });
}

function isTopModal(id: number): boolean {
  return modalStack.at(-1) === id;
}

function syncModalStack() {
  const topId = modalStack.at(-1);
  document.querySelectorAll<HTMLElement>("[data-modal-instance]").forEach((modal) => {
    const id = Number(modal.dataset.modalInstance);
    const top = id === topId;
    modal.toggleAttribute("data-modal-top", top);
    modal.toggleAttribute("aria-hidden", !top);
    (modal as HTMLElement & { inert: boolean }).inert = !top;
  });
}

function registerModal(id: number): () => void {
  modalStack.push(id);
  syncModalStack();
  return () => {
    const index = modalStack.lastIndexOf(id);
    if (index >= 0) modalStack.splice(index, 1);
    syncModalStack();
  };
}

export function Modal({
  title,
  children,
  footer,
  onClose,
  wide = false,
  className = "",
  resizable = false,
  hideHeader = false,
  dragFromBody = false,
  surface,
  responsiveMode = "auto",
  closeOnBackdrop = true,
}: Props) {
  const modalRef = useRef<HTMLElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const instanceIdRef = useRef<number | null>(null);
  if (instanceIdRef.current === null) instanceIdRef.current = ++modalSequence;
  const instanceId = instanceIdRef.current;
  const background = useSurfaceBackground(surface);
  const { isPhone } = useResponsiveLayout();
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [size, setSize] = useState<{ width: number; height: number } | null>(null);
  const drag = useRef<{ x: number; y: number; startX: number; startY: number } | null>(null);
  const resize = useRef<{
    edge: ResizeEdge;
    startX: number;
    startY: number;
    left: number;
    top: number;
    right: number;
    bottom: number;
    width: number;
    height: number;
    positionX: number;
    positionY: number;
  } | null>(null);

  const presentation: ModalPresentation = isPhone && responsiveMode !== "dialog"
    ? responsiveMode === "auto"
      ? (wide || resizable || hideHeader || dragFromBody ? "fullscreen" : "sheet")
      : responsiveMode
    : "dialog";
  const mobilePresentation = presentation !== "dialog";
  const showHeader = !hideHeader || mobilePresentation;

  useEffect(() => registerModal(instanceId), [instanceId]);

  useEffect(() => {
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const frame = window.requestAnimationFrame(() => {
      const modal = modalRef.current;
      if (!modal || !isTopModal(instanceId)) return;
      const requested = modal.querySelector<HTMLElement>("[autofocus], [data-modal-initial-focus]");
      (requested || closeRef.current || focusableElements(modal)[0] || modal).focus({ preventScroll: true });
    });
    return () => {
      window.cancelAnimationFrame(frame);
      if (previousFocus?.isConnected) previousFocus.focus({ preventScroll: true });
    };
  }, [instanceId]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (!isTopModal(instanceId) || event.defaultPrevented || event.isComposing) return;
      if (event.key === "Escape") {
        event.preventDefault();
        event.stopPropagation();
        onClose();
        return;
      }
      if (event.key !== "Tab") return;
      const modal = modalRef.current;
      if (!modal) return;
      const focusable = focusableElements(modal);
      if (!focusable.length) {
        event.preventDefault();
        modal.focus({ preventScroll: true });
        return;
      }
      const first = focusable[0];
      const last = focusable.at(-1)!;
      const active = document.activeElement;
      if (event.shiftKey && (active === first || !modal.contains(active))) {
        event.preventDefault();
        last.focus({ preventScroll: true });
      } else if (!event.shiftKey && (active === last || !modal.contains(active))) {
        event.preventDefault();
        first.focus({ preventScroll: true });
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [instanceId, onClose]);

  useEffect(() => {
    if (!mobilePresentation) return;
    drag.current = null;
    resize.current = null;
    setPosition({ x: 0, y: 0 });
    setSize(null);
    return lockBodyScroll();
  }, [mobilePresentation]);

  const startDrag = (event: ReactPointerEvent<HTMLElement>) => {
    if (presentation !== "dialog" || event.button !== 0) return;
    if ((event.target as HTMLElement).closest("button, a, input, select, textarea, summary, label, [contenteditable], [role='button']")) return;
    // Un pointerdown sulla barra di scorrimento non deve trascinare la finestra.
    if (event.target === event.currentTarget) {
      const host = event.currentTarget;
      if (event.nativeEvent.offsetX > host.clientWidth || event.nativeEvent.offsetY > host.clientHeight) return;
    }
    // Trascinando dal corpo si eviterebbe altrimenti di selezionare il testo per sbaglio.
    if (event.currentTarget.classList.contains("modal-body")) event.preventDefault();
    drag.current = { x: position.x, y: position.y, startX: event.clientX, startY: event.clientY };
    event.currentTarget.setPointerCapture(event.pointerId);
  };
  const moveDrag = (event: ReactPointerEvent<HTMLElement>) => {
    if (!drag.current || presentation !== "dialog") return;
    setPosition({
      x: drag.current.x + event.clientX - drag.current.startX,
      y: drag.current.y + event.clientY - drag.current.startY
    });
  };
  const stopDrag = () => { drag.current = null; };

  const startResize = (edge: ResizeEdge, event: ReactPointerEvent<HTMLElement>) => {
    if (presentation !== "dialog") return;
    const modal = modalRef.current;
    if (!modal) return;
    const rect = modal.getBoundingClientRect();
    resize.current = {
      edge,
      startX: event.clientX,
      startY: event.clientY,
      left: rect.left,
      top: rect.top,
      right: rect.right,
      bottom: rect.bottom,
      width: rect.width,
      height: rect.height,
      positionX: position.x,
      positionY: position.y,
    };
    event.preventDefault();
    event.stopPropagation();
    event.currentTarget.setPointerCapture(event.pointerId);
  };
  const moveResize = (event: ReactPointerEvent<HTMLElement>) => {
    const current = resize.current;
    if (!current || presentation !== "dialog") return;
    let width = current.width;
    let height = current.height;
    let x = current.positionX;
    let y = current.positionY;

    if (current.edge === "left") {
      const left = Math.min(current.right - MIN_MODAL_WIDTH, Math.max(0, current.left + event.clientX - current.startX));
      width = current.right - left;
      x += (left - current.left) / 2;
    } else if (current.edge === "right") {
      const right = Math.min(window.innerWidth, Math.max(current.left + MIN_MODAL_WIDTH, current.right + event.clientX - current.startX));
      width = right - current.left;
      x += (right - current.right) / 2;
    } else if (current.edge === "top") {
      const top = Math.min(current.bottom - MIN_MODAL_HEIGHT, Math.max(0, current.top + event.clientY - current.startY));
      height = current.bottom - top;
      y += (top - current.top) / 2;
    } else {
      const bottom = Math.min(window.innerHeight, Math.max(current.top + MIN_MODAL_HEIGHT, current.bottom + event.clientY - current.startY));
      height = bottom - current.top;
      y += (bottom - current.bottom) / 2;
    }

    setSize({ width, height });
    setPosition({ x, y });
  };
  const stopResize = () => { resize.current = null; };

  const dragHandlers = { onPointerDown: startDrag, onPointerMove: moveDrag, onPointerUp: stopDrag, onPointerCancel: stopDrag };
  const style = presentation === "dialog"
    ? { "--modal-background": background ? `url(${background})` : "none", transform: `translate(${position.x}px, ${position.y}px)`, width: size?.width, height: size?.height }
    : { "--modal-background": background ? `url(${background})` : "none" };
  // Il portale su body tiene la finestra sopra la barra laterale e la barra superiore,
  // che altrimenti coprirebbero il contesto di impilamento dell'area di lavoro.
  return createPortal(
    <div
      className={`modal-backdrop ${background ? "theme-reveal-surface" : ""}`}
      role="presentation"
      onMouseDown={(event) => event.target === event.currentTarget && closeOnBackdrop && isTopModal(instanceId) && onClose()}
    >
      <section
        ref={modalRef}
        className={`rd-modal ${wide ? "rd-modal-wide" : ""} ${resizable ? "rd-modal-resizable" : ""} ${hideHeader && !mobilePresentation ? "rd-modal-headless" : ""} ${background ? "rd-modal-dressed" : ""} ${className}`.trim()}
        data-component-type="modal"
        data-theme="parchment"
        data-surface={surface}
        data-modal-instance={instanceId}
        data-responsive-presentation={presentation}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
        style={style as CSSProperties}
      >
        {background && <div className="rd-modal-atmosphere" aria-hidden="true" />}
        {showHeader && <header className="modal-header" {...dragHandlers}>
          <h2>{title}</h2>
          <button ref={closeRef} className="icon-button" type="button" onClick={onClose} aria-label="Chiudi">×</button>
        </header>}
        <div className="modal-body" {...(dragFromBody ? dragHandlers : {})}>{children}</div>
        {footer && <footer className="modal-footer" {...(hideHeader && !mobilePresentation ? dragHandlers : {})}>
          {hideHeader && !mobilePresentation && <span className="modal-drag-grip" aria-hidden="true" title="Trascina per spostare la finestra">⠿</span>}
          {footer}
        </footer>}
        {resizable && presentation === "dialog" && (["top", "right", "bottom", "left"] as const).map((edge) => <span
          key={edge}
          className={`rd-modal-resize-handle ${edge}`}
          data-resize-edge={edge}
          aria-hidden="true"
          onPointerDown={(event) => startResize(edge, event)}
          onPointerMove={moveResize}
          onPointerUp={stopResize}
          onPointerCancel={stopResize}
        />)}
      </section>
    </div>,
    document.body,
  );
}
