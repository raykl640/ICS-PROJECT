import {
  BookOpen,
  CircleUser,
  FileText,
  Home,
  Library,
  Lock,
  LogOut,
  MessageSquare,
  Scale,
  Settings,
  Sun,
} from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { IconButton } from "../components/Button";
import { CommandPalette, type CommandItem } from "../components/CommandPalette";
import { Badge } from "../components/Display";
import { Menu, MenuContent, MenuItem, MenuSeparator, MenuTrigger } from "../components/Menu";
import { Sidebar, TopBar, type NavItem } from "../components/Shell";
import { useToast } from "../components/toastContext";
import { LOREM, TOC } from "./mockData";

export type Screen = "home" | "conversation" | "reader";

const NAV: (Omit<NavItem, "current"> & { screen?: Screen })[] = [
  { id: "home", label: "Home", icon: <Home size={20} />, href: "?view=home", primary: true, screen: "home" },
  {
    id: "ask",
    label: "Ask",
    icon: <MessageSquare size={20} />,
    href: "?view=conversation",
    primary: true,
    screen: "conversation",
  },
  { id: "library", label: "Library", icon: <Library size={20} />, href: "#library", primary: true },
  { id: "laws", label: "Laws", icon: <BookOpen size={20} />, href: "?view=reader", primary: true, screen: "reader" },
  { id: "today", label: "Today", icon: <Sun size={20} />, href: "#today" },
  { id: "settings", label: "Settings", icon: <Settings size={20} />, href: "#settings", primary: true },
];

/** Brand lock-up used in the sidebar. */
function Brand() {
  return (
    <span className="flex items-center gap-2 text-ink">
      <Scale aria-hidden="true" size={22} className="text-accent" />
      <span className="font-display-style text-xl">HakiAI</span>
    </span>
  );
}

/** Mock app shell: sidebar, top bar with search and account menu, command palette on Ctrl/Cmd+K. */
export function AppFrame({ screen, start, children }: { screen: Screen; start: ReactNode; children: ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const toast = useToast();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const commands: CommandItem[] = [
    ...NAV.map((n) => ({
      id: `go-${n.id}`,
      label: `Go to ${n.label}`,
      group: "Navigate",
      icon: n.icon,
      onSelect: () => {},
    })),
    ...TOC.flatMap((p) => p.sections).map((s) => ({
      id: `law-${s}`,
      label: s,
      hint: "Sample Act",
      group: "Laws (placeholder)",
      icon: <FileText size={18} />,
      onSelect: () => toast({ title: "Opened a placeholder section", description: LOREM[1] }),
    })),
  ];

  return (
    <div className="flex min-h-dvh flex-col bg-canvas md:flex-row">
      <Sidebar
        label="Main"
        brand={<Brand />}
        items={NAV.map(({ screen: s, ...n }) => ({ ...n, current: s === screen }))}
        collapsed={collapsed}
        onCollapsedChange={setCollapsed}
        collapseLabel="Collapse navigation"
        expandLabel="Expand navigation"
      />
      <div className="min-w-0 flex-1">
        <TopBar
          start={
            <div className="flex items-center gap-2">
              {start}
              <Badge tone="warn">Placeholder data</Badge>
            </div>
          }
          search={{ label: "Search laws and chats", shortcut: "Ctrl K", onOpen: () => setPaletteOpen(true) }}
          end={
            <Menu>
              <MenuTrigger asChild>
                <IconButton label="Account" icon={<CircleUser size={22} />} />
              </MenuTrigger>
              <MenuContent>
                <MenuItem icon={<Settings size={18} />}>Settings</MenuItem>
                <MenuItem icon={<Lock size={18} />}>Lock</MenuItem>
                <MenuSeparator />
                <MenuItem icon={<LogOut size={18} />} tone="danger">
                  Sign out
                </MenuItem>
              </MenuContent>
            </Menu>
          }
        />
        <main className="mx-auto max-w-6xl px-4 py-6 sm:px-6 lg:py-8">{children}</main>
      </div>
      <CommandPalette
        open={paletteOpen}
        onOpenChange={setPaletteOpen}
        title="Search and commands"
        placeholder="Type to search…"
        emptyText="Nothing matches."
        items={commands}
      />
    </div>
  );
}
