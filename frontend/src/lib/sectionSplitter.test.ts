// Same cases as backend/tests/test_sections.py (all answer text is invented).
import { type ParsedResponse, SectionSplitter, type SectionDelta, splitSections } from "./sectionSplitter";

const DEFAULT_SCRIPT = [
  "## RIGHTS",
  " EXPLA",
  "NATION\nYou have rights under Sample Act, Section 12.\n\n#",
  "# RECOMMENDED",
  " STEPS\n1. Write to the other party.\n\n",
  "## FORMAL LE",
  "TTER\nDear Sir or Madam,\n",
];
const WELL_FORMED =
  "## RIGHTS EXPLANATION\nYou have rights.\n## RECOMMENDED STEPS\n1. Act.\n## FORMAL LETTER\nDear Sir,\n";

function parsed(fields: Partial<ParsedResponse>): ParsedResponse {
  return { rights: "", steps: "", letter: "", formatOk: true, ...fields };
}

function feedAll(tokens: string[]): [SectionDelta[], ParsedResponse] {
  const splitter = new SectionSplitter();
  const events = tokens.flatMap((token) => splitter.feed(token));
  return [events, splitter.finalize()];
}

test("default fake script with headers split across tokens", () => {
  const [events, result] = feedAll(DEFAULT_SCRIPT);
  expect(result).toEqual(
    parsed({
      rights: "You have rights under Sample Act, Section 12.",
      steps: "1. Write to the other party.",
      letter: "Dear Sir or Madam,",
    }),
  );
  expect(events.some((e) => e.text.includes("##") || e.text.includes("RIGHTS"))).toBe(false);
});

test.each([1, 2, 3, 7])("any token split (%i chars) gives the same result", (size) => {
  const tokens: string[] = [];
  for (let i = 0; i < WELL_FORMED.length; i += size) tokens.push(WELL_FORMED.slice(i, i + size));
  const [events, result] = feedAll(tokens);
  expect(result).toEqual(splitSections(WELL_FORMED));
  const steps = events
    .filter((e) => e.section === "steps")
    .map((e) => e.text)
    .join("");
  expect(steps.trim()).toBe("1. Act.");
});

test("body text streams before its line ends", () => {
  const splitter = new SectionSplitter();
  splitter.feed("## RIGHTS EXPLANATION\n");
  expect(splitter.feed("You have")).toEqual([{ section: "rights", text: "You have" }]);
  expect(splitter.feed(" rights")).toEqual([{ section: "rights", text: " rights" }]);
});

test("a possible header is held until decided", () => {
  const splitter = new SectionSplitter();
  expect(splitter.feed("##")).toEqual([]);
  expect(splitter.feed(" Rec")).toEqual([]);
  expect(splitter.feed("ommended Steps\n")).toEqual([]);
  expect(splitter.feed("1. Go")).toEqual([{ section: "steps", text: "1. Go" }]);
});

test.each<[string, string, ParsedResponse]>([
  [
    "markdown bold, title case, colon variants",
    "**RIGHTS EXPLANATION**\nA.\n### Recommended Steps:\nB.\n**Formal Letter:**\nC.",
    parsed({ rights: "A.", steps: "B.", letter: "C." }),
  ],
  [
    "reordered headers",
    "## FORMAL LETTER\nC.\n## RIGHTS EXPLANATION\nA.\n## RECOMMENDED STEPS\nB.",
    parsed({ rights: "A.", steps: "B.", letter: "C." }),
  ],
  [
    "duplicated header appends",
    "## RIGHTS EXPLANATION\nA1.\n## RECOMMENDED STEPS\nB.\n## RIGHTS EXPLANATION\nA2.\n## FORMAL LETTER\nC.",
    parsed({ rights: "A1.\nA2.", steps: "B.", letter: "C." }),
  ],
  [
    "missing letter header",
    "## RIGHTS EXPLANATION\nA.\n## RECOMMENDED STEPS\nB.",
    parsed({ rights: "A.", steps: "B.", formatOk: false }),
  ],
  [
    "no headers at all: everything is rights",
    "You have rights.\n1. Do this.\nDear Sir,",
    parsed({ rights: "You have rights.\n1. Do this.\nDear Sir,", formatOk: false }),
  ],
  [
    "preamble before the first header stays in rights",
    "Here is my answer.\n## RIGHTS EXPLANATION\nA.\n## RECOMMENDED STEPS\nB.\n## FORMAL LETTER\nC.",
    parsed({ rights: "Here is my answer.\nA.", steps: "B.", letter: "C." }),
  ],
  [
    "trailing text after the letter stays in the letter",
    "## RIGHTS EXPLANATION\nA.\n## RECOMMENDED STEPS\nB.\n## FORMAL LETTER\nC.\n\nGood luck.",
    parsed({ rights: "A.", steps: "B.", letter: "C.\n\nGood luck." }),
  ],
  [
    "header with inline content after a colon",
    "Rights Explanation: A.\nRecommended steps: B.\n__Formal letter__: C.",
    parsed({ rights: "A.", steps: "B.", letter: "C." }),
  ],
  [
    "words that merely start like a header are body text",
    "## RIGHTS EXPLANATION\nRights explanation is short.\n## RECOMMENDED STEPS\nB.\n## FORMAL LETTER\nC.",
    parsed({ rights: "Rights explanation is short.", steps: "B.", letter: "C." }),
  ],
  ["empty output", "", parsed({ formatOk: false })],
])("malformed output: %s", (_name, text, expected) => {
  expect(splitSections(text)).toEqual(expected);
  expect(feedAll([...text])[1]).toEqual(expected); // one character per token
});

test("an unfinished last line is classified on finalize", () => {
  const splitter = new SectionSplitter();
  splitter.feed("## RIGHTS EXPLANATION\nA.\n## FORMAL LETTER");
  expect(splitter.finalize()).toEqual(parsed({ rights: "A.", formatOk: false }));
});

test("snapshot exposes the live sections and the headers seen so far", () => {
  const splitter = new SectionSplitter();
  splitter.feed("## RIGHTS EXPLANATION\nA.\n## RECOMMENDED STEPS\n1. Go");
  expect(splitter.snapshot()).toEqual({ rights: "A.\n", steps: "1. Go", letter: "" });
  expect(splitter.current).toBe("steps");
  expect(splitter.seen).toEqual(["rights", "steps"]);
});
