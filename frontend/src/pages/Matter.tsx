import { FolderX, Trash2 } from "lucide-react";
import { type ReactNode, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { deleteMatter, getMatter, patchMatter } from "../api/library";
import { useLibrary } from "../app/contexts";
import { PageTitle } from "../app/PageTitle";
import { ItemMenu } from "../components/library/ItemMenu";
import { BookmarkRow, ChatRow, LetterRow, NoteRow } from "../components/library/Rows";
import { useUndoDelete } from "../components/library/useUndoDelete";
import { Button } from "../design/components/Button";
import { Dialog, DialogContent } from "../design/components/Dialog";
import { Badge, EmptyState, Notice } from "../design/components/Display";
import { useLoad } from "../hooks/useLoad";
import { useI18n } from "../i18n";
import { NewNote } from "./Library";

function Section({ title, count, children }: { title: string; count: number; children: ReactNode }) {
  const id = `matter-${title.toLowerCase().replace(/\W+/g, "-")}`;
  return (
    <section aria-labelledby={id} className="flex flex-col gap-3">
      <h2 id={id} className="font-display-style text-2xl text-ink">
        {title} <span className="text-base text-ink-muted">({count})</span>
      </h2>
      {children}
    </section>
  );
}

/** One matter (case folder): its status and everything filed in it. */
export function Matter() {
  const { t } = useI18n();
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const { bump } = useLibrary();
  const { result } = useLoad(`matter:${id}`, () => getMatter(id));
  const { hidden, remove } = useUndoDelete();
  const [confirming, setConfirming] = useState(false);

  if (result.status === "loading") return <p role="status">{t("loading")}</p>;
  if (result.status === "error") {
    return (
      <EmptyState icon={<FolderX size={32} />} title={t(result.notFound ? "matter_not_found" : "library_error")}>
        <Link to="/library" className="font-semibold text-brand underline underline-offset-3">
          {t("library_open")}
        </Link>
      </EmptyState>
    );
  }
  const matter = result.data;
  const open = matter.status === "open";
  const visible = <T extends { id: string }>(items: T[]) => items.filter((item) => !hidden.has(item.id));
  const chats = visible(matter.conversations);
  const letters = visible(matter.letters);
  const bookmarks = visible(matter.bookmarks);
  const notes = visible(matter.notes);
  const empty = chats.length + letters.length + bookmarks.length + notes.length === 0;

  const rename = async (name: string) => {
    await patchMatter(matter.id, { name });
    bump();
  };
  const toggle = async () => {
    await patchMatter(matter.id, { status: open ? "closed" : "open" });
    bump();
  };
  const destroy = async () => {
    await deleteMatter(matter.id);
    bump();
    navigate("/library");
  };

  return (
    <div className="flex max-w-4xl flex-col gap-8">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-ink-muted">{t("matters_title")}</p>
          <PageTitle>{matter.name}</PageTitle>
          <p className="mt-2">
            <Badge tone={open ? "success" : "neutral"}>{t(open ? "matter_open" : "matter_closed")}</Badge>
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button onClick={() => void toggle()}>{t(open ? "matter_close" : "matter_reopen")}</Button>
          <ItemMenu title={matter.name} onRename={rename} onDelete={() => setConfirming(true)} />
        </div>
      </div>
      {empty && <Notice tone="info">{t("matter_empty")}</Notice>}
      <Section title={t("library_tab_chats")} count={chats.length}>
        <ul className="flex flex-col gap-2">
          {chats.map((chat) => (
            <ChatRow key={chat.id} chat={chat} remove={remove} />
          ))}
        </ul>
      </Section>
      <Section title={t("library_tab_letters")} count={letters.length}>
        <ul className="flex flex-col gap-2">
          {letters.map((letter) => (
            <LetterRow key={letter.id} letter={letter} remove={remove} />
          ))}
        </ul>
      </Section>
      <Section title={t("library_tab_saved")} count={bookmarks.length}>
        <ul className="flex flex-col gap-2">
          {bookmarks.map((bookmark) => (
            <BookmarkRow key={bookmark.id} bookmark={bookmark} remove={remove} />
          ))}
        </ul>
      </Section>
      <Section title={t("library_tab_notes")} count={notes.length}>
        <NewNote matterId={matter.id} />
        <ul className="flex flex-col gap-2">
          {notes.map((note) => (
            <NoteRow key={note.id} note={note} remove={remove} />
          ))}
        </ul>
      </Section>
      {confirming && (
        <Dialog open onOpenChange={(next) => !next && setConfirming(false)}>
          <DialogContent title={t("matter_delete")} description={t("matter_delete_body")} closeLabel={t("dismiss")}>
            <div className="flex justify-end gap-2">
              <Button onClick={() => setConfirming(false)}>{t("cancel")}</Button>
              <Button variant="danger" icon={<Trash2 size={18} />} onClick={() => void destroy()}>
                {t("matter_delete")}
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
}
