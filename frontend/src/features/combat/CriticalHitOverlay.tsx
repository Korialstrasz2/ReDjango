import { useEffect, useRef, useState } from "react";

const CRIT_ASSETS: Record<string, { image: string; audio: string }> = {
  minor: { image: "/static/frontend/images/combat/crits/critico-minore.png", audio: "/static/frontend/audio/combat/critico-minore.m4a" },
  normal: { image: "/static/frontend/images/combat/crits/critico-normale.png", audio: "/static/frontend/audio/combat/critico-normale.m4a" },
  major: { image: "/static/frontend/images/combat/crits/critico-maggiore.png", audio: "/static/frontend/audio/combat/critico-maggiore.m4a" },
};

export type CriticalHitTrigger = { level: string; token: number };

/** Mostra un'immagine a schermo intero e riproduce un suono quando arriva un nuovo critico. */
export function CriticalHitOverlay({ trigger }: { trigger: CriticalHitTrigger | null }) {
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    if (!trigger) return;
    const assets = CRIT_ASSETS[trigger.level];
    if (!assets) return;
    setImageUrl(assets.image);
    const audio = audioRef.current;
    if (audio) {
      audio.src = assets.audio;
      audio.currentTime = 0;
      void audio.play().catch(() => {});
    }
    const timeout = window.setTimeout(() => setImageUrl(null), 3000);
    return () => window.clearTimeout(timeout);
  }, [trigger?.token]);

  return <>
    <audio ref={audioRef} hidden />
    {imageUrl && <div className="ca-critical-overlay" role="presentation"><img src={imageUrl} alt="" /></div>}
  </>;
}
