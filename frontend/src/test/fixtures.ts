// Invented answer text and sources for UI tests (never statute text).
import type { DonePayload, SourceChunk } from "../api/types";

export const ANSWER =
  "## RIGHTS EXPLANATION\nYour employer must give a reason (Sample Employment Act, s. 4).\n\n" +
  "## RECOMMENDED STEPS\n1. Write down the dates.\n\n" +
  "## FORMAL LETTER\n[Date]\n\nDear [Recipient],\n\nYours faithfully,\n[Your Name]\n";

export const SOURCES: SourceChunk[] = [
  {
    chunk_id: "sample-employment-act-4",
    act: "Sample Employment Act",
    unit_type: "section",
    section_num: "4",
    section_title: "Reasons for ending a job",
    part: "Part II - Duties",
    page: 3,
    text: "(1) An employer shall give a reason.",
    truncated: false,
    rank: 1,
  },
  {
    chunk_id: "sample-constitution-7",
    act: "Sample Constitution",
    unit_type: "article",
    section_num: "7",
    section_title: "Fair work",
    part: "",
    page: 9,
    text: "Every person has the right to fair work.",
    truncated: true,
    rank: 2,
  },
];

export const DONE: DonePayload = {
  warnings: [],
  citation_check: { verified: ["Sample Employment Act s. 4"], unmatched: [] },
  format_ok: true,
  truncated_chunks: ["sample-constitution-7"],
  untranslated: [],
  disclaimer: "HakiAI provides legal information, not legal advice.",
};

export const QUERY_OK = { session_id: "s1", null_response: false, acts: ["sample-employment-act"], language: "en" };
