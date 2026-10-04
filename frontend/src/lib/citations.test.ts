import type { SourceChunk } from "../api/types";
import { findCitations } from "./citations";

function chunk(chunk_id: string, act: string, unit_type: SourceChunk["unit_type"], section_num: string): SourceChunk {
  return {
    chunk_id,
    act,
    unit_type,
    section_num,
    section_title: "T",
    part: "",
    page: 1,
    text: "x",
    truncated: false,
    rank: 1,
  };
}

const SOURCES = [
  chunk("emp-41", "Sample Employment Act", "section", "41"),
  chunk("emp-45", "Sample Employment Act", "section", "45"),
  chunk("ten-41", "Sample Tenancy Act", "section", "41"),
  chunk("con-41", "Sample Constitution", "article", "41"),
  chunk("emp-12a", "Sample Employment Act", "section", "12A"),
];

const linked = (text: string) => findCitations(text, SOURCES).map((c) => [text.slice(c.start, c.end), c.chunkId]);

test("act named before the citation picks that act's section", () => {
  expect(linked("Under the Sample Tenancy Act, Section 41 applies.")).toEqual([["Section 41", "ten-41"]]);
  expect(linked("(Sample Employment Act, s. 41(2))")).toEqual([["s. 41(2)", "emp-41"]]);
});

test("act named after the citation is used too", () => {
  expect(linked("see section 41 of the Sample Tenancy Act")).toEqual([["section 41", "ten-41"]]);
});

test("articles only match article chunks", () => {
  expect(linked("Article 41 protects fair labour practices.")).toEqual([["Article 41", "con-41"]]);
});

test("without an act the first source with that unit and number is used", () => {
  expect(linked("Section 41 says so.")).toEqual([["Section 41", "emp-41"]]);
});

test("lists link every number, subsections stay with their number", () => {
  expect(linked("Sample Employment Act, ss. 41(1)(a) and 45, also 12a")).toEqual([
    ["ss. 41(1)(a)", "emp-41"],
    ["45", "emp-45"],
  ]);
  expect(linked("Sections 12A, 41 or 45")).toEqual([
    ["Sections 12A", "emp-12a"],
    ["41", "emp-41"],
    ["45", "emp-45"],
  ]);
});

test("citations with no matching source, or a named act without it, are not linked", () => {
  expect(linked("Section 99 and Sample Tenancy Act, s. 45")).toEqual([]);
  expect(linked("possessions 41 and days 45")).toEqual([]);
});
