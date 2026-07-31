import { type PointerEvent, type WheelEvent, useEffect, useMemo, useRef, useState } from "react";

import { axialVectorToPixel, cellKey, gridToPixel, pixelToGrid, polygonPoints } from "./hex";
import type { Axial, CombatMap, MapParticipant, PathResult, TerrainBadge } from "./types";

type Props = {
  map: CombatMap;
  selected: Axial | null;
  selectedCells: Axial[];
  selectionEnabled: boolean;
  /** Sigle da stampare sugli esagoni tipizzati; `null` quando la scheda Tipologia è chiusa. */
  terrainBadges: Record<number, TerrainBadge> | null;
  paths: PathResult | null;
  pathStart: Axial | null;
  controlledCharacterId: number | null;
  canControlAll: boolean;
  onHexClick: (cell: Axial) => void;
  onSelectionChange: (cells: Axial[]) => void;
  onMoveParticipant: (participantId: number, cell: Axial) => void;
  onContextParticipant: (participant: MapParticipant) => void;
};

type PanDrag = { startX: number; startY: number; originX: number; originY: number };
type SelectionDrag = { mode: "add" | "remove"; cells: Map<string, Axial>; visited: Set<string> };

const clamp = (value: number, minimum: number, maximum: number) => Math.min(maximum, Math.max(minimum, value));

export function CombatMapCanvas({
  map, selected, selectedCells, selectionEnabled, terrainBadges, paths, pathStart, controlledCharacterId, canControlAll,
  onHexClick, onSelectionChange, onMoveParticipant, onContextParticipant,
}: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const panDrag = useRef<PanDrag | null>(null);
  const panMoved = useRef(false);
  const selectionDrag = useRef<SelectionDrag | null>(null);
  const [dragging, setDragging] = useState<MapParticipant | null>(null);
  const [dragPoint, setDragPoint] = useState<{ x: number; y: number } | null>(null);
  const [view, setView] = useState({ scale: map.viewportScale || 1, x: -map.viewportOffsetX, y: -map.viewportOffsetY });
  const [imageSize, setImageSize] = useState({ width: 0, height: 0 });

  useEffect(() => {
    setView({ scale: map.viewportScale || 1, x: -map.viewportOffsetX, y: -map.viewportOffsetY });
  }, [map.id, map.viewportOffsetX, map.viewportOffsetY, map.viewportScale]);
  useEffect(() => {
    if (!map.imageUrl) { setImageSize({ width: 0, height: 0 }); return; }
    const image = new Image();
    image.onload = () => setImageSize({ width: image.naturalWidth, height: image.naturalHeight });
    image.src = map.imageUrl;
  }, [map.imageUrl]);
  const cells = useMemo(() => Array.from(
    { length: map.rows * map.columns },
    (_, index) => ({ q: index % map.columns, r: Math.floor(index / map.columns) }),
  ), [map.columns, map.rows]);
  const edited = useMemo(() => new Map(map.hexes.map((entry) => [cellKey(entry), entry])), [map.hexes]);
  const selectedKeys = useMemo(() => new Set(selectedCells.map(cellKey)), [selectedCells]);
  const direct = useMemo(() => new Set((paths?.direct.path || []).map(cellKey)), [paths]);
  const fastest = useMemo(() => new Set((paths?.fastest.path || []).map(cellKey)), [paths]);
  const gridOriginX = map.gridOffsetX + map.hexSize * 1.2;
  const gridOriginY = map.gridOffsetY + map.hexSize * 1.2;
  const centers = cells.map((cell) => gridToPixel(cell, map.hexSize, map.orientation, gridOriginX, gridOriginY));
  const badgeFont = Math.max(7, Math.min(15, map.hexSize * .46));
  const badgeHeight = badgeFont * 1.55;
  const maxX = Math.max(600, imageSize.width * map.imageScale + map.imageOffsetX, ...centers.map((entry) => entry.x + map.hexSize * 1.4));
  const maxY = Math.max(420, imageSize.height * map.imageScale + map.imageOffsetY, ...centers.map((entry) => entry.y + map.hexSize * 1.4));

  const svgPoint = (event: { clientX: number; clientY: number }) => {
    const svg = svgRef.current;
    if (!svg) return null;
    const point = svg.createSVGPoint();
    point.x = event.clientX; point.y = event.clientY;
    return point.matrixTransform(svg.getScreenCTM()?.inverse());
  };
  const pointerCell = (event: PointerEvent<SVGSVGElement>) => {
    const point = svgPoint(event);
    if (!point) return null;
    const cell = pixelToGrid((point.x - view.x) / view.scale, (point.y - view.y) / view.scale, map.hexSize, map.orientation, gridOriginX, gridOriginY);
    return cell.q >= 0 && cell.q < map.columns && cell.r >= 0 && cell.r < map.rows ? cell : null;
  };
  const pointerWorld = (event: { clientX: number; clientY: number }) => {
    const point = svgPoint(event);
    return point ? { x: (point.x - view.x) / view.scale, y: (point.y - view.y) / view.scale } : null;
  };
  const finishPointer = (event: PointerEvent<SVGSVGElement>) => {
    if (selectionDrag.current) {
      selectionDrag.current = null;
    } else if (dragging) {
      const cell = pointerCell(event);
      if (cell) onMoveParticipant(dragging.id, cell);
      setDragging(null);
      setDragPoint(null);
    } else if (panDrag.current && !panMoved.current) {
      const cell = pointerCell(event);
      if (cell) onHexClick(cell);
    }
    panDrag.current = null;
    panMoved.current = false;
  };
  const zoomAt = (nextScale: number, clientX?: number, clientY?: number) => {
    const svg = svgRef.current;
    const focus = clientX != null && clientY != null ? svgPoint({ clientX, clientY }) : null;
    const point = focus || { x: (svg?.clientWidth || maxX) / 2, y: (svg?.clientHeight || maxY) / 2 };
    setView((current) => {
      const scale = clamp(nextScale, .25, 4);
      const worldX = (point.x - current.x) / current.scale;
      const worldY = (point.y - current.y) / current.scale;
      return { scale, x: point.x - worldX * scale, y: point.y - worldY * scale };
    });
  };
  const handleWheel = (event: WheelEvent<SVGSVGElement>) => {
    event.preventDefault();
    zoomAt(view.scale * Math.exp(-event.deltaY * .0014), event.clientX, event.clientY);
  };
  const startPan = (event: PointerEvent<SVGSVGElement>) => {
    if (event.button !== 0 && event.button !== 1) return;
    if (selectionEnabled && event.button === 0) {
      const cell = pointerCell(event);
      if (!cell) return;
      const key = cellKey(cell);
      const mode = selectedKeys.has(key) ? "remove" : "add";
      const selectedMap = new Map(selectedCells.map((entry) => [cellKey(entry), entry]));
      if (mode === "add") selectedMap.set(key, cell); else selectedMap.delete(key);
      selectionDrag.current = { mode, cells: selectedMap, visited: new Set([key]) };
      onSelectionChange([...selectedMap.values()]);
      event.currentTarget.setPointerCapture(event.pointerId);
      return;
    }
    panMoved.current = false;
    panDrag.current = { startX: event.clientX, startY: event.clientY, originX: view.x, originY: view.y };
    event.currentTarget.setPointerCapture(event.pointerId);
  };
  const movePan = (event: PointerEvent<SVGSVGElement>) => {
    if (dragging) {
      setDragPoint(pointerWorld(event));
      return;
    }
    const selection = selectionDrag.current;
    if (selection) {
      const cell = pointerCell(event);
      if (!cell) return;
      const key = cellKey(cell);
      if (selection.visited.has(key)) return;
      selection.visited.add(key);
      if (selection.mode === "add") selection.cells.set(key, cell); else selection.cells.delete(key);
      onSelectionChange([...selection.cells.values()]);
      return;
    }
    const drag = panDrag.current;
    if (!drag) return;
    const dx = event.clientX - drag.startX;
    const dy = event.clientY - drag.startY;
    if (Math.abs(dx) + Math.abs(dy) > 3) panMoved.current = true;
    setView((current) => ({ ...current, x: drag.originX + dx, y: drag.originY + dy }));
  };
  const resetView = () => setView({ scale: map.viewportScale || 1, x: -map.viewportOffsetX, y: -map.viewportOffsetY });

  return <div className="combat-map-stage" data-component-type="grid" data-theme="tactical">
    <div className="combat-map-runtime-toolbar" data-component-type="toolbar" data-theme="combat">
      <button type="button" title="Riduci" onClick={() => zoomAt(view.scale / 1.2)}>−</button>
      <output>{Math.round(view.scale * 100)}%</output>
      <button type="button" title="Ingrandisci" onClick={() => zoomAt(view.scale * 1.2)}>+</button>
      <button type="button" onClick={resetView}>Centra</button>
    </div>
    <svg
      ref={svgRef}
      className={`${dragging ? "is-dragging-token" : ""} ${selectionEnabled ? "is-selecting-hexes" : ""}`}
      viewBox={`0 0 ${maxX} ${maxY}`}
      role="application"
      aria-label={`Mappa tattica ${map.name}`}
      onPointerDown={startPan}
      onPointerMove={movePan}
      onPointerUp={finishPointer}
      onPointerCancel={() => { setDragging(null); setDragPoint(null); selectionDrag.current = null; panDrag.current = null; panMoved.current = false; }}
      onWheel={handleWheel}
    >
      <defs>
        <filter id="token-shadow"><feDropShadow dx="0" dy="3" stdDeviation="3" floodOpacity=".7" /></filter>
        <filter id="local-fog-filter" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="5" /><feColorMatrix type="saturate" values="0" /><feComponentTransfer><feFuncR type="linear" slope=".58" /><feFuncG type="linear" slope=".58" /><feFuncB type="linear" slope=".58" /></feComponentTransfer></filter>
        <pattern id="blocked-pattern" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="3" height="8" fill="#b8493f" opacity=".62" /></pattern>
        {map.hexes.filter((entry) => entry.fogEffect).map((entry) => {
          const center = gridToPixel(entry, map.hexSize, map.orientation, gridOriginX, gridOriginY);
          return <clipPath key={`fog-clip-${cellKey(entry)}`} id={`fog-clip-${entry.q}-${entry.r}`}><polygon points={polygonPoints(center, map.hexSize - .5, map.orientation)} /></clipPath>;
        })}
      </defs>
      <g transform={`translate(${view.x} ${view.y}) scale(${view.scale})`}>
        {map.imageUrl && <image href={map.imageUrl} x={map.imageOffsetX} y={map.imageOffsetY} width={imageSize.width * map.imageScale} height={imageSize.height * map.imageScale} preserveAspectRatio="none" />}
        <g className="combat-local-fog-layer" pointerEvents="none">
          {map.hexes.filter((entry) => entry.fogEffect).map((entry) => {
            const center = gridToPixel(entry, map.hexSize, map.orientation, gridOriginX, gridOriginY);
            return <g key={`local-fog-${cellKey(entry)}`} clipPath={`url(#fog-clip-${entry.q}-${entry.r})`}>
              {map.imageUrl && <image href={map.imageUrl} x={map.imageOffsetX} y={map.imageOffsetY} width={imageSize.width * map.imageScale} height={imageSize.height * map.imageScale} preserveAspectRatio="none" filter="url(#local-fog-filter)" />}
              <polygon points={polygonPoints(center, map.hexSize, map.orientation)} fill="#06100e" fillOpacity=".56" />
            </g>;
          })}
        </g>
        <g className="combat-hex-layer">
          {cells.map((cell, index) => {
            const key = cellKey(cell);
            const state = edited.get(key);
            const isSelected = selected && cellKey(selected) === key;
            const isPendingSelection = selectedKeys.has(key);
            const center = centers[index];
            const pathClass = fastest.has(key) ? "fastest" : direct.has(key) ? "direct" : "";
            const badges = terrainBadges && state?.terrainTypeIds.length
              ? state.terrainTypeIds.map((terrainId) => terrainBadges[terrainId]).filter(Boolean)
              : [];
            const badgeTop = center.y - (badges.length * badgeHeight + (badges.length - 1) * 2) / 2;
            return <g key={key} className={`combat-hex ${pathClass} ${isSelected ? "selected" : ""} ${isPendingSelection ? "pending-selection" : ""}`}>
              <polygon points={polygonPoints(center, map.hexSize - .8, map.orientation)} fill={state?.overlayColor || "transparent"} fillOpacity={state?.overlayOpacity ?? 0} />
              {state?.blocked && <polygon points={polygonPoints(center, map.hexSize - 1, map.orientation)} fill="url(#blocked-pattern)" />}
              <polygon className="hex-line" points={polygonPoints(center, map.hexSize - .8, map.orientation)} />
              {(isSelected || pathStart && cellKey(pathStart) === key) && <text x={center.x} y={badges.length ? badgeTop - badgeFont * .5 : center.y + 4} textAnchor="middle">{cell.q},{cell.r}</text>}
              {badges.map((badge, position) => {
                const width = Math.min(map.hexSize * 1.6, badge.label.length * badgeFont * .68 + badgeFont * .85);
                const top = badgeTop + position * (badgeHeight + 2);
                return <g key={badge.id} className="combat-hex-terrain-badge">
                  <rect x={center.x - width / 2} y={top} width={width} height={badgeHeight} rx={badgeHeight / 2} fill={badge.color} stroke={badge.ink} />
                  <text x={center.x} y={top + badgeHeight / 2} style={{ fontSize: `${badgeFont}px`, fill: badge.ink }} textAnchor="middle" dominantBaseline="central">{badge.label}</text>
                  <title>{badge.name} · {badge.detail}</title>
                </g>;
              })}
            </g>;
          })}
        </g>
        {map.fogEnabled && <g className={`combat-fog-layer ${map.viewerCanSeeAll ? "master" : "player"}`} pointerEvents="none">
          {cells.map((cell, index) => {
            const state = edited.get(cellKey(cell));
            if (state?.revealed) return null;
            return <polygon key={cellKey(cell)} points={polygonPoints(centers[index], map.hexSize - .4, map.orientation)} fill="#020504" fillOpacity={map.viewerCanSeeAll ? Math.min(.68, map.fogOpacity) : map.fogOpacity} />;
          })}
        </g>}
        <g className="combat-token-layer">
          {map.participants.map((participant) => {
            const anchor = gridToPixel(participant.anchor, map.hexSize, map.orientation, gridOriginX, gridOriginY);
            const radius = map.hexSize * .58;
            const canMove = canControlAll || participant.character.id === controlledCharacterId;
            return <g
              key={participant.id}
              className={`combat-token ${participant.character.id === map.activeCharacterId ? "active" : ""} ${canMove ? "can-move" : "locked"} ${dragging?.id === participant.id ? "drag-origin" : ""}`}
              transform={`translate(${anchor.x} ${anchor.y})`}
              onPointerDown={(event) => {
                if (!canMove || event.button !== 0) return;
                event.stopPropagation();
                setDragging(participant);
                setDragPoint(pointerWorld(event));
                event.currentTarget.setPointerCapture(event.pointerId);
              }}
              onContextMenu={(event) => { event.preventDefault(); event.stopPropagation(); if (canControlAll) onContextParticipant(participant); }}
              filter="url(#token-shadow)"
            >
              {participant.footprint.map((offset) => {
                const relative = axialVectorToPixel(offset, map.hexSize, map.orientation);
                return <circle key={cellKey(offset)} cx={relative.x} cy={relative.y} r={radius} fill={participant.tokenColor} fillOpacity=".82" stroke="#f4dfb4" strokeWidth="2" />;
              })}
              {participant.character.portrait
                ? <image href={participant.character.portrait} x={-radius} y={-radius} width={radius * 2} height={radius * 2} preserveAspectRatio="xMidYMid slice" clipPath="circle()" />
                : <text textAnchor="middle" y="5">{participant.character.name.slice(0, 2).toUpperCase()}</text>}
              <title>{participant.character.name}{canMove ? " · trascina mantenendo la sagoma" : ""}{canControlAll ? " · clic destro per le azioni" : ""}</title>
            </g>;
          })}
          {dragging && dragPoint && (() => {
            const radius = map.hexSize * .58;
            return <g className="combat-token-drag-preview" transform={`translate(${dragPoint.x} ${dragPoint.y})`} pointerEvents="none" filter="url(#token-shadow)">
              {dragging.footprint.map((offset) => {
                const relative = axialVectorToPixel(offset, map.hexSize, map.orientation);
                return <circle key={cellKey(offset)} cx={relative.x} cy={relative.y} r={radius} fill={dragging.tokenColor} fillOpacity=".92" stroke="#ffe996" strokeWidth="3" />;
              })}
              {dragging.character.portrait
                ? <image href={dragging.character.portrait} x={-radius} y={-radius} width={radius * 2} height={radius * 2} preserveAspectRatio="xMidYMid slice" clipPath="circle()" />
                : <text textAnchor="middle" y="5">{dragging.character.name.slice(0, 2).toUpperCase()}</text>}
            </g>;
          })()}
        </g>
      </g>
    </svg>
    {!map.imageUrl && <div className="combat-map-empty"><strong>Nessuna immagine</strong><span>Apri l'editor mappa per scegliere o caricare uno sfondo.</span></div>}
  </div>;
}
