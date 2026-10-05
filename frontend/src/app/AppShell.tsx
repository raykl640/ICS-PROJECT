import {
  CircleHelp,
  CircleUser,
  Home,
  Lock,
  LogIn,
  LogOut,
  MessageSquare,
  Moon,
  Scale,
  Settings as SettingsIcon,
  SlidersHorizontal,
  Sun,
} from "lucide-react";
import { Suspense, useEffect, useLayoutEffect, useRef, useState, type ComponentProps } from "react";
import { Link, Outlet, useLocation, useNavigate } from "react-router";
import { lock, logout } from "../api/accounts";
import type { UiLanguage } from "../api/types";
import { HealthBanner } from "../components/ErrorState";
import { IconButton } from "../design/components/Button";
import { Menu, MenuContent, MenuItem, MenuLabel, MenuSeparator, MenuTrigger } from "../design/components/Menu";
import { CommandPalette, type CommandItem } from "../design/components/CommandPalette";
import { Popover, PopoverContent, PopoverTrigger, Tooltip } from "../design/components/Overlay";
import { Sidebar, TopBar } from "../design/components/Shell";
import { useToast } from "../design/components/toastContext";
import { ToggleGroup } from "../design/components/ToggleGroup";
import { useMediaQuery } from "../design/useMediaQuery";
import { isBusy, type Phase } from "../hooks/session";
import { type StringKey, useI18n } from "../i18n";
import { useAuth, useSession, useSettings } from "./contexts";
import { LockScreen } from "./LockScreen";
import { requestPageFocus } from "./pageFocus";
import { TEXT_SIZES, type ThemeChoice } from "./settings";

const NAV: { href: string; key: StringKey; icon: typeof Home }[] = [
  { href: "/", key: "nav_home", icon: Home },
  { href: "/ask", key: "nav_ask", icon: MessageSquare },
  { href: "/how-it-works", key: "nav_how", icon: CircleHelp },
  { href: "/settings", key: "nav_settings", icon: SettingsIcon },
];

/** Client-side link with the anchor-style props the design components pass. */
function RouterLink({ href, ...props }: ComponentProps<"a"> & { href: string }) {
  return <Link to={href} {...props} />;
}

function Brand() {
  return (
    <Link to="/" className="flex items-center gap-2 rounded-sm text-ink">
      <Scale aria-hidden="true" size={22} className="text-accent" />
      <span className="font-display-style text-xl">HakiAI</span>
    </Link>
  );
}

/** EN / SW interface language. */
function LanguageSwitch() {
  const { t } = useI18n();
  const { settings, update } = useSettings();
  return (
    <ToggleGroup
      label={t("ui_language")}
      value={settings.language}
      onValueChange={(language: UiLanguage) => update({ language })}
      iconOnly
      items={[
        { value: "en", label: t("language_en"), icon: <span className="text-sm">EN</span> },
        { value: "sw", label: t("language_sw"), icon: <span className="text-sm">SW</span> },
      ]}
    />
  );
}

/** Theme and text size without leaving the page. */
function QuickSettings() {
  const { t } = useI18n();
  const { settings, update } = useSettings();
  return (
    <Popover>
      <Tooltip label={t("quick_settings")}>
        <PopoverTrigger asChild>
          <IconButton label={t("quick_settings")} icon={<SlidersHorizontal size={20} />} />
        </PopoverTrigger>
      </Tooltip>
      <PopoverContent align="end" aria-label={t("quick_settings")} className="flex flex-col gap-4">
        <div className="flex flex-col gap-1">
          <span aria-hidden="true" className="text-sm font-semibold text-ink-muted">
            {t("theme_label")}
          </span>
          <ToggleGroup
            label={t("theme_label")}
            value={settings.theme}
            onValueChange={(theme: ThemeChoice) => update({ theme })}
            items={[
              { value: "system", label: t("theme_system") },
              { value: "light", label: t("theme_light") },
              { value: "dark", label: t("theme_dark") },
            ]}
          />
        </div>
        <div className="flex flex-col gap-1">
          <span aria-hidden="true" className="text-sm font-semibold text-ink-muted">
            {t("text_size_label")}
          </span>
          <ToggleGroup
            label={t("text_size_label")}
            value={settings.text}
            onValueChange={(text) => update({ text })}
            iconOnly
            items={TEXT_SIZES.map((size) => ({
              value: size,
              label: t(`text_${size}`),
              icon: <span className="text-sm">{size.toUpperCase()}</span>,
            }))}
          />
        </div>
        <Link to="/settings" className="font-semibold text-brand underline underline-offset-3">
          {t("nav_settings")}
        </Link>
      </PopoverContent>
    </Popover>
  );
}

const AUTH_PATHS = new Set(["/welcome", "/signin", "/signup", "/recover"]);

/** Signed in: a menu with Lock, Settings and Sign out. Guest: a link to sign in. */
function AccountControl() {
  const { t } = useI18n();
  const { me, apply } = useAuth();
  const { reset } = useSession();
  const navigate = useNavigate();
  if (!me?.user) {
    return (
      <Tooltip label={t("sign_in")}>
        <Link
          to="/welcome"
          aria-label={t("sign_in")}
          className="target inline-flex items-center justify-center rounded-md p-2 text-ink motion-colors hover:bg-sunken"
        >
          <LogIn aria-hidden="true" size={20} />
        </Link>
      </Tooltip>
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
        <IconButton label={t("account_menu")} icon={<CircleUser size={22} />} />
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

/** Thin notice for guests outside the sign-in pages. */
function GuestBanner({ pathname }: { pathname: string }) {
  const { t } = useI18n();
  const { me } = useAuth();
  if (!me || me.user || AUTH_PATHS.has(pathname)) return null;
  return (
    <p className="mb-5 flex flex-wrap items-center gap-x-3 gap-y-1 rounded-md bg-sunken px-4 py-2 text-sm text-ink">
      <span className="font-semibold">{t("guest_banner")}</span>
      <Link to="/welcome" className="font-semibold text-brand underline underline-offset-3">
        {t("guest_banner_action")}
      </Link>
    </p>
  );
}

/** Toast when an answer finishes while the user is on another page. */
function useAnswerReadyToast(phase: Phase, pathname: string): void {
  const { t } = useI18n();
  const toast = useToast();
  const previous = useRef(phase);
  useEffect(() => {
    if (isBusy(previous.current) && phase === "done" && pathname !== "/ask") {
      toast({ title: t("answer_ready"), description: t("answer_ready_body"), tone: "success" });
    }
    previous.current = phase;
  }, [phase, pathname, t, toast]);
}

/** Layout of every page: navigation, top bar, health notice, the routed page and the command palette. */
export function AppShell() {
  const { t } = useI18n();
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const { settings, update } = useSettings();
  const { state, health } = useSession();
  const { me } = useAuth();
  const [collapsed, setCollapsed] = useState(false);
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
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useAnswerReadyToast(state.phase, pathname);

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
  const here = NAV.find((item) => item.href === pathname);

  if (me?.user && me.locked) return <LockScreen name={me.user.display_name} />;

  return (
    <div className="flex min-h-dvh flex-col bg-canvas md:flex-row">
      <a
        href="#main-content"
        className="sr-only z-50 rounded-md bg-brand px-4 py-3 font-semibold text-brand-ink focus:not-sr-only focus:fixed focus:top-2 focus:left-2"
      >
        {t("skip_to_content")}
      </a>
      <Sidebar
        label={t("nav_label")}
        brand={<Brand />}
        items={NAV.map(({ href, key, icon: Icon }) => ({
          id: href,
          label: t(key),
          icon: <Icon size={20} />,
          href,
          current: href === pathname,
          primary: true,
        }))}
        collapsed={collapsed}
        onCollapsedChange={setCollapsed}
        collapseLabel={t("nav_collapse")}
        expandLabel={t("nav_expand")}
        linkComponent={RouterLink}
      />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar
          start={here && <span className="font-semibold text-ink">{t(here.key)}</span>}
          search={{ label: t("search_label"), shortcut: t("search_shortcut"), onOpen: () => setPaletteOpen(true) }}
          end={
            <>
              <LanguageSwitch />
              <QuickSettings />
              <AccountControl />
            </>
          }
        />
        <main
          id="main-content"
          tabIndex={-1}
          className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 outline-none sm:px-6 lg:py-8"
        >
          {health && health.status !== "ok" && (
            <div className="mb-6">
              <HealthBanner health={health} />
            </div>
          )}
          <GuestBanner pathname={pathname} />
          <Suspense
            fallback={
              <p role="status" className="text-ink-muted">
                {t("loading")}
              </p>
            }
          >
            <Outlet />
          </Suspense>
        </main>
      </div>
      <CommandPalette
        open={paletteOpen}
        onOpenChange={setPaletteOpen}
        title={t("palette_title")}
        placeholder={t("palette_placeholder")}
        emptyText={t("palette_empty")}
        items={commands}
      />
    </div>
  );
}
