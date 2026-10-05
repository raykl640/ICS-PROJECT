import { act, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { postQuery } from "../api/client";
import { strength } from "../lib/password";
import { renderApp } from "../test/app";
import { HEALTHY } from "../test/fixtures";
import { stubFetch } from "../test/http";

const USER = { id: "u1", username: "wanjiku", display_name: "Wanjiku" };
const GUEST = { user: null, locked: false, lock_in_s: 0 };
const CODE = "ABCD-EFGH-IJKL-MNOP-QRST";

afterEach(() => vi.unstubAllGlobals());

/** A fake backend whose sign-in state the tests can change. */
function backend(initial: { user: typeof USER | null; locked: boolean; lock_in_s: number } = GUEST) {
  const state = { ...initial };
  const calls = stubFetch({
    "GET /api/health": { body: HEALTHY },
    "GET /api/auth/me": () => ({ body: state }),
    "POST /api/auth/register": () => {
      Object.assign(state, { user: USER, locked: false, lock_in_s: 900 });
      return { body: { user: USER, recovery_code: CODE } };
    },
    "POST /api/auth/login": () =>
      state.user === null &&
      calls.at(-1)?.body &&
      (calls.at(-1)!.body as { password: string }).password === "right password!"
        ? (Object.assign(state, { user: USER, locked: false, lock_in_s: 900 }),
          { body: { user: USER, recovery_code: null } })
        : { status: 401, body: { error: { code: "invalid_credentials", message: "x" } } },
    "POST /api/auth/lock": () => (Object.assign(state, { locked: true, lock_in_s: 0 }), { body: state }),
    "POST /api/auth/unlock": () =>
      (calls.at(-1)!.body as { password: string }).password === "right password!"
        ? (Object.assign(state, { locked: false, lock_in_s: 900 }), { body: { user: USER, recovery_code: null } })
        : { status: 401, body: { error: { code: "invalid_credentials", message: "x" } } },
    "POST /api/auth/logout": () => (Object.assign(state, GUEST), { body: GUEST }),
    "GET /api/account/profile": { body: { name: "", address: "", phone: "", email: "", id_number: "" } },
    "PUT /api/account/profile": () => ({ body: calls.at(-1)!.body }),
    "GET /api/account/prefs": { body: { save_history: true, auto_lock_minutes: 15 } },
    "PUT /api/account/prefs": () => ({ body: calls.at(-1)!.body }),
  });
  return { state, calls };
}

test("password strength is length based", () => {
  expect(strength("short", 10)).toBe("short");
  expect(strength("ten chars!", 10)).toBe("fair");
  expect(strength("fourteen chars", 10)).toBe("good");
  expect(strength("twenty characters ok", 10)).toBe("strong");
});

test("mutating API calls carry X-Haki: 1", async () => {
  const fetchStub = vi.fn(
    async () => new Response(JSON.stringify({ session_id: "s", null_response: true, acts: [], language: "en" })),
  );
  vi.stubGlobal("fetch", fetchStub);
  await postQuery("Why?", "en");
  expect(new Headers((fetchStub.mock.calls[0] as unknown as [string, RequestInit])[1].headers).get("X-Haki")).toBe("1");
});

test("guests see the banner and a sign-in link; nothing about accounts in Settings", async () => {
  backend();
  renderApp("/settings");
  expect(await screen.findByText("Guest: nothing is saved.")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Sign in" })).toHaveAttribute("href", "/welcome");
  expect(screen.queryByRole("tab", { name: "Profile" })).not.toBeInTheDocument();
});

test("sign-up validates, then the recovery code cannot be skipped without ticking 'I saved it'", async () => {
  const user = userEvent.setup();
  const { calls } = backend();
  renderApp("/signup");
  await user.type(await screen.findByRole("textbox", { name: "Username" }), "wanjiku");
  await user.type(screen.getByLabelText("Password"), "short");
  expect(screen.getByText("The password needs at least 10 characters.")).toBeInTheDocument();
  expect(screen.getByRole("meter", { name: "Password strength" })).toHaveAttribute("aria-valuetext", "Too short");
  await user.type(screen.getByLabelText("Password"), " but now long");
  await user.type(screen.getByLabelText("Repeat the password"), "short but now lon");
  expect(screen.getByText("The two passwords are different.")).toBeInTheDocument();
  await user.type(screen.getByLabelText("Repeat the password"), "g");
  await user.click(screen.getByRole("button", { name: "Create account" }));

  expect(await screen.findByRole("heading", { name: "Save your recovery code" })).toBeInTheDocument();
  expect(screen.getByTestId("recovery-code")).toHaveTextContent(CODE);
  expect(calls.find((c) => c.url === "/api/auth/register")?.body).toEqual({
    username: "wanjiku",
    password: "short but now long",
    display_name: "",
  });
  const next = screen.getByRole("button", { name: "Continue" });
  expect(next).toBeDisabled();
  await user.click(screen.getByRole("checkbox", { name: "I have saved my recovery code" }));
  await user.click(next);
  expect(await screen.findByRole("heading", { level: 1, name: /Know where you stand/ })).toBeInTheDocument();
  expect(screen.queryByText("Guest: nothing is saved.")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Account" })).toBeInTheDocument();
});

test("sign-in shows a generic error, remembers the username when asked, and lands on Home", async () => {
  const user = userEvent.setup();
  backend();
  localStorage.setItem("hakiai.usernames", JSON.stringify(["amina"]));
  renderApp("/signin");
  const name = await screen.findByRole("textbox", { name: "Username" });
  expect(name).toHaveValue("amina");
  await user.clear(name);
  await user.type(name, "wanjiku");
  await user.type(screen.getByLabelText("Password"), "wrong password");
  await user.click(screen.getByRole("button", { name: "Sign in" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("do not match an account on this computer");
  expect(screen.getByLabelText("Password")).toHaveValue("");
  await user.type(screen.getByLabelText("Password"), "right password!");
  await user.click(screen.getByRole("button", { name: "Sign in" }));
  expect(await screen.findByRole("heading", { level: 1, name: /Know where you stand/ })).toBeInTheDocument();
  expect(JSON.parse(localStorage.getItem("hakiai.usernames")!)).toEqual(["wanjiku", "amina"]);
});

test("a remembered username can be forgotten", async () => {
  const user = userEvent.setup();
  backend();
  localStorage.setItem("hakiai.usernames", JSON.stringify(["amina"]));
  renderApp("/signin");
  await user.click(await screen.findByRole("button", { name: "Forget amina" }));
  expect(localStorage.getItem("hakiai.usernames")).toBe("[]");
  expect(screen.queryByRole("button", { name: "amina" })).not.toBeInTheDocument();
});

test("Lock from the account menu hides the app behind the lock screen until the password is entered", async () => {
  const user = userEvent.setup();
  backend({ user: USER, locked: false, lock_in_s: 900 });
  renderApp("/");
  await user.click(await screen.findByRole("button", { name: "Account" }));
  await user.click(await screen.findByRole("menuitem", { name: "Lock" }));
  expect(await screen.findByRole("heading", { level: 1, name: "HakiAI is locked" })).toBeInTheDocument();
  expect(screen.queryByRole("navigation", { name: "Main" })).not.toBeInTheDocument();
  expect(screen.getByText("Signed in as Wanjiku. Enter your password to continue.")).toBeInTheDocument();
  await user.type(screen.getByLabelText("Password"), "wrong password");
  await user.click(screen.getByRole("button", { name: "Unlock" }));
  expect(await screen.findByRole("alert")).toBeInTheDocument();
  await user.type(screen.getByLabelText("Password"), "right password!");
  await user.click(screen.getByRole("button", { name: "Unlock" }));
  expect(await screen.findByRole("navigation", { name: "Main" })).toBeInTheDocument();
});

test("the lock screen appears when the server's idle auto-lock falls due", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  try {
    const { state } = backend({ user: USER, locked: false, lock_in_s: 5 });
    renderApp("/");
    await screen.findByRole("navigation", { name: "Main" });
    Object.assign(state, { locked: true, lock_in_s: 0 });
    await act(() => vi.advanceTimersByTimeAsync(6000));
    expect(await screen.findByRole("heading", { level: 1, name: "HakiAI is locked" })).toBeInTheDocument();
  } finally {
    vi.useRealTimers();
  }
});

test("activity is reported to the server at most once a minute", async () => {
  const user = userEvent.setup();
  backend({ user: USER, locked: false, lock_in_s: 900 });
  const fetchSpy = vi.mocked(fetch);
  renderApp("/");
  await screen.findByRole("navigation", { name: "Main" });
  await user.keyboard("a");
  await user.keyboard("b");
  await waitFor(() =>
    expect(fetchSpy.mock.calls.filter(([url]) => String(url).includes("active=true"))).toHaveLength(1),
  );
});

test("signed-in users get Profile and Privacy tabs; the profile is saved", async () => {
  const user = userEvent.setup();
  const { calls } = backend({ user: USER, locked: false, lock_in_s: 900 });
  renderApp("/settings?tab=profile");
  const name = await screen.findByRole("textbox", { name: "Full name" });
  await user.type(name, "Wanjiku Kamau");
  await user.click(screen.getByRole("button", { name: "Save profile" }));
  expect(await screen.findByText("Saved.")).toBeInTheDocument();
  expect(calls.find((c) => c.method === "PUT")?.body).toMatchObject({ name: "Wanjiku Kamau" });

  await user.click(screen.getByRole("tab", { name: "Privacy" }));
  await user.click(await screen.findByRole("radio", { name: "Off" }));
  await waitFor(() =>
    expect(calls.filter((c) => c.url === "/api/account/prefs" && c.method === "PUT").at(-1)?.body).toEqual({
      save_history: false,
      auto_lock_minutes: 15,
    }),
  );
  expect(screen.getByRole("link", { name: "Export my data" })).toHaveAttribute("href", "/api/account/export");
});

test("sign out from the menu returns to guest mode", async () => {
  const user = userEvent.setup();
  backend({ user: USER, locked: false, lock_in_s: 900 });
  renderApp("/");
  await user.click(await screen.findByRole("button", { name: "Account" }));
  await user.click(await screen.findByRole("menuitem", { name: "Sign out" }));
  expect(await screen.findByText("Guest: nothing is saved.")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Sign in" })).toHaveAttribute("href", "/welcome");
});
