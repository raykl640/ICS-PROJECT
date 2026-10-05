import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ActInfo, SectionView } from "../api/laws";
import { renderApp } from "../test/app";
import { HEALTHY } from "../test/fixtures";
import { stubFetch } from "../test/http";

const ACTS: ActInfo[] = [
  { slug: "sample-constitution", name: "Sample Constitution", year: 2000, unit: "Article", sections: 4, repealed: 0 },
  {
    slug: "sample-employment-act",
    name: "Sample Employment Act",
    year: 2000,
    unit: "Section",
    sections: 9,
    repealed: 1,
  },
];
const chunk = (num: string, title: string, text: string) => ({
  chunk_id: `sample-employment-act-${num}`,
  act: "Sample Employment Act",
  act_slug: "sample-employment-act",
  act_year: 2000,
  unit_type: "section" as const,
  chapter: "",
  part: "PART II — CONTRACTS",
  section_num: num,
  section_title: title,
  text,
  page: 3,
  repealed: false,
});
const SECTION: SectionView = {
  chunk: chunk(
    "8",
    "Summary dismissal",
    "Gross misconduct may justify dismissal under section 4.\n(2) <b>Not bold</b>.",
  ),
  prev: "sample-employment-act-7",
  next: "sample-employment-act-9",
  refs_out: [
    { label: "Section 4", chunk_id: "sample-employment-act-4" },
    { label: "Section 6", chunk_id: null },
  ],
  refs_in: [{ label: "Sample Employment Act, section 9", chunk_id: "sample-employment-act-9" }],
};
const NEXT: SectionView = {
  ...SECTION,
  chunk: chunk("9", "Sick leave", "Sick leave text."),
  prev: SECTION.chunk.chunk_id,
  next: null,
};

beforeEach(() => {
  stubFetch({
    "GET /api/health": { body: HEALTHY },
    "GET /api/laws": { body: ACTS },
    "GET /api/laws/sample-employment-act": {
      body: {
        act: ACTS[1],
        groups: [
          {
            part: "PART I — PRELIMINARY",
            items: [
              {
                chunk_id: "sample-employment-act-1",
                num: "1",
                title: "Interpretation",
                unit_type: "section",
                repealed: false,
              },
            ],
          },
          {
            part: "PART II — CONTRACTS",
            items: [
              {
                chunk_id: "sample-employment-act-2",
                num: "2",
                title: "Contracts",
                unit_type: "section",
                repealed: false,
              },
              { chunk_id: "sample-employment-act-7", num: "7", title: "Deleted", unit_type: "section", repealed: true },
            ],
          },
        ],
      },
    },
    "GET /api/laws/sections/sample-employment-act-8": { body: SECTION },
    "GET /api/laws/sections/sample-employment-act-9": { body: NEXT },
    "GET /api/search": {
      body: {
        hits: [
          {
            chunk_id: "sample-employment-act-3",
            act: "Sample Employment Act",
            act_slug: "sample-employment-act",
            unit_type: "section",
            num: "3",
            title: "Notice",
            snippet: "…give 😀 notice <img src=x onerror=alert(1)> in writing…",
            marks: [[8, 14]],
          },
        ],
      },
    },
  });
});

afterEach(() => vi.unstubAllGlobals());

test("the Act list links to each table of contents, grouped by Part with repealed items marked", async () => {
  const user = userEvent.setup();
  renderApp("/laws");
  await user.click(await screen.findByRole("link", { name: /Sample Employment Act/ }));
  const toc = await screen.findByRole("navigation", { name: "Contents" });
  const parts = within(toc)
    .getAllByRole("heading", { level: 2 })
    .map((h) => h.textContent);
  expect(parts).toEqual(["PART I — PRELIMINARY", "PART II — CONTRACTS"]);
  const links = within(toc)
    .getAllByRole("link")
    .map((a) => a.getAttribute("href"));
  expect(links).toEqual([
    "/laws/sample-employment-act/sample-employment-act-1",
    "/laws/sample-employment-act/sample-employment-act-2",
    "/laws/sample-employment-act/sample-employment-act-7",
  ]);
  expect(within(toc).getByRole("link", { name: /Deleted/ })).toHaveTextContent("Repealed");
});

test("the reader shows the text verbatim, refs, cited by, and arrow keys move between sections", async () => {
  const user = userEvent.setup();
  renderApp("/laws/sample-employment-act/sample-employment-act-8");
  expect(await screen.findByRole("heading", { level: 1, name: "Section 8 — Summary dismissal" })).toBeInTheDocument();
  expect(screen.getByText(/<b>Not bold<\/b>/)).toBeInTheDocument();
  expect(screen.getByText("Page 3 of the official PDF")).toBeInTheDocument();
  const refs = screen.getByRole("region", { name: "This section refers to" });
  expect(within(refs).getByRole("link", { name: "Section 4" })).toHaveAttribute(
    "href",
    "/laws/sample-employment-act/sample-employment-act-4",
  );
  expect(within(refs).queryByRole("link", { name: "Section 6" })).toBeNull();
  expect(within(screen.getByRole("region", { name: "Cited by" })).getByRole("link")).toHaveTextContent("section 9");
  expect(screen.queryByRole("button", { name: "Save section" })).toBeNull();

  await user.keyboard("{ArrowRight}");
  expect(await screen.findByRole("heading", { level: 1, name: "Section 9 — Sick leave" })).toBeInTheDocument();
  await user.keyboard("{ArrowLeft}");
  expect(await screen.findByRole("heading", { level: 1, name: "Section 8 — Summary dismissal" })).toBeInTheDocument();
});

test("Ask about this section pre-fills the composer on Home", async () => {
  const user = userEvent.setup();
  renderApp("/laws/sample-employment-act/sample-employment-act-8");
  await user.click(await screen.findByRole("button", { name: "Ask about this section" }));
  const box = await screen.findByRole("textbox", { name: /question/i });
  expect(box).toHaveValue("Sample Employment Act, section 8 (Summary dismissal): ");
  await waitFor(() => expect(box).toHaveFocus());
});

test("search renders marks as <mark> from code-point offsets and never injects HTML", async () => {
  renderApp("/search?q=notice");
  const hit = await screen.findByRole("link", { name: "Sample Employment Act, Section 3: Notice" });
  const article = hit.closest("article")!;
  expect(article.querySelectorAll("mark")).toHaveLength(1);
  expect(article.querySelector("mark")).toHaveTextContent(/^notice$/);
  expect(article.querySelector("img")).toBeNull();
  expect(article).toHaveTextContent("<img src=x onerror=alert(1)>");
  expect(screen.getByRole("button", { name: "Sample Constitution" })).toHaveAttribute("aria-pressed", "false");
});

test("no results suggest asking instead", async () => {
  stubFetch({
    "GET /api/health": { body: HEALTHY },
    "GET /api/laws": { body: ACTS },
    "GET /api/search": { body: { hits: [] } },
  });
  const user = userEvent.setup();
  renderApp("/search?q=zebra");
  expect(await screen.findByRole("heading", { name: "No sections match" })).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Ask instead" }));
  expect(await screen.findByRole("textbox", { name: /question/i })).toHaveValue("zebra");
});

test("an unknown section is a 404 page", async () => {
  renderApp("/laws/sample-employment-act/nope");
  expect(await screen.findByRole("heading", { name: "Page not found" })).toBeInTheDocument();
});

test("the palette jumps to a section typed as 'Employment s.41', and '?' opens the shortcut sheet", async () => {
  const user = userEvent.setup();
  renderApp("/");
  await screen.findByRole("heading", { level: 1 });
  await user.keyboard("?");
  expect(await screen.findByRole("dialog", { name: "Keyboard shortcuts" })).toBeInTheDocument();
  await user.keyboard("{Escape}");
  await user.keyboard("/");
  const input = await screen.findByRole("combobox");
  await user.type(input, "Employment s.8");
  const option = await screen.findByRole("option", { name: "Sample Employment Act, section 8" });
  expect(screen.getByRole("option", { name: "Search the laws for “Employment s.8”" })).toBeInTheDocument();
  await user.click(option);
  expect(await screen.findByRole("heading", { level: 1, name: "Section 8 — Summary dismissal" })).toBeInTheDocument();
});
