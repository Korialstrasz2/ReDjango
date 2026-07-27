import { type CSSProperties, type PointerEvent as ReactPointerEvent, type ReactNode, useEffect, useRef, useState } from "react";

type Props = {
  title: string;
  children: ReactNode;
  footer?: ReactNode;
  onClose: () => void;
  wide?: boolean;
  className?: string;
  resizable?: boolean;
};

type ResizeEdge = "top" | "right" | "bottom" | "left";

const MIN_MODAL_WIDTH = 360;
const MIN_MODAL_HEIGHT = 240;

export function Modal({ title, children, footer, onClose, wide = false, className = "", resizable = false }: Props) {
  const modalRef = useRef<HTMLElement>(null);
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
    if ((event.target as HTMLElement).closest("button")) return;
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

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section
        ref={modalRef}
        className={`rd-modal ${wide ? "rd-modal-wide" : ""} ${resizable ? "rd-modal-resizable" : ""} ${className}`.trim()}
        data-component-type="modal"
        data-theme="parchment"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        style={{ transform: `translate(${position.x}px, ${position.y}px)`, width: size?.width, height: size?.height } as CSSProperties}
      >
        <header className="modal-header" onPointerDown={startDrag} onPointerMove={moveDrag} onPointerUp={stopDrag} onPointerCancel={stopDrag}>
          <h2>{title}</h2>
          <button className="icon-button" type="button" onClick={onClose} aria-label="Chiudi">×</button>
        </header>
        <div className="modal-body">{children}</div>
        {footer && <footer className="modal-footer">{footer}</footer>}
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
    </div>
  );
}
