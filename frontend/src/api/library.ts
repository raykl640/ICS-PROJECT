// The signed-in user's library: conversations, letters, matters, bookmarks, notes (DESIGN_V2 "API v2").
import { JSON_HEADERS, parse } from "./client";
import type { CitationCheck, SourceChunk, UiLanguage } from "./types";
import type { Sections } from "../lib/sectionSplitter";

export interface Page<T> {
  items: T[];
  next_cursor: string | null;
}

export interface Turn {
  id: string;
  idx: number;
  question: string;
  sections: Sections;
  null_response: boolean;
  lang: UiLanguage;
  citation_check: CitationCheck;
  format_ok: boolean;
  warnings: string[];
  untranslated: string[];
  sources: SourceChunk[];
  session_id: string | null;
  created_at: string;
}

export interface ConversationSummary {
  id: string;
  title: string;
  pinned: boolean;
  matter_id: string | null;
  lang: UiLanguage;
  acts: string[];
  turns: number;
  created_at: string;
  updated_at: string;
}

export interface Conversation extends ConversationSummary {
  thread: Turn[];
  running: { session_id: string; question: string; status: string }[];
}

export interface LetterSummary {
  id: string;
  title: string;
  pinned: boolean;
  matter_id: string | null;
  conversation_id: string | null;
  version: number;
  preview: string;
  created_at: string;
  updated_at: string;
}

export interface Letter extends LetterSummary {
  body: string;
}

export interface LetterVersion {
  n: number;
  body: string;
  created_at: string;
}

export interface Matter {
  id: string;
  name: string;
  status: "open" | "closed";
  created_at: string;
  updated_at: string;
}

export interface MatterDetail extends Matter {
  conversations: ConversationSummary[];
  letters: LetterSummary[];
  bookmarks: Bookmark[];
  notes: Note[];
}

export interface Bookmark {
  id: string;
  chunk_id: string;
  act: string;
  unit_type: string;
  section_num: string;
  section_title: string;
  matter_id: string | null;
  created_at: string;
}

export type NoteTarget = "none" | "conversation" | "letter" | "chunk" | "matter";

export interface Note {
  id: string;
  target_kind: NoteTarget;
  target_id: string | null;
  body: string;
  matter_id: string | null;
  created_at: string;
  updated_at: string;
}

/** Fields that can be changed on an item in a list (matter_id null = take it out of its matter). */
export interface ItemPatch {
  title?: string;
  pinned?: boolean;
  matter_id?: string | null;
}

async function send<T>(method: string, path: string, body?: unknown): Promise<T> {
  const init: RequestInit = { method, headers: JSON_HEADERS };
  if (body !== undefined) init.body = JSON.stringify(body);
  return parse<T>(await fetch(path, init));
}

const id = (value: string) => encodeURIComponent(value);
const withQuery = (path: string, query: string) => (query ? `${path}?${query}` : path);

export const listConversations = (query = "") =>
  send<Page<ConversationSummary>>("GET", withQuery("/api/conversations", query));
export const getConversation = (cid: string) => send<Conversation>("GET", `/api/conversations/${id(cid)}`);
export const patchConversation = (cid: string, patch: ItemPatch) =>
  send<Conversation>("PATCH", `/api/conversations/${id(cid)}`, patch);
export const deleteConversation = (cid: string) => send<unknown>("DELETE", `/api/conversations/${id(cid)}`);

export const listLetters = (query = "") => send<Page<LetterSummary>>("GET", withQuery("/api/letters", query));
export const createLetter = (input: { title?: string; body?: string; turn_id?: string; matter_id?: string }) =>
  send<Letter>("POST", "/api/letters", input);
export const getLetter = (lid: string) => send<Letter>("GET", `/api/letters/${id(lid)}`);
export const putLetter = (lid: string, patch: ItemPatch & { body?: string }) =>
  send<Letter>("PUT", `/api/letters/${id(lid)}`, patch);
export const deleteLetter = (lid: string) => send<unknown>("DELETE", `/api/letters/${id(lid)}`);
export const getVersions = (lid: string) => send<LetterVersion[]>("GET", `/api/letters/${id(lid)}/versions`);
export const restoreVersion = (lid: string, n: number) =>
  send<Letter>("POST", `/api/letters/${id(lid)}/versions/${n}/restore`);
export const letterExportUrl = (lid: string, format: "txt" | "docx", lang: UiLanguage) =>
  `/api/letters/${id(lid)}/export?format=${format}&lang=${lang}`;

export const listMatters = (query = "") => send<Page<Matter>>("GET", withQuery("/api/matters", query));
export const createMatter = (name: string) => send<Matter>("POST", "/api/matters", { name });
export const getMatter = (mid: string) => send<MatterDetail>("GET", `/api/matters/${id(mid)}`);
export const patchMatter = (mid: string, patch: { name?: string; status?: "open" | "closed" }) =>
  send<Matter>("PATCH", `/api/matters/${id(mid)}`, patch);
export const deleteMatter = (mid: string) => send<unknown>("DELETE", `/api/matters/${id(mid)}`);

export const listBookmarks = (query = "") => send<Page<Bookmark>>("GET", withQuery("/api/bookmarks", query));
export const addBookmark = (chunk_id: string, matter_id?: string) =>
  send<Bookmark>("POST", "/api/bookmarks", matter_id ? { chunk_id, matter_id } : { chunk_id });
export const patchBookmark = (bid: string, patch: { matter_id: string | null }) =>
  send<Bookmark>("PATCH", `/api/bookmarks/${id(bid)}`, patch);
export const deleteBookmark = (bid: string) => send<unknown>("DELETE", `/api/bookmarks/${id(bid)}`);

export const listNotes = (query = "") => send<Page<Note>>("GET", withQuery("/api/notes", query));
export const createNote = (input: { body: string; target_kind?: NoteTarget; target_id?: string; matter_id?: string }) =>
  send<Note>("POST", "/api/notes", input);
export const putNote = (nid: string, patch: { body?: string; matter_id?: string | null }) =>
  send<Note>("PUT", `/api/notes/${id(nid)}`, patch);
export const deleteNote = (nid: string) => send<unknown>("DELETE", `/api/notes/${id(nid)}`);
