import { formatDuration } from "../../lib/audio";
import { useAudioPlayer } from "./AudioPlayerProvider";

type Props = { onOpen: () => void };

/**
 * Lives in the quick-tools bar and only exists while something is loaded, so the
 * campaign readout keeps its room whenever the soundtrack is silent.
 */
export function AudioMiniPlayer({ onOpen }: Props) {
  const player = useAudioPlayer();
  const track = player.current;
  if (!track) return null;

  const total = player.duration || track.durationSeconds || 0;
  const progress = total ? Math.min(100, (player.position / total) * 100) : 0;

  return <div className="audio-mini-player" data-component-type="toolbar" data-theme="gold" role="group" aria-label="Traccia in riproduzione">
    <button
      type="button"
      className="audio-mini-title"
      onClick={onOpen}
      title={`${track.title} — apri Audio`}
      aria-label={`${track.title}. Apri il lettore audio.`}
    >
      <span aria-hidden="true">{player.playing ? "♪" : "❚❚"}</span>
      <strong>{track.title}</strong>
    </button>
    <span className="audio-mini-progress" aria-hidden="true"><i style={{ width: `${progress}%` }} /></span>
    <span className="audio-mini-time" aria-hidden="true">{formatDuration(player.position)}</span>
    <button type="button" className="icon-button" onClick={player.previous} disabled={player.queue.length < 2} aria-label="Traccia precedente" title="Traccia precedente"><span aria-hidden="true">⏮</span></button>
    <button type="button" className="icon-button" onClick={player.toggle} aria-label={player.playing ? "Metti in pausa" : "Riprendi"} title={player.playing ? "Pausa" : "Riprendi"}><span aria-hidden="true">{player.playing ? "⏸" : "▶"}</span></button>
    <button type="button" className="icon-button" onClick={player.next} disabled={player.queue.length < 2} aria-label="Traccia successiva" title="Traccia successiva"><span aria-hidden="true">⏭</span></button>
    <button type="button" className="icon-button" onClick={player.stop} aria-label="Interrompi la traccia" title="Interrompi"><span aria-hidden="true">⏹</span></button>
  </div>;
}
