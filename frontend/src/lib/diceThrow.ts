import { useEffect, useRef, type RefObject } from "react";

export const THROW_RESTITUTION = 2 / 3;
export const FIXED_STEP_SECONDS = 1 / 60;
export const MAX_FRAME_SECONDS = 0.05;

const DRAG_PER_STEP = 0.995;
const STOP_SPEED_RATIO = 0.06;
const FACE_STRIDE = 70;
const MIN_FACE_INTERVAL_MS = 45;
const MAX_FACE_INTERVAL_MS = 320;
const SETTLE_DURATION_MS = 120;

export type ThrowBounds = {
  maxX: number;
  maxY: number;
};

export type ThrowState = {
  x: number;
  y: number;
  velocityX: number;
  velocityY: number;
  rotation: number;
  angularVelocity: number;
  stopSpeed: number;
  bounceCount: number;
  randomSeed: number;
  stopped: boolean;
};

type DiceThrowOptions = {
  enabled: boolean;
  boardRef: RefObject<HTMLElement | null>;
  dieRef: RefObject<HTMLElement | null>;
  sides: number;
  animationDisabled?: boolean;
  onFaceChange: (face: number) => void;
  onSettle: () => void;
};

function nextRandom(seed: number) {
  let value = seed | 0;
  value ^= value << 13;
  value ^= value >>> 17;
  value ^= value << 5;
  return { seed: value >>> 0, value: (value >>> 0) / 0x1_0000_0000 };
}

function rotateVelocity(x: number, y: number, radians: number) {
  const cosine = Math.cos(radians);
  const sine = Math.sin(radians);
  return {
    x: x * cosine - y * sine,
    y: x * sine + y * cosine,
  };
}

function speedOf(state: ThrowState) {
  return Math.hypot(state.velocityX, state.velocityY);
}

/**
 * Advances one deterministic arcade-physics step. Coordinates are offsets from
 * the board centre, so the same state model works for every dice surface.
 */
export function stepThrow(state: ThrowState, dt: number, bounds: ThrowBounds): ThrowState {
  if (state.stopped || dt <= 0) return state;

  let x = state.x + state.velocityX * dt;
  let y = state.y + state.velocityY * dt;
  let velocityX = state.velocityX;
  let velocityY = state.velocityY;
  let angularVelocity = state.angularVelocity;
  let bounceCount = state.bounceCount;
  let randomSeed = state.randomSeed;

  const bounce = (axis: "x" | "y") => {
    if (axis === "x") velocityX *= -1;
    else velocityY *= -1;
    velocityX *= THROW_RESTITUTION;
    velocityY *= THROW_RESTITUTION;
    angularVelocity *= THROW_RESTITUTION;
    bounceCount += 1;

    const random = nextRandom(randomSeed);
    randomSeed = random.seed;
    const jitter = ((random.value * 2) - 1) * 0.08;
    const rotated = rotateVelocity(velocityX, velocityY, jitter);
    velocityX = rotated.x;
    velocityY = rotated.y;
  };

  if (x < -bounds.maxX || x > bounds.maxX) {
    x = Math.max(-bounds.maxX, Math.min(bounds.maxX, x));
    bounce("x");
  }
  if (y < -bounds.maxY || y > bounds.maxY) {
    y = Math.max(-bounds.maxY, Math.min(bounds.maxY, y));
    bounce("y");
  }

  const drag = Math.pow(DRAG_PER_STEP, dt / FIXED_STEP_SECONDS);
  velocityX *= drag;
  velocityY *= drag;
  angularVelocity *= drag;
  const stopped = Math.hypot(velocityX, velocityY) < state.stopSpeed;

  return {
    x,
    y,
    velocityX: stopped ? 0 : velocityX,
    velocityY: stopped ? 0 : velocityY,
    rotation: state.rotation + angularVelocity * dt,
    angularVelocity: stopped ? 0 : angularVelocity,
    stopSpeed: state.stopSpeed,
    bounceCount,
    randomSeed,
    stopped,
  };
}

function measureBounds(board: HTMLElement, die: HTMLElement): ThrowBounds {
  const boardRect = board.getBoundingClientRect();
  const dieRect = die.getBoundingClientRect();
  return {
    maxX: Math.max(0, (boardRect.width - dieRect.width) / 2),
    maxY: Math.max(0, (boardRect.height - dieRect.height) / 2),
  };
}

function createThrow(bounds: ThrowBounds): ThrowState {
  const diagonal = Math.max(1, Math.hypot(bounds.maxX * 2, bounds.maxY * 2));
  const launchSpeed = diagonal * (1.6 + Math.random());
  const angle = ((Math.random() * 120) - 60) * Math.PI / 180;
  const spinDirection = Math.random() < 0.5 ? -1 : 1;

  return {
    x: (Math.random() * 0.8 - 0.4) * bounds.maxX,
    y: bounds.maxY,
    velocityX: Math.sin(angle) * launchSpeed,
    velocityY: -Math.cos(angle) * launchSpeed,
    rotation: (Math.random() * 90) - 45,
    angularVelocity: launchSpeed * (0.55 + Math.random() * 0.35) * spinDirection,
    stopSpeed: launchSpeed * STOP_SPEED_RATIO,
    bounceCount: 0,
    randomSeed: Math.max(1, Math.floor(Math.random() * 0xffff_ffff)),
    stopped: false,
  };
}

function randomFace(sides: number, previous: number) {
  if (sides <= 1) return 1;
  const candidate = Math.floor(Math.random() * (sides - 1)) + 1;
  return candidate >= previous ? candidate + 1 : candidate;
}

export function useDiceThrow({
  enabled,
  boardRef,
  dieRef,
  sides,
  animationDisabled = false,
  onFaceChange,
  onSettle,
}: DiceThrowOptions) {
  const faceCallback = useRef(onFaceChange);
  const settleCallback = useRef(onSettle);

  useEffect(() => { faceCallback.current = onFaceChange; }, [onFaceChange]);
  useEffect(() => { settleCallback.current = onSettle; }, [onSettle]);

  useEffect(() => {
    if (!enabled) return;

    const board = boardRef.current;
    const die = dieRef.current;
    if (!board || !die) {
      settleCallback.current();
      return;
    }

    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const documentReducedMotion = document.documentElement.dataset.reducedMotion === "true";
    if (animationDisabled || prefersReducedMotion || documentReducedMotion) {
      die.style.transform = "";
      settleCallback.current();
      return;
    }

    let bounds = measureBounds(board, die);
    let state = createThrow(bounds);
    let animationFrame = 0;
    let previousTime = performance.now();
    let accumulator = 0;
    let travelledSinceFace = 0;
    let timeSinceFace = MAX_FACE_INTERVAL_MS;
    let lastFace = randomFace(sides, 0);
    let settleStartedAt: number | null = null;
    let settleFromX = 0;
    let settleFromY = 0;
    let settleFromRotation = 0;
    let settleRotation = 0;
    let finished = false;

    faceCallback.current(lastFace);
    die.style.willChange = "transform";
    die.style.transform = `translate3d(${state.x}px, ${state.y}px, 0) rotate(${state.rotation}deg)`;

    const updateBounds = () => {
      bounds = measureBounds(board, die);
      state = {
        ...state,
        x: Math.max(-bounds.maxX, Math.min(bounds.maxX, state.x)),
        y: Math.max(-bounds.maxY, Math.min(bounds.maxY, state.y)),
      };
    };
    const resizeObserver = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(updateBounds);
    resizeObserver?.observe(board);
    resizeObserver?.observe(die);
    window.addEventListener("resize", updateBounds);

    const finish = () => {
      if (finished) return;
      finished = true;
      die.style.willChange = "";
      settleCallback.current();
    };

    const frame = (now: number) => {
      const frameSeconds = Math.min(MAX_FRAME_SECONDS, Math.max(0, (now - previousTime) / 1000));
      previousTime = now;

      if (settleStartedAt !== null) {
        const progress = Math.min(1, (now - settleStartedAt) / SETTLE_DURATION_MS);
        const eased = 1 - Math.pow(1 - progress, 3);
        const rotation = settleFromRotation + (settleRotation - settleFromRotation) * eased;
        die.style.transform = `translate3d(${settleFromX}px, ${settleFromY}px, 0) rotate(${rotation}deg)`;
        if (progress >= 1) finish();
        else animationFrame = window.requestAnimationFrame(frame);
        return;
      }

      accumulator += frameSeconds;
      timeSinceFace += frameSeconds * 1000;
      while (accumulator >= FIXED_STEP_SECONDS) {
        const previousX = state.x;
        const previousY = state.y;
        state = stepThrow(state, FIXED_STEP_SECONDS, bounds);
        travelledSinceFace += Math.hypot(state.x - previousX, state.y - previousY);
        accumulator -= FIXED_STEP_SECONDS;
      }

      if (
        timeSinceFace >= MIN_FACE_INTERVAL_MS
        && (travelledSinceFace >= FACE_STRIDE || timeSinceFace >= MAX_FACE_INTERVAL_MS)
      ) {
        lastFace = randomFace(sides, lastFace);
        faceCallback.current(lastFace);
        travelledSinceFace %= FACE_STRIDE;
        timeSinceFace = 0;
      }

      die.style.transform = `translate3d(${state.x}px, ${state.y}px, 0) rotate(${state.rotation}deg)`;
      if (state.stopped) {
        settleStartedAt = now;
        settleFromX = state.x;
        settleFromY = state.y;
        settleFromRotation = state.rotation;
        const rotationStep = sides === 6 ? 90 : 360 / Math.max(1, sides);
        settleRotation = Math.round(state.rotation / rotationStep) * rotationStep;
      }
      animationFrame = window.requestAnimationFrame(frame);
    };

    animationFrame = window.requestAnimationFrame(frame);
    return () => {
      finished = true;
      window.cancelAnimationFrame(animationFrame);
      resizeObserver?.disconnect();
      window.removeEventListener("resize", updateBounds);
      die.style.willChange = "";
    };
  }, [animationDisabled, boardRef, dieRef, enabled, sides]);
}
