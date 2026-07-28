import { formatDuration } from "../../lib/audio";
import { useAudioPlayer } from "./AudioPlayerProvider";

type Props = { compact?: boolean };

/** The transport shared by the drawer and the miniature player in the top bar. */
export function AudioPlayerControls({ compact = false }: Props) {
  const player = useAudioPlayer();
  const { current, playing, position, duration, volume } = player;
  const maximum = duration || current?.durationSeconds || 0;

  return <div className={`audio-transport ${compact ? "compact" : ""}`.trim()} data-component-type="toolbar" data-theme="gold">
    <div className="audio-transport-buttons">
      <button type="button" className="icon-button" onClick={player.previous} disabled={player.queue.length < 2} aria-label="Traccia precedente" title="Traccia precedente"><span aria-hidden="true">⏮</span></button>
      <button type="button" className="icon-button audio-transport-play" onClick={player.toggle} disabled={!current} aria-label={playing ? "Metti in pausa" : "Riprendi"} title={playing ? "Pausa" : "Riprendi"}><span aria-hidden="true">{playing ? "⏸" : "▶"}</span></button>
      <button type="button" className="icon-button" onClick={player.stop} disabled={!current} aria-label="Interrompi" title="Interrompi"><span aria-hidden="true">⏹</span></button>
      <button type="button" className="icon-button" onClick={player.next} disabled={player.queue.length < 2} aria-label="Traccia successiva" title="Traccia successiva"><span aria-hidden="true">⏭</span></button>
    </div>
    <label className="audio-progress">
      <span className="sr-only">Posizione nella traccia</span>
      <input
        type="range"
        min={0}
        max={Math.max(maximum, 1)}
        step={1}
        value={Math.min(position, maximum || position)}
        disabled={!current || !maximum}
        onChange={(event) => player.seek(Number(event.target.value))}
      />
      <small aria-hidden="true">{formatDuration(position)} / {formatDuration(maximum || null)}</small>
    </label>
    <label className="audio-volume">
      <span aria-hidden="true">{volume === 0 ? "🔇" : "🔊"}</span>
      <span className="sr-only">Volume</span>
      <input
        type="range"
        min={0}
        max={100}
        step={1}
        value={volume}
        aria-valuetext={`${volume} per cento`}
        onChange={(event) => player.changeVolume(Number(event.target.value))}
      />
    </label>
  </div>;
}
