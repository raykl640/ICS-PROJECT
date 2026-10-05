import { initialSession, type SessionState } from "../hooks/session";
import { etaSeconds, loadSpeed, measure, recordSpeed, SPEED_KEY, splitDuration } from "./eta";

const T0 = 1_000_000;
const written = (fields: Partial<SessionState>): SessionState => ({
  ...initialSession,
  phase: "done",
  connections: 1,
  tokens: 400,
  generatingAt: T0,
  firstTokenAt: T0 + 60_000,
  lastTokenAt: T0 + 140_000,
  ...fields,
});

afterEach(() => localStorage.clear());

test("a clean answer is measured; replays and empty answers are not samples", () => {
  expect(measure(written({}))).toEqual({ firstTokenSeconds: 60, tokensPerSecond: 5, answerTokens: 400 });
  expect(measure(written({ connections: 2 }))).toBeNull();
  expect(measure(written({ tokens: 0, firstTokenAt: null, lastTokenAt: null }))).toBeNull();
});

test("samples are averaged in storage; junk in storage is ignored", () => {
  expect(loadSpeed()).toBeNull();
  recordSpeed({ firstTokenSeconds: 60, tokensPerSecond: 5, answerTokens: 400 });
  recordSpeed({ firstTokenSeconds: 20, tokensPerSecond: 7, answerTokens: 300 });
  expect(loadSpeed()).toEqual({ firstTokenSeconds: 40, tokensPerSecond: 6, answerTokens: 350 });
  localStorage.setItem(SPEED_KEY, '{"tokensPerSecond": -1}');
  expect(loadSpeed()).toBeNull();
  localStorage.setItem(SPEED_KEY, "not json");
  expect(loadSpeed()).toBeNull();
});

test("the estimate covers the wait for the first token, then follows the answer's own rate", () => {
  const speed = { firstTokenSeconds: 60, tokensPerSecond: 5, answerTokens: 400 };
  const waiting = written({ phase: "generating", tokens: 0, firstTokenAt: null, lastTokenAt: null });
  expect(etaSeconds(speed, waiting, T0 + 20_000)).toBe(40 + 80);
  expect(etaSeconds(speed, waiting, T0 + 90_000)).toBe(80);
  // 10 tokens: too few to trust, so the stored rate is used.
  expect(etaSeconds(speed, written({ phase: "generating", tokens: 10, lastTokenAt: T0 + 61_000 }), T0)).toBe(78);
  // 100 tokens in 10 s: this answer runs at 10 tokens/s.
  expect(etaSeconds(speed, written({ phase: "generating", tokens: 100, lastTokenAt: T0 + 70_000 }), T0)).toBe(30);
  // Longer than expected: no made-up number.
  expect(etaSeconds(speed, written({ phase: "generating", tokens: 500 }), T0)).toBeNull();
  expect(etaSeconds(null, waiting, T0)).toBeNull();
});

test("durations split into minutes and seconds", () => {
  expect(splitDuration(125.4)).toEqual({ m: 2, s: 5 });
  expect(splitDuration(-3)).toEqual({ m: 0, s: 0 });
});
