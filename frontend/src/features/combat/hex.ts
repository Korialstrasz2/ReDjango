import type { Axial } from "./types";

export function offsetToAxial(cell: Axial, orientation: "pointy" | "flat"): Axial {
  if (orientation === "flat") {
    return { q: cell.q, r: cell.r - (cell.q - (cell.q & 1)) / 2 };
  }
  return { q: cell.q - (cell.r - (cell.r & 1)) / 2, r: cell.r };
}

export function axialToOffset(cell: Axial, orientation: "pointy" | "flat"): Axial {
  if (orientation === "flat") {
    return { q: cell.q, r: cell.r + (cell.q - (cell.q & 1)) / 2 };
  }
  return { q: cell.q + (cell.r - (cell.r & 1)) / 2, r: cell.r };
}

export function axialVectorToPixel(cell: Axial, size: number, orientation: "pointy" | "flat") {
  if (orientation === "flat") {
    return { x: size * 1.5 * cell.q, y: size * Math.sqrt(3) * (cell.r + cell.q / 2) };
  }
  return { x: size * Math.sqrt(3) * (cell.q + cell.r / 2), y: size * 1.5 * cell.r };
}

export function gridToPixel(cell: Axial, size: number, orientation: "pointy" | "flat", offsetX = 0, offsetY = 0) {
  const axial = offsetToAxial(cell, orientation);
  const point = axialVectorToPixel(axial, size, orientation);
  return { x: offsetX + point.x, y: offsetY + point.y };
}

function axialRound(q: number, r: number): Axial {
  let x = q, z = r, y = -x - z;
  let rx = Math.round(x), ry = Math.round(y), rz = Math.round(z);
  const dx = Math.abs(rx - x), dy = Math.abs(ry - y), dz = Math.abs(rz - z);
  if (dx > dy && dx > dz) rx = -ry - rz;
  else if (dy > dz) ry = -rx - rz;
  else rz = -rx - ry;
  return { q: rx, r: rz };
}

export function pixelToGrid(x: number, y: number, size: number, orientation: "pointy" | "flat", offsetX = 0, offsetY = 0): Axial {
  x -= offsetX; y -= offsetY;
  if (orientation === "flat") {
    return axialToOffset(axialRound((2 / 3 * x) / size, (-1 / 3 * x + Math.sqrt(3) / 3 * y) / size), orientation);
  }
  return axialToOffset(axialRound((Math.sqrt(3) / 3 * x - 1 / 3 * y) / size, (2 / 3 * y) / size), orientation);
}

export function polygonPoints(center: { x: number; y: number }, size: number, orientation: "pointy" | "flat") {
  const startAngle = orientation === "pointy" ? -30 : 0;
  return Array.from({ length: 6 }, (_, index) => {
    const angle = (startAngle + index * 60) * Math.PI / 180;
    return `${center.x + size * Math.cos(angle)},${center.y + size * Math.sin(angle)}`;
  }).join(" ");
}

export function cellKey(cell: Axial) { return `${cell.q}:${cell.r}`; }
