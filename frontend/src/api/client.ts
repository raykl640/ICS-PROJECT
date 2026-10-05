// Thin fetch wrappers for the same-origin API; every non-2xx body is {"error": {code, message}}.
import type { Health, QueryResponse, SourceChunk, SourcesResponse, UiLanguage } from "./types";

export type RequestedLanguage = UiLanguage | "auto";
export type Rating = "up" | "down";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  /** Seconds from a Retry-After header (429 and 503), if any. */
  readonly retryAfter: number | null;

  constructor(status: number, code: string, message: string, retryAfter: number | null = null) {
    super(message);
    this.status = status;
    this.code = code;
    this.retryAfter = retryAfter;
  }
}

/** Mutating requests carry X-Haki: 1; the backend refuses them otherwise (cross-site request defence). */
export const JSON_HEADERS = { "Content-Type": "application/json", "X-Haki": "1" };

/** Parse a JSON response, raising ApiError with the backend's error code on non-2xx. */
export async function parse<T>(response: Response): Promise<T> {
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const error = (body as { error?: { code?: string; message?: string } } | null)?.error;
    const retry = Number(response.headers.get("Retry-After"));
    throw new ApiError(
      response.status,
      error?.code ?? "http_error",
      error?.message ?? response.statusText,
      Number.isFinite(retry) && retry > 0 ? retry : null,
    );
  }
  return body as T;
}

/** POST /api/query: retrieve context and open a session. */
export async function postQuery(
  question: string,
  language: RequestedLanguage,
  signal?: AbortSignal,
): Promise<QueryResponse> {
  const init = { method: "POST", headers: JSON_HEADERS, body: JSON.stringify({ question, language }), signal };
  return parse<QueryResponse>(await fetch("/api/query", init));
}

/** GET /api/sources/{id}: the retrieved chunks, verbatim, in rank order. */
export async function getSources(sessionId: string, signal?: AbortSignal): Promise<SourceChunk[]> {
  const response = await fetch(`/api/sources/${encodeURIComponent(sessionId)}`, { signal });
  return (await parse<SourcesResponse>(response)).chunks;
}

/** GET /api/health: readiness; a 503 still carries the health body. */
export async function getHealth(signal?: AbortSignal): Promise<Health> {
  const response = await fetch("/api/health", { signal });
  return (await response.json()) as Health;
}

/** POST /api/feedback: true if recorded, false if this session already had feedback. */
export async function postFeedback(sessionId: string, rating: Rating, comment: string): Promise<boolean> {
  const init = {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({ session_id: sessionId, rating, comment }),
  };
  return (await parse<{ recorded: boolean }>(await fetch("/api/feedback", init))).recorded;
}

/** URL of the SSE answer stream. */
export const streamUrl = (sessionId: string): string => `/api/stream/${encodeURIComponent(sessionId)}`;

/** URL of the letter export. */
export const letterUrl = (sessionId: string, format: "txt" | "docx"): string =>
  `/api/letter/${encodeURIComponent(sessionId)}?format=${format}`;
