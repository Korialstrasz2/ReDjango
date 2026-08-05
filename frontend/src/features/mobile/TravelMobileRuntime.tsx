import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";

import { useResponsiveLayout } from "../../lib/responsive";

type Point = { x: number; y: number };
type MarkerPlacement = { type: string; label: string };

type SyntheticEvent = Event & { __redjangoTravelSynthetic?: boolean };

const MARKER_SHAPES: Record<string, string> = {
  Cerchio: "circle",
  Bandiera: "flag",
  Spada: "sword",
  Casa: "house",
  Perno: "pin",
  Stella: "star",
  Scudo: "shield",
  Diamante: "diamond",
};

function distance(left: Point, right: Point): number {
  return Math.hypot(left.x - right.x, left.y - right.y);
}

function midpoint(left: Point, right: Point): Point {
  return { x: (left.x + right.x) / 2, y: (left.y + right.y) / 2 };
}

function markSynthetic(event: Event) {
  Object.defineProperty(event, "__redjangoTravelSynthetic", { value: true });
}

function dispatchMouse(canvas: HTMLCanvasElement, type: string, point: Point, buttons = 0) {
  const event = new MouseEvent(type, {
    bubbles: true,
    cancelable: true,
    clientX: point.x,
    clientY: point.y,
    button: 0,
    buttons,
  });
  markSynthetic(event);
  canvas.dispatchEvent(event);
}

function dispatchWheel(canvas: HTMLCanvasElement, deltaY: number) {
  const rect = canvas.getBoundingClientRect();
  const event = new WheelEvent("wheel", {
    bubbles: true,
    cancelable: true,
    clientX: rect.left + rect.width / 2,
    clientY: rect.top + rect.height / 2,
    deltaY,
  });
  markSynthetic(event);
  canvas.dispatchEvent(event);
}

function dispatchMarkerDrop(canvas: HTMLCanvasElement, point: Point, markerType: string) {
  let dataTransfer: DataTransfer | { getData: (format: string) => string };
  try {
    const transfer = new DataTransfer();
    transfer.setData("application/x-redjango-travel-marker", markerType);
    dataTransfer = transfer;
  } catch {
    dataTransfer = {
      getData: (format: string) => format === "application/x-redjango-travel-marker" ? markerType : "",
    };
  }

  let event: Event;
  try {
    event = new DragEvent("drop", {
      bubbles: true,
      cancelable: true,
      clientX: point.x,
      clientY: point.y,
      dataTransfer: dataTransfer instanceof DataTransfer ? dataTransfer : undefined,
    });
  } catch {
    event = new Event("drop", { bubbles: true, cancelable: true });
  }
  Object.defineProperties(event, {
    clientX: { value: point.x },
    clientY: { value: point.y },
    dataTransfer: { value: dataTransfer },
  });
  markSynthetic(event);
  canvas.dispatchEvent(event);
}

function visibleControls(): HTMLElement[] {
  return Array.from(document.querySelectorAll<HTMLElement>(
    ".travel-mobile-controls-bar button, .travel-sidebar button, .travel-sidebar input, .travel-sidebar select, .travel-sidebar summary, .travel-sidebar [tabindex]",
  )).filter((element) => !element.hasAttribute("disabled") && element.getClientRects().length > 0);
}

export function TravelMobileRuntime() {
  const location = useLocation();
  const responsive = useResponsiveLayout();
  const enabled = responsive.isPhone && location.pathname.startsWith("/travel");
  const [controlsOpen, setControlsOpen] = useState(false);
  const [markerPlacement, setMarkerPlacement] = useState<MarkerPlacement | null>(null);
  const [canvasAvailable, setCanvasAvailable] = useState(false);
  const [hasMarkers, setHasMarkers] = useState(false);
  const controlsTriggerRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (enabled) return;
    setControlsOpen(false);
    setMarkerPlacement(null);
  }, [enabled]);

  useEffect(() => {
    if (!enabled) return;
    const sync = () => {
      setCanvasAvailable(Boolean(document.querySelector(".travel-canvas")));
      setHasMarkers(Boolean(document.querySelector(".travel-active-markers > button")));
    };
    sync();
    const observer = new MutationObserver(sync);
    observer.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ["class"] });
    return () => observer.disconnect();
  }, [enabled]);

  useEffect(() => {
    if (!enabled) return;
    const root = document.documentElement;
    const page = document.querySelector<HTMLElement>(".travel-page");
    const sidebar = document.querySelector<HTMLElement>(".travel-sidebar");
    const canvasPanel = document.querySelector<HTMLElement>(".travel-canvas-panel");
    if (controlsOpen) {
      root.dataset.mobileTravelControlsOpen = "true";
      page?.setAttribute("data-mobile-controls-open", "true");
      sidebar?.setAttribute("role", "dialog");
      sidebar?.setAttribute("aria-modal", "true");
      sidebar?.setAttribute("aria-label", "Controlli viaggio");
      canvasPanel?.setAttribute("inert", "");
      const previousOverflow = document.body.style.overflow;
      document.body.style.overflow = "hidden";
      window.setTimeout(() => visibleControls()[1]?.focus(), 0);
      return () => {
        document.body.style.overflow = previousOverflow;
        delete root.dataset.mobileTravelControlsOpen;
        page?.removeAttribute("data-mobile-controls-open");
        sidebar?.removeAttribute("role");
        sidebar?.removeAttribute("aria-modal");
        sidebar?.removeAttribute("aria-label");
        canvasPanel?.removeAttribute("inert");
      };
    }
    delete root.dataset.mobileTravelControlsOpen;
    page?.removeAttribute("data-mobile-controls-open");
    return undefined;
  }, [controlsOpen, enabled]);

  useEffect(() => {
    if (!enabled) return;
    if (markerPlacement) document.documentElement.dataset.mobileTravelMarkerMode = "true";
    else delete document.documentElement.dataset.mobileTravelMarkerMode;
    return () => { delete document.documentElement.dataset.mobileTravelMarkerMode; };
  }, [enabled, markerPlacement]);

  useEffect(() => {
    if (!enabled) return;
    const onPaletteClick = (event: MouseEvent) => {
      const button = (event.target as Element | null)?.closest<HTMLButtonElement>(".travel-marker-choice > button");
      if (!button) return;
      const title = button.getAttribute("title") || "";
      const label = title.replace(/^Trascina:\s*/, "").trim();
      const shape = MARKER_SHAPES[label];
      const color = button.closest(".travel-marker-choice")?.querySelector<HTMLSelectElement>("select")?.value || "red";
      if (!shape) return;
      event.preventDefault();
      event.stopPropagation();
      setMarkerPlacement({ type: `${shape}-${color}`, label });
      setControlsOpen(false);
    };
    document.addEventListener("click", onPaletteClick, true);
    return () => document.removeEventListener("click", onPaletteClick, true);
  }, [enabled]);

  useEffect(() => {
    if (!enabled) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        if (controlsOpen) {
          event.preventDefault();
          setControlsOpen(false);
          window.setTimeout(() => controlsTriggerRef.current?.focus(), 0);
        } else if (markerPlacement) {
          event.preventDefault();
          setMarkerPlacement(null);
        }
        return;
      }
      if (!controlsOpen || event.key !== "Tab") return;
      const controls = visibleControls();
      if (!controls.length) return;
      const first = controls[0];
      const last = controls[controls.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown, true);
    return () => document.removeEventListener("keydown", onKeyDown, true);
  }, [controlsOpen, enabled, markerPlacement]);

  useEffect(() => {
    if (!enabled) return;
    let activeCanvas: HTMLCanvasElement | null = null;
    let detach = () => undefined;

    const attach = () => {
      const canvas = document.querySelector<HTMLCanvasElement>(".travel-canvas");
      if (canvas === activeCanvas) return;
      detach();
      activeCanvas = canvas;
      if (!canvas) return;

      const pointers = new Map<number, Point>();
      let dragStart: Point | null = null;
      let dragMoved = false;
      let pinchCenter: Point | null = null;
      let pinchDistance = 0;
      let lastTap: { at: number; point: Point } | null = null;
      let suppressClickUntil = 0;
      let zoomFrame = 0;

      canvas.dataset.mobileTravelTouchReady = "true";

      const reset = () => {
        pointers.clear();
        dragStart = null;
        dragMoved = false;
        pinchCenter = null;
        pinchDistance = 0;
      };

      const onPointerDown = (event: PointerEvent) => {
        if (event.pointerType === "mouse") return;
        event.preventDefault();
        const point = { x: event.clientX, y: event.clientY };
        pointers.set(event.pointerId, point);
        try { canvas.setPointerCapture(event.pointerId); } catch { /* unsupported capture */ }
        if (pointers.size === 1) {
          dragStart = point;
          dragMoved = false;
          dispatchMouse(canvas, "mousedown", point, 1);
        } else if (pointers.size === 2) {
          dispatchMouse(canvas, "mouseup", point, 0);
          const [left, right] = [...pointers.values()];
          pinchCenter = midpoint(left, right);
          pinchDistance = distance(left, right);
          canvas.dataset.mobileTravelLastGesture = "pinch";
        }
      };

      const onPointerMove = (event: PointerEvent) => {
        if (event.pointerType === "mouse" || !pointers.has(event.pointerId)) return;
        event.preventDefault();
        const point = { x: event.clientX, y: event.clientY };
        pointers.set(event.pointerId, point);
        if (pointers.size === 1) {
          if (dragStart && distance(dragStart, point) > 5) dragMoved = true;
          dispatchMouse(canvas, "mousemove", point, 1);
          if (dragMoved) canvas.dataset.mobileTravelLastGesture = "pan";
          return;
        }
        const [left, right] = [...pointers.values()];
        const nextCenter = midpoint(left, right);
        const nextDistance = distance(left, right);
        if (pinchCenter && distance(pinchCenter, nextCenter) > .5) {
          dispatchMouse(canvas, "mousedown", pinchCenter, 1);
          dispatchMouse(canvas, "mousemove", nextCenter, 1);
          dispatchMouse(canvas, "mouseup", nextCenter, 0);
        }
        if (pinchDistance > 0) {
          const ratio = nextDistance / pinchDistance;
          if (ratio > 1.035 || ratio < .965) {
            window.cancelAnimationFrame(zoomFrame);
            zoomFrame = window.requestAnimationFrame(() => dispatchWheel(canvas, ratio > 1 ? -1 : 1));
            pinchDistance = nextDistance;
          }
        }
        pinchCenter = nextCenter;
        canvas.dataset.mobileTravelLastGesture = "pinch";
      };

      const finishPointer = (event: PointerEvent, cancelled = false) => {
        if (event.pointerType === "mouse" || !pointers.has(event.pointerId)) return;
        event.preventDefault();
        const point = { x: event.clientX, y: event.clientY };
        const wasPinching = pointers.size > 1;
        pointers.delete(event.pointerId);
        dispatchMouse(canvas, "mouseup", point, 0);
        suppressClickUntil = Date.now() + 450;
        if (!cancelled && !wasPinching && !dragMoved) {
          if (markerPlacement) {
            dispatchMarkerDrop(canvas, point, markerPlacement.type);
            canvas.dataset.mobileTravelLastGesture = "marker";
            setMarkerPlacement(null);
          } else if (lastTap && Date.now() - lastTap.at < 350 && distance(lastTap.point, point) < 24) {
            dispatchMouse(canvas, "dblclick", point, 0);
            canvas.dataset.mobileTravelLastGesture = "double-tap";
            lastTap = null;
          } else {
            dispatchMouse(canvas, "click", point, 0);
            canvas.dataset.mobileTravelLastGesture = "tap";
            lastTap = { at: Date.now(), point };
          }
        }
        if (pointers.size === 1) {
          const remaining = [...pointers.values()][0];
          dragStart = remaining;
          dragMoved = false;
          pinchCenter = null;
          pinchDistance = 0;
          dispatchMouse(canvas, "mousedown", remaining, 1);
        } else if (!pointers.size) reset();
      };

      const onClickCapture = (event: MouseEvent) => {
        if (Date.now() >= suppressClickUntil || (event as SyntheticEvent).__redjangoTravelSynthetic) return;
        event.preventDefault();
        event.stopImmediatePropagation();
      };

      const onPointerUp = (event: PointerEvent) => finishPointer(event);
      const onPointerCancel = (event: PointerEvent) => finishPointer(event, true);
      canvas.addEventListener("pointerdown", onPointerDown, { passive: false });
      canvas.addEventListener("pointermove", onPointerMove, { passive: false });
      canvas.addEventListener("pointerup", onPointerUp, { passive: false });
      canvas.addEventListener("pointercancel", onPointerCancel, { passive: false });
      canvas.addEventListener("click", onClickCapture, true);

      detach = () => {
        window.cancelAnimationFrame(zoomFrame);
        canvas.removeEventListener("pointerdown", onPointerDown);
        canvas.removeEventListener("pointermove", onPointerMove);
        canvas.removeEventListener("pointerup", onPointerUp);
        canvas.removeEventListener("pointercancel", onPointerCancel);
        canvas.removeEventListener("click", onClickCapture, true);
        delete canvas.dataset.mobileTravelTouchReady;
        reset();
      };
    };

    attach();
    const observer = new MutationObserver(attach);
    observer.observe(document.body, { childList: true, subtree: true });
    return () => { observer.disconnect(); detach(); };
  }, [enabled, markerPlacement]);

  if (!enabled) return null;

  const centerMarker = () => {
    const marker = document.querySelector<HTMLButtonElement>(".travel-active-markers > button.active")
      || document.querySelector<HTMLButtonElement>(".travel-active-markers > button");
    marker?.click();
  };

  return <>
    <div className="travel-mobile-toolbar" aria-label="Controlli rapidi della mappa">
      <button type="button" disabled={!canvasAvailable} aria-label="Riduci zoom mappa" onClick={() => {
        const canvas = document.querySelector<HTMLCanvasElement>(".travel-canvas");
        if (canvas) dispatchWheel(canvas, 1);
      }}>−</button>
      <button type="button" disabled={!canvasAvailable} aria-label="Aumenta zoom mappa" onClick={() => {
        const canvas = document.querySelector<HTMLCanvasElement>(".travel-canvas");
        if (canvas) dispatchWheel(canvas, -1);
      }}>+</button>
      <button type="button" disabled={!hasMarkers} aria-label="Centra un'icona attiva" onClick={centerMarker}>⌖</button>
      <button ref={controlsTriggerRef} type="button" aria-expanded={controlsOpen} onClick={() => setControlsOpen(true)}>Controlli</button>
    </div>

    {markerPlacement && <div className="travel-mobile-placement" role="status">
      <span>Tocca un esagono per inserire: <strong>{markerPlacement.label}</strong></span>
      <button type="button" onClick={() => setMarkerPlacement(null)}>Annulla</button>
    </div>}

    {controlsOpen && <header className="travel-mobile-controls-bar">
      <button type="button" onClick={() => {
        setControlsOpen(false);
        window.setTimeout(() => controlsTriggerRef.current?.focus(), 0);
      }}>← Mappa</button>
      <strong>Controlli viaggio</strong>
      <span aria-hidden="true">⌖</span>
    </header>}
  </>;
}
