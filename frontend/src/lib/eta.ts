// Honest ETA for a CPU-bound answer, learned from answers measured in this browser (localStorage, numbers only).
// Total time ≈ wait for the first token (model load + prompt reading) + answer tokens ÷ tokens per second.
import type { SessionState } from "../hooks/session";

export const SPEED_KEY = "hakiai.speed";
/** Weight of the newest answer in the running averages. */
const NEW_WEIGHT = 0.5;
/** Tokens after which the current answer's own rate replaces the stored one. */
const OWN_RATE_AFTER = 20;

export interface Speed {
  firstTokenSeconds: number;
  tokensPerSecond: number;
  answerTokens: number;
}

const valid = (n: unknown): n is number => typeof n === "number" && Number.isFinite(n) && n > 0;

/** The stored averages, or null before the first measured answer (or if storage is unavailable). */
export function loadSpeed(): Speed | null {
  try {
    const raw = JSON.parse(localStorage.getItem(SPEED_KEY) ?? "null") as Partial<Speed> | null;
    if (raw && valid(raw.firstTokenSeconds) && valid(raw.tokensPerSecond) && valid(raw.answerTokens)) {
      return {
        firstTokenSeconds: raw.firstTokenSeconds,
        tokensPerSecond: raw.tokensPerSecond,
        answerTokens: raw.answerTokens,
      };
    }
  } catch {
    // Unreadable: start over.
  }
  return null;
}

/** One finished answer's timing, or null if it cannot serve as a sample (replayed, no tokens, no clock). */
export function measure(state: SessionState): Speed | null {
  const { connections, tokens, generatingAt, firstTokenAt, lastTokenAt } = state;
  if (connections !== 1 || tokens < 2 || generatingAt === null || firstTokenAt === null || lastTokenAt === null) {
    return null;
  }
  const writing = (lastTokenAt - firstTokenAt) / 1000;
  if (writing <= 0) return null;
  return {
    firstTokenSeconds: Math.max((firstTokenAt - generatingAt) / 1000, 0.1),
    tokensPerSecond: tokens / writing,
    answerTokens: tokens,
  };
}

/** Fold a sample into the stored averages. */
export function recordSpeed(sample: Speed): void {
  const old = loadSpeed();
  const mix = (key: keyof Speed) => (old ? old[key] * (1 - NEW_WEIGHT) + sample[key] * NEW_WEIGHT : sample[key]);
  try {
    localStorage.setItem(
      SPEED_KEY,
      JSON.stringify({
        firstTokenSeconds: mix("firstTokenSeconds"),
        tokensPerSecond: mix("tokensPerSecond"),
        answerTokens: mix("answerTokens"),
      }),
    );
  } catch {
    // Storage blocked: no estimate next time.
  }
}

/** Seconds left for the answer being written, or null when there is nothing honest to say. */
export function etaSeconds(speed: Speed | null, state: SessionState, now: number): number | null {
  if (!speed || state.generatingAt === null) return null;
  const { tokens, firstTokenAt, lastTokenAt } = state;
  if (tokens === 0 || firstTokenAt === null || lastTokenAt === null) {
    const waited = (now - state.generatingAt) / 1000;
    return Math.max(speed.firstTokenSeconds - waited, 0) + speed.answerTokens / speed.tokensPerSecond;
  }
  const writing = (lastTokenAt - firstTokenAt) / 1000;
  const rate = tokens >= OWN_RATE_AFTER && writing > 0 ? tokens / writing : speed.tokensPerSecond;
  const left = (speed.answerTokens - tokens) / rate;
  return left > 0 ? left : null;
}

/** Whole minutes and seconds of a duration. */
export const splitDuration = (seconds: number): { m: number; s: number } => {
  const total = Math.max(Math.round(seconds), 0);
  return { m: Math.floor(total / 60), s: total % 60 };
};
