import { describe, expect, it } from "vitest";

import { FIXED_STEP_SECONDS, stepThrow, THROW_RESTITUTION, type ThrowState } from "./diceThrow";

const bounds = { maxX: 100, maxY: 80 };

function state(overrides: Partial<ThrowState> = {}): ThrowState {
  return {
    x: 0,
    y: 0,
    velocityX: 300,
    velocityY: -500,
    rotation: 0,
    angularVelocity: 400,
    stopSpeed: 10,
    bounceCount: 0,
    randomSeed: 12345,
    stopped: false,
    ...overrides,
  };
}

describe("dice throw physics", () => {
  it("never lets the die leave the measured bounds", () => {
    let current = state({ x: 99, y: -79, velocityX: 1200, velocityY: -900 });
    for (let index = 0; index < 2_000 && !current.stopped; index += 1) {
      current = stepThrow(current, FIXED_STEP_SECONDS, bounds);
      expect(Math.abs(current.x)).toBeLessThanOrEqual(bounds.maxX);
      expect(Math.abs(current.y)).toBeLessThanOrEqual(bounds.maxY);
    }
  });

  it("loses one third of its speed at every wall bounce", () => {
    const initialSpeed = 900;
    let current = state({ x: 99, velocityX: initialSpeed, velocityY: 0, stopSpeed: 1 });

    for (let bounce = 1; bounce <= 5; bounce += 1) {
      current = stepThrow(current, FIXED_STEP_SECONDS, bounds);
      const expected = initialSpeed * Math.pow(THROW_RESTITUTION * 0.995, bounce);
      expect(current.bounceCount).toBe(bounce);
      expect(Math.hypot(current.velocityX, current.velocityY)).toBeCloseTo(expected, 8);
      current = { ...current, x: current.velocityX > 0 ? 99 : -99 };
    }
  });

  it("terminates every representative throw in bounded time", () => {
    const launches = [
      state({ velocityX: -420, velocityY: -900, stopSpeed: 60, randomSeed: 1 }),
      state({ velocityX: 0, velocityY: -1_200, stopSpeed: 72, randomSeed: 22 }),
      state({ velocityX: 650, velocityY: -700, stopSpeed: 57, randomSeed: 333 }),
    ];

    for (const launch of launches) {
      let current = launch;
      let steps = 0;
      while (!current.stopped && steps < 1_200) {
        current = stepThrow(current, FIXED_STEP_SECONDS, bounds);
        steps += 1;
      }
      expect(current.stopped).toBe(true);
      expect(steps).toBeLessThan(1_200);
    }
  });
});
