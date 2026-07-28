import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { legacyAction } from "../../lib/api";
import { stepIndex } from "../../lib/audio";
import type { AudioTrack, SettingsData } from "../../lib/types";

type AudioPlayerValue = {
  current: AudioTrack | null;
  queue: AudioTrack[];
  playing: boolean;
  volume: number;
  position: number;
  duration: number;
  play: (track: AudioTrack, queue?: AudioTrack[]) => void;
  toggle: () => void;
  stop: () => void;
  next: () => void;
  previous: () => void;
  seek: (seconds: number) => void;
  changeVolume: (value: number) => void;
  forget: (trackId: number) => void;
  syncQueue: (tracks: AudioTrack[]) => void;
};

const AudioPlayerContext = createContext<AudioPlayerValue | null>(null);

export function useAudioPlayer() {
  const value = useContext(AudioPlayerContext);
  if (!value) throw new Error("Audio player context unavailable");
  return value;
}

function storedVolume(settings: SettingsData): number {
  const value = Number(settings.ui["audio.volume"]);
  return Number.isFinite(value) ? Math.min(100, Math.max(0, Math.round(value))) : 60;
}

type Props = {
  children: ReactNode;
  settings: SettingsData;
  notify: (message: string, kind?: "success" | "error" | "info") => void;
};

/**
 * Owns the single audio element of the workstation. It lives above the router, so
 * moving from Combattimento to a character sheet never interrupts the soundtrack.
 */
export function AudioPlayerProvider({ children, settings, notify }: Props) {
  const queryClient = useQueryClient();
  const audioRef = useRef<HTMLAudioElement>(null);
  const volumeSaveTimer = useRef<number | null>(null);
  const pendingVolume = useRef<number | null>(null);
  const [current, setCurrent] = useState<AudioTrack | null>(null);
  const [queue, setQueue] = useState<AudioTrack[]>([]);
  const [playing, setPlaying] = useState(false);
  const [position, setPosition] = useState(0);
  const [duration, setDuration] = useState(0);
  const preferredVolume = storedVolume(settings);
  const [volume, setVolume] = useState(preferredVolume);
  const autoplayNext = settings.ui["audio.autoplay_next"] !== false;

  useEffect(() => {
    const element = audioRef.current;
    if (element) element.volume = volume / 100;
  }, [volume]);

  // Follow the saved preference when it changes elsewhere, but never fight a save in flight.
  useEffect(() => {
    if (pendingVolume.current === null) setVolume(preferredVolume);
  }, [preferredVolume]);

  useEffect(() => () => { if (volumeSaveTimer.current) window.clearTimeout(volumeSaveTimer.current); }, []);

  const startPlayback = useCallback((track: AudioTrack) => {
    const element = audioRef.current;
    if (!element) return;
    if (element.getAttribute("src") === track.url) element.currentTime = 0;
    else {
      element.src = track.url;
      element.load();
    }
    setPosition(0);
    setDuration(track.durationSeconds || 0);
    void element.play().catch(() => notify("Il browser non è riuscito ad avviare la traccia.", "error"));
  }, [notify]);

  const play = useCallback((track: AudioTrack, nextQueue?: AudioTrack[]) => {
    if (nextQueue) setQueue(nextQueue);
    setCurrent(track);
    startPlayback(track);
  }, [startPlayback]);

  const toggle = useCallback(() => {
    const element = audioRef.current;
    if (!element || !current) return;
    if (element.paused) void element.play().catch(() => notify("Il browser non è riuscito a riprendere la traccia.", "error"));
    else element.pause();
  }, [current, notify]);

  // The source is deliberately left in place: clearing it makes browsers raise a
  // spurious media error, and the next selection replaces it anyway.
  const stop = useCallback(() => {
    const element = audioRef.current;
    if (element) {
      element.pause();
      element.currentTime = 0;
    }
    setCurrent(null);
    setPlaying(false);
    setPosition(0);
    setDuration(0);
  }, []);

  const step = useCallback((direction: 1 | -1) => {
    if (!queue.length) return;
    const index = current ? queue.findIndex((entry) => entry.id === current.id) : -1;
    const target = index < 0 ? (direction === 1 ? 0 : queue.length - 1) : stepIndex(queue.length, index, direction);
    const track = queue[target];
    if (track) play(track);
  }, [current, play, queue]);

  const next = useCallback(() => step(1), [step]);
  const previous = useCallback(() => step(-1), [step]);

  const seek = useCallback((seconds: number) => {
    const element = audioRef.current;
    if (!element || !Number.isFinite(seconds)) return;
    element.currentTime = Math.max(0, seconds);
    setPosition(element.currentTime);
  }, []);

  // The slider stays instant; the personal preference is written once the hand stops.
  const changeVolume = useCallback((value: number) => {
    const next = Math.min(100, Math.max(0, Math.round(value)));
    setVolume(next);
    if (volumeSaveTimer.current) window.clearTimeout(volumeSaveTimer.current);
    volumeSaveTimer.current = window.setTimeout(() => {
      volumeSaveTimer.current = null;
      if (next === preferredVolume) return;
      pendingVolume.current = next;
      legacyAction<SettingsData>("/api/settings/", "settings.save", { settings: { "audio.volume": next } })
        .then((result) => queryClient.setQueryData(["settings"], result.data))
        .catch(() => undefined)
        .finally(() => { pendingVolume.current = null; });
    }, 900);
  }, [preferredVolume, queryClient]);

  /** Drops a track that no longer exists, without disturbing anything else playing. */
  const forget = useCallback((trackId: number) => {
    setQueue((entries) => entries.filter((entry) => entry.id !== trackId));
    if (current?.id === trackId) stop();
  }, [current, stop]);

  const syncQueue = useCallback((tracks: AudioTrack[]) => setQueue(tracks), []);

  const value = useMemo<AudioPlayerValue>(() => ({
    current,
    queue,
    playing,
    volume,
    position,
    duration,
    play,
    toggle,
    stop,
    next,
    previous,
    seek,
    changeVolume,
    forget,
    syncQueue,
  }), [changeVolume, current, duration, forget, next, play, playing, position, previous, queue, seek, stop, syncQueue, toggle, volume]);

  return <AudioPlayerContext.Provider value={value}>
    {children}
    <audio
      ref={audioRef}
      preload="metadata"
      onPlay={() => setPlaying(true)}
      onPause={() => setPlaying(false)}
      onTimeUpdate={(event) => setPosition(event.currentTarget.currentTime)}
      onLoadedMetadata={(event) => {
        const measured = event.currentTarget.duration;
        if (Number.isFinite(measured) && measured > 0) setDuration(measured);
      }}
      onEnded={() => {
        if (autoplayNext && queue.length > 1) next();
        else stop();
      }}
      onError={() => { if (current) notify(`Impossibile riprodurre ${current.title}.`, "error"); }}
    />
  </AudioPlayerContext.Provider>;
}
