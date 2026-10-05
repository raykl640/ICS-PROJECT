import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ANSWER, DONE, HEALTHY, QUERY_OK, SOURCES } from "./test/fixtures";
import { renderApp } from "./test/app";
import { stubFetch } from "./test/http";
import { MockEventSource } from "./test/mockEventSource";

const scrollIntoView = vi.fn();

beforeEach(() => {
  MockEventSource.reset();
  vi.stubGlobal("EventSource", MockEventSource);
  Element.prototype.scrollIntoView = scrollIntoView;
});

afterEach(() => vi.unstubAllGlobals());

/** Ask from Home; the app moves to /ask and opens the stream. */
async function ask(routes: Parameters<typeof stubFetch>[0]) {
  const user = userEvent.setup();
  stubFetch({ "GET /api/health": { body: HEALTHY }, ...routes });
  renderApp("/");
  await user.type(await screen.findByRole("textbox", { name: "Your question" }), "Why was I fired?");
  await user.click(screen.getByRole("button", { name: "Ask" }));
  await waitFor(() => expect(MockEventSource.instances).toHaveLength(1));
  await screen.findByRole("heading", { name: "Your question and answer" });
  return user;
}

test("asking from Home opens Ask; a citation opens the sources, scrolls to the chunk and highlights it", async () => {
  const user = await ask({
    "POST /api/query": { body: QUERY_OK },
    "GET /api/sources/s1": { body: { session_id: "s1", chunks: SOURCES } },
  });
  expect(screen.getByText("Why was I fired?")).toBeInTheDocument();
  act(() => MockEventSource.last.emit("token", { text: ANSWER, deltas: [] }));
  act(() => MockEventSource.last.emit("done", DONE));
  await screen.findByRole("button", { name: "Sources (2)" });
  expect(document.getElementById("source-sample-employment-act-4")).toBeNull();

  await user.click(screen.getByRole("tab", { name: "What the law says" }));
  await user.click(screen.getByRole("button", { name: "Show s. 4 in the sources" }));

  const sheet = await screen.findByRole("dialog", { name: "Sources" });
  const chunk = document.getElementById("source-sample-employment-act-4")!;
  expect(sheet).toContainElement(chunk);
  expect(chunk).toHaveAttribute("data-highlighted", "true");
  expect(document.getElementById("source-sample-constitution-7")).toHaveAttribute("data-highlighted", "false");
  expect(scrollIntoView).toHaveBeenCalled();
  expect(document.activeElement).toBe(chunk);
  expect(within(chunk).getByText("(1) An employer shall give a reason.")).toBeInTheDocument();
  expect(within(sheet).getByText("Shortened for the model")).toBeInTheDocument();

  await user.keyboard("{Escape}");
  await user.click(screen.getByRole("tab", { name: "Draft letter" }));
  expect(screen.getAllByRole("tablist")).toHaveLength(1);
  expect(screen.getByRole("link", { name: "Download letter (.docx)" })).toHaveAttribute(
    "href",
    "/api/letter/s1?format=docx",
  );
  expect(screen.getByText(DONE.disclaimer)).toBeInTheDocument();
});

test("a null response shows the fallback screen and feedback, never the answer tabs", async () => {
  await ask({ "POST /api/query": { body: { ...QUERY_OK, null_response: true } } });
  act(() => MockEventSource.last.emit("null", { message: "I cannot find a provision.", disclaimer: "Not advice." }));
  expect(screen.getByRole("heading", { name: "No matching provision found" })).toBeInTheDocument();
  expect(screen.getByText("I cannot find a provision.")).toBeInTheDocument();
  expect(screen.queryByRole("tablist")).not.toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Was this helpful?" })).toBeInTheDocument();
});

test("an engine failure shows the health details and a retry", async () => {
  let health: object = HEALTHY;
  stubFetch({
    "GET /api/health": () => ({ status: 200, body: health }),
    "POST /api/query": { body: QUERY_OK },
    "GET /api/sources/s1": { body: { session_id: "s1", chunks: SOURCES } },
  });
  const user = userEvent.setup();
  renderApp("/ask");
  await user.type(await screen.findByRole("textbox", { name: "Your question" }), "Why?");
  await user.click(screen.getByRole("button", { name: "Ask" }));
  await waitFor(() => expect(MockEventSource.instances).toHaveLength(1));
  health = {
    ...HEALTHY,
    status: "degraded",
    ollama: false,
    error: { code: "degraded", message: "start it: ollama serve" },
  };
  act(() => MockEventSource.last.emit("error", { code: "llm_unavailable", message: "Ollama is not reachable." }));
  const alert = await screen.findByRole("alert");
  expect(alert).toHaveTextContent("The answer engine (Ollama) is not available.");
  await waitFor(() => expect(alert).toHaveTextContent("start it: ollama serve"));
  expect(screen.getByText("HakiAI is not fully ready")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Try again" }));
  await waitFor(() => expect(MockEventSource.instances).toHaveLength(2));
});

test("progress shows the steps while the answer is written", async () => {
  await ask({
    "POST /api/query": { body: QUERY_OK },
    "GET /api/sources/s1": { body: { session_id: "s1", chunks: SOURCES } },
  });
  act(() => MockEventSource.last.emit("status", { stage: "retrieved", chunks: 2 }));
  act(() => MockEventSource.last.emit("status", { stage: "queued", position: 3 }));
  const steps = within(screen.getByRole("list", { name: "Answer progress" })).getAllByRole("listitem");
  expect(steps.map((s) => s.textContent)).toEqual([
    "Searching the laws, doneFound 2 relevant provisions.",
    "Waiting in line, in progressNumber 3 in line",
    "Writing the answer, waiting",
  ]);
  act(() => MockEventSource.last.emit("status", { stage: "generating" }));
  expect(screen.getByText(/so far\. You can open other pages/)).toBeInTheDocument();
  act(() => MockEventSource.last.emit("done", DONE));
  expect(screen.queryByRole("list", { name: "Answer progress" })).not.toBeInTheDocument();
  expect(screen.getByRole("status", { name: "" })).toHaveTextContent("Answer complete.");
});
