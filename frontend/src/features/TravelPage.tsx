import { type CSSProperties, type DragEvent, type FormEvent, type MouseEvent as ReactMouseEvent, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Modal } from "../components/Modal";
import { getData, updateTravelMap, uploadTravelMap } from "../lib/api";
import type { ImageCategory, TravelGrid, TravelHexEffect, TravelMap, TravelMapsData, TravelMarker } from "../lib/types";

type Hex = { col: number; row: number };
type Point = { x: number; y: number };
type MarkerDraft = { markerType: string; hex: string; marker?: TravelMarker };
type Quality = "high" | "balanced" | "light" | "verylow";

const SHAPES = [
  ["circle", "●", "Cerchio"], ["flag", "⚑", "Bandiera"], ["sword", "⚔", "Spada"], ["house", "⌂", "Casa"],
  ["pin", "⌖", "Perno"], ["star", "★", "Stella"], ["shield", "⛨", "Scudo"], ["diamond", "◆", "Diamante"],
] as const;
const COLORS: Record<string, { fill: string; text: string; edge: string }> = {
  red: { fill: "#8d3434", text: "#f6d9d9", edge: "#4d1b1b" },
  blue: { fill: "#284f8f", text: "#dbe8ff", edge: "#122a57" },
  green: { fill: "#2d6f52", text: "#cdeedf", edge: "#154332" },
  purple: { fill: "#5f3e87", text: "#ebdefd", edge: "#392058" },
};
const QUALITY: Record<Quality, { pixelRatio: number; maxTextureSize: number; grid: boolean; blur: boolean; hover: boolean; markerGradient: boolean; gridAlpha: number; gridPadding: number }> = {
  high: { pixelRatio: 1, maxTextureSize: 8192, grid: true, blur: true, hover: true, markerGradient: true, gridAlpha: .58, gridPadding: 2.4 },
  balanced: { pixelRatio: .9, maxTextureSize: 2300, grid: true, blur: true, hover: true, markerGradient: true, gridAlpha: .45, gridPadding: 1.8 },
  light: { pixelRatio: .72, maxTextureSize: 1450, grid: true, blur: false, hover: false, markerGradient: false, gridAlpha: .32, gridPadding: 1.2 },
  verylow: { pixelRatio: .58, maxTextureSize: 1100, grid: false, blur: false, hover: false, markerGradient: false, gridAlpha: 0, gridPadding: 1.1 },
};
const QUALITY_DESCRIPTION: Record<Quality, string> = {
  high: "Texture fino a 8192px, griglia ed effetti completi.",
  balanced: "Texture fino a 2300px con effetti completi.",
  light: "Texture fino a 1450px, senza blur, gradienti o tooltip.",
  verylow: "Texture fino a 1100px, senza griglia, blur, gradienti o tooltip.",
};
const hexKey = (hex: Hex) => `${hex.col}-${hex.row}`;
const parseHex = (value: string): Hex | null => {
  const match = /^(\d+)-(\d+)$/.exec(value);
  return match ? { col: Number(match[1]), row: Number(match[2]) } : null;
};
const clamp = (value: number, min: number, max: number) => Math.max(min, Math.min(value, max));

function hexBaseCenter(hex: Hex, grid: TravelGrid): Point {
  const size = grid.hexSize;
  return grid.orientation === "flat"
    ? { x: size * 1.5 * hex.col, y: Math.sqrt(3) * size * (hex.row + (hex.col % 2) / 2) }
    : { x: Math.sqrt(3) * size * (hex.col + (hex.row % 2) / 2), y: size * 1.5 * hex.row };
}
function hexCenter(hex: Hex, grid: TravelGrid): Point {
  const base = hexBaseCenter(hex, grid);
  return { x: grid.offsetX + grid.scale * (grid.gridOffsetX + base.x), y: grid.offsetY + grid.scale * (grid.gridOffsetY + base.y) };
}
function hexCorners(center: Point, grid: TravelGrid): Point[] {
  const start = grid.orientation === "pointy" ? -30 : 0;
  return Array.from({ length: 6 }, (_, index) => {
    const angle = (Math.PI / 180) * (start + index * 60);
    return { x: center.x + Math.cos(angle) * grid.hexSize * grid.scale, y: center.y + Math.sin(angle) * grid.hexSize * grid.scale };
  });
}
function canvasPoint(canvas: HTMLCanvasElement, clientX: number, clientY: number): Point {
  const rect = canvas.getBoundingClientRect();
  return { x: clientX - rect.left, y: clientY - rect.top };
}
function nearestHex(point: Point, grid: TravelGrid): Hex | null {
  let nearest: Hex | null = null;
  let distance = Number.POSITIVE_INFINITY;
  for (let row = 0; row < grid.rows; row += 1) for (let col = 0; col < grid.cols; col += 1) {
    const center = hexCenter({ col, row }, grid);
    const candidate = (center.x - point.x) ** 2 + (center.y - point.y) ** 2;
    if (candidate < distance) { distance = candidate; nearest = { col, row }; }
  }
  return distance <= (grid.hexSize * grid.scale * 1.15) ** 2 ? nearest : null;
}
function axial(hex: Hex, orientation: TravelGrid["orientation"]) {
  return orientation === "flat" ? { q: hex.col, r: hex.row - (hex.col - (hex.col & 1)) / 2 } : { q: hex.col - (hex.row - (hex.row & 1)) / 2, r: hex.row };
}
function hexDistance(left: Hex, right: Hex, orientation: TravelGrid["orientation"]) {
  const a = axial(left, orientation); const b = axial(right, orientation);
  return (Math.abs(a.q - b.q) + Math.abs(a.r - b.r) + Math.abs((a.q + a.r) - (b.q + b.r))) / 2;
}
function markerTemplate(markerType: string) {
  const [shapeId, colorId] = markerType.split("-");
  const shape = SHAPES.find(([id]) => id === shapeId) || SHAPES[0];
  return { glyph: shape[1], label: shape[2], colors: COLORS[colorId] || COLORS.green };
}
function drawPath(context: CanvasRenderingContext2D, corners: Point[]) {
  context.beginPath();
  corners.forEach((point, index) => index ? context.lineTo(point.x, point.y) : context.moveTo(point.x, point.y));
  context.closePath();
}
function visibleHexBounds(grid: TravelGrid, width: number, height: number, padding: number) {
  const size = Math.max(1, grid.hexSize); const scale = Math.max(.01, grid.scale);
  const minX = (0 - grid.offsetX) / scale - grid.gridOffsetX; const maxX = (width - grid.offsetX) / scale - grid.gridOffsetX;
  const minY = (0 - grid.offsetY) / scale - grid.gridOffsetY; const maxY = (height - grid.offsetY) / scale - grid.gridOffsetY;
  const stepX = grid.orientation === "flat" ? size * 1.5 : size * Math.sqrt(3);
  const stepY = grid.orientation === "flat" ? size * Math.sqrt(3) : size * 1.5;
  return {
    minCol: clamp(Math.floor(Math.min(minX, maxX) / stepX - padding - 1), 0, grid.cols - 1),
    maxCol: clamp(Math.ceil(Math.max(minX, maxX) / stepX + padding + 1), 0, grid.cols - 1),
    minRow: clamp(Math.floor(Math.min(minY, maxY) / stepY - padding - 1), 0, grid.rows - 1),
    maxRow: clamp(Math.ceil(Math.max(minY, maxY) / stepY + padding + 1), 0, grid.rows - 1),
  };
}

function TravelCanvas({ travelMap, grid, effects, markers, selected, quality, focusedMarkerId, onGridChange, onSelect, onMarkerDrop, onMarkerEdit }: {
  travelMap: TravelMap; grid: TravelGrid; effects: Record<string, TravelHexEffect>; markers: TravelMarker[]; selected: Set<string>; quality: Quality;
  focusedMarkerId?: string | null;
  onGridChange: (grid: TravelGrid) => void; onSelect: (hex: Hex, event: ReactMouseEvent<HTMLCanvasElement>) => void;
  onMarkerDrop: (markerType: string, hex: Hex) => void; onMarkerEdit: (marker: TravelMarker) => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const imageRef = useRef<HTMLImageElement | null>(null);
  const qualityImageRef = useRef<{ key: string; source: CanvasImageSource } | null>(null);
  const dragRef = useRef<{ start: Point; grid: TravelGrid; gridOnly: boolean; moved: boolean } | null>(null);
  const [hover, setHover] = useState<{ marker: TravelMarker; point: Point } | null>(null);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const image = new Image();
    image.onload = () => { imageRef.current = image; qualityImageRef.current = null; setRevision((value) => value + 1); };
    image.src = travelMap.imageUrl;
    return () => { imageRef.current = null; qualityImageRef.current = null; };
  }, [travelMap.imageUrl]);
  useEffect(() => {
    const canvas = canvasRef.current; const container = canvas?.parentElement;
    if (!canvas || !container) return;
    const resize = () => {
      const ratio = Math.max(.5, window.devicePixelRatio * QUALITY[quality].pixelRatio);
      const width = Math.max(1, container.clientWidth); const height = Math.max(1, container.clientHeight);
      canvas.width = Math.round(width * ratio); canvas.height = Math.round(height * ratio);
      canvas.style.width = `${width}px`; canvas.style.height = `${height}px`;
      canvas.getContext("2d")?.setTransform(ratio, 0, 0, ratio, 0, 0);
      setRevision((value) => value + 1);
    };
    const observer = new ResizeObserver(resize); observer.observe(container); resize();
    return () => observer.disconnect();
  }, [quality]);
  useEffect(() => {
    const canvas = canvasRef.current; const context = canvas?.getContext("2d"); const image = imageRef.current;
    if (!canvas || !context) return;
    const profile = QUALITY[quality];
    const ratio = canvas.width / Math.max(1, canvas.clientWidth);
    context.setTransform(ratio, 0, 0, ratio, 0, 0); context.clearRect(0, 0, canvas.clientWidth, canvas.clientHeight);
    context.fillStyle = "rgba(8, 12, 16, .88)"; context.fillRect(0, 0, canvas.clientWidth, canvas.clientHeight);
    let source: CanvasImageSource | null = image;
    if (image && Math.max(image.width, image.height) > profile.maxTextureSize) {
      const key = `${travelMap.imageUrl}:${profile.maxTextureSize}:${image.width}x${image.height}`;
      if (qualityImageRef.current?.key !== key) {
        const textureRatio = profile.maxTextureSize / Math.max(image.width, image.height);
        const texture = document.createElement("canvas");
        texture.width = Math.max(1, Math.floor(image.width * textureRatio)); texture.height = Math.max(1, Math.floor(image.height * textureRatio));
        const textureContext = texture.getContext("2d");
        textureContext?.drawImage(image, 0, 0, texture.width, texture.height);
        qualityImageRef.current = { key, source: texture };
      }
      source = qualityImageRef.current?.source || image;
    }
    if (source && image) context.drawImage(source, grid.offsetX, grid.offsetY, image.width * grid.scale, image.height * grid.scale);
    const bounds = visibleHexBounds(grid, canvas.clientWidth, canvas.clientHeight, profile.gridPadding);
    for (let row = bounds.minRow; row <= bounds.maxRow; row += 1) for (let col = bounds.minCol; col <= bounds.maxCol; col += 1) {
      const key = `${col}-${row}`; const center = hexCenter({ col, row }, grid);
      const effect = effects[key];
      if (effect && (effect.black || effect.bw || effect.blur > 0)) {
        context.save(); drawPath(context, hexCorners(center, grid)); context.clip();
        if (source && image && (effect.bw || (effect.blur > 0 && profile.blur))) {
          context.filter = `${effect.bw ? "grayscale(1)" : ""} ${effect.blur > 0 && profile.blur ? `blur(${effect.blur}px)` : ""}`.trim();
          context.drawImage(source, grid.offsetX, grid.offsetY, image.width * grid.scale, image.height * grid.scale); context.filter = "none";
        }
        if (effect.black || (!profile.blur && effect.blur > 0)) { context.fillStyle = "rgba(0, 0, 0, .92)"; context.fillRect(0, 0, canvas.clientWidth, canvas.clientHeight); }
        context.restore();
      }
      if (profile.grid) {
        drawPath(context, hexCorners(center, grid)); context.fillStyle = selected.has(key) ? "rgba(206, 169, 83, .25)" : "transparent"; context.fill();
        context.strokeStyle = selected.has(key) ? "rgba(255, 221, 132, .95)" : `rgba(231, 221, 193, ${profile.gridAlpha})`;
        context.lineWidth = selected.has(key) ? 2 : 1; context.stroke();
      }
    }
    markers.forEach((marker) => {
      const hex = parseHex(marker.hex); if (!hex) return;
      const center = hexCenter(hex, grid); const template = markerTemplate(marker.markerType);
      const radius = clamp(grid.hexSize * .28 * grid.scale, 9, 26);
      if (center.x < -radius || center.y < -radius || center.x > canvas.clientWidth + radius || center.y > canvas.clientHeight + radius) return;
      context.save(); context.beginPath(); context.arc(center.x, center.y, radius, 0, Math.PI * 2);
      if (profile.markerGradient) {
        const gradient = context.createLinearGradient(center.x - radius, center.y - radius, center.x + radius, center.y + radius);
        gradient.addColorStop(0, template.colors.fill); gradient.addColorStop(.5, template.colors.text); gradient.addColorStop(1, template.colors.edge);
        context.fillStyle = gradient;
      } else context.fillStyle = template.colors.fill;
      context.fill(); context.strokeStyle = template.colors.edge; context.lineWidth = 2; context.stroke();
      context.fillStyle = template.colors.text; context.font = "bold 17px serif"; context.textAlign = "center"; context.textBaseline = "middle";
      context.fillText(template.glyph, center.x, center.y); context.restore();
      if (marker.id === focusedMarkerId) {
        context.save(); context.beginPath(); context.arc(center.x, center.y, radius + 7, 0, Math.PI * 2);
        context.strokeStyle = "rgba(255, 221, 132, .98)"; context.lineWidth = 3; context.setLineDash([5, 4]); context.stroke(); context.restore();
      }
    });
    if (hover && profile.hover) {
      const text = `${hover.marker.tag || markerTemplate(hover.marker.markerType).label} · ${hover.marker.author}`;
      context.font = "12px sans-serif"; const width = context.measureText(text).width + 18;
      context.fillStyle = "rgba(10, 14, 18, .94)"; context.fillRect(hover.point.x + 12, hover.point.y + 12, width, 30);
      context.strokeStyle = "rgba(206, 169, 83, .75)"; context.strokeRect(hover.point.x + 12, hover.point.y + 12, width, 30);
      context.fillStyle = "#f5eedc"; context.textAlign = "left"; context.textBaseline = "middle"; context.fillText(text, hover.point.x + 21, hover.point.y + 27);
    }
  }, [effects, focusedMarkerId, grid, hover, markers, quality, revision, selected, travelMap.imageUrl]);
  const markerAt = (point: Point) => markers.find((marker) => {
    const hex = parseHex(marker.hex); if (!hex) return false; const center = hexCenter(hex, grid);
    return (center.x - point.x) ** 2 + (center.y - point.y) ** 2 < 20 ** 2;
  });
  const onMouseDown = (event: ReactMouseEvent<HTMLCanvasElement>) => {
    if (event.button !== 0 && event.button !== 2) return;
    dragRef.current = { start: canvasPoint(event.currentTarget, event.clientX, event.clientY), grid: { ...grid }, gridOnly: event.shiftKey || event.button === 2, moved: false };
  };
  const onMouseMove = (event: ReactMouseEvent<HTMLCanvasElement>) => {
    const point = canvasPoint(event.currentTarget, event.clientX, event.clientY); const drag = dragRef.current;
    if (drag) {
      const dx = point.x - drag.start.x; const dy = point.y - drag.start.y;
      if (Math.abs(dx) + Math.abs(dy) > 4) drag.moved = true;
      onGridChange(drag.gridOnly ? { ...drag.grid, gridOffsetX: drag.grid.gridOffsetX + dx / drag.grid.scale, gridOffsetY: drag.grid.gridOffsetY + dy / drag.grid.scale } : { ...drag.grid, offsetX: drag.grid.offsetX + dx, offsetY: drag.grid.offsetY + dy });
      return;
    }
    const marker = QUALITY[quality].hover ? markerAt(point) : undefined; setHover(marker ? { marker, point } : null);
  };
  const finishDrag = () => window.setTimeout(() => { dragRef.current = null; }, 0);
  const onClick = (event: ReactMouseEvent<HTMLCanvasElement>) => {
    if (dragRef.current?.moved) return;
    const hex = nearestHex(canvasPoint(event.currentTarget, event.clientX, event.clientY), grid); if (hex) onSelect(hex, event);
  };
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const onWheel = (event: globalThis.WheelEvent) => {
      if (event.ctrlKey || event.metaKey) return;
      event.preventDefault();
      const point = canvasPoint(canvas, event.clientX, event.clientY);
      const nextScale = clamp(grid.scale * (event.deltaY < 0 ? 1.1 : .9), .1, 12); const factor = nextScale / grid.scale;
      onGridChange({ ...grid, scale: nextScale, offsetX: point.x - (point.x - grid.offsetX) * factor, offsetY: point.y - (point.y - grid.offsetY) * factor });
    };
    canvas.addEventListener("wheel", onWheel, { passive: false });
    return () => canvas.removeEventListener("wheel", onWheel);
  }, [grid, onGridChange]);
  return <canvas ref={canvasRef} className="travel-canvas" aria-label={`Mappa globale ${travelMap.name}`} onMouseDown={onMouseDown} onMouseMove={onMouseMove} onMouseUp={finishDrag} onMouseLeave={() => { finishDrag(); setHover(null); }} onClick={onClick} onDoubleClick={(event) => { const marker = markerAt(canvasPoint(event.currentTarget, event.clientX, event.clientY)); if (marker) onMarkerEdit(marker); }} onDragOver={(event) => event.preventDefault()} onDrop={(event: DragEvent<HTMLCanvasElement>) => { event.preventDefault(); const markerType = event.dataTransfer.getData("application/x-redjango-travel-marker"); const hex = nearestHex(canvasPoint(event.currentTarget, event.clientX, event.clientY), grid); if (markerType && hex) onMarkerDrop(markerType, hex); }} onContextMenu={(event) => event.preventDefault()} />;
}

function MarkerPalette() {
  const [colors, setColors] = useState<Record<string, string>>(() => Object.fromEntries(SHAPES.map(([id]) => [id, "red"])));
  return <div className="travel-marker-palette">{SHAPES.map(([shape, glyph, label]) => {
    const color = colors[shape]; const type = `${shape}-${color}`;
    return <div className="travel-marker-choice" key={shape}><button draggable type="button" title={`Trascina: ${label}`} style={{ "--marker-color": COLORS[color].fill } as CSSProperties} onDragStart={(event) => event.dataTransfer.setData("application/x-redjango-travel-marker", type)}>{glyph}</button><select aria-label={`Colore ${label}`} value={color} onChange={(event) => setColors((current) => ({ ...current, [shape]: event.target.value }))}>{Object.keys(COLORS).map((entry) => <option key={entry} value={entry}>{entry === "red" ? "Rosso" : entry === "blue" ? "Blu" : entry === "green" ? "Verde" : "Viola"}</option>)}</select></div>;
  })}</div>;
}

export function TravelPage({ categories, notify }: { categories: ImageCategory[]; notify: (message: string, kind?: "success" | "error" | "info") => void }) {
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["travel-maps"], queryFn: () => getData<TravelMapsData>("/api/travel/maps/") });
  const [selectedMapId, setSelectedMapId] = useState<number | null>(null);
  const [grid, setGrid] = useState<TravelGrid | null>(null);
  const [effects, setEffects] = useState<Record<string, TravelHexEffect>>({});
  const [markers, setMarkers] = useState<TravelMarker[]>([]);
  const [selection, setSelection] = useState<Set<string>>(new Set());
  const [anchor, setAnchor] = useState<Hex | null>(null);
  const [areaRadius, setAreaRadius] = useState(0);
  const [quality, setQuality] = useState<Quality>(() => (localStorage.getItem("redjango.travel.quality") as Quality) || "high");
  const [effectBlack, setEffectBlack] = useState(false); const [effectBw, setEffectBw] = useState(false); const [effectBlur, setEffectBlur] = useState(0);
  const [markerDraft, setMarkerDraft] = useState<MarkerDraft | null>(null); const [markerTag, setMarkerTag] = useState(""); const [guideOpen, setGuideOpen] = useState(true);
  const [focusedMarkerId, setFocusedMarkerId] = useState<string | null>(null);
  const canvasPanelRef = useRef<HTMLElement>(null);
  const maps = query.data?.maps || [];
  const selectedMap = maps.find((entry) => entry.id === selectedMapId) || maps.find((entry) => entry.isDefault) || maps[0] || null;
  useEffect(() => {
    if (!selectedMap) return;
    if (selectedMapId !== selectedMap.id) setSelectedMapId(selectedMap.id);
    setGrid({ ...selectedMap.grid }); setEffects({ ...selectedMap.hexEffects }); setMarkers([...selectedMap.markers]); setSelection(new Set()); setAnchor(null); setFocusedMarkerId(null);
  }, [selectedMap?.id]);
  const mapCategory = useMemo(() => categories.find((category) => category.usageTypes.includes("travel_map")) || categories.find((category) => category.usageTypes.includes("generic")) || categories[0], [categories]);
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["travel-maps"] });
  const updateMutation = useMutation({
    mutationFn: ({ operation, payload }: { operation: "saveGrid" | "saveEffects" | "saveMarkers" | "saveAll" | "setDefault"; payload: Record<string, unknown> }) => {
      if (!selectedMap) throw new Error("Seleziona una mappa."); return updateTravelMap(selectedMap.id, operation, payload);
    },
    onSuccess: (result) => { queryClient.setQueryData<TravelMapsData>(["travel-maps"], (current) => current ? { ...current, maps: current.maps.map((entry) => entry.id === result.data.map.id ? result.data.map : entry) } : current); notify(result.events[0]?.message || "Mappa aggiornata."); },
    onError: (error: Error) => notify(error.message, "error"),
  });
  const uploadMutation = useMutation({
    mutationFn: ({ file, name }: { file: File; name: string }) => uploadTravelMap(file, name, mapCategory?.id || null),
    onSuccess: async (result) => { await refresh(); setSelectedMapId(result.data.map.id); notify("Mappa globale caricata."); },
    onError: (error: Error) => notify(error.message, "error"),
  });
  const chooseMap = (mapId: number) => {
    const travelMap = maps.find((entry) => entry.id === mapId); if (!travelMap) return;
    setSelectedMapId(mapId); setGrid({ ...travelMap.grid }); setEffects({ ...travelMap.hexEffects }); setMarkers([...travelMap.markers]); setSelection(new Set()); setFocusedMarkerId(null);
  };
  const focusMarker = (marker: TravelMarker) => {
    const hex = parseHex(marker.hex); const panel = canvasPanelRef.current;
    if (!grid || !hex || !panel) return;
    const base = hexBaseCenter(hex, grid);
    setGrid({
      ...grid,
      offsetX: panel.clientWidth / 2 - grid.scale * (grid.gridOffsetX + base.x),
      offsetY: panel.clientHeight / 2 - grid.scale * (grid.gridOffsetY + base.y),
    });
    setFocusedMarkerId(marker.id);
  };
  const saveAll = () => {
    if (!grid) return;
    updateMutation.mutate({ operation: "saveAll", payload: { grid, hexEffects: effects, markers } });
  };
  const selectHex = (hex: Hex, event: ReactMouseEvent<HTMLCanvasElement>) => {
    if (!grid) return; const targets: Hex[] = [];
    if (event.ctrlKey || event.metaKey) {
      const start = anchor || hex;
      for (let row = Math.min(start.row, hex.row); row <= Math.max(start.row, hex.row); row += 1) for (let col = Math.min(start.col, hex.col); col <= Math.max(start.col, hex.col); col += 1) targets.push({ col, row });
    } else {
      const center = event.shiftKey && anchor ? anchor : hex; const radius = event.shiftKey && anchor ? hexDistance(anchor, hex, grid.orientation) : areaRadius;
      for (let row = 0; row < grid.rows; row += 1) for (let col = 0; col < grid.cols; col += 1) { const candidate = { col, row }; if (hexDistance(center, candidate, grid.orientation) <= radius) targets.push(candidate); }
    }
    setSelection((current) => { const next = new Set(event.altKey ? current : []); targets.forEach((target) => { const key = hexKey(target); if (event.altKey && next.has(key)) next.delete(key); else next.add(key); }); return next; });
    setAnchor(hex);
  };
  const saveMarkers = (next: TravelMarker[]) => { setMarkers(next); updateMutation.mutate({ operation: "saveMarkers", payload: { markers: next } }); };
  const openMarker = (draft: MarkerDraft) => { setMarkerDraft(draft); setMarkerTag(draft.marker?.tag || ""); };
  const confirmMarker = () => {
    if (!markerDraft) return;
    const nextMarker: TravelMarker = markerDraft.marker ? { ...markerDraft.marker, tag: markerTag.trim() } : { id: crypto.randomUUID(), hex: markerDraft.hex, markerType: markerDraft.markerType, tag: markerTag.trim(), author: query.data?.playerName || "Sconosciuto", createdAt: new Date().toISOString() };
    saveMarkers(markerDraft.marker ? markers.map((entry) => entry.id === nextMarker.id ? nextMarker : entry) : [...markers, nextMarker]); setMarkerDraft(null);
  };
  const applyEffects = (clear = false) => {
    const next = { ...effects }; selection.forEach((key) => { if (clear) delete next[key]; else next[key] = { black: effectBlack, bw: effectBw, blur: effectBlur }; });
    setEffects(next); updateMutation.mutate({ operation: "saveEffects", payload: { hexEffects: next } });
  };
  const submitUpload = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); const data = new FormData(event.currentTarget); const file = data.get("file"); const name = String(data.get("name") || "").trim();
    if (file instanceof File && file.size && name) uploadMutation.mutate({ file, name });
  };
  if (query.isLoading) return <div className="page"><p>Preparazione della Mappa Globale…</p></div>;
  if (query.error) return <div className="page"><section className="panel" data-theme="danger"><h1>Viaggio non disponibile</h1><p>{(query.error as Error).message}</p></section></div>;
  return <div className="page travel-page" data-component-type="view" data-theme="default">
    <header className="page-header"><div><p className="eyebrow">Esplorazione</p><h1>Viaggio</h1><p>{query.data?.campaign ? `Mappa Globale · ${query.data.campaign.name}` : "Seleziona una campagna dalle Impostazioni."}</p></div></header>
    <div className="travel-layout"><aside className="travel-sidebar panel" data-component-type="panel" data-theme="dark">
      <section><h2>Mappa Globale</h2><label>Mappa<select value={selectedMap?.id || ""} onChange={(event) => chooseMap(Number(event.target.value))}><option value="" disabled>Nessuna mappa</option>{maps.map((entry) => <option key={entry.id} value={entry.id}>{entry.name}{entry.isDefault ? " · predefinita" : ""}</option>)}</select></label>{query.data?.canManage && selectedMap && <button type="button" className="button primary travel-save-all" disabled={!grid || updateMutation.isPending} onClick={saveAll}>{updateMutation.isPending ? "Salvataggio…" : "Salva"}</button>}{query.data?.canManage && selectedMap && !selectedMap.isDefault && <button type="button" className="button secondary" onClick={() => updateMutation.mutate({ operation: "setDefault", payload: {} })}>Imposta predefinita</button>}</section>
      <section><h3>Qualità</h3><div className="travel-quality">{(["high", "balanced", "light", "verylow"] as Quality[]).map((entry) => <button type="button" className={quality === entry ? "active" : ""} aria-pressed={quality === entry} title={QUALITY_DESCRIPTION[entry]} key={entry} onClick={() => { setQuality(entry); localStorage.setItem("redjango.travel.quality", entry); }}>{entry === "high" ? "Alta" : entry === "balanced" ? "Bilanciata" : entry === "light" ? "Leggera" : "Molto bassa"}</button>)}</div></section>
      {query.data?.canManage && <details><summary>Carica mappa</summary><form className="stacked-form" onSubmit={submitUpload}><label>Nome<input name="name" maxLength={180} required /></label><label>Immagine<input name="file" type="file" accept="image/*" required /></label><button className="button primary" disabled={uploadMutation.isPending || !mapCategory}>Carica</button>{!mapCategory && <small>Configura una categoria immagini attiva.</small>}</form></details>}
      {query.data?.canManage && grid && <details open><summary>Configura griglia</summary><div className="travel-grid-form"><label>Orientamento<select value={grid.orientation} onChange={(event) => setGrid({ ...grid, orientation: event.target.value as TravelGrid["orientation"] })}><option value="pointy">Punta in alto</option><option value="flat">Lato in alto</option></select></label><label>Colonne<input type="number" min={1} max={1000} value={grid.cols} onChange={(event) => setGrid({ ...grid, cols: clamp(Number(event.target.value), 1, 1000) })} /></label><label>Righe<input type="number" min={1} max={1000} value={grid.rows} onChange={(event) => setGrid({ ...grid, rows: clamp(Number(event.target.value), 1, 1000) })} /></label><label>Dimensione esagono<input type="range" min={3} max={200} step={.5} value={grid.hexSize} onChange={(event) => setGrid({ ...grid, hexSize: Number(event.target.value) })} /><span className="travel-hex-finetune"><button type="button" aria-label="Riduci dimensione esagono di 0,1 pixel" onClick={() => setGrid({ ...grid, hexSize: clamp(Number((grid.hexSize - .1).toFixed(1)), 3, 200) })}>−</button><output>{grid.hexSize.toFixed(1)}px</output><button type="button" aria-label="Aumenta dimensione esagono di 0,1 pixel" onClick={() => setGrid({ ...grid, hexSize: clamp(Number((grid.hexSize + .1).toFixed(1)), 3, 200) })}>+</button></span></label></div><div className="button-row"><button className="button primary" onClick={() => updateMutation.mutate({ operation: "saveGrid", payload: { grid } })}>Conferma griglia</button><button className="button secondary" onClick={() => setGrid({ ...selectedMap!.grid })}>Reset</button></div></details>}
      {query.data?.canManage && grid && <details><summary>Effetti esagoni</summary><p className="travel-help">Click seleziona; Shift crea un'area circolare; Ctrl/Cmd un rettangolo; Alt aggiunge o rimuove.</p><div className="travel-area-radius">{[0, 1, 2, 3, 4].map((value) => <button type="button" className={areaRadius === value ? "active" : ""} onClick={() => setAreaRadius(value)} key={value}>{value}</button>)}</div><div className="button-row"><button className="button secondary" onClick={() => setSelection(new Set())}>Pulisci</button><button className="button secondary" onClick={() => setSelection(new Set(Array.from({ length: grid.rows }, (_, row) => Array.from({ length: grid.cols }, (_, col) => `${col}-${row}`)).flat()))}>Tutti</button></div><label className="travel-check"><input type="checkbox" checked={effectBlack} onChange={(event) => setEffectBlack(event.target.checked)} />Oscura immagine</label><label className="travel-check"><input type="checkbox" checked={effectBw} onChange={(event) => setEffectBw(event.target.checked)} />Bianco e nero</label><label>Blur <input type="range" min={0} max={20} step={.5} value={effectBlur} onChange={(event) => setEffectBlur(Number(event.target.value))} /><output>{effectBlur}px</output></label><div className="button-row"><button className="button primary" disabled={!selection.size} onClick={() => applyEffects(false)}>Applica</button><button className="button secondary" disabled={!selection.size} onClick={() => applyEffects(true)}>Rimuovi</button></div></details>}
      <details open><summary>Icone giocatori</summary><p className="travel-help">Trascina un'icona su un esagono. Doppio click per modificarla.</p><MarkerPalette />{query.data?.canManage && markers.length > 0 && <button className="button danger" type="button" onClick={() => saveMarkers([])}>Rimuovi tutte</button>}</details>
      <details open><summary>Icone Attive ({markers.length})</summary>{markers.length ? <div className="travel-active-markers">{markers.map((marker) => { const template = markerTemplate(marker.markerType); return <button type="button" className={focusedMarkerId === marker.id ? "active" : ""} onClick={() => focusMarker(marker)} key={marker.id}><span style={{ "--marker-color": template.colors.fill } as CSSProperties}>{template.glyph}</span><span><strong>{marker.tag || template.label}</strong><small>Esagono {marker.hex} · {marker.author}</small></span></button>; })}</div> : <p className="travel-help">Nessuna icona sulla mappa.</p>}</details>
      <footer><strong>Esagoni selezionati: {selection.size}</strong><small>Rotella: zoom · trascina: mappa · Shift o tasto destro + trascina: griglia</small></footer>
    </aside><section ref={canvasPanelRef} className="travel-canvas-panel panel" data-component-type="panel" data-theme="dark"><div className={`travel-guide ${guideOpen ? "open" : ""}`}><button onClick={() => setGuideOpen((value) => !value)} aria-expanded={guideOpen}>Guida Mappa</button>{guideOpen && <div><p><strong>Giocatori:</strong> trascina un'icona, scrivi un tag e salva.</p><p><strong>Master:</strong> configura la griglia e applica effetti agli esagoni.</p></div>}</div>{selectedMap && grid ? <TravelCanvas travelMap={selectedMap} grid={grid} effects={effects} markers={markers} selected={selection} quality={quality} focusedMarkerId={focusedMarkerId} onGridChange={setGrid} onSelect={selectHex} onMarkerDrop={(markerType, hex) => openMarker({ markerType, hex: hexKey(hex) })} onMarkerEdit={(marker) => openMarker({ markerType: marker.markerType, hex: marker.hex, marker })} /> : <div className="travel-empty"><strong>Nessuna mappa globale</strong><p>{query.data?.canManage ? "Carica la prima mappa dal pannello laterale." : "Un Master deve ancora configurare la Mappa Globale."}</p></div>}</section></div>
    {markerDraft && <Modal title={markerDraft.marker ? "Modifica icona" : "Inserisci tag"} onClose={() => setMarkerDraft(null)} footer={<><button className="button secondary" onClick={() => setMarkerDraft(null)}>Annulla</button>{markerDraft.marker && <button className="button danger" onClick={() => { saveMarkers(markers.filter((entry) => entry.id !== markerDraft.marker!.id)); setMarkerDraft(null); }}>Elimina</button>}<button className="button primary" onClick={confirmMarker}>Salva</button></>}><label>Tag icona<input autoFocus maxLength={120} value={markerTag} onChange={(event) => setMarkerTag(event.target.value)} /></label>{markerDraft.marker && <p>Creata da <strong>{markerDraft.marker.author}</strong>.</p>}</Modal>}
  </div>;
}
