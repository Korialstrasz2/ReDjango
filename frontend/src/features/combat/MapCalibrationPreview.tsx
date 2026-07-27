import { type PointerEvent, type WheelEvent, useEffect, useMemo, useRef, useState } from "react";

import { gridToPixel, polygonPoints } from "./hex";
import type { Axial } from "./types";

export type MapCalibrationDraft = {
  mapId?: number;
  name: string;
  mapTypeId: number;
  imageId: number | null;
  orientation: "pointy" | "flat";
  rows: number;
  columns: number;
  hexSize: number;
  gridOffsetX: number;
  gridOffsetY: number;
  imageScale: number;
  imageOffsetX: number;
  imageOffsetY: number;
  viewportScale: number;
  viewportOffsetX: number;
  viewportOffsetY: number;
  fogEnabled: boolean;
  fogOpacity: number;
};

type Props = {
  draft: MapCalibrationDraft;
  imageUrl: string;
  onChange: (draft: MapCalibrationDraft) => void;
};

type DragState = {
  mode: "image" | "grid";
  start: { x: number; y: number };
  image: { x: number; y: number };
  grid: { x: number; y: number };
};

const clamp = (value: number, minimum: number, maximum: number) => Math.min(maximum, Math.max(minimum, value));

export function MapCalibrationPreview({ draft, imageUrl, onChange }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const drag = useRef<DragState | null>(null);
  const [dragMode, setDragMode] = useState<"image" | "grid">("grid");
  const [imageSize, setImageSize] = useState({ width: 0, height: 0 });
  useEffect(() => {
    if (!imageUrl) { setImageSize({ width: 0, height: 0 }); return; }
    const image = new Image();
    image.onload = () => setImageSize({ width: image.naturalWidth, height: image.naturalHeight });
    image.src = imageUrl;
  }, [imageUrl]);

  const cells = useMemo<Axial[]>(() => Array.from(
    { length: Math.max(0, draft.rows * draft.columns) },
    (_, index) => ({ q: index % draft.columns, r: Math.floor(index / draft.columns) }),
  ), [draft.columns, draft.rows]);
  const originX = draft.gridOffsetX + draft.hexSize * 1.2;
  const originY = draft.gridOffsetY + draft.hexSize * 1.2;
  const centers = useMemo(
    () => cells.map((cell) => gridToPixel(cell, draft.hexSize, draft.orientation, originX, originY)),
    [cells, draft.hexSize, draft.orientation, originX, originY],
  );
  const gridWidth = Math.max(800, ...centers.map((point) => point.x + draft.hexSize * 1.3));
  const gridHeight = Math.max(560, ...centers.map((point) => point.y + draft.hexSize * 1.3));
  const canvasWidth = Math.max(800, imageSize.width || gridWidth);
  const canvasHeight = Math.max(560, imageSize.height || gridHeight);

  const localPoint = (event: PointerEvent<SVGSVGElement> | WheelEvent<SVGSVGElement>) => {
    const svg = svgRef.current;
    if (!svg) return { x: 0, y: 0 };
    const point = svg.createSVGPoint();
    point.x = event.clientX;
    point.y = event.clientY;
    return point.matrixTransform(svg.getScreenCTM()?.inverse());
  };
  const startDrag = (event: PointerEvent<SVGSVGElement>) => {
    const start = localPoint(event);
    drag.current = {
      mode: dragMode,
      start,
      image: { x: draft.imageOffsetX, y: draft.imageOffsetY },
      grid: { x: draft.gridOffsetX, y: draft.gridOffsetY },
    };
    event.currentTarget.setPointerCapture(event.pointerId);
  };
  const moveDrag = (event: PointerEvent<SVGSVGElement>) => {
    if (!drag.current) return;
    const point = localPoint(event);
    const dx = point.x - drag.current.start.x;
    const dy = point.y - drag.current.start.y;
    if (drag.current.mode === "image") {
      onChange({ ...draft, imageOffsetX: drag.current.image.x + dx, imageOffsetY: drag.current.image.y + dy });
    } else {
      onChange({ ...draft, gridOffsetX: drag.current.grid.x + dx, gridOffsetY: drag.current.grid.y + dy });
    }
  };
  const zoomImage = (event: WheelEvent<SVGSVGElement>) => {
    if (!imageUrl) return;
    event.preventDefault();
    const point = localPoint(event);
    const nextScale = clamp(draft.imageScale * Math.exp(-event.deltaY * .0014), .1, 4);
    const imageX = (point.x - draft.imageOffsetX) / draft.imageScale;
    const imageY = (point.y - draft.imageOffsetY) / draft.imageScale;
    onChange({
      ...draft,
      imageScale: nextScale,
      imageOffsetX: point.x - imageX * nextScale,
      imageOffsetY: point.y - imageY * nextScale,
    });
  };

  return <section className="combat-calibration-preview" data-component-type="map-editor" data-theme="tactical">
    <header>
      <div className="segmented" aria-label="Elemento da trascinare">
        <button type="button" className={dragMode === "grid" ? "active" : ""} onClick={() => setDragMode("grid")}>Trascina griglia</button>
        <button type="button" className={dragMode === "image" ? "active" : ""} onClick={() => setDragMode("image")} disabled={!imageUrl}>Trascina immagine</button>
      </div>
      <span>{imageSize.width ? `${imageSize.width} × ${imageSize.height} px` : "Scegli un'immagine"} · rotella = scala immagine</span>
    </header>
    <div className="combat-calibration-stage">
      <svg
        ref={svgRef}
        viewBox={`0 0 ${canvasWidth} ${canvasHeight}`}
        role="application"
        aria-label="Anteprima dal vivo di immagine e griglia esagonale"
        className={`drag-${dragMode}`}
        onPointerDown={startDrag}
        onPointerMove={moveDrag}
        onPointerUp={() => { drag.current = null; }}
        onPointerCancel={() => { drag.current = null; }}
        onWheel={zoomImage}
      >
        <rect width={canvasWidth} height={canvasHeight} fill="#0c100f" />
        {imageUrl && <image
          href={imageUrl}
          x={draft.imageOffsetX}
          y={draft.imageOffsetY}
          width={imageSize.width * draft.imageScale}
          height={imageSize.height * draft.imageScale}
          preserveAspectRatio="none"
        />}
        <g className="calibration-grid-layer">
          {centers.map((center, index) => <polygon
            key={`${cells[index].q}:${cells[index].r}`}
            points={polygonPoints(center, Math.max(2, draft.hexSize - .8), draft.orientation)}
          />)}
        </g>
      </svg>
      {!imageUrl && <div className="combat-calibration-empty"><strong>Importa una mappa</strong><span>L'anteprima della griglia resta visibile durante tutta la configurazione.</span></div>}
    </div>
    <footer><span>Griglia {draft.columns} × {draft.rows}</span><span>Esagono {draft.hexSize.toFixed(1)} px</span><span>Immagine {draft.imageScale.toFixed(2)}×</span></footer>
  </section>;
}
