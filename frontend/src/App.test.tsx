import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { App } from "./App";
import { ANSWER, DONE, QUERY_OK, SOURCES } from "./test/fixtures";
import { stubFetch } from "./test/http";
import { MockEventSource } from "./test/mockEventSource";

const HEALTHY = { status: "ok", ollama: true, model_present: true, indexes_loaded: true, models_warm: true };
const scrollIntoView = vi.fn();

beforeEach(() => {
  MockEventSource.reset();
  vi.stubGlobal("EventSource", MockEventSource);
  Element.prototype.scrollIntoView = scrollIntoView;
});

afterEach(() => vi.unstubAllGlobals());

async function ask(routes: Parameters<typeof stubFetch>[0]) {
  const user = userEvent.setup();
  stubFetch({ "GET /api/health": { body: HEALTHY }, ...routes });
  render(<App />);
  await user.type(screen.getByRole("textbox", { name: "Your question" }), "Why was I fired?");
  await user.click(screen.getByRole("button", { name: "Ask" }));
  await waitFor(() => expect(MockEventSource.instances).toHaveLength(1));
  return user;
}

test("clicking a citation opens the sources, scrolls to the chunk and highlights it", async () => {
  const user = await ask({
    "POST /api/query": { body: QUERY_OK },
    "GET /api/sources/s1": { body: { session_id: "s1", chunks: SOURCES } },
  });
  act(() => MockEventSource.last.emit("token", { text: ANSWER, deltas: [] }));
  act(() => MockEventSource.last.emit("done", DONE));
  await screen.findByRole("button", { name: "Show the legal text used" });
  expect(document.getElementById("sources-list")).not.toBeVisible();

  await user.click(screen.getByRole("tab", { name: "Rights Explanation" }));
  await user.click(screen.getByRole("button", { name: "Show s. 4 in the sources" }));

  const chunk = document.getElementById("source-sample-employment-act-4")!;
  expect(chunk).toBeVisible();
  expect(chunk).toHaveAttribute("data-highlighted", "true");
  expect(document.getElementById("source-sample-constitution-7")).toHaveAttribute("data-highlighted", "false");
  expect(scrollIntoView).toHaveBeenCalled();
  expect(document.activeElement).toBe(chunk);
  expect(within(chunk).getByText("(1) An employer shall give a reason.")).toBeInTheDocument();
  expect(screen.getByText("Shortened for the model")).toBeInTheDocument();
  await user.click(screen.getByRole("tab", { name: "Formal Letter" }));
  expect(screen.getAllByRole("tablist")).toHaveLength(1);
  expect(screen.getByRole("link", { name: "Download letter (.docx)" })).toHaveAttribute(
    "href",
    "/api/letter/s1?format=docx",
  );
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
  render(<App />);
  await user.type(screen.getByRole("textbox", { name: "Your question" }), "Why?");
  await user.click(screen.getByRole("button", { name: "Ask" }));
  await waitFor(() => expect(MockEventSource.instances).toHaveLength(1));
  health = {
    ...HEALTHY,
    status: "degraded",
    ollama: false,
    error: { code: "degraded", message: "start it: ollama serve" },
  };
  act(() => MockEventSource.last.emit("error", { code: "llm_unavailable", message: "Ollama is not reachable." }));
  const alert = screen.getByRole("alert");
  expect(alert).toHaveTextContent("The answer engine (Ollama) is not available.");
  await waitFor(() => expect(alert).toHaveTextContent("start it: ollama serve"));
  await user.click(within(alert.parentElement!).getByRole("button", { name: "Try again" }));
  await waitFor(() => expect(MockEventSource.instances).toHaveLength(2));
});
