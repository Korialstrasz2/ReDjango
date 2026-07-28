import { describe, expect, it } from "vitest";

import { filterAudioTracks, formatDuration, formatFileSize, stepIndex, tagLabel, UNTAGGED_FILTER } from "./audio";
import type { AudioTrack } from "./types";

const track = (id: number, title: string, tags: string[], tagLabels: string[]): AudioTrack => ({
  id,
  title,
  tags,
  tagLabels,
  url: `/media/v2/audio/${id}.mp3`,
  originalName: `${id}.mp3`,
  mimeType: "audio/mpeg",
  sizeBytes: 1024,
  durationSeconds: 120,
  notes: "",
  createdAt: null,
});

const library: AudioTrack[] = [
  track(1, "Taverna del Cinghiale", ["musica", "taverna"], ["Musica", "Taverna"]),
  track(2, "Vento sulle rovine", ["ambient"], ["Ambient"]),
  track(3, "Assalto finale", ["combattimento", "boss"], ["Combattimento", "Scontro epico"]),
  track(4, "Registrazione senza nome", [], []),
];

describe("audio library filters", () => {
  it("matches free text on both the title and the tag labels", () => {
    expect(filterAudioTracks(library, "taverna", []).map((entry) => entry.id)).toEqual([1]);
    expect(filterAudioTracks(library, "scontro epico", []).map((entry) => entry.id)).toEqual([3]);
    expect(filterAudioTracks(library, "  VENTO ", []).map((entry) => entry.id)).toEqual([2]);
  });

  it("widens the selection when several tags are active", () => {
    expect(filterAudioTracks(library, "", ["ambient"]).map((entry) => entry.id)).toEqual([2]);
    expect(filterAudioTracks(library, "", ["ambient", "boss"]).map((entry) => entry.id)).toEqual([2, 3]);
  });

  it("keeps untagged tracks reachable through their own filter", () => {
    expect(filterAudioTracks(library, "", [UNTAGGED_FILTER]).map((entry) => entry.id)).toEqual([4]);
    expect(filterAudioTracks(library, "", []).map((entry) => entry.id)).toEqual([1, 2, 3, 4]);
  });

  it("combines text and tags", () => {
    expect(filterAudioTracks(library, "assalto", ["ambient"])).toEqual([]);
    expect(filterAudioTracks(library, "assalto", ["boss"]).map((entry) => entry.id)).toEqual([3]);
  });
});

describe("player queue navigation", () => {
  it("wraps around in both directions", () => {
    expect(stepIndex(4, 0, 1)).toBe(1);
    expect(stepIndex(4, 3, 1)).toBe(0);
    expect(stepIndex(4, 0, -1)).toBe(3);
  });

  it("reports no destination for an empty queue", () => {
    expect(stepIndex(0, 0, 1)).toBe(-1);
  });
});

describe("readable values", () => {
  it("formats durations and unknown lengths", () => {
    expect(formatDuration(0)).toBe("0:00");
    expect(formatDuration(65)).toBe("1:05");
    expect(formatDuration(600)).toBe("10:00");
    expect(formatDuration(null)).toBe("--:--");
    expect(formatDuration(Number.NaN)).toBe("--:--");
  });

  it("formats file sizes", () => {
    expect(formatFileSize(0)).toBe("");
    expect(formatFileSize(4096)).toBe("4 KB");
    expect(formatFileSize(3 * 1024 * 1024)).toBe("3.0 MB");
  });

  it("falls back to the raw value for an unknown tag", () => {
    const tags = [{ value: "musica", label: "Musica" }];
    expect(tagLabel(tags, "musica")).toBe("Musica");
    expect(tagLabel(tags, "sconosciuto")).toBe("sconosciuto");
  });
});
