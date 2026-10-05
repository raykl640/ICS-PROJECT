import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { initialSession, type SessionState } from "../hooks/session";
import { DONE } from "../test/fixtures";
import { renderIn } from "../test/render";
import { Answer } from "./Answer";

const SECTIONS = { rights: "You may claim.", steps: "1. Write it down.", letter: "" };

function state(fields: Partial<SessionState>): SessionState {
  return { ...initialSession, phase: "generating", sessionId: "s1", language: "en", ...fields };
}

const view = (s: SessionState, sections = SECTIONS) => (
  <Answer state={s} sections={sections} sources={[]} onCite={() => {}} onShowSources={null} />
);
const selected = () => screen.getByRole("tab", { selected: true });

test("tabs follow the stream as headers arrive, without moving focus", () => {
  const { rerender } = renderIn(view(state({ latest: "rights" })));
  expect(selected()).toHaveTextContent("What the law says");
  const before = document.activeElement;
  rerender(view(state({ latest: "steps" })));
  expect(selected()).toHaveTextContent("What you can do");
  expect(screen.getByRole("tabpanel")).toHaveTextContent("Write it down.");
  expect(document.activeElement).toBe(before);
});

test("the tab being written carries a 'writing' mark and panels are busy", () => {
  renderIn(view(state({ latest: "steps" })));
  expect(screen.getByRole("tab", { name: /What you can do/ })).toHaveTextContent("writing");
  expect(screen.getByRole("tabpanel")).toHaveAttribute("aria-busy", "true");
});

test("once the user picks a tab, arriving headers no longer switch it", async () => {
  const user = userEvent.setup();
  const { rerender } = renderIn(view(state({ latest: "steps" })));
  await user.click(screen.getByRole("tab", { name: /What the law says/ }));
  rerender(view(state({ latest: "letter" })));
  expect(selected()).toHaveTextContent("What the law says");
});

test("arrow keys move between tabs and select them", async () => {
  const user = userEvent.setup();
  renderIn(view(state({ latest: "rights" })));
  await user.click(selected());
  await user.keyboard("{ArrowRight}");
  expect(selected()).toHaveTextContent("What you can do");
  expect(document.activeElement).toBe(selected());
  await user.keyboard("{ArrowLeft}{ArrowLeft}");
  expect(selected()).toHaveTextContent("Draft letter");
});

test("an empty section shows a placeholder while streaming and the citation warning after done", () => {
  const { rerender } = renderIn(view(state({ latest: "letter" })));
  expect(screen.getByRole("tabpanel")).toHaveTextContent("This part has not been written yet.");
  expect(screen.getByText(/legal information, not legal advice/)).toBeInTheDocument();
  const done = { ...DONE, citation_check: { verified: [], unmatched: ["Sample Act s. 99"] } };
  rerender(view(state({ phase: "done", done, latest: "letter" })));
  expect(screen.getByRole("tabpanel")).toHaveTextContent("The answer did not include this part.");
  expect(screen.getByText(/could not be matched/)).toBeInTheDocument();
  expect(screen.getByText("Sample Act s. 99")).toBeInTheDocument();
  expect(screen.getByText(DONE.disclaimer)).toBeInTheDocument();
});

test("a Kiswahili session shows the English-draft notice until the translation arrives", () => {
  const sw = state({ language: "sw", latest: "rights" });
  const { rerender } = renderIn(view(sw));
  expect(screen.getByText("English draft — Kiswahili translation in progress")).toBeInTheDocument();
  expect(screen.getByRole("list", { name: "Answer progress" })).toHaveTextContent("Translating into Kiswahili");
  const translated = { rights: "Haki.", steps: "1. Andika.", letter: "Mpendwa," };
  rerender(view({ ...sw, translated }, translated));
  expect(screen.queryByText(/English draft/)).not.toBeInTheDocument();
});

test("a stored speed sample gives an ETA while waiting for the first token", () => {
  localStorage.setItem(
    "hakiai.speed",
    JSON.stringify({ firstTokenSeconds: 60, tokensPerSecond: 5, answerTokens: 300 }),
  );
  vi.useFakeTimers({ now: 100_000 });
  try {
    renderIn(view(state({ latest: null, generatingAt: 100_000 - 30_000 })));
    expect(screen.getByText(/30 s so far, about 1 min 30 s left/)).toBeInTheDocument();
  } finally {
    vi.useRealTimers();
  }
});
