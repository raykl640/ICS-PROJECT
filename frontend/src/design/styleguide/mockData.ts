// Placeholder data for the style guide only. Deliberately lorem ipsum: no statute text and no real section claims.

export const FAKE_ACT = "Sample Act (placeholder)";

export const LOREM = [
  "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.",
  "Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.",
  "Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur.",
  "Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum.",
];

export const QUESTION = "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod?";
export const FOLLOW_UP = "Ut enim ad minim veniam, quis nostrud exercitation?";

export const RECENT = [
  { id: "r1", kind: "chat", title: "Lorem ipsum dolor sit amet", when: "Today", status: "Answer ready" },
  { id: "r2", kind: "letter", title: "Consectetur adipiscing letter", when: "Yesterday", status: "Draft" },
  { id: "r3", kind: "chat", title: "Sed do eiusmod tempor", when: "3 days ago", status: "Answer ready" },
] as const;

export const TOPICS = [
  "Lorem at work",
  "Ipsum at home",
  "Dolor and money",
  "Amet and police",
  "Elit and land",
  "Tempor and roads",
];

export const SOURCES = [
  { id: "s1", locator: "Section 0.1 · page 0", text: [LOREM[0], LOREM[1]] },
  { id: "s2", locator: "Section 0.2 · page 0", text: [LOREM[2]] },
  { id: "s3", locator: "Section 0.3 · page 0", text: [LOREM[3], LOREM[0]] },
];

export const TOC = [
  { part: "Part I — Lorem ipsum", sections: ["0.1 Lorem ipsum", "0.2 Dolor sit amet", "0.3 Consectetur"] },
  { part: "Part II — Adipiscing elit", sections: ["0.4 Sed do eiusmod", "0.5 Tempor incididunt", "0.6 Ut labore"] },
  { part: "Part III — Magna aliqua", sections: ["0.7 Ut enim ad minim", "0.8 Quis nostrud"] },
];

export const CURRENT_SECTION = "0.5 Tempor incididunt";
