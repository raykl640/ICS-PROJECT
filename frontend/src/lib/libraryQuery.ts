// Library tabs and filters <-> the page URL (?tab=&q=&matter=&lang=&sort=) and the API list query.
import type { UiLanguage } from "../api/types";

export const LIBRARY_TABS = ["chats", "letters", "saved", "notes"] as const;
export type LibraryTab = (typeof LIBRARY_TABS)[number];
export const SORTS = ["updated", "created", "title"] as const;
export type Sort = (typeof SORTS)[number];
/** Matter filter value for items that are in no matter. */
export const NO_MATTER = "none";

export interface LibraryFilters {
  q: string;
  /** "" = any matter, NO_MATTER, or a matter id. */
  matter: string;
  /** "" = any language (chats only). */
  lang: "" | UiLanguage;
  sort: Sort;
}

export const DEFAULT_FILTERS: LibraryFilters = { q: "", matter: "", lang: "", sort: "updated" };

/** Which filters a tab offers (bookmarks are always newest first; only chats have a language). */
export const TAB_FILTERS: Record<LibraryTab, { lang: boolean; sort: boolean }> = {
  chats: { lang: true, sort: true },
  letters: { lang: false, sort: true },
  saved: { lang: false, sort: false },
  notes: { lang: false, sort: true },
};

const oneOf = <T extends string>(value: string | null, allowed: readonly T[], fallback: T): T =>
  allowed.includes(value as T) ? (value as T) : fallback;

/** Tab and filters from the URL; unknown values fall back to the defaults. */
export function readLibraryParams(params: URLSearchParams): { tab: LibraryTab; filters: LibraryFilters } {
  return {
    tab: oneOf(params.get("tab"), LIBRARY_TABS, "chats"),
    filters: {
      q: params.get("q") ?? "",
      matter: params.get("matter") ?? "",
      lang: oneOf(params.get("lang"), ["", "en", "sw"] as const, ""),
      sort: oneOf(params.get("sort"), SORTS, "updated"),
    },
  };
}

/** The URL for a tab and filters; defaults are left out so links stay short. */
export function writeLibraryParams(tab: LibraryTab, filters: LibraryFilters): URLSearchParams {
  const params = new URLSearchParams({ tab });
  if (filters.q.trim()) params.set("q", filters.q.trim());
  if (filters.matter) params.set("matter", filters.matter);
  if (filters.lang && TAB_FILTERS[tab].lang) params.set("lang", filters.lang);
  if (filters.sort !== "updated" && TAB_FILTERS[tab].sort) params.set("sort", filters.sort);
  return params;
}

/** Query string for the tab's list endpoint, with only the filters that tab supports. */
export function libraryApiQuery(tab: LibraryTab, filters: LibraryFilters, cursor: string | null = null): string {
  const params = new URLSearchParams();
  if (filters.q.trim()) params.set("q", filters.q.trim());
  if (filters.matter) params.set("matter", filters.matter);
  if (filters.lang && TAB_FILTERS[tab].lang) params.set("lang", filters.lang);
  if (TAB_FILTERS[tab].sort && filters.sort !== "updated") params.set("sort", filters.sort);
  if (cursor) params.set("cursor", cursor);
  return params.toString();
}

/** True when any filter differs from the defaults (shows "Clear filters"). */
export const hasFilters = (filters: LibraryFilters): boolean =>
  filters.q.trim() !== "" || filters.matter !== "" || filters.lang !== "" || filters.sort !== "updated";
