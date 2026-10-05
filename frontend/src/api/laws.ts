// Laws browser API (public): Act list, tables of contents, verbatim sections, BM25 search; recent reads (signed in).
import { JSON_HEADERS, parse } from "./client";

export interface ActInfo {
  slug: string;
  name: string;
  year: number;
  unit: "Section" | "Article";
  sections: number;
  repealed: number;
}

export interface TocItem {
  chunk_id: string;
  num: string;
  title: string;
  unit_type: UnitType;
  repealed: boolean;
}

export interface ActToc {
  act: ActInfo;
  groups: { part: string; items: TocItem[] }[];
}

export type UnitType = "section" | "article" | "schedule";

/** A statutory unit exactly as stored in chunks.json. */
export interface LawChunk {
  chunk_id: string;
  act: string;
  act_slug: string;
  act_year: number;
  unit_type: UnitType;
  chapter: string;
  part: string;
  section_num: string;
  section_title: string;
  text: string;
  page: number;
  repealed: boolean;
}

export interface RefLink {
  label: string;
  chunk_id: string | null;
}

export interface SectionView {
  chunk: LawChunk;
  prev: string | null;
  next: string | null;
  refs_out: RefLink[];
  refs_in: RefLink[];
}

/** marks are [start, end) offsets in Unicode code points into snippet. */
export interface SearchHit {
  chunk_id: string;
  act: string;
  act_slug: string;
  unit_type: UnitType;
  num: string;
  title: string;
  snippet: string;
  marks: [number, number][];
}

export interface RecentRead {
  chunk_id: string;
  act: string;
  unit_type: UnitType;
  section_num: string;
  section_title: string;
  at: string;
}

const get = async <T>(path: string) => parse<T>(await fetch(path));
const id = (value: string) => encodeURIComponent(value);

let actsCache: Promise<ActInfo[]> | null = null;

/** GET /api/laws, fetched once per page load (the corpus does not change while the app runs). */
export function listActs(): Promise<ActInfo[]> {
  actsCache ??= get<ActInfo[]>("/api/laws").catch((error: unknown) => {
    actsCache = null;
    throw error;
  });
  return actsCache;
}

export const getAct = (slug: string) => get<ActToc>(`/api/laws/${id(slug)}`);
export const getSection = (chunkId: string) => get<SectionView>(`/api/laws/sections/${id(chunkId)}`);

export async function searchLaws(q: string, acts: string[]): Promise<SearchHit[]> {
  const params = new URLSearchParams({ q });
  if (acts.length) params.set("acts", acts.join(","));
  return (await get<{ hits: SearchHit[] }>(`/api/search?${params}`)).hits;
}

export const listReads = (limit: number) => get<RecentRead[]>(`/api/reads?limit=${limit}`);

export async function recordRead(chunkId: string): Promise<void> {
  const init = { method: "POST", headers: JSON_HEADERS, body: JSON.stringify({ chunk_id: chunkId }) };
  await parse<unknown>(await fetch("/api/reads", init));
}

/** The Act slug of a chunk id ("employment-act-41" -> "employment-act"); the longest matching slug wins. */
export function actSlugOf(chunkId: string, acts: ActInfo[]): string | undefined {
  return acts
    .map((act) => act.slug)
    .filter((slug) => chunkId.startsWith(`${slug}-`))
    .sort((a, b) => b.length - a.length)[0];
}

/** Reader URL of a chunk; the Act part is only for readable addresses (the reader loads by chunk id). */
export const sectionHref = (chunkId: string, slug: string | undefined) => `/laws/${slug ?? "act"}/${chunkId}`;
