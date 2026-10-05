// A saved turn shown with the same answer card as a live one: it becomes a finished session state.
import type { Turn } from "../api/library";
import { initialSession, type SessionState } from "../hooks/session";
import { SECTIONS } from "./sectionSplitter";

/** The finished (or null) session state of a saved turn; disclaimer is in the reader's interface language. */
export function turnState(turn: Turn, disclaimer: string): SessionState {
  return {
    ...initialSession,
    phase: turn.null_response ? "null" : "done",
    question: turn.question,
    sessionId: turn.session_id,
    language: turn.lang,
    draft: turn.sections,
    seen: SECTIONS.filter((section) => turn.sections[section]),
    done: {
      warnings: turn.warnings,
      citation_check: turn.citation_check,
      format_ok: turn.format_ok,
      truncated_chunks: turn.sources.filter((s) => s.truncated).map((s) => s.chunk_id),
      untranslated: turn.untranslated,
      disclaimer,
    },
    sources: turn.sources,
  };
}
