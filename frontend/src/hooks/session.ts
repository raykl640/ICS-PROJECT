// State machine of one question: idle -> searching -> retrieved -> [queued] -> generating -> [translating] -> done,
// or -> null (fallback) / error. A new stream connection resets the answer, because the server replays it whole.
import type { RequestedLanguage } from "../api/client";
import type { DonePayload, NullPayload, QueryResponse, SourceChunk, StatusPayload, UiLanguage } from "../api/types";
import { emptySections, type Section, type Sections } from "../lib/sectionSplitter";

export type Phase =
  "idle" | "searching" | "retrieved" | "queued" | "generating" | "translating" | "done" | "null" | "error";

export type SessionError =
  | { kind: "http"; status: number; code: string; message: string }
  | { kind: "stream"; code: string; message: string }
  | { kind: "disconnected" };

export interface SessionState {
  phase: Phase;
  question: string;
  requested: RequestedLanguage;
  sessionId: string | null;
  language: UiLanguage | null;
  chunkCount: number | null;
  queuePosition: number | null;
  draft: Sections;
  translated: Sections | null;
  latest: Section | null;
  seen: Section[];
  done: DonePayload | null;
  nullInfo: NullPayload | null;
  error: SessionError | null;
  sources: SourceChunk[] | null;
  sourcesFailed: boolean;
  reconnecting: boolean;
}

export type SessionAction =
  | { type: "submit"; question: string; requested: RequestedLanguage }
  | { type: "queried"; response: QueryResponse }
  | { type: "connect" }
  | { type: "status"; payload: StatusPayload }
  | { type: "token"; sections: Sections; latest: Section | null; seen: Section[] }
  | { type: "translated"; sections: Sections }
  | { type: "done"; payload: DonePayload; sections: Sections }
  | { type: "null"; payload: NullPayload }
  | { type: "failed"; error: SessionError }
  | { type: "reconnecting" }
  | { type: "sources"; chunks: SourceChunk[] }
  | { type: "sourcesFailed" }
  | { type: "reset" };

export const initialSession: SessionState = {
  phase: "idle",
  question: "",
  requested: "en",
  sessionId: null,
  language: null,
  chunkCount: null,
  queuePosition: null,
  draft: emptySections(),
  translated: null,
  latest: null,
  seen: [],
  done: null,
  nullInfo: null,
  error: null,
  sources: null,
  sourcesFailed: false,
  reconnecting: false,
};

const STAGE_PHASE: Record<StatusPayload["stage"], Phase> = {
  retrieved: "retrieved",
  queued: "queued",
  generating: "generating",
  translating: "translating",
};

/** Next state for an action. */
export function sessionReducer(state: SessionState, action: SessionAction): SessionState {
  switch (action.type) {
    case "submit":
      return { ...initialSession, phase: "searching", question: action.question, requested: action.requested };
    case "queried":
      return {
        ...state,
        phase: "retrieved",
        sessionId: action.response.session_id,
        language: action.response.language,
        sources: action.response.null_response ? [] : null,
      };
    case "connect":
      return { ...state, draft: emptySections(), translated: null, latest: null, seen: [], done: null };
    case "status":
      return {
        ...state,
        phase: STAGE_PHASE[action.payload.stage],
        chunkCount: action.payload.chunks ?? state.chunkCount,
        queuePosition: action.payload.stage === "queued" ? (action.payload.position ?? null) : null,
        reconnecting: false,
      };
    case "token":
      return {
        ...state,
        phase: state.phase === "translating" ? state.phase : "generating",
        draft: action.sections,
        latest: action.latest ?? state.latest,
        seen: action.seen,
        reconnecting: false,
      };
    case "translated":
      return { ...state, translated: action.sections };
    case "done":
      return { ...state, phase: "done", done: action.payload, draft: action.sections, reconnecting: false };
    case "null":
      return { ...state, phase: "null", nullInfo: action.payload, sources: [], reconnecting: false };
    case "failed":
      return { ...state, phase: "error", error: action.error, reconnecting: false };
    case "reconnecting":
      return { ...state, reconnecting: true };
    case "sources":
      return { ...state, sources: action.chunks };
    case "sourcesFailed":
      return { ...state, sourcesFailed: true };
    case "reset":
      return initialSession;
  }
}

/** True while an answer is still on its way. */
export const isBusy = (phase: Phase): boolean =>
  phase === "searching" ||
  phase === "retrieved" ||
  phase === "queued" ||
  phase === "generating" ||
  phase === "translating";

const ENGINE_CODES = new Set(["llm_unavailable", "model_not_loaded", "not_ready"]);

/** True if the failure points at the backend's readiness (worth re-checking /api/health). */
export const isEngineError = (error: SessionError | null): boolean =>
  error !== null && error.kind !== "disconnected" && ENGINE_CODES.has(error.code);
