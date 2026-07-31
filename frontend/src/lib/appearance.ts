const HEX_COLOR = /^#([0-9a-f]{6})$/i;
const RGB_COLOR = /^rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)(?:\s*[,/]\s*[\d.]+%?)?\s*\)$/i;
const SRGB_COLOR = /^color\(srgb\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)(?:\s*\/\s*[\d.]+%?)?\s*\)$/i;

function colorChannels(value: string): number[] | null {
  const hexMatch = HEX_COLOR.exec(value);
  if (hexMatch) {
    return [0, 2, 4].map((offset) => Number.parseInt(hexMatch[1].slice(offset, offset + 2), 16) / 255);
  }
  const rgbMatch = RGB_COLOR.exec(value);
  if (rgbMatch) return rgbMatch.slice(1, 4).map((channel) => Math.min(255, Number(channel)) / 255);
  const srgbMatch = SRGB_COLOR.exec(value);
  if (srgbMatch) return srgbMatch.slice(1, 4).map((channel) => Math.min(1, Number(channel)));
  return null;
}

export function colorLuminance(value: string): number {
  const channels = colorChannels(value);
  if (!channels) return 0;
  const [red, green, blue] = channels.map((channel) => channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4);
  return 0.2126 * red + 0.7152 * green + 0.0722 * blue;
}

export function contrastingTextOutline(value: string): "#000000" | "#ffffff" {
  return colorLuminance(value) > 0.179 ? "#000000" : "#ffffff";
}

/** Rapporto di contrasto WCAG fra due colori: da 1 (identici) a 21 (nero su bianco). */
export function contrastRatio(foreground: string, background: string): number {
  const first = colorLuminance(foreground);
  const second = colorLuminance(background);
  const lighter = Math.max(first, second);
  const darker = Math.min(first, second);
  return (lighter + 0.05) / (darker + 0.05);
}

/** Il livello WCAG raggiunto dal rapporto, per il testo normale. */
export function contrastLevel(ratio: number): "AAA" | "AA" | "AA Large" | "insufficiente" {
  if (ratio >= 7) return "AAA";
  if (ratio >= 4.5) return "AA";
  if (ratio >= 3) return "AA Large";
  return "insufficiente";
}
