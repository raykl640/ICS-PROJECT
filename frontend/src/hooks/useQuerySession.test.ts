import { act, renderHook, waitFor } from "@testing-library/react";
import { ANSWER, DONE, QUERY_OK, SOURCES } from "../test/fixtures";
import { stubFetch } from "../test/http";
import { MockEventSource } from "../test/mockEventSource";
import { MAX_RECONNECTS, RECONNECT_DELAY_MS, useQuerySession } from "./useQuerySession";

beforeEach(() => {
  MockEventSource.reset();
  vi.stubGlobal("EventSource", MockEventSource);
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

async function started(queryResponse: object = QUERY_OK) {
  const calls = stubFetch({
    "POST /api/query": { body: queryResponse },
    "GET /api/sources/s1": { body: { session_id: "s1", chunks: SOURCES } },
  });
  const hook = renderHook(() => useQuerySession());
  await act(() => hook.result.current.submit("Why was I fired?", "en"));
  return { ...hook, calls };
}

test("queued -> generating -> done, tokens split into sections and sources loaded", async () => {
  const { result, calls } = await started();
  expect(calls[0]).toEqual({
    method: "POST",
    url: "/api/query",
    body: { question: "Why was I fired?", language: "en" },
  });
  const stream = MockEventSource.last;
  expect(stream.url).toBe("/api/stream/s1");
  expect(result.current.state.phase).toBe("retrieved");

  act(() => stream.emit("status", { stage: "retrieved", chunks: 2 }));
  act(() => stream.emit("status", { stage: "queued", position: 2 }));
  expect(result.current.state).toMatchObject({ phase: "queued", queuePosition: 2, chunkCount: 2 });

  act(() => stream.emit("status", { stage: "generating" }));
  act(() => stream.emit("token", { text: ANSWER.slice(0, 40), deltas: [] }));
  expect(result.current.state.phase).toBe("generating");
  expect(result.current.state.latest).toBe("rights");
  act(() => stream.emit("token", { text: ANSWER.slice(40), deltas: [] }));
  expect(result.current.state.latest).toBe("letter");
  expect(result.current.state.seen).toEqual(["rights", "steps", "letter"]);

  act(() => stream.emit("done", DONE));
  const { state } = result.current;
  expect(state.phase).toBe("done");
  expect(state.done).toEqual(DONE);
  expect(state.draft.steps).toBe("1. Write down the dates.");
  expect(state).toMatchObject({ connections: 1, tokens: 2 });
  expect(state.generatingAt).not.toBeNull();
  expect(state.lastTokenAt! >= state.firstTokenAt!).toBe(true);
  expect(stream.closed).toBe(true);
  await waitFor(() => expect(result.current.state.sources).toEqual(SOURCES));
});

test("a null session shows the server's fallback and never fetches sources", async () => {
  const { result, calls } = await started({ ...QUERY_OK, null_response: true });
  act(() => MockEventSource.last.emit("null", { message: "No provision.", disclaimer: "Not advice." }));
  expect(result.current.state).toMatchObject({ phase: "null", nullInfo: { message: "No provision." }, sources: [] });
  expect(calls.map((c) => c.url)).toEqual(["/api/query"]);
  expect(MockEventSource.last.closed).toBe(true);
});

test("a server error event ends the session with its code", async () => {
  const { result } = await started();
  act(() => MockEventSource.last.emit("error", { code: "llm_unavailable", message: "Ollama is down." }));
  expect(result.current.state.phase).toBe("error");
  expect(result.current.state.error).toEqual({ kind: "stream", code: "llm_unavailable", message: "Ollama is down." });
  expect(MockEventSource.instances).toHaveLength(1);
});

test("translated replaces the English draft for Kiswahili sessions", async () => {
  const { result } = await started({ ...QUERY_OK, language: "sw" });
  const stream = MockEventSource.last;
  act(() => stream.emit("token", { text: ANSWER, deltas: [] }));
  act(() => stream.emit("status", { stage: "translating" }));
  expect(result.current.state).toMatchObject({ phase: "translating", language: "sw", translated: null });
  const sections = { rights: "Haki.", steps: "1. Andika.", letter: "Mpendwa," };
  act(() => stream.emit("translated", { sections }));
  act(() => stream.emit("done", DONE));
  expect(result.current.state.translated).toEqual(sections);
  expect(result.current.state.phase).toBe("done");
});

test("a dropped connection reconnects and the replay replaces the partial answer", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const { result } = await started();
  const first = MockEventSource.last;
  act(() => first.emit("token", { text: "## RIGHTS EXPLANATION\nPartial", deltas: [] }));
  act(() => first.fail());
  expect(first.closed).toBe(true);
  expect(result.current.state.reconnecting).toBe(true);

  act(() => vi.advanceTimersByTime(RECONNECT_DELAY_MS));
  const second = MockEventSource.last;
  expect(second).not.toBe(first);
  act(() => second.emit("token", { text: ANSWER, deltas: [] }));
  act(() => second.emit("done", DONE));
  expect(result.current.state.draft.rights).toBe("Your employer must give a reason (Sample Employment Act, s. 4).");
  expect(result.current.state.reconnecting).toBe(false);
  // The replay restarts the count, and a second connection marks the timing as unusable for the ETA.
  expect(result.current.state).toMatchObject({ connections: 2, tokens: 1 });
});

test("after the last reconnect fails the session is disconnected; retry asks again", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const { result, calls } = await started();
  for (let attempt = 0; attempt <= MAX_RECONNECTS; attempt++) {
    act(() => MockEventSource.last.fail());
    act(() => vi.advanceTimersByTime(RECONNECT_DELAY_MS * (attempt + 1)));
  }
  expect(MockEventSource.instances).toHaveLength(MAX_RECONNECTS + 1);
  expect(result.current.state.error).toEqual({ kind: "disconnected" });

  await act(async () => result.current.retry());
  expect(calls.filter((c) => c.url === "/api/query")).toHaveLength(2);
  expect(result.current.state.phase).toBe("retrieved");
});

test("an HTTP error from /api/query is kept with its code", async () => {
  stubFetch({ "POST /api/query": { status: 429, body: { error: { code: "rate_limited", message: "Slow down." } } } });
  const { result } = renderHook(() => useQuerySession());
  await act(() => result.current.submit("Why?", "en"));
  expect(result.current.state.error).toEqual({
    kind: "http",
    status: 429,
    code: "rate_limited",
    message: "Slow down.",
  });
  expect(MockEventSource.instances).toHaveLength(0);
});

test("events from a replaced session are ignored", async () => {
  const { result } = await started();
  const old = MockEventSource.last;
  await act(() => result.current.submit("Another question?", "en"));
  act(() => old.emit("done", DONE));
  expect(old.closed).toBe(true);
  expect(result.current.state.phase).toBe("retrieved");
  expect(result.current.state.question).toBe("Another question?");
});
