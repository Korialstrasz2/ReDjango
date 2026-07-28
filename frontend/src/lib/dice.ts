export function playRollSound() {
  const AudioContextClass = window.AudioContext;
  if (!AudioContextClass) return;
  try {
    const context = new AudioContextClass();
    const oscillator = context.createOscillator();
    const gain = context.createGain();
    oscillator.type = "triangle";
    oscillator.frequency.setValueAtTime(132, context.currentTime);
    oscillator.frequency.exponentialRampToValueAtTime(54, context.currentTime + .22);
    gain.gain.setValueAtTime(.06, context.currentTime);
    gain.gain.exponentialRampToValueAtTime(.001, context.currentTime + .24);
    oscillator.connect(gain).connect(context.destination);
    oscillator.start();
    oscillator.stop(context.currentTime + .25);
    oscillator.addEventListener("ended", () => void context.close());
  } catch {
    // Audio can be unavailable when the browser blocks a newly-created context.
  }
}
