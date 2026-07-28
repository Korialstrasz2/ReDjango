import type { AudioTag, AudioTrack } from "./types";

export const UNTAGGED_FILTER = "__senza-tag__";

/** Filters the library by free text and by tags; several tags widen the selection. */
export function filterAudioTracks(tracks: AudioTrack[], query: string, tags: string[]): AudioTrack[] {
  const needle = query.trim().toLocaleLowerCase("it");
  const wanted = new Set(tags);
  return tracks.filter((track) => {
    if (needle && !`${track.title} ${track.tagLabels.join(" ")}`.toLocaleLowerCase("it").includes(needle)) return false;
    if (!wanted.size) return true;
    if (wanted.has(UNTAGGED_FILTER) && !track.tags.length) return true;
    return track.tags.some((tag) => wanted.has(tag));
  });
}

/** Wraps around so a session never ends on a dead end. */
export function stepIndex(length: number, index: number, step: number): number {
  if (length <= 0) return -1;
  return (((index + step) % length) + length) % length;
}

export function tagLabel(tags: AudioTag[], value: string): string {
  return tags.find((tag) => tag.value === value)?.label || value;
}

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || !Number.isFinite(seconds) || seconds < 0) return "--:--";
  const whole = Math.floor(seconds);
  const minutes = Math.floor(whole / 60);
  const rest = whole % 60;
  return `${minutes}:${String(rest).padStart(2, "0")}`;
}

export function formatFileSize(bytes: number): string {
  if (!bytes) return "";
  const megabytes = bytes / (1024 * 1024);
  return megabytes >= 1 ? `${megabytes.toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;
}
