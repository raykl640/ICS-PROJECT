import type { Section } from "./sectionSplitter";

/** The visible tab: the user's choice wins; otherwise follow the section the stream last wrote to. */
export const activeTab = (chosen: Section | null, latest: Section | null): Section => chosen ?? latest ?? "rights";
