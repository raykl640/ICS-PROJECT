import {
  Bookmark,
  BookmarkCheck,
  ChevronLeft,
  ChevronRight,
  Copy,
  MessageSquare,
  StickyNote,
  Volume2,
  VolumeX,
} from "lucide-react";
import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { addBookmark, createNote, listBookmarks } from "../api/library";
import { actSlugOf, getSection, listActs, recordRead, sectionHref, type LawChunk, type RefLink } from "../api/laws";
import { useAuth, useLibrary } from "../app/contexts";
import { PageTitle } from "../app/PageTitle";
import { Button } from "../design/components/Button";
import { Dialog, DialogContent } from "../design/components/Dialog";
import { Badge, Skeleton } from "../design/components/Display";
import { TextArea } from "../design/components/Field";
import { LawRef, LawText } from "../design/components/Legal";
import { useToast } from "../design/components/toastContext";
import { useLoad } from "../hooks/useLoad";
import { useI18n } from "../i18n";
import { isTyping } from "../lib/keys";
import { citation, unitName } from "../lib/lawText";
import { NotFound } from "./NotFound";

/** One section verbatim with its references, prev/next (also ← / →) and actions. */
export function LawSection() {
  const { t } = useI18n();
  const { chunkId = "" } = useParams();
  const navigate = useNavigate();
  const { me } = useAuth();
  const signedIn = Boolean(me?.user && !me.locked);
  const { result } = useLoad(`section-${chunkId}`, () => getSection(chunkId));
  const acts = useLoad("acts", listActs).result;
  const slugs = acts.status === "ok" ? acts.data : [];
  const href = (id: string) => sectionHref(id, actSlugOf(id, slugs));
  const view = result.status === "ok" ? result.data : null;

  useEffect(() => {
    if (!view) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.altKey || event.ctrlKey || event.metaKey || isTyping(event.target)) return;
      const target = { ArrowLeft: view.prev, ArrowRight: view.next }[event.key];
      if (target) {
        event.preventDefault();
        navigate(sectionHref(target, view.chunk.act_slug));
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [view, navigate]);

  useEffect(() => {
    if (signedIn && view) recordRead(view.chunk.chunk_id).catch(() => undefined);
  }, [signedIn, view]);

  if (result.status === "error")
    return result.notFound ? <NotFound /> : <p className="text-danger">{t("laws_error")}</p>;
  if (!view) return <Skeleton className="h-64 rounded-md" />;
  const { chunk } = view;
  const heading = [chunk.chapter, chunk.part].filter(Boolean).join(" — ");

  return (
    <article className="flex max-w-3xl flex-col gap-5">
      <div>
        <Link
          to={`/laws/${chunk.act_slug}`}
          className="inline-flex items-center gap-1 font-semibold text-brand underline underline-offset-3 hover:bg-highlight hover:text-ink"
        >
          <ChevronLeft aria-hidden="true" size={18} />
          {chunk.act}
        </Link>
        {heading && <p className="label-mono mt-2 text-accent">{heading}</p>}
        <PageTitle className="mt-1">{`${unitName(t, chunk.unit_type, chunk.section_num)} — ${chunk.section_title}`}</PageTitle>
        <p className="mt-1 flex flex-wrap items-center gap-2 text-sm text-ink-muted">
          <span>{t("laws_page", { page: chunk.page })}</span>
          {chunk.repealed && <Badge>{t("laws_repealed")}</Badge>}
        </p>
      </div>

      <Actions chunk={chunk} signedIn={signedIn} />

      <div className="border-l-[6px] border-ink bg-raised py-4 pr-4 pl-5 sm:pl-7">
        <LawText className="whitespace-pre-line">{chunk.text}</LawText>
      </div>

      <RefList title={t("laws_refs_out")} links={view.refs_out} href={href} />
      <RefList title={t("laws_refs_in")} links={view.refs_in} href={href} />

      <nav
        aria-label={t("laws_prev_next")}
        className="flex flex-wrap justify-between gap-3 border-t border-line-subtle pt-4"
      >
        {view.prev ? (
          <Link
            to={sectionHref(view.prev, chunk.act_slug)}
            rel="prev"
            className="inline-flex items-center gap-1 font-semibold text-brand"
          >
            <ChevronLeft aria-hidden="true" size={18} />
            {t("laws_prev")}
          </Link>
        ) : (
          <span />
        )}
        {view.next && (
          <Link
            to={sectionHref(view.next, chunk.act_slug)}
            rel="next"
            className="inline-flex items-center gap-1 font-semibold text-brand"
          >
            {t("laws_next")}
            <ChevronRight aria-hidden="true" size={18} />
          </Link>
        )}
      </nav>
    </article>
  );
}

function RefList({ title, links, href }: { title: string; links: RefLink[]; href: (id: string) => string }) {
  if (!links.length) return null;
  return (
    <section aria-label={title}>
      <h2 className="mb-2 font-display-style text-xl text-ink">{title}</h2>
      <ul className="flex flex-wrap gap-x-4 gap-y-2">
        {links.map((link) => (
          <li key={link.label}>
            {link.chunk_id ? (
              <LawRef href={href(link.chunk_id)}>{link.label}</LawRef>
            ) : (
              <span className="text-ink-muted">{link.label}</span>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

function Actions({ chunk, signedIn }: { chunk: LawChunk; signedIn: boolean }) {
  const { t } = useI18n();
  const toast = useToast();
  const navigate = useNavigate();
  const { bump } = useLibrary();
  const [noteOpen, setNoteOpen] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const bookmarks = useLoad(signedIn ? "bookmarks-saved" : null, () => listBookmarks()).result;
  const saved = useMemo(
    () => bookmarks.status === "ok" && bookmarks.data.items.some((b) => b.chunk_id === chunk.chunk_id),
    [bookmarks, chunk.chunk_id],
  );
  const canSpeak = typeof window !== "undefined" && "speechSynthesis" in window;
  const cite = citation(t, chunk);

  useEffect(
    () => () => {
      if (canSpeak) window.speechSynthesis.cancel();
    },
    [canSpeak, chunk.chunk_id],
  );

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(cite);
      toast({ title: t("copied"), tone: "success" });
    } catch {
      toast({ title: t("copy_failed"), tone: "danger" });
    }
  };
  const bookmark = () =>
    void addBookmark(chunk.chunk_id).then(
      () => {
        bump();
        toast({ title: t("bookmarked"), tone: "success" });
      },
      () => toast({ title: t("library_error"), tone: "danger" }),
    );
  const speak = () => {
    if (speaking) {
      window.speechSynthesis.cancel();
      setSpeaking(false);
      return;
    }
    const utterance = new SpeechSynthesisUtterance(`${cite}. ${chunk.text}`);
    utterance.lang = "en";
    utterance.onend = () => setSpeaking(false);
    window.speechSynthesis.speak(utterance);
    setSpeaking(true);
  };

  return (
    <div className="flex flex-wrap gap-2">
      <Button
        variant="primary"
        icon={<MessageSquare size={18} />}
        onClick={() => navigate("/", { state: { prefill: `${cite}: ` } })}
      >
        {t("laws_ask_about")}
      </Button>
      <Button icon={<Copy size={18} />} onClick={() => void copy()}>
        {t("laws_copy_citation")}
      </Button>
      {signedIn && (
        <Button icon={saved ? <BookmarkCheck size={18} /> : <Bookmark size={18} />} disabled={saved} onClick={bookmark}>
          {t(saved ? "bookmarked" : "bookmark_source")}
        </Button>
      )}
      {signedIn && (
        <Button icon={<StickyNote size={18} />} onClick={() => setNoteOpen(true)}>
          {t("add_note")}
        </Button>
      )}
      {canSpeak && (
        <Button icon={speaking ? <VolumeX size={18} /> : <Volume2 size={18} />} aria-pressed={speaking} onClick={speak}>
          {t(speaking ? "laws_stop_reading" : "laws_read_aloud")}
        </Button>
      )}
      <Dialog open={noteOpen} onOpenChange={setNoteOpen}>
        {noteOpen && <NoteForm chunkId={chunk.chunk_id} title={cite} onDone={() => setNoteOpen(false)} />}
      </Dialog>
    </div>
  );
}

function NoteForm({ chunkId, title, onDone }: { chunkId: string; title: string; onDone: () => void }) {
  const { t } = useI18n();
  const toast = useToast();
  const { bump } = useLibrary();
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!text.trim()) return;
    setBusy(true);
    try {
      await createNote({ body: text, target_kind: "chunk", target_id: chunkId });
      bump();
      toast({ title: t("note_saved"), tone: "success" });
      onDone();
    } catch {
      toast({ title: t("library_error"), tone: "danger" });
      setBusy(false);
    }
  };
  return (
    <DialogContent title={t("add_note")} description={title} closeLabel={t("close")}>
      <form onSubmit={submit} className="flex flex-col gap-3">
        <TextArea label={t("note_label")} value={text} onChange={(e) => setText(e.target.value)} className="min-h-28" />
        <Button type="submit" variant="primary" disabled={busy || !text.trim()} className="self-start">
          {t("save")}
        </Button>
      </form>
    </DialogContent>
  );
}
