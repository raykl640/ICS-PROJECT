import { Bell, Command, Copy, Inbox, MoreHorizontal, Pencil, Trash2 } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { contrastRatio } from "../contrast";
import { Button, IconButton } from "../components/Button";
import { CommandPalette } from "../components/CommandPalette";
import { Dialog, DialogClose, DialogContent, DialogTrigger } from "../components/Dialog";
import { Badge, Card, EmptyState, Kbd, Skeleton } from "../components/Display";
import { Field, Select, TextArea } from "../components/Field";
import { AnswerCard, LawRef, LawText, SourceCard } from "../components/Legal";
import { Menu, MenuContent, MenuItem, MenuLabel, MenuSeparator, MenuTrigger } from "../components/Menu";
import { Popover, PopoverContent, PopoverTrigger, ScrollArea, Tooltip, TooltipProvider } from "../components/Overlay";
import { ProgressSteps } from "../components/ProgressSteps";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/Tabs";
import { ToastProvider } from "../components/Toast";
import { useToast } from "../components/toastContext";
import { ToggleGroup } from "../components/ToggleGroup";
import { DIRECTION_IDS, DIRECTIONS, resolvePalette } from "../themes";
import { COLOR_ROLES, type Contrast, type DirectionId, type Mode, type TextSize } from "../themes/types";
import { useApplyTheme } from "../useTheme";
import { FAKE_ACT, LOREM } from "./mockData";
import { ConversationMock, HomeMock, ReaderMock } from "./Screens";

type View = "gallery" | "home" | "conversation" | "reader";

interface State {
  direction: DirectionId;
  mode: Mode;
  contrast: Contrast;
  text: TextSize;
  view: View;
}

const pick = <T extends string>(value: string | null, allowed: readonly T[], fallback: T): T =>
  allowed.includes(value as T) ? (value as T) : fallback;

function readUrl(): State & { bare: boolean; sources?: boolean } {
  const q = new URLSearchParams(window.location.search);
  return {
    direction: pick(q.get("direction"), DIRECTION_IDS, "mahakama"),
    mode: pick(q.get("theme"), ["light", "dark"] as const, "light"),
    contrast: pick(q.get("contrast"), ["standard", "more"] as const, "standard"),
    text: pick(q.get("text"), ["sm", "md", "lg", "xl"] as const, "md"),
    view: pick(q.get("view"), ["gallery", "home", "conversation", "reader"] as const, "gallery"),
    bare: q.get("bare") === "1",
    sources: q.has("sources") ? q.get("sources") === "1" : undefined,
  };
}

/** Dev-only style guide: direction switcher, every component, and three mock screens. */
export function Styleguide() {
  const [initial] = useState(readUrl);
  const [state, setState] = useState<State>(initial);
  useApplyTheme({ ...state, motion: "system" });

  useEffect(() => {
    const q = new URLSearchParams({
      direction: state.direction,
      theme: state.mode,
      contrast: state.contrast,
      text: state.text,
      view: state.view,
    });
    window.history.replaceState(null, "", `?${q}`);
  }, [state]);

  const set =
    <K extends keyof State>(key: K) =>
    (value: State[K]) =>
      setState((s) => ({ ...s, [key]: value }));
  const screen = {
    gallery: <Gallery state={state} />,
    home: <HomeMock />,
    conversation: <ConversationMock sourcesOpen={initial.sources} />,
    reader: <ReaderMock />,
  }[state.view];

  return (
    <TooltipProvider delayDuration={300}>
      <ToastProvider closeLabel="Dismiss" regionLabel="Notifications">
        {!initial.bare && (
          <div className="sticky top-0 z-40 flex flex-wrap items-end gap-4 border-b-2 border-accent bg-sunken px-4 py-3">
            <Control label="Direction">
              <ToggleGroup
                label="Direction"
                value={state.direction}
                onValueChange={set("direction")}
                items={DIRECTION_IDS.map((id) => ({ value: id, label: DIRECTIONS[id].name }))}
              />
            </Control>
            <Control label="Theme">
              <ToggleGroup
                label="Theme"
                value={state.mode}
                onValueChange={set("mode")}
                items={[
                  { value: "light", label: "Light" },
                  { value: "dark", label: "Dark" },
                ]}
              />
            </Control>
            <Control label="Contrast">
              <ToggleGroup
                label="Contrast"
                value={state.contrast}
                onValueChange={set("contrast")}
                items={[
                  { value: "standard", label: "Standard" },
                  { value: "more", label: "More" },
                ]}
              />
            </Control>
            <Control label="Text size">
              <ToggleGroup
                label="Text size"
                value={state.text}
                onValueChange={set("text")}
                items={(["sm", "md", "lg", "xl"] as const).map((v) => ({ value: v, label: v.toUpperCase() }))}
              />
            </Control>
            <Control label="View">
              <ToggleGroup
                label="View"
                value={state.view}
                onValueChange={set("view")}
                items={[
                  { value: "gallery", label: "Components" },
                  { value: "home", label: "Home" },
                  { value: "conversation", label: "Conversation" },
                  { value: "reader", label: "Reader" },
                ]}
              />
            </Control>
          </div>
        )}
        {screen}
      </ToastProvider>
    </TooltipProvider>
  );
}

function Control({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <span aria-hidden="true" className="text-xs font-semibold tracking-wide text-ink-muted uppercase">
        {label}
      </span>
      {children}
    </div>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="border-t border-line-subtle py-8">
      <h2 className="mb-4 font-display-style text-2xl text-ink">{title}</h2>
      {children}
    </section>
  );
}

function Swatches({ state }: { state: State }) {
  const palette = resolvePalette(DIRECTIONS[state.direction], state.mode, state.contrast);
  return (
    <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
      {COLOR_ROLES.map((role) => (
        <li key={role} className="overflow-hidden rounded-md border border-line-subtle bg-surface">
          <div className="h-14" style={{ background: `var(--hk-${role})` }} />
          <div className="p-2 text-sm">
            <p className="font-semibold text-ink">{role}</p>
            <p className="text-ink-muted">{palette[role]}</p>
            <p className="text-ink-muted">{contrastRatio(palette[role], palette.surface).toFixed(2)}:1 on surface</p>
          </div>
        </li>
      ))}
    </ul>
  );
}

function ToastDemo() {
  const toast = useToast();
  return (
    <Button
      icon={<Bell size={18} />}
      onClick={() => toast({ title: "Your answer is ready", description: LOREM[1], tone: "success" })}
    >
      Show a toast
    </Button>
  );
}

function Gallery({ state }: { state: State }) {
  const direction = DIRECTIONS[state.direction];
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [lang, setLang] = useState<"en" | "sw">("en");
  return (
    <main className="mx-auto max-w-6xl px-4 pb-16 sm:px-6">
      <header className="py-8">
        <p className="font-semibold text-accent">Direction</p>
        <h1 className="font-display-style text-4xl text-ink">{direction.name}</h1>
        <p className="mt-2 max-w-prose text-lg text-ink-muted">{direction.summary}</p>
      </header>

      <Section title="Colour roles">
        <Swatches state={state} />
      </Section>

      <Section title="Type">
        <div className="flex flex-col gap-4">
          <p className="font-display-style text-4xl text-ink">Display: Lorem ipsum dolor</p>
          <p className="font-display-style text-2xl text-ink">Heading: Sit amet consectetur</p>
          <p className="text-ink">UI text: {LOREM[0]}</p>
          <p className="text-sm text-ink-muted">Small muted text: {LOREM[1]}</p>
          <LawText>
            <p>
              Reading text: {LOREM[2]} {LOREM[3]}
            </p>
          </LawText>
        </div>
      </Section>

      <Section title="Buttons">
        <div className="flex flex-wrap items-center gap-3">
          <Button variant="primary">Primary</Button>
          <Button>Secondary</Button>
          <Button variant="ghost">Ghost</Button>
          <Button variant="danger" icon={<Trash2 size={18} />}>
            Delete
          </Button>
          <Button disabled>Disabled</Button>
          <Tooltip label="Copy citation">
            <IconButton label="Copy citation" icon={<Copy size={20} />} />
          </Tooltip>
          <IconButton label="Edit" variant="secondary" icon={<Pencil size={20} />} />
        </div>
      </Section>

      <Section title="Fields">
        <div className="grid gap-5 md:grid-cols-2">
          <Field label="Full name" hint="Used only in your letters." placeholder="Lorem Ipsum" />
          <Field label="Phone number" error="Enter a number with 10 digits." defaultValue="0700" />
          <Select
            label="Language"
            options={[
              { value: "en", label: "English" },
              { value: "sw", label: "Kiswahili" },
            ]}
          />
          <TextArea label="Your question" aside="0 / 2000" placeholder={LOREM[0]} />
        </div>
      </Section>

      <Section title="Badges, keys, skeleton">
        <div className="flex flex-wrap items-center gap-3">
          {(["neutral", "brand", "accent", "success", "warn", "danger", "info"] as const).map((tone) => (
            <Badge key={tone} tone={tone}>
              {tone}
            </Badge>
          ))}
          <span className="text-ink">
            Press <Kbd>Ctrl</Kbd> <Kbd>K</Kbd> to search
          </span>
        </div>
        <div className="mt-4 flex max-w-md flex-col gap-2">
          <Skeleton className="w-full" />
          <Skeleton className="w-3/4" />
        </div>
      </Section>

      <Section title="Cards and empty state">
        <div className="grid gap-4 md:grid-cols-3">
          <Card eyebrow="Eyebrow" title="Surface card">
            <p className="text-ink-muted">{LOREM[1]}</p>
          </Card>
          <Card title="Raised card" tone="raised" level={3}>
            <p className="text-ink-muted">{LOREM[2]}</p>
          </Card>
          <EmptyState icon={<Inbox size={28} />} title="Nothing saved yet" action={<Button>Start a chat</Button>}>
            {LOREM[3]}
          </EmptyState>
        </div>
      </Section>

      <Section title="Progress">
        <ProgressSteps
          label="Answer progress"
          orientation="horizontal"
          statusText={{ done: "done", current: "in progress", todo: "waiting" }}
          steps={[
            { label: "Searching", status: "done" },
            { label: "Reading", status: "done" },
            { label: "Writing", status: "current" },
            { label: "Checking", status: "todo" },
          ]}
        />
      </Section>

      <Section title="Tabs and toggle group">
        <ToggleGroup
          label="Answer language"
          value={lang}
          onValueChange={setLang}
          items={[
            { value: "en", label: "English" },
            { value: "sw", label: "Kiswahili" },
          ]}
        />
        <Tabs defaultValue="a" className="mt-5">
          <TabsList>
            <TabsTrigger value="a">What the law says</TabsTrigger>
            <TabsTrigger value="b">What you can do</TabsTrigger>
            <TabsTrigger value="c">Draft letter</TabsTrigger>
          </TabsList>
          <TabsContent value="a" className="text-ink">
            {LOREM[0]}
          </TabsContent>
          <TabsContent value="b" className="text-ink">
            {LOREM[1]}
          </TabsContent>
          <TabsContent value="c" className="text-ink">
            {LOREM[2]}
          </TabsContent>
        </Tabs>
      </Section>

      <Section title="Overlays">
        <div className="flex flex-wrap gap-3">
          <Dialog>
            <DialogTrigger asChild>
              <Button>Open dialog</Button>
            </DialogTrigger>
            <DialogContent title="Delete this chat?" description="This cannot be undone." closeLabel="Close">
              <div className="flex justify-end gap-2">
                <DialogClose asChild>
                  <Button>Cancel</Button>
                </DialogClose>
                <DialogClose asChild>
                  <Button variant="danger">Delete</Button>
                </DialogClose>
              </div>
            </DialogContent>
          </Dialog>
          <Dialog>
            <DialogTrigger asChild>
              <Button>Open sheet</Button>
            </DialogTrigger>
            <DialogContent title="Sources" closeLabel="Close" side="right">
              <p className="text-ink-muted">{LOREM[0]}</p>
            </DialogContent>
          </Dialog>
          <Menu>
            <MenuTrigger asChild>
              <Button icon={<MoreHorizontal size={18} />}>Menu</Button>
            </MenuTrigger>
            <MenuContent align="start">
              <MenuLabel>Chat</MenuLabel>
              <MenuItem icon={<Pencil size={18} />}>Rename</MenuItem>
              <MenuItem icon={<Copy size={18} />}>Duplicate</MenuItem>
              <MenuSeparator />
              <MenuItem icon={<Trash2 size={18} />} tone="danger">
                Delete
              </MenuItem>
            </MenuContent>
          </Menu>
          <Popover>
            <PopoverTrigger asChild>
              <Button>Popover</Button>
            </PopoverTrigger>
            <PopoverContent aria-label="Citation">
              <p className="font-semibold text-ink">{FAKE_ACT}</p>
              <p className="text-sm text-ink-muted">{LOREM[1]}</p>
            </PopoverContent>
          </Popover>
          <ToastDemo />
          <Button icon={<Command size={18} />} onClick={() => setPaletteOpen(true)}>
            Command palette
          </Button>
          <CommandPalette
            open={paletteOpen}
            onOpenChange={setPaletteOpen}
            title="Search and commands"
            placeholder="Type to search…"
            emptyText="Nothing matches."
            items={["Lorem", "Ipsum", "Dolor", "Sit amet"].map((label, i) => ({
              id: String(i),
              label,
              group: i < 2 ? "Navigate" : "Laws (placeholder)",
              onSelect: () => {},
            }))}
          />
        </div>
      </Section>

      <Section title="Scroll area">
        <ScrollArea className="h-40 rounded-md border border-line-subtle bg-surface" label="Scrollable example">
          <div className="p-4 text-ink">
            {[...LOREM, ...LOREM].map((l, i) => (
              <p key={i} className="mb-2">
                {l}
              </p>
            ))}
          </div>
        </ScrollArea>
      </Section>

      <Section title="Answer and sources">
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_22rem]">
          <AnswerCard
            question="Lorem ipsum dolor sit amet?"
            meta={<Badge tone="success">Citations found</Badge>}
            tabs={[
              {
                id: "a",
                label: "What the law says",
                content: (
                  <p>
                    {LOREM[0]} <LawRef href="#s">Sample Act, s. 0.1</LawRef>.
                  </p>
                ),
              },
              { id: "b", label: "What you can do", content: <p>{LOREM[1]}</p> },
            ]}
            footer="Legal information, not legal advice."
          />
          <SourceCard act={FAKE_ACT} locator="Section 0.1 · page 0" highlighted>
            <p>{LOREM[2]}</p>
          </SourceCard>
        </div>
      </Section>
    </main>
  );
}
