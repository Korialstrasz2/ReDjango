import { type CSSProperties, type PointerEvent as ReactPointerEvent, type ReactNode, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { useSurfaceBackground } from "../lib/surfaces";

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
};

type ResizeEdge = "top" | "right" | "bottom" | "left";

const MIN_MODAL_WIDTH = 360;
const MIN_MODAL_HEIGHT = 240;

export function Modal({ title, children, footer, onClose, wide = false, className = "", resizable = false, hideHeader = false, dragFromBody = false, surface }: Props) {
  const modalRef = useRef<HTMLElement>(null);
  const background = useSurfaceBackground(surface);
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

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const startDrag = (event: ReactPointerEvent<HTMLElement>) => {
    if (event.button !== 0) return;
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
    if (!drag.current) return;
    setPosition({
      x: drag.current.x + event.clientX - drag.current.startX,
      y: drag.current.y + event.clientY - drag.current.startY
    });
  };
  const stopDrag = () => { drag.current = null; };

  const startResize = (edge: ResizeEdge, event: ReactPointerEvent<HTMLElement>) => {
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
    if (!current) return;
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
  // Il portale su body tiene la finestra sopra la barra laterale e la barra superiore,
  // che altrimenti coprirebbero il contesto di impilamento dell'area di lavoro.
  return createPortal(
    <div className={`modal-backdrop ${background ? "theme-reveal-surface" : ""}`} role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section
        ref={modalRef}
        className={`rd-modal ${wide ? "rd-modal-wide" : ""} ${resizable ? "rd-modal-resizable" : ""} ${hideHeader ? "rd-modal-headless" : ""} ${background ? "rd-modal-dressed" : ""} ${className}`.trim()}
        data-component-type="modal"
        data-theme="parchment"
        data-surface={surface}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        style={{ "--modal-background": background ? `url(${background})` : "none", transform: `translate(${position.x}px, ${position.y}px)`, width: size?.width, height: size?.height } as CSSProperties}
      >
        {background && <div className="rd-modal-atmosphere" aria-hidden="true" />}
        {!hideHeader && <header className="modal-header" {...dragHandlers}>
          <h2>{title}</h2>
          <button className="icon-button" type="button" onClick={onClose} aria-label="Chiudi">×</button>
        </header>}
        <div className="modal-body" {...(dragFromBody ? dragHandlers : {})}>{children}</div>
        {footer && <footer className="modal-footer" {...(hideHeader ? dragHandlers : {})}>
          {hideHeader && <span className="modal-drag-grip" aria-hidden="true" title="Trascina per spostare la finestra">⠿</span>}
          {footer}
        </footer>}
        {resizable && (["top", "right", "bottom", "left"] as const).map((edge) => <span
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
