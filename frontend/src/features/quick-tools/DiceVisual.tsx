import { forwardRef, type CSSProperties } from "react";

import type { DiceTexture } from "../../lib/types";

type DiceVisualProps = {
  sides: number;
  value?: number | string;
  texture?: DiceTexture | null;
  rolling?: boolean;
  className?: string;
  label?: string;
};

function DiceGeometry({ sides }: { sides: number }) {
  return <svg className={`dice-geometry ${sides === 100 ? "dice-geometry-fine" : ""}`} viewBox="0 0 100 100" aria-hidden="true">
    {sides === 4 && <path d="M50 2v58M2 96l48-36 48 36" />}
    {sides === 6 && <rect x="9" y="9" width="82" height="82" rx="3" />}
    {sides === 8 && <path d="M50 50 50 1M50 50 98 50M50 50 50 99M50 50 2 50" />}
    {sides === 10 && <path d="M50 50 50 1M50 50 94 35M50 50 77 89M50 50 50 99M50 50 23 89M50 50 6 35" />}
    {sides === 12 && <path d="M50 22 76 41 66 71H34L24 41ZM50 1v21M92 25 76 41M92 75 66 71M50 99V71M8 75l26-4M8 25l16 16" />}
    {sides === 20 && <path d="M50 18 74 64H26ZM50 1v17M94 25 74 64M94 75 74 64M50 99 74 64M50 99 26 64M6 75l20-11M6 25l20 39" />}
    {sides === 100 && <>
      <circle cx="50" cy="50" r="47" />
      <ellipse cx="50" cy="50" rx="43" ry="17" />
      <ellipse cx="50" cy="50" rx="17" ry="43" />
      <ellipse cx="50" cy="50" rx="41" ry="15" transform="rotate(45 50 50)" />
      <ellipse cx="50" cy="50" rx="41" ry="15" transform="rotate(-45 50 50)" />
    </>}
  </svg>;
}

export const DiceVisual = forwardRef<HTMLDivElement, DiceVisualProps>(function DiceVisual({ sides, value, texture, rolling = false, className = "", label }, ref) {
  const textureStyle = texture ? ({
    backgroundImage: `url("${texture.imageUrl}")`,
    transform: `translate(${texture.offsetX}%, ${texture.offsetY}%) rotate(${texture.rotation}deg) scale(${texture.scale / 100})`
  } as CSSProperties) : undefined;

  return <div
    ref={ref}
    className={`dice-visual dice-shape-${sides} ${rolling ? "is-rolling" : ""} ${className}`}
    data-sides={sides}
    aria-label={label || `Dado a ${sides} facce`}
  >
    <span className="dice-texture" style={textureStyle} aria-hidden="true" />
    <DiceGeometry sides={sides} />
    <strong className="dice-face-value">{value ?? `d${sides}`}</strong>
  </div>;
});
