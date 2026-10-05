// Shapes of the backend HTTP and SSE contract (docs/DESIGN.md "SSE contract", DEVIATIONS D16).
import type { Section, Sections } from "../lib/sectionSplitter";

export type UiLanguage = "en" | "sw";
export type UnitType = "section" | "article" | "schedule";

export interface QueryResponse {
  session_id: string;
  null_response: boolean;
  acts: string[];
  language: UiLanguage;
  /** Where the turn is saved (signed in with history on); null for guests and private mode. */
  conversation_id?: string | null;
  /** The answer keeps generating if this page goes away (signed in). */
  background?: boolean;
}

export interface SourceChunk {
  chunk_id: string;
  act: string;
  unit_type: UnitType;
  section_num: string;
  section_title: string;
  part: string;
  page: number;
  text: string;
  truncated: boolean;
  rank: number;
}

export interface SourcesResponse {
  session_id: string;
  chunks: SourceChunk[];
}

export interface CitationCheck {
  verified: string[];
  unmatched: string[];
}

export interface StatusPayload {
  stage: "retrieved" | "queued" | "generating" | "translating";
  chunks?: number;
  position?: number;
}

export interface TokenPayload {
  text: string;
  deltas: { section: Section; text: string }[];
}

export interface TranslatedPayload {
  sections: Sections;
}

export interface DonePayload {
  warnings: string[];
  citation_check: CitationCheck;
  format_ok: boolean;
  truncated_chunks: string[];
  untranslated: string[];
  disclaimer: string;
}

export interface NullPayload {
  message: string;
  disclaimer: string;
}

export interface ErrorPayload {
  code: string;
  message: string;
}

export interface Health {
  status: "ok" | "degraded";
  ollama: boolean;
  model_present: boolean;
  indexes_loaded: boolean;
  models_warm: boolean;
  error?: ErrorPayload;
}
