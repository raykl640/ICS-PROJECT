import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { initialSession, type SessionState } from "../hooks/session";
import { DONE } from "../test/fixtures";
import { renderIn } from "../test/render";
import { ResponsePanel } from "./ResponsePanel";

const SECTIONS = { rights: "You may claim.", steps: "1. Write it down.", letter: "" };

function state(fields: Partial<SessionState>): SessionState {
  return { ...initialSession, phase: "generating", sessionId: "s1", language: "en", ...fields };
}

const selected = () => screen.getByRole("tab", { selected: true });

test("tabs follow the stream as headers arrive, without moving focus", () => {
  const { rerender } = renderIn(
    <ResponsePanel state={state({ latest: "rights" })} sections={SECTIONS} sources={[]} onCite={() => {}} />,
  );
  expect(selected()).toHaveTextContent("Rights Explanation");
  const before = document.activeElement;
  rerender(<ResponsePanel state={state({ latest: "steps" })} sections={SECTIONS} sources={[]} onCite={() => {}} />);
  expect(selected()).toHaveTextContent("Recommended Steps");
  expect(screen.getByRole("tabpanel")).toHaveTextContent("Write it down.");
  expect(document.activeElement).toBe(before);
});

test("once the user picks a tab, arriving headers no longer switch it", async () => {
  const user = userEvent.setup();
  const view = (latest: "rights" | "steps" | "letter") => (
    <ResponsePanel state={state({ latest })} sections={SECTIONS} sources={[]} onCite={() => {}} />
  );
  const { rerender } = renderIn(view("steps"));
  await user.click(screen.getByRole("tab", { name: /Rights Explanation/ }));
  rerender(view("letter"));
  expect(selected()).toHaveTextContent("Rights Explanation");
});

test("arrow keys move between tabs and select them", async () => {
  const user = userEvent.setup();
  renderIn(<ResponsePanel state={state({ latest: "rights" })} sections={SECTIONS} sources={[]} onCite={() => {}} />);
  await user.click(selected());
  await user.keyboard("{ArrowRight}");
  expect(selected()).toHaveTextContent("Recommended Steps");
  expect(document.activeElement).toBe(selected());
  await user.keyboard("{ArrowLeft}{ArrowLeft}");
  expect(selected()).toHaveTextContent("Formal Letter");
});

test("an empty section shows a skeleton while streaming and the citation warning after done", () => {
  const { rerender } = renderIn(
    <ResponsePanel state={state({ latest: "letter" })} sections={SECTIONS} sources={[]} onCite={() => {}} />,
  );
  expect(screen.getByRole("tabpanel")).toHaveTextContent("This part has not been written yet.");
  const done = { ...DONE, citation_check: { verified: [], unmatched: ["Sample Act s. 99"] } };
  rerender(
    <ResponsePanel
      state={state({ phase: "done", done, latest: "letter" })}
      sections={SECTIONS}
      sources={[]}
      onCite={() => {}}
    />,
  );
  expect(screen.getByText(/could not be matched/)).toBeInTheDocument();
  expect(screen.getByText("Sample Act s. 99")).toBeInTheDocument();
  expect(screen.getByText(DONE.disclaimer)).toBeInTheDocument();
});

test("a Kiswahili session shows the English-draft banner until the translation arrives", () => {
  const sw = state({ language: "sw", latest: "rights" });
  const { rerender } = renderIn(<ResponsePanel state={sw} sections={SECTIONS} sources={[]} onCite={() => {}} />);
  expect(screen.getByText("English draft — Kiswahili translation in progress")).toBeInTheDocument();
  const translated = { rights: "Haki.", steps: "1. Andika.", letter: "Mpendwa," };
  rerender(<ResponsePanel state={{ ...sw, translated }} sections={translated} sources={[]} onCite={() => {}} />);
  expect(screen.queryByText(/English draft/)).not.toBeInTheDocument();
});
