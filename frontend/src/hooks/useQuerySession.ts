// POST /api/query, then the SSE answer stream; tokens go through the SectionSplitter port.
import { useCallback, useEffect, useReducer, useRef } from "react";
import { ApiError, getSources, postQuery, type RequestedLanguage, streamUrl } from "../api/client";
import type {
  DonePayload,
  ErrorPayload,
  NullPayload,
  StatusPayload,
  TokenPayload,
  TranslatedPayload,
} from "../api/types";
import { SectionSplitter } from "../lib/sectionSplitter";
import { initialSession, type SessionAction, type SessionError, sessionReducer, type SessionState } from "./session";

export const MAX_RECONNECTS = 2;
export const RECONNECT_DELAY_MS = 1000;

interface Run {
  stopped: boolean;
  source: EventSource | null;
  timer: ReturnType<typeof setTimeout> | undefined;
  abort: AbortController;
}

type Dispatch = (action: SessionAction) => void;

const payload = <T>(event: Event): T => JSON.parse((event as MessageEvent<string>).data) as T;

/** ApiError -> http error; anything else (network failure) -> disconnected. */
function toSessionError(error: unknown): SessionError {
  if (error instanceof ApiError)
    return { kind: "http", status: error.status, code: error.code, message: error.message };
  return { kind: "disconnected" };
}

/** Open (or reopen) the answer stream; each connection starts a fresh splitter since the server replays whole. */
function connect(run: Run, sessionId: string, attempt: number, dispatch: Dispatch): void {
  const source = new EventSource(streamUrl(sessionId));
  const splitter = new SectionSplitter();
  run.source = source;
  dispatch({ type: "connect" });
  const on = (name: string, handle: (event: Event) => void) =>
    source.addEventListener(name, (event) => {
      if (!run.stopped && run.source === source) handle(event);
    });
  const finish = (action: SessionAction) => {
    source.close();
    dispatch(action);
  };

  on("status", (event) => dispatch({ type: "status", payload: payload<StatusPayload>(event), at: Date.now() }));
  on("token", (event) => {
    const deltas = splitter.feed(payload<TokenPayload>(event).text);
    const latest = deltas.length ? deltas[deltas.length - 1].section : null;
    dispatch({ type: "token", sections: splitter.snapshot(), latest, seen: [...splitter.seen], at: Date.now() });
  });
  on("translated", (event) => dispatch({ type: "translated", sections: payload<TranslatedPayload>(event).sections }));
  on("done", (event) => {
    const { rights, steps, letter } = splitter.finalize();
    finish({ type: "done", payload: payload<DonePayload>(event), sections: { rights, steps, letter } });
  });
  on("null", (event) => finish({ type: "null", payload: payload<NullPayload>(event) }));
  // A server "error" event carries JSON data; a bare Event is the connection failing (EventSource would retry itself).
  on("error", (event) => {
    source.close();
    if (event instanceof MessageEvent && typeof event.data === "string") {
      dispatch({ type: "failed", error: { kind: "stream", ...payload<ErrorPayload>(event) } });
    } else if (attempt >= MAX_RECONNECTS) {
      dispatch({ type: "failed", error: { kind: "disconnected" } });
    } else {
      dispatch({ type: "reconnecting" });
      run.timer = setTimeout(() => connect(run, sessionId, attempt + 1, dispatch), RECONNECT_DELAY_MS * (attempt + 1));
    }
  });
}

/** One question at a time: submit, retry (same question, new session) and reset; cleans up on unmount. */
export function useQuerySession(): {
  state: SessionState;
  submit: (question: string, language: RequestedLanguage) => Promise<void>;
  retry: () => void;
  reset: () => void;
} {
  const [state, dispatch] = useReducer(sessionReducer, initialSession);
  const current = useRef<Run | null>(null);

  const stop = useCallback(() => {
    const run = current.current;
    if (!run) return;
    run.stopped = true;
    run.source?.close();
    clearTimeout(run.timer);
    run.abort.abort();
    current.current = null;
  }, []);

  useEffect(() => stop, [stop]);

  const submit = useCallback(
    async (question: string, language: RequestedLanguage) => {
      stop();
      const run: Run = { stopped: false, source: null, timer: undefined, abort: new AbortController() };
      current.current = run;
      const guarded: Dispatch = (action) => {
        if (!run.stopped) dispatch(action);
      };
      guarded({ type: "submit", question, requested: language });
      try {
        const response = await postQuery(question, language, run.abort.signal);
        guarded({ type: "queried", response });
        if (run.stopped) return;
        if (!response.null_response) {
          getSources(response.session_id, run.abort.signal).then(
            (chunks) => guarded({ type: "sources", chunks }),
            () => guarded({ type: "sourcesFailed" }),
          );
        }
        connect(run, response.session_id, 0, guarded);
      } catch (error) {
        guarded({ type: "failed", error: toSessionError(error) });
      }
    },
    [stop],
  );

  const { question, requested } = state;
  const retry = useCallback(() => void submit(question, requested), [submit, question, requested]);
  const reset = useCallback(() => {
    stop();
    dispatch({ type: "reset" });
  }, [stop]);

  return { state, submit, retry, reset };
}
