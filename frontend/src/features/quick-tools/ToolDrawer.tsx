import { type CSSProperties, type PointerEvent as ReactPointerEvent, type ReactNode, useEffect, useRef, useState } from "react";

import { useResponsiveLayout } from "../../lib/responsive";

type Props = {
  title: string;
  eyebrow: string;
  children: ReactNode;
  onClose: () => void;
  background?: string;
  wide?: boolean;
  compact?: boolean;
  draggable?: boolean;
  resizable?: boolean;
};

type ResizeEdge = "top" | "right" | "bottom" | "left";

const VIEWPORT_TOP = 35;
const MIN_DRAWER_WIDTH = 360;
const MIN_DRAWER_HEIGHT = 320;
const FOCUSABLE_SELECTOR = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled]):not([type='hidden'])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "[contenteditable='true']",
  "[tabindex]:not([tabindex='-1'])",
].join(",");
let mobileDrawerLockCount = 0;
let bodyOverflowBeforeDrawerLock = "";

function lockBodyForMobileDrawer(): () => void {
  if (mobileDrawerLockCount === 0) {
    bodyOverflowBeforeDrawerLock = document.body.style.overflow;
    document.body.style.overflow = "hidden";
  }
  mobileDrawerLockCount += 1;
  return () => {
    mobileDrawerLockCount = Math.max(0, mobileDrawerLockCount - 1);
    if (mobileDrawerLockCount === 0) document.body.style.overflow = bodyOverflowBeforeDrawerLock;
  };
}

export function ToolDrawer({ title, eyebrow, children, onClose, background = "", wide = false, compact = false, draggable = false, resizable = false }: Props) {
  const { isPhone } = useResponsiveLayout();
  const closeRef = useRef<HTMLButtonElement>(null);
  const drawerRef = useRef<HTMLElement>(null);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [size, setSize] = useState<{ width: number; height: number } | null>(null);
  const drag = useRef<{
    startX: number;
    startY: number;
    left: number;
    top: number;
    right: number;
    bottom: number;
    positionX: number;
    positionY: number;
  } | null>(null);
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
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.defaultPrevented || event.isComposing) return;
      const drawer = drawerRef.current;
      if (!drawer) return;
      if (event.key === "Escape") {
        // A nested shared/custom dialog owns Escape before the drawer.
        if (document.querySelector("[data-modal-instance][data-modal-top]")
          || drawer.querySelector("[role='dialog'][aria-modal='true']")) return;
        event.preventDefault();
        event.stopPropagation();
        onClose();
        return;
      }
      if (!isPhone || event.key !== "Tab") return;
      const focusable = Array.from(drawer.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR))
        .filter((element) => element.getClientRects().length > 0);
      if (!focusable.length) {
        event.preventDefault();
        drawer.focus({ preventScroll: true });
        return;
      }
      const first = focusable[0];
      const last = focusable.at(-1)!;
      const active = document.activeElement;
      if (event.shiftKey && (active === first || !drawer.contains(active))) {
        event.preventDefault();
        last.focus({ preventScroll: true });
      } else if (!event.shiftKey && (active === last || !drawer.contains(active))) {
        event.preventDefault();
        first.focus({ preventScroll: true });
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [isPhone, onClose]);

  useEffect(() => {
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const frame = window.requestAnimationFrame(() => closeRef.current?.focus({ preventScroll: true }));
    if (!isPhone) return () => {
      window.cancelAnimationFrame(frame);
      previousFocus?.focus({ preventScroll: true });
    };

    drag.current = null;
    resize.current = null;
    setPosition({ x: 0, y: 0 });
    setSize(null);
    const unlock = lockBodyForMobileDrawer();
    return () => {
      window.cancelAnimationFrame(frame);
      unlock();
      previousFocus?.focus({ preventScroll: true });
    };
  }, [isPhone]);

  const startDrag = (event: ReactPointerEvent<HTMLElement>) => {
    if (isPhone || !draggable || (event.target as HTMLElement).closest("button")) return;
    if (!drawerRef.current) return;
    const rect = drawerRef.current.getBoundingClientRect();
    drag.current = {
      startX: event.clientX,
      startY: event.clientY,
      left: rect.left,
      top: rect.top,
      right: rect.right,
      bottom: rect.bottom,
      positionX: position.x,
      positionY: position.y,
    };
    event.currentTarget.setPointerCapture(event.pointerId);
  };
  const moveDrag = (event: ReactPointerEvent<HTMLElement>) => {
    const current = drag.current;
    if (!current || isPhone) return;
    const deltaX = Math.min(window.innerWidth - current.right, Math.max(-current.left, event.clientX - current.startX));
    const deltaY = Math.min(window.innerHeight - current.bottom, Math.max(VIEWPORT_TOP - current.top, event.clientY - current.startY));
    setPosition({
      x: current.positionX + deltaX,
      y: current.positionY + deltaY,
    });
  };
  const stopDrag = () => { drag.current = null; };

  const startResize = (edge: ResizeEdge, event: ReactPointerEvent<HTMLElement>) => {
    if (isPhone || !drawerRef.current) return;
    const rect = drawerRef.current.getBoundingClientRect();
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
      positionY: position.y
    };
    event.preventDefault();
    event.stopPropagation();
    event.currentTarget.setPointerCapture(event.pointerId);
  };
  const moveResize = (event: ReactPointerEvent<HTMLElement>) => {
    const current = resize.current;
    if (!current || isPhone) return;
    let width = current.width;
    let height = current.height;
    let x = current.positionX;
    let y = current.positionY;

    if (current.edge === "left") {
      const left = Math.min(current.right - MIN_DRAWER_WIDTH, Math.max(0, current.left + event.clientX - current.startX));
      width = current.right - left;
      x += (left - current.left) / 2;
    } else if (current.edge === "right") {
      const right = Math.min(window.innerWidth, Math.max(current.left + MIN_DRAWER_WIDTH, current.right + event.clientX - current.startX));
      width = right - current.left;
      x += (right - current.right) / 2;
    } else if (current.edge === "top") {
      const top = Math.min(current.bottom - MIN_DRAWER_HEIGHT, Math.max(VIEWPORT_TOP, current.top + event.clientY - current.startY));
      height = current.bottom - top;
      y += (top - current.top) / 2;
    } else {
      const bottom = Math.min(window.innerHeight, Math.max(current.top + MIN_DRAWER_HEIGHT, current.bottom + event.clientY - current.startY));
      height = bottom - current.top;
      y += (bottom - current.bottom) / 2;
    }

    setSize({ width, height });
    setPosition({ x, y });
  };
  const stopResize = () => { resize.current = null; };

  const style = isPhone
    ? { "--tool-background": background ? `url(${background})` : "none" }
    : { "--tool-background": background ? `url(${background})` : "none", "--tool-x": `${position.x}px`, "--tool-y": `${position.y}px`, width: size?.width, height: size?.height };

  return <aside
    ref={drawerRef}
    className={`tool-drawer ${background ? "theme-reveal-surface" : ""} ${wide ? "tool-drawer-wide" : ""} ${compact ? "tool-drawer-compact" : ""} ${draggable && !isPhone ? "tool-drawer-draggable" : ""}`}
    role="dialog"
    aria-modal={isPhone}
    aria-label={title}
    data-component-type="modal"
    data-theme="parchment"
    data-responsive-presentation={isPhone ? "fullscreen" : "dialog"}
    style={style as CSSProperties}
    tabIndex={-1}
  >
    <div className="tool-drawer-atmosphere" aria-hidden="true" />
    <header className="tool-drawer-header" onPointerDown={startDrag} onPointerMove={moveDrag} onPointerUp={stopDrag} onPointerCancel={stopDrag}>
      <div><p className="eyebrow">{eyebrow}</p><h2>{title}</h2></div>
      <button ref={closeRef} className="icon-button" type="button" onClick={onClose} aria-label={`Chiudi ${title}`}>×</button>
    </header>
    <div className="tool-drawer-body">{children}</div>
    {resizable && !isPhone && (["top", "right", "bottom", "left"] as const).map((edge) => <span
      key={edge}
      className={`tool-drawer-resize-handle ${edge}`}
      data-resize-edge={edge}
      aria-hidden="true"
      onPointerDown={(event) => startResize(edge, event)}
      onPointerMove={moveResize}
      onPointerUp={stopResize}
      onPointerCancel={stopResize}
    />)}
  </aside>;
}
