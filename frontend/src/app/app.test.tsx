import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderApp } from "../test/app";
import { HEALTHY } from "../test/fixtures";
import { stubFetch } from "../test/http";
import { renderIn } from "../test/render";
import { ErrorBoundary } from "./ErrorBoundary";
import { SETTINGS_KEY } from "./settings";

beforeEach(() => {
  stubFetch({ "GET /api/health": { body: HEALTHY } });
});

afterEach(() => vi.unstubAllGlobals());

test("an unknown path shows the 404 page inside the shell, with a way home", async () => {
  renderApp("/no/such/page");
  expect(await screen.findByRole("heading", { name: "Page not found" })).toBeInTheDocument();
  expect(screen.getByRole("navigation", { name: "Main" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Go to Home" })).toHaveAttribute("href", "/");
});

test.each([
  ["/", "Know where you stand under Kenyan law."],
  ["/settings", "Settings"],
  ["/how-it-works", "How HakiAI works"],
])("a direct load of %s renders its page and marks it current", async (path, heading) => {
  renderApp(path);
  expect(await screen.findByRole("heading", { level: 1, name: heading })).toBeInTheDocument();
  expect(document.title).toBe(`${heading} — HakiAI`);
  const current = within(screen.getByRole("navigation", { name: "Main" })).getByRole("link", { current: "page" });
  expect(current).toHaveAttribute("href", path);
});

test("/ask with no question in progress goes to Home, where questions start; Ask stays current", async () => {
  renderApp("/ask");
  expect(await screen.findByRole("heading", { level: 1, name: /Know where you stand/ })).toBeInTheDocument();
  const nav = screen.getByRole("navigation", { name: "Main" });
  expect(within(nav).getByRole("link", { current: "page" })).toHaveAccessibleName("Ask");
  expect(within(nav).queryByRole("link", { name: "Home" })).not.toBeInTheDocument();
});

test("the style guide is a route in dev builds", async () => {
  renderApp("/styleguide");
  expect(await screen.findByRole("heading", { level: 1, name: "Style guide" })).toBeInTheDocument();
  expect(screen.getByText("ink-muted")).toBeInTheDocument();
});

test("navigating moves focus to the new page's heading", async () => {
  const user = userEvent.setup();
  renderApp("/");
  await screen.findByRole("heading", { level: 1, name: /Know where you stand/ });
  await user.click(
    within(screen.getByRole("navigation", { name: "Main" })).getByRole("link", { name: "How it works" }),
  );
  const heading = await screen.findByRole("heading", { level: 1, name: "How HakiAI works" });
  await waitFor(() => expect(heading).toHaveFocus());
});

test("settings persist across reloads and are applied to <html>", async () => {
  const user = userEvent.setup();
  const first = renderApp("/settings");
  await user.click(await screen.findByRole("radio", { name: "Dark" }));
  await user.click(screen.getByRole("radio", { name: "Extra large" }));
  await user.click(within(screen.getByRole("radiogroup", { name: "Contrast" })).getByRole("radio", { name: "More" }));
  await user.click(within(screen.getByRole("radiogroup", { name: "Motion" })).getByRole("radio", { name: "Reduce" }));
  expect(document.documentElement.dataset).toMatchObject({
    theme: "dark",
    text: "xl",
    contrast: "more",
    motion: "reduce",
  });
  expect(JSON.parse(localStorage.getItem(SETTINGS_KEY)!)).toMatchObject({ theme: "dark", text: "xl" });

  first.unmount();
  renderApp("/settings");
  expect(await screen.findByRole("radio", { name: "Dark" })).toBeChecked();
});

test("the interface language switches every label and sets lang", async () => {
  const user = userEvent.setup();
  renderApp("/settings?tab=language");
  await screen.findByRole("heading", { level: 1, name: "Settings" });
  const main = screen.getByRole("main");
  await user.click(
    within(within(main).getByRole("radiogroup", { name: "Interface language" })).getAllByRole("radio")[1],
  );
  expect(await screen.findByRole("heading", { level: 1, name: "Mipangilio" })).toBeInTheDocument();
  expect(document.documentElement.lang).toBe("sw");
  expect(
    within(screen.getByRole("navigation", { name: "Kuu" })).getByRole("link", { name: "Uliza" }),
  ).toBeInTheDocument();
});

test("Ctrl+K opens the command palette, which navigates", async () => {
  const user = userEvent.setup();
  renderApp("/");
  await screen.findByRole("heading", { level: 1, name: /Know where you stand/ });
  await user.keyboard("{Control>}k{/Control}");
  await user.keyboard("settings");
  await user.keyboard("{Enter}");
  expect(await screen.findByRole("heading", { level: 1, name: "Settings" })).toBeInTheDocument();
});

test("Home has one question box and points to the laws instead of listing them", async () => {
  renderApp("/");
  await screen.findByRole("heading", { level: 1, name: /Know where you stand/ });
  expect(screen.getAllByRole("textbox")).toHaveLength(1);
  expect(screen.queryByRole("button", { name: /Employment Act/ })).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Browse the laws" })).toHaveAttribute("href", "/laws");
});

test("the error boundary replaces a crashed tree with a reload screen", () => {
  vi.mocked(console.error).mockImplementation(() => {});
  function Boom(): never {
    throw new Error("boom");
  }
  renderIn(
    <ErrorBoundary>
      <Boom />
    </ErrorBoundary>,
  );
  expect(screen.getByRole("heading", { name: "Something went wrong on this page" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Reload" })).toBeInTheDocument();
});
