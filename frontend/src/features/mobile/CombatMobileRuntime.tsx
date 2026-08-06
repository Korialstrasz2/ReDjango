import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { useResponsiveLayout } from "../../lib/responsive";
import { MobileWorkspaceBar, navigateBackOrHome } from "./MobileWorkspaceBar";

type CombatMobilePanel = "map" | "character" | "roster" | "attack";
type Point = { x: number; y: number };
type SyntheticPointerEvent = PointerEvent & { __redjangoCombatSynthetic?: boolean };

const pointDistance = (left: Point, right: Point) => Math.hypot(left.x - right.x, left.y - right.y);
const pointMidpoint = (left: Point, right: Point): Point => ({ x: (left.x + right.x) / 2, y: (left.y + right.y) / 2 });

function dispatchPointerCancel(target: SVGSVGElement, pointerId: number, point: Point) {
  const event = new PointerEvent("pointercancel", {
    bubbles: true,
    cancelable: true,
    pointerId,
    pointerType: "touch",
    clientX: point.x,
    clientY: point.y,
  }) as SyntheticPointerEvent;
  Object.defineProperty(event, "__redjangoCombatSynthetic", { value: true });
  target.dispatchEvent(event);
}

function dispatchMapWheel(target: SVGSVGElement, point: Point, deltaY: number) {
  target.dispatchEvent(new WheelEvent("wheel", {
    bubbles: true,
    cancelable: true,
    clientX: point.x,
    clientY: point.y,
    deltaY,
  }));
}

function openParticipantContext(token: Element, point: Point) {
  token.dispatchEvent(new MouseEvent("contextmenu", {
    bubbles: true,
    cancelable: true,
    clientX: point.x,
    clientY: point.y,
    button: 2,
    buttons: 0,
  }));
}

export function CombatMobileRuntime() {
  const location = useLocation();
  const navigate = useNavigate();
  const responsive = useResponsiveLayout();
  const enabled = responsive.isPhone && location.pathname.startsWith("/combat");
  const [panel, setPanel] = useState<CombatMobilePanel>("map");
  const [workspaceAvailable, setWorkspaceAvailable] = useState(false);
  const [characterAvailable, setCharacterAvailable] = useState(false);
  const [rosterAvailable, setRosterAvailable] = useState(false);
  const [attackAvailable, setAttackAvailable] = useState(false);
  const navRef = useRef<HTMLElement>(null);

  const closeCombatChild = () => {
    const hexClose = document.querySelector<HTMLButtonElement>(".combat-hex-tool-window [aria-label='Chiudi strumenti esagono']");
    if (hexClose) {
      hexClose.click();
      return true;
    }
    if (panel !== "map") {
      setPanel("map");
      window.setTimeout(() => navRef.current?.querySelector<HTMLButtonElement>("[data-combat-mobile-panel='map']")?.focus(), 0);
      return true;
    }
    const pendingAttack = document.querySelector(".combat-attack[data-combat-attack-pending='true']");
    if (pendingAttack && !window.confirm("È in corso una configurazione di attacco. Uscire e perdere le modifiche?")) return true;
    return false;
  };

  useEffect(() => {
    if (enabled) return;
    setPanel("map");
  }, [enabled]);

  useEffect(() => {
    if (!enabled) return;
    const sync = () => {
      setWorkspaceAvailable(Boolean(document.querySelector(".combat-stage-layout")));
      setCharacterAvailable(Boolean(document.querySelector(".combat-selected-character")));
      setRosterAvailable(Boolean(document.querySelector(".combat-active-strip")));
      setAttackAvailable(Boolean(document.querySelector(".combat-attack-trigger")));
    };
    sync();
    const observer = new MutationObserver(sync);
    observer.observe(document.body, { childList: true, subtree: true });
    return () => observer.disconnect();
  }, [enabled]);

  useEffect(() => {
    if (!enabled || !workspaceAvailable) {
      setPanel("map");
      return;
    }
    if ((panel === "character" && !characterAvailable)
      || (panel === "roster" && !rosterAvailable)
      || (panel === "attack" && !attackAvailable)) setPanel("map");
  }, [attackAvailable, characterAvailable, enabled, panel, rosterAvailable, workspaceAvailable]);

  useEffect(() => {
    if (!enabled || !workspaceAvailable) {
      delete document.documentElement.dataset.mobileCombatPanel;
      return;
    }
    document.documentElement.dataset.mobileCombatPanel = panel;
    document.querySelector<HTMLElement>(".combat-page")?.setAttribute("data-mobile-panel", panel);
    return () => {
      delete document.documentElement.dataset.mobileCombatPanel;
      document.querySelector<HTMLElement>(".combat-page")?.removeAttribute("data-mobile-panel");
    };
  }, [enabled, panel, workspaceAvailable]);

  useEffect(() => {
    if (!enabled) return;
    const onClick = (event: MouseEvent) => {
      const target = event.target as Element | null;
      if (target?.closest(".combat-attack-trigger")) {
        setPanel("attack");
        return;
      }
      if (target?.closest(".combat-attack-drawer-toggle")) {
        window.setTimeout(() => {
          if (!document.querySelector(".combat-attack-drawer.open")) setPanel("map");
        }, 0);
      }
    };
    document.addEventListener("click", onClick, true);
    return () => document.removeEventListener("click", onClick, true);
  }, [enabled]);

  useEffect(() => {
  if (!enabled) return;
  const onKeyDown = (event: KeyboardEvent) => {
    if (event.key !== "Escape" || event.defaultPrevented) return;
    // Modal owns Escape while present. The workspace Back contract handles
    // the non-modal inspector, active panel, and finally route history.
    if (document.querySelector(".modal-backdrop")) return;
    event.preventDefault();
    if (closeCombatChild()) return;
    navigateBackOrHome(navigate);
  };
  document.addEventListener("keydown", onKeyDown, true);
  return () => document.removeEventListener("keydown", onKeyDown, true);
}, [enabled, navigate, panel]);

  useEffect(() => {
    if (!enabled) return;
    let activeStage: HTMLElement | null = null;
    let activeMap: SVGSVGElement | null = null;
    let detach = () => undefined;

    const attach = () => {
      const stage = document.querySelector<HTMLElement>(".combat-map-stage");
      const map = stage?.querySelector<SVGSVGElement>("svg") || null;
      if (stage === activeStage && map === activeMap) return;
      detach();
      activeStage = stage;
      activeMap = map;
      if (!stage || !map) return;

      const pointers = new Map<number, Point>();
      let pinching = false;
      let pinchDistance = 0;
      let longPressTimer = 0;
      let longPressPointer = -1;
      let longPressStart: Point | null = null;
      let longPressToken: Element | null = null;
      let longPressFired = false;
      let suppressUntilReleased = false;

      map.dataset.mobileCombatTouchReady = "true";

      const clearLongPress = () => {
        window.clearTimeout(longPressTimer);
        longPressTimer = 0;
        longPressPointer = -1;
        longPressStart = null;
        longPressToken = null;
      };

      const reset = () => {
        pointers.clear();
        pinching = false;
        pinchDistance = 0;
        longPressFired = false;
        suppressUntilReleased = false;
        clearLongPress();
      };

      const onPointerDown = (event: PointerEvent) => {
        if ((event as SyntheticPointerEvent).__redjangoCombatSynthetic || event.pointerType === "mouse") return;
        const point = { x: event.clientX, y: event.clientY };
        pointers.set(event.pointerId, point);

        if (pointers.size === 1) {
          longPressFired = false;
          const token = (event.target as Element | null)?.closest(".combat-token");
          if (token) {
            longPressPointer = event.pointerId;
            longPressStart = point;
            longPressToken = token;
            longPressTimer = window.setTimeout(() => {
              const current = pointers.get(longPressPointer);
              if (!current || !longPressToken || !longPressStart || pointDistance(current, longPressStart) > 8) return;
              longPressFired = true;
              suppressUntilReleased = true;
              dispatchPointerCancel(map, longPressPointer, current);
              openParticipantContext(longPressToken, current);
              map.dataset.mobileCombatLastGesture = "token-context";
            }, 560);
          }
          return;
        }

        clearLongPress();
        if (pointers.size === 2) {
          const entries = [...pointers.entries()];
          pinching = true;
          suppressUntilReleased = true;
          pinchDistance = pointDistance(entries[0][1], entries[1][1]);
          dispatchPointerCancel(map, entries[0][0], entries[0][1]);
          event.preventDefault();
          event.stopImmediatePropagation();
          map.dataset.mobileCombatLastGesture = "pinch";
        } else if (pinching) {
          event.preventDefault();
          event.stopImmediatePropagation();
        }
      };

      const onPointerMove = (event: PointerEvent) => {
        if ((event as SyntheticPointerEvent).__redjangoCombatSynthetic || event.pointerType === "mouse" || !pointers.has(event.pointerId)) return;
        const point = { x: event.clientX, y: event.clientY };
        pointers.set(event.pointerId, point);

        if (longPressStart && event.pointerId === longPressPointer && pointDistance(longPressStart, point) > 8) clearLongPress();
        if (!pinching) return;

        event.preventDefault();
        event.stopImmediatePropagation();
        const values = [...pointers.values()];
        if (values.length < 2) return;
        const nextDistance = pointDistance(values[0], values[1]);
        if (pinchDistance > 0) {
          const ratio = nextDistance / pinchDistance;
          if (ratio > 1.025 || ratio < .975) {
            const deltaY = Math.max(-260, Math.min(260, -Math.log(ratio) / .0014));
            dispatchMapWheel(map, pointMidpoint(values[0], values[1]), deltaY);
            pinchDistance = nextDistance;
          }
        }
        map.dataset.mobileCombatLastGesture = "pinch";
      };

      const finishPointer = (event: PointerEvent) => {
        if ((event as SyntheticPointerEvent).__redjangoCombatSynthetic || event.pointerType === "mouse" || !pointers.has(event.pointerId)) return;
        const wasManaged = pinching || suppressUntilReleased || longPressFired;
        pointers.delete(event.pointerId);
        if (event.pointerId === longPressPointer) clearLongPress();
        if (wasManaged) {
          event.preventDefault();
          event.stopImmediatePropagation();
        }
        if (pointers.size < 2) {
          pinching = false;
          pinchDistance = 0;
        }
        if (!pointers.size) {
          suppressUntilReleased = false;
          longPressFired = false;
        }
      };

      const onContextMenu = (event: Event) => {
        if ((event.target as Element | null)?.closest(".combat-token")) event.preventDefault();
      };

      stage.addEventListener("pointerdown", onPointerDown, true);
      stage.addEventListener("pointermove", onPointerMove, true);
      stage.addEventListener("pointerup", finishPointer, true);
      stage.addEventListener("pointercancel", finishPointer, true);
      stage.addEventListener("contextmenu", onContextMenu);

      detach = () => {
        stage.removeEventListener("pointerdown", onPointerDown, true);
        stage.removeEventListener("pointermove", onPointerMove, true);
        stage.removeEventListener("pointerup", finishPointer, true);
        stage.removeEventListener("pointercancel", finishPointer, true);
        stage.removeEventListener("contextmenu", onContextMenu);
        delete map.dataset.mobileCombatTouchReady;
        reset();
      };
    };

    attach();
    const observer = new MutationObserver(attach);
    observer.observe(document.body, { childList: true, subtree: true });
    return () => { observer.disconnect(); detach(); };
  }, [enabled]);

  if (!enabled || !workspaceAvailable) return null;

  const choosePanel = (next: CombatMobilePanel) => {
    if (next === "attack") {
      const drawer = document.querySelector(".combat-attack-drawer");
      if (drawer && !drawer.classList.contains("open")) document.querySelector<HTMLButtonElement>(".combat-attack-trigger")?.click();
    }
    setPanel(next);
  };

  const tabs: Array<{ id: CombatMobilePanel; label: string; icon: string; disabled: boolean }> = [
    { id: "map", label: "Mappa", icon: "⬡", disabled: false },
    { id: "character", label: "Scheda", icon: "♙", disabled: !characterAvailable },
    { id: "roster", label: "Attivi", icon: "☷", disabled: !rosterAvailable },
    { id: "attack", label: "Attacco", icon: "⚔", disabled: !attackAvailable },
  ];

  return <>
  <MobileWorkspaceBar
    workspace="combat"
    title="Combattimento"
    navigate={navigate}
    onBeforeNavigate={closeCombatChild}
  />
  <nav ref={navRef} className="combat-mobile-navigation" role="tablist" aria-label="Pannelli del combattimento">
    {tabs.map((tab) => <button
      key={tab.id}
      type="button"
      role="tab"
      data-combat-mobile-panel={tab.id}
      aria-selected={panel === tab.id}
      disabled={tab.disabled}
      className={panel === tab.id ? "active" : ""}
      onClick={() => choosePanel(tab.id)}
    ><span aria-hidden="true">{tab.icon}</span><strong>{tab.label}</strong></button>)}
  </nav>
</>;
}
