const HEX_COLOR = /^#([0-9a-f]{6})$/i;

export function colorLuminance(value: string): number {
  const match = HEX_COLOR.exec(value);
  if (!match) return 0;
  const channels = [0, 2, 4].map((offset) => Number.parseInt(match[1].slice(offset, offset + 2), 16) / 255);
  const [red, green, blue] = channels.map((channel) => channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4);
  return 0.2126 * red + 0.7152 * green + 0.0722 * blue;
}

export function contrastingTextOutline(value: string): "#000000" | "#ffffff" {
  return colorLuminance(value) > 0.179 ? "#000000" : "#ffffff";
}
