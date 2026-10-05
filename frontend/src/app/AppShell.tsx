import {
  BookOpen,
  CircleHelp,
  FileSearch,
  Keyboard,
  Languages,
  Plus,
  CircleUser,
  Library as LibraryIcon,
  Lock,
  LogIn,
  LogOut,
  MessageSquare,
  Moon,
  Settings as SettingsIcon,
  Sun,
} from "lucide-react";
import { Suspense, useEffect, useLayoutEffect, useRef, useState, type ComponentProps } from "react";
import { Link, Outlet, useLocation, useNavigate } from "react-router";
import { lock, logout } from "../api/accounts";
import { listActs, sectionHref, type ActInfo } from "../api/laws";
import type { UiLanguage } from "../api/types";
import { HealthBanner } from "../components/ErrorState";
import { Menu, MenuContent, MenuItem, MenuLabel, MenuSeparator, MenuTrigger } from "../design/components/Menu";
import { CommandPalette, type CommandItem } from "../design/components/CommandPalette";
import { Dialog, DialogContent } from "../design/components/Dialog";
import { Kbd } from "../design/components/Display";
import { Tooltip } from "../design/components/Overlay";
import { Masthead, RAIL_OFFSET } from "../design/components/Shell";
import { useToast } from "../design/components/toastContext";
import { cx } from "../design/cx";
import { useMediaQuery } from "../design/useMediaQuery";
import { isBusy, type Phase } from "../hooks/session";
import { type StringKey, type Translate, useI18n } from "../i18n";
import { parseLawQuery } from "../lib/lawRef";
import { isTyping } from "../lib/keys";
import { useAuth, useSession, useSettings } from "./contexts";
import { EventsBridge } from "./EventsBridge";
import { LockScreen } from "./LockScreen";
import { requestPageFocus } from "./pageFocus";

// "/" is where a question starts; its answer lives under /ask, so both belong to the Ask item.
const NAV: { href: string; key: StringKey; icon: typeof BookOpen; match: string[]; secondary?: boolean }[] = [
  { href: "/", key: "nav_ask", icon: MessageSquare, match: ["/ask"] },
  { href: "/laws", key: "nav_laws", icon: BookOpen, match: ["/laws", "/search"] },
  { href: "/library", key: "nav_library", icon: LibraryIcon, match: ["/library", "/matters", "/letters"] },
  { href: "/how-it-works", key: "nav_how", icon: CircleHelp, match: [], secondary: true },
  { href: "/settings", key: "nav_settings", icon: SettingsIcon, match: [] },
];

const isCurrent = (item: (typeof NAV)[number], pathname: string) =>
  item.href === "/"
    ? pathname === "/" || item.match.some((m) => pathname.startsWith(m))
    : pathname.startsWith(item.href) || item.match.some((m) => pathname.startsWith(m));

/** Client-side link with the anchor-style props the design components pass. */
function RouterLink({ href, ...props }: ComponentProps<"a"> & { href: string }) {
  return <Link to={href} {...props} />;
}

/** The section-sign mark and the name. */
function Brand() {
  return (
    <Link to="/" className="flex shrink-0 items-center gap-2 rounded-md text-ink">
      <span
        aria-hidden="true"
        className="grid size-8 place-items-center rounded-md bg-brand font-display-style text-xl leading-none text-brand-ink"
      >
        §
      </span>
      <span className="text-lg leading-none font-bold tracking-tight">HakiAI</span>
    </Link>
  );
}

/** One button that switches the interface language (the full choice is in Settings). */
function LanguageSwitch() {
  const { t } = useI18n();
  const { settings, update } = useSettings();
  const next: UiLanguage = settings.language === "en" ? "sw" : "en";
  return (
    <button
      type="button"
      lang={next}
      onClick={() => update({ language: next })}
      className="target inline-flex cursor-pointer items-center justify-center gap-2 rounded-md px-2 text-sm font-semibold text-ink-muted motion-colors hover:bg-sunken hover:text-ink lg:justify-start lg:px-3"
    >
      <Languages aria-hidden="true" size={18} />
      <span className="lg:hidden" aria-hidden="true">
        {next.toUpperCase()}
      </span>
      <span className="sr-only lg:not-sr-only">{t("palette_language")}</span>
    </button>
  );
}

const AUTH_PATHS = new Set(["/welcome", "/signin", "/signup", "/recover"]);

/** Signed in: a menu with Lock, Settings and Sign out. Guest: a link to sign in. */
function AccountControl({ pathname }: { pathname: string }) {
  const { t } = useI18n();
  const { me, apply } = useAuth();
  const { reset } = useSession();
  const navigate = useNavigate();
  if (!me?.user) {
    return (
      <div className="flex items-center gap-3 lg:flex-col lg:items-stretch lg:gap-2">
        {me && !AUTH_PATHS.has(pathname) && (
          <p className="hidden text-sm text-ink-muted lg:block">{t("guest_banner")}</p>
        )}
        <Tooltip label={t("sign_in")}>
          <Link
            to="/welcome"
            aria-label={t("sign_in")}
            className="target inline-flex items-center justify-center gap-2 rounded-md p-2 font-semibold text-ink motion-colors hover:bg-sunken lg:justify-start lg:border lg:border-line lg:bg-raised lg:px-3"
          >
            <LogIn aria-hidden="true" size={18} />
            <span aria-hidden="true" className="hidden lg:inline">
              {t("sign_in")}
            </span>
          </Link>
        </Tooltip>
      </div>
    );
  }
  const signOut = async () => {
    apply(await logout());
    reset();
    navigate("/");
  };
  return (
    <Menu>
      <MenuTrigger asChild>
        <button
          type="button"
          aria-label={t("account_menu")}
          className="target inline-flex cursor-pointer items-center gap-2 rounded-md p-2 text-ink motion-colors hover:bg-sunken lg:px-2"
        >
          <CircleUser aria-hidden="true" size={22} />
          <span aria-hidden="true" className="hidden truncate font-semibold lg:inline">
            {me.user.display_name}
          </span>
        </button>
      </MenuTrigger>
      <MenuContent>
        <MenuLabel>{t("signed_in_as", { name: me.user.display_name })}</MenuLabel>
        <MenuItem icon={<Lock size={18} />} onSelect={() => void lock().then(apply)}>
          {t("lock_now")}
        </MenuItem>
        <MenuItem icon={<SettingsIcon size={18} />} onSelect={() => navigate("/settings?tab=profile")}>
          {t("nav_settings")}
        </MenuItem>
        <MenuSeparator />
        <MenuItem icon={<LogOut size={18} />} tone="danger" onSelect={() => void signOut()}>
          {t("sign_out")}
        </MenuItem>
      </MenuContent>
    </Menu>
  );
}

/** Toast when an answer finishes while the user is on another page. */
function useAnswerReadyToast(phase: Phase, pathname: string, background: boolean): void {
  const { t } = useI18n();
  const toast = useToast();
  const previous = useRef(phase);
  useEffect(() => {
    if (isBusy(previous.current) && phase === "done" && !background && !pathname.startsWith("/ask")) {
      toast({ title: t("answer_ready"), description: t("answer_ready_body"), tone: "success" });
    }
    previous.current = phase;
  }, [phase, pathname, background, t, toast]);
}

const SHORTCUTS: { keys: string[]; key: StringKey }[] = [
  { keys: ["Ctrl", "K"], key: "shortcut_palette" },
  { keys: ["/"], key: "shortcut_palette" },
  { keys: ["?"], key: "shortcut_sheet" },
  { keys: ["←", "→"], key: "shortcut_prev_next" },
  { keys: ["Ctrl", "Enter"], key: "shortcut_ask" },
];

/** The keyboard shortcut sheet ("?"). */
function ShortcutSheet({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const { t } = useI18n();
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title={t("shortcuts_title")} closeLabel={t("close")}>
        <dl className="grid grid-cols-[auto_1fr] items-center gap-x-4 gap-y-3">
          {SHORTCUTS.map(({ keys, key }) => (
            <div key={keys.join("+")} className="contents">
              <dt className="flex gap-1">
                {keys.map((k) => (
                  <Kbd key={k}>{k}</Kbd>
                ))}
              </dt>
              <dd className="text-ink">{t(key)}</dd>
            </div>
          ))}
        </dl>
      </DialogContent>
    </Dialog>
  );
}

/** Palette commands that jump to an Act or section named in the typed text ("Employment s.41", "art 27"). */
function lawJumps(query: string, acts: ActInfo[], t: Translate, go: (to: string) => void): CommandItem[] {
  return parseLawQuery(query.trim(), acts)
    .slice(0, 5)
    .map((target) => ({
      id: `law-${target.chunkId ?? target.slug}`,
      label: target.label,
      group: t("palette_group_laws"),
      icon: <BookOpen size={18} />,
      onSelect: () => go(target.chunkId ? sectionHref(target.chunkId, target.slug) : `/laws/${target.slug}`),
    }));
}

/** Palette commands that search the laws (and, signed in, the library) for the typed text. */
function searchCommands(query: string, signedIn: boolean, t: Translate, go: (to: string) => void): CommandItem[] {
  const q = query.trim();
  if (!q) return [];
  const searches: CommandItem[] = [
    {
      id: "search-laws",
      label: t("palette_search_laws", { q }),
      group: t("palette_group_search"),
      icon: <FileSearch size={18} />,
      onSelect: () => go(`/search?${new URLSearchParams({ q })}`),
    },
  ];
  if (signedIn) {
    searches.push({
      id: "search-library",
      label: t("palette_search_library", { q }),
      group: t("palette_group_search"),
      icon: <LibraryIcon size={18} />,
      onSelect: () => go(`/library?${new URLSearchParams({ q })}`),
    });
  }
  return searches;
}

/** Layout of every page: masthead with navigation, health notice, the routed page and the command palette. */
export function AppShell() {
  const { t } = useI18n();
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const { settings, update } = useSettings();
  const { state, health, reset } = useSession();
  const { me, apply } = useAuth();
  const signedIn = Boolean(me?.user && !me.locked);
  const [shortcutsOpen, setShortcutsOpen] = useState(false);
  const [acts, setActs] = useState<ActInfo[]>([]);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const firstPath = useRef(pathname);

  useLayoutEffect(() => {
    if (pathname !== firstPath.current) requestPageFocus();
  }, [pathname]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setPaletteOpen(true);
      } else if (!event.ctrlKey && !event.metaKey && !event.altKey && !isTyping(event.target)) {
        if (event.key === "/") {
          event.preventDefault();
          setPaletteOpen(true);
        } else if (event.key === "?") {
          event.preventDefault();
          setShortcutsOpen(true);
        }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (paletteOpen) listActs().then(setActs, () => undefined);
  }, [paletteOpen]);

  useAnswerReadyToast(state.phase, pathname, state.background);

  const systemDark = useMediaQuery("(prefers-color-scheme: dark)");
  const dark = settings.theme === "dark" || (settings.theme === "system" && systemDark);
  const commands: CommandItem[] = [
    ...NAV.map(({ href, key, icon: Icon }) => ({
      id: `go-${href}`,
      label: t(key),
      group: t("palette_group_go"),
      icon: <Icon size={18} />,
      onSelect: () => navigate(href),
    })),
    {
      id: "new-question",
      label: t("palette_new_question"),
      group: t("palette_group_actions"),
      icon: <Plus size={18} />,
      onSelect: () => {
        if (!isBusy(state.phase)) reset();
        navigate("/");
      },
    },
    ...(signedIn
      ? [
          {
            id: "lock",
            label: t("lock_now"),
            group: t("palette_group_actions"),
            icon: <Lock size={18} />,
            onSelect: () => void lock().then(apply),
          },
        ]
      : []),
    {
      id: "shortcuts",
      label: t("shortcuts_title"),
      group: t("palette_group_actions"),
      icon: <Keyboard size={18} />,
      onSelect: () => setShortcutsOpen(true),
    },
    {
      id: "theme",
      label: t(dark ? "palette_theme_light" : "palette_theme_dark"),
      group: t("palette_group_actions"),
      icon: dark ? <Sun size={18} /> : <Moon size={18} />,
      onSelect: () => update({ theme: dark ? "light" : "dark" }),
    },
    {
      id: "language",
      label: t("palette_language"),
      group: t("palette_group_actions"),
      onSelect: () => update({ language: settings.language === "en" ? "sw" : "en" }),
    },
  ];

  if (me?.user && me.locked) return <LockScreen name={me.user.display_name} />;

  return (
    <div className="flex min-h-dvh flex-col bg-canvas">
      <a
        href="#main-content"
        className="sr-only z-50 rounded-sm bg-highlight px-4 py-3 font-semibold text-ink focus:not-sr-only focus:fixed focus:top-2 focus:left-2"
      >
        {t("skip_to_content")}
      </a>
      <Masthead
        label={t("nav_label")}
        brand={<Brand />}
        items={NAV.map((item) => ({
          id: item.href,
          label: t(item.key),
          icon: <item.icon size={20} />,
          href: item.href,
          current: isCurrent(item, pathname),
          secondary: item.secondary,
        }))}
        search={{
          label: t("search_label"),
          short: t("search_short"),
          shortcut: t("search_shortcut"),
          onOpen: () => setPaletteOpen(true),
        }}
        end={
          <>
            <LanguageSwitch />
            <AccountControl pathname={pathname} />
          </>
        }
        linkComponent={RouterLink}
      />
      <div className={cx("flex min-w-0 flex-1 flex-col", RAIL_OFFSET)}>
        <main
          id="main-content"
          tabIndex={-1}
          className="mx-auto w-full max-w-6xl flex-1 px-4 pt-6 pb-28 outline-none sm:px-8 lg:pt-12 lg:pb-16"
        >
          {health && health.status !== "ok" && (
            <div className="mb-6">
              <HealthBanner health={health} />
            </div>
          )}
          <Suspense
            fallback={
              <p role="status" className="text-ink-muted">
                {t("loading")}
              </p>
            }
          >
            <div className="page-enter">
              <Outlet />
            </div>
          </Suspense>
        </main>
      </div>
      <EventsBridge />
      <CommandPalette
        open={paletteOpen}
        onOpenChange={setPaletteOpen}
        title={t("palette_title")}
        placeholder={t("palette_placeholder")}
        emptyText={t("palette_empty")}
        items={commands}
        dynamic={(query) => lawJumps(query, acts, t, navigate)}
        fallback={(query) => searchCommands(query, signedIn, t, navigate)}
      />
      <ShortcutSheet open={shortcutsOpen} onOpenChange={setShortcutsOpen} />
    </div>
  );
}
