import { FilePlus, FolderOpen, FolderPlus, Library as LibraryIcon, Plus, SearchX } from "lucide-react";
import { type FormEvent, type ReactNode, useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { getPrefs } from "../api/accounts";
import {
  createLetter,
  createMatter,
  createNote,
  listBookmarks,
  listConversations,
  listLetters,
  listMatters,
  listNotes,
  type Page,
} from "../api/library";
import { useAuth, useLibrary } from "../app/contexts";
import { PageTitle } from "../app/PageTitle";
import { BookmarkRow, ChatRow, LetterRow, NoteRow, type Remove } from "../components/library/Rows";
import { usePagedList } from "../components/library/usePagedList";
import { useUndoDelete } from "../components/library/useUndoDelete";
import { Button, ButtonLink } from "../design/components/Button";
import { Dialog, DialogContent } from "../design/components/Dialog";
import { Badge, Card, EmptyState, Notice, Skeleton } from "../design/components/Display";
import { Field, Select, TextArea } from "../design/components/Field";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../design/components/Tabs";
import { useLoad } from "../hooks/useLoad";
import { type StringKey, useI18n } from "../i18n";
import limits from "../limits.json";
import {
  hasFilters,
  LIBRARY_TABS,
  type LibraryFilters,
  type LibraryTab,
  libraryApiQuery,
  NO_MATTER,
  readLibraryParams,
  SORTS,
  TAB_FILTERS,
  writeLibraryParams,
} from "../lib/libraryQuery";

const TAB_LABELS: Record<LibraryTab, StringKey> = {
  chats: "library_tab_chats",
  letters: "library_tab_letters",
  saved: "library_tab_saved",
  notes: "library_tab_notes",
};
const SORT_LABELS: Record<(typeof SORTS)[number], StringKey> = {
  updated: "sort_updated",
  created: "sort_created",
  title: "sort_title",
};
const SEARCH_DELAY_MS = 300;

/** Library: saved chats, letters, sections and notes with search, filters, matters and undoable delete. */
export function Library() {
  const { t } = useI18n();
  const { me } = useAuth();
  const [params, setParams] = useSearchParams();
  const { tab, filters } = readLibraryParams(params);
  const signedIn = Boolean(me?.user && !me.locked);

  if (!me) return <p role="status">{t("loading")}</p>;
  if (!signedIn) {
    return (
      <div className="flex max-w-3xl flex-col gap-6">
        <PageTitle>{t("library_title")}</PageTitle>
        <EmptyState
          icon={<LibraryIcon size={32} />}
          title={t("library_guest_title")}
          action={
            <ButtonLink href="/welcome" variant="primary">
              {t("guest_banner_action")}
            </ButtonLink>
          }
        >
          {t("library_guest_body")}
        </EmptyState>
      </div>
    );
  }

  const change = (next: Partial<LibraryFilters>, nextTab: LibraryTab = tab) =>
    setParams(writeLibraryParams(nextTab, { ...filters, ...next }), { replace: true });

  return (
    <div className="flex flex-col gap-6">
      <div>
        <PageTitle>{t("library_title")}</PageTitle>
        <p className="mt-2 max-w-3xl text-ink-muted">{t("library_intro")}</p>
      </div>
      <PrivateModeNote />
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <Tabs value={tab} onValueChange={(id) => change({}, id as LibraryTab)} className="min-w-0">
          <TabsList aria-label={t("library_title")}>
            {LIBRARY_TABS.map((id) => (
              <TabsTrigger key={id} value={id}>
                {t(TAB_LABELS[id])}
              </TabsTrigger>
            ))}
          </TabsList>
          <Filters key={tab} tab={tab} filters={filters} onChange={change} />
          {LIBRARY_TABS.map((id) => (
            <TabsContent key={id} value={id}>
              {id === tab && <TabList tab={id} filters={filters} />}
            </TabsContent>
          ))}
        </Tabs>
        <Matters />
      </div>
    </div>
  );
}

function PrivateModeNote() {
  const { t } = useI18n();
  const { result } = useLoad("prefs", getPrefs);
  if (result.status !== "ok" || result.data.save_history) return null;
  return <Notice tone="info">{t("library_private_note")}</Notice>;
}

function Filters({
  tab,
  filters,
  onChange,
}: {
  tab: LibraryTab;
  filters: LibraryFilters;
  onChange: (next: Partial<LibraryFilters>) => void;
}) {
  const { t } = useI18n();
  const [text, setText] = useState(filters.q);
  const { result } = useLoad("matters-for-filter", () => listMatters());
  const matters = result.status === "ok" ? result.data.items : [];
  const offered = TAB_FILTERS[tab];

  useEffect(() => {
    if (text === filters.q) return;
    const timer = setTimeout(() => onChange({ q: text }), SEARCH_DELAY_MS);
    return () => clearTimeout(timer);
  }, [text, filters.q, onChange]);

  return (
    <div className="my-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <Field
        type="search"
        label={t("library_search")}
        value={text}
        onChange={(e) => setText(e.target.value)}
        frameClassName="sm:col-span-2 xl:col-span-1"
        maxLength={200}
      />
      <Select
        label={t("filter_matter")}
        value={filters.matter}
        onChange={(e) => onChange({ matter: e.target.value })}
        options={[
          { value: "", label: t("filter_matter_any") },
          { value: NO_MATTER, label: t("filter_matter_none") },
          ...matters.map((m) => ({ value: m.id, label: m.name })),
        ]}
      />
      {offered.lang && (
        <Select
          label={t("filter_language")}
          value={filters.lang}
          onChange={(e) => onChange({ lang: e.target.value as LibraryFilters["lang"] })}
          options={[
            { value: "", label: t("filter_language_any") },
            { value: "en", label: t("language_en") },
            { value: "sw", label: t("language_sw") },
          ]}
        />
      )}
      {offered.sort && (
        <Select
          label={t("filter_sort")}
          value={filters.sort}
          onChange={(e) => onChange({ sort: e.target.value as LibraryFilters["sort"] })}
          options={SORTS.map((sort) => ({ value: sort, label: t(SORT_LABELS[sort]) }))}
        />
      )}
      {hasFilters(filters) && (
        <div className="flex items-end">
          <Button
            variant="ghost"
            onClick={() => {
              setText("");
              onChange({ q: "", matter: "", lang: "", sort: "updated" });
            }}
          >
            {t("filters_clear")}
          </Button>
        </div>
      )}
    </div>
  );
}

const FETCHERS: Record<LibraryTab, (query: string) => Promise<Page<{ id: string }>>> = {
  chats: listConversations,
  letters: listLetters,
  saved: listBookmarks,
  notes: listNotes,
};

const EMPTY: Record<LibraryTab, [StringKey, StringKey]> = {
  chats: ["empty_chats_title", "empty_chats_body"],
  letters: ["empty_letters_title", "empty_letters_body"],
  saved: ["empty_saved_title", "empty_saved_body"],
  notes: ["empty_notes_title", "empty_notes_body"],
};

function TabList({ tab, filters }: { tab: LibraryTab; filters: LibraryFilters }) {
  const { t } = useI18n();
  const query = libraryApiQuery(tab, filters);
  const list = usePagedList(`${tab}?${query}`, (cursor) => FETCHERS[tab](libraryApiQuery(tab, filters, cursor)));
  const { hidden, remove } = useUndoDelete();
  const items = list.items.filter((item) => !hidden.has(item.id));
  const [title, body] = EMPTY[tab];

  return (
    <div className="flex flex-col gap-4">
      {tab === "letters" && <NewLetterButton />}
      {tab === "notes" && <NewNote matterId={filters.matter && filters.matter !== NO_MATTER ? filters.matter : null} />}
      {list.status === "loading" && <ListSkeleton />}
      {list.status === "error" && <Notice tone="danger">{t("library_error")}</Notice>}
      {list.status === "ok" && items.length === 0 && (
        <EmptyState
          icon={hasFilters(filters) ? <SearchX size={28} /> : <FolderOpen size={28} />}
          title={t(hasFilters(filters) ? "empty_search_title" : title)}
        >
          {t(hasFilters(filters) ? "empty_search_body" : body)}
        </EmptyState>
      )}
      {items.length > 0 && (
        <ul className="flex flex-col gap-2" aria-label={t(TAB_LABELS[tab])}>
          {items.map((item) => (
            <ItemRow key={item.id} tab={tab} item={item} remove={remove} />
          ))}
        </ul>
      )}
      {list.hasMore && (
        <Button onClick={list.loadMore} disabled={list.loadingMore} className="self-start">
          {list.loadingMore ? t("loading") : t("load_more")}
        </Button>
      )}
    </div>
  );
}

/** One row of whichever kind the tab lists. */
export function ItemRow({ tab, item, remove }: { tab: LibraryTab; item: { id: string }; remove: Remove }): ReactNode {
  switch (tab) {
    case "chats":
      return <ChatRow chat={item as Parameters<typeof ChatRow>[0]["chat"]} remove={remove} />;
    case "letters":
      return <LetterRow letter={item as Parameters<typeof LetterRow>[0]["letter"]} remove={remove} />;
    case "saved":
      return <BookmarkRow bookmark={item as Parameters<typeof BookmarkRow>[0]["bookmark"]} remove={remove} />;
    case "notes":
      return <NoteRow note={item as Parameters<typeof NoteRow>[0]["note"]} remove={remove} />;
  }
}

function ListSkeleton() {
  return (
    <div aria-hidden="true" className="flex flex-col gap-2">
      {[0, 1, 2].map((i) => (
        <Skeleton key={i} className="h-16 rounded-md" />
      ))}
    </div>
  );
}

function NewLetterButton() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const create = async () => {
    setBusy(true);
    try {
      const letter = await createLetter({ title: t("untitled_letter") });
      navigate(`/letters/${letter.id}`);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Button icon={<FilePlus size={18} />} onClick={() => void create()} disabled={busy} className="self-start">
      {t("new_letter")}
    </Button>
  );
}

/** Note composer (in a matter when one is given). */
export function NewNote({ matterId }: { matterId: string | null }) {
  const { t } = useI18n();
  const { bump } = useLibrary();
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!text.trim()) return;
    setBusy(true);
    try {
      await createNote(matterId ? { body: text, matter_id: matterId } : { body: text });
      setText("");
      bump();
    } finally {
      setBusy(false);
    }
  };
  return (
    <form
      onSubmit={submit}
      className="flex flex-col gap-2 rounded-lg border border-line-subtle bg-raised shadow-raised p-4"
    >
      <TextArea label={t("note_label")} value={text} onChange={(e) => setText(e.target.value)} className="min-h-20" />
      <Button type="submit" icon={<Plus size={18} />} disabled={busy || !text.trim()} className="self-start">
        {t("add_note")}
      </Button>
    </form>
  );
}

function Matters() {
  const { t } = useI18n();
  const { result } = useLoad("matters", () => listMatters());
  const [creating, setCreating] = useState(false);
  return (
    <Card
      title={t("matters_title")}
      actions={
        <Button icon={<FolderPlus size={18} />} onClick={() => setCreating(true)}>
          {t("new_matter")}
        </Button>
      }
    >
      <p className="mb-3 text-sm text-ink-muted">{t("matters_hint")}</p>
      {result.status === "ok" && result.data.items.length === 0 && (
        <p className="text-ink-muted">{t("matters_empty")}</p>
      )}
      {result.status === "ok" && result.data.items.length > 0 && (
        <ul className="flex flex-col gap-1">
          {result.data.items.map((matter) => (
            <li key={matter.id}>
              <Link
                to={`/matters/${matter.id}`}
                className="-mx-2 flex items-center justify-between gap-2 rounded-md px-2 py-2 text-ink hover:bg-sunken"
              >
                <span className="min-w-0 truncate font-semibold">{matter.name}</span>
                <Badge tone={matter.status === "open" ? "success" : "neutral"}>
                  {t(matter.status === "open" ? "matter_open" : "matter_closed")}
                </Badge>
              </Link>
            </li>
          ))}
        </ul>
      )}
      {creating && <NewMatterDialog onClose={() => setCreating(false)} />}
    </Card>
  );
}

function NewMatterDialog({ onClose }: { onClose: () => void }) {
  const { t } = useI18n();
  const navigate = useNavigate();
  const { bump } = useLibrary();
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!name.trim()) return;
    setBusy(true);
    try {
      const matter = await createMatter(name.trim());
      bump();
      onClose();
      navigate(`/matters/${matter.id}`);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent title={t("new_matter")} closeLabel={t("dismiss")}>
        <form onSubmit={submit} className="flex flex-col gap-4">
          <Field
            label={t("matter_name")}
            hint={t("matter_name_hint")}
            value={name}
            onChange={(e) => setName(e.target.value)}
            maxLength={limits.matter_name_max_chars}
          />
          <div className="flex justify-end gap-2">
            <Button onClick={onClose}>{t("cancel")}</Button>
            <Button type="submit" variant="primary" disabled={busy || !name.trim()}>
              {t("matter_create")}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
