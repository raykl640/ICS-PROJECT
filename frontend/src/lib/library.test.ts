import type { Profile } from "../api/accounts";
import {
  DEFAULT_FILTERS,
  hasFilters,
  libraryApiQuery,
  NO_MATTER,
  readLibraryParams,
  writeLibraryParams,
} from "./libraryQuery";
import { ASKED_KEY, askPermissionOnce, notify } from "./notify";
import { fillFromProfile, normaliseLabel, placeholders, segments } from "./placeholders";

describe("library filters", () => {
  test("unknown or missing URL values fall back to the defaults", () => {
    expect(readLibraryParams(new URLSearchParams(""))).toEqual({ tab: "chats", filters: DEFAULT_FILTERS });
    const odd = readLibraryParams(new URLSearchParams("tab=trash&lang=fr&sort=random&q=rent&matter=m1"));
    expect(odd).toEqual({ tab: "chats", filters: { q: "rent", matter: "m1", lang: "", sort: "updated" } });
  });

  test("the URL keeps only non-default filters the tab offers, and reads back the same", () => {
    const filters = { q: "  wages ", matter: NO_MATTER, lang: "sw" as const, sort: "title" as const };
    expect(writeLibraryParams("chats", filters).toString()).toBe("tab=chats&q=wages&matter=none&lang=sw&sort=title");
    expect(writeLibraryParams("saved", filters).toString()).toBe("tab=saved&q=wages&matter=none");
    expect(writeLibraryParams("letters", DEFAULT_FILTERS).toString()).toBe("tab=letters");
    const back = readLibraryParams(writeLibraryParams("chats", filters));
    expect(back).toEqual({ tab: "chats", filters: { ...filters, q: "wages" } });
  });

  test("the API query drops filters a list does not support and adds the cursor", () => {
    const filters = { q: "rent", matter: "m1", lang: "en" as const, sort: "created" as const };
    expect(libraryApiQuery("chats", filters)).toBe("q=rent&matter=m1&lang=en&sort=created");
    expect(libraryApiQuery("letters", filters, "abc")).toBe("q=rent&matter=m1&sort=created&cursor=abc");
    expect(libraryApiQuery("saved", filters)).toBe("q=rent&matter=m1");
    expect(libraryApiQuery("notes", DEFAULT_FILTERS)).toBe("");
  });

  test("hasFilters ignores blank search text", () => {
    expect(hasFilters({ ...DEFAULT_FILTERS, q: "   " })).toBe(false);
    expect(hasFilters({ ...DEFAULT_FILTERS, sort: "title" })).toBe(true);
  });
});

const PROFILE: Profile = {
  name: "Wanjiku Kamau",
  address: "P.O. Box 1, Nyeri",
  phone: "",
  email: "wk@example.org",
  id_number: "12345678",
};
const LETTER =
  "[Date]\n\nDear [Recipient],\n\nI am [Your Name] (ID [ID Number]), phone [Your Phone Number].\n[Your Name]";

describe("letter placeholders", () => {
  test("labels are normalised", () => {
    expect(normaliseLabel("Your Name")).toBe("name");
    expect(normaliseLabel("Today's date")).toBe("todays date");
    expect(normaliseLabel("My E-mail Address")).toBe("email address");
  });

  test("segments mark every placeholder and lose no text", () => {
    const parts = segments(LETTER);
    expect(parts.map((p) => p.text).join("")).toBe(LETTER);
    expect(parts.filter((p) => p.placeholder).map((p) => p.text)).toEqual([
      "[Date]",
      "[Recipient]",
      "[Your Name]",
      "[ID Number]",
      "[Your Phone Number]",
      "[Your Name]",
    ]);
    expect(placeholders(LETTER)).toEqual([
      "[Date]",
      "[Recipient]",
      "[Your Name]",
      "[ID Number]",
      "[Your Phone Number]",
    ]);
    expect(segments("No placeholders.")).toEqual([{ text: "No placeholders.", placeholder: false }]);
  });

  test("fill uses the profile and the date, counts repeats and leaves unknown or empty ones", () => {
    const result = fillFromProfile(LETTER, PROFILE, "5 October 2026");
    expect(result.text).toBe(
      "5 October 2026\n\nDear [Recipient],\n\nI am Wanjiku Kamau (ID 12345678), phone [Your Phone Number].\nWanjiku Kamau",
    );
    expect(result.changes).toEqual([
      { placeholder: "[Date]", value: "5 October 2026", count: 1 },
      { placeholder: "[Your Name]", value: "Wanjiku Kamau", count: 2 },
      { placeholder: "[ID Number]", value: "12345678", count: 1 },
    ]);
    expect(result.missing).toEqual(["[Recipient]", "[Your Phone Number]"]);
  });

  test("an empty profile changes nothing", () => {
    const empty = { name: "", address: "", phone: "", email: "", id_number: "" };
    const result = fillFromProfile("Dear [Recipient], [Your Name]", empty, "");
    expect(result).toEqual({
      text: "Dear [Recipient], [Your Name]",
      changes: [],
      missing: ["[Recipient]", "[Your Name]"],
    });
  });
});

describe("notifications", () => {
  class FakeNotification {
    static permission: NotificationPermission = "default";
    static requestPermission = vi.fn(async () => "granted" as NotificationPermission);
    static shown: FakeNotification[] = [];
    onclick: (() => void) | null = null;
    title: string;
    constructor(title: string) {
      this.title = title;
      FakeNotification.shown.push(this);
    }
    close() {}
  }

  beforeEach(() => {
    FakeNotification.permission = "default";
    FakeNotification.shown = [];
    FakeNotification.requestPermission.mockClear();
    localStorage.clear();
  });
  afterEach(() => vi.unstubAllGlobals());

  test("without the Notification API nothing is shown and nothing throws", async () => {
    vi.stubGlobal("Notification", undefined);
    Reflect.deleteProperty(window, "Notification");
    expect(notify("Ready", "Open it", () => {})).toBe("unsupported");
    await expect(askPermissionOnce()).resolves.toBeUndefined();
  });

  test("permission is asked only once per browser", async () => {
    vi.stubGlobal("Notification", FakeNotification);
    await askPermissionOnce();
    await askPermissionOnce();
    expect(FakeNotification.requestPermission).toHaveBeenCalledTimes(1);
    expect(localStorage.getItem(ASKED_KEY)).toBe("1");
  });

  test("denied or undecided permission falls back to the in-app toast only", () => {
    vi.stubGlobal("Notification", FakeNotification);
    expect(notify("Ready", "Open it", () => {})).toBe("not-asked");
    FakeNotification.permission = "denied";
    expect(notify("Ready", "Open it", () => {})).toBe("denied");
    expect(FakeNotification.shown).toEqual([]);
  });

  test("granted permission shows a notification whose click opens the answer", () => {
    vi.stubGlobal("Notification", FakeNotification);
    FakeNotification.permission = "granted";
    const open = vi.fn();
    vi.spyOn(window, "focus").mockImplementation(() => {});
    expect(notify("Ready", "Open it", open)).toBe("shown");
    FakeNotification.shown[0].onclick?.();
    expect(open).toHaveBeenCalledOnce();
  });
});
