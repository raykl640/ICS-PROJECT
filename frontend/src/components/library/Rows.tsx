import { Bookmark as BookmarkIcon, FileText, MessageSquare, StickyNote } from "lucide-react";
import { type ReactNode, useState } from "react";
import { Link } from "react-router";
import {
  type Bookmark,
  type ConversationSummary,
  deleteBookmark,
  deleteConversation,
  deleteLetter,
  deleteNote,
  type LetterSummary,
  type Note,
  patchBookmark,
  patchConversation,
  putLetter,
  putNote,
} from "../../api/library";
import { useLibrary } from "../../app/contexts";
import { Button } from "../../design/components/Button";
import { Badge } from "../../design/components/Display";
import { TextArea } from "../../design/components/Field";
import { useI18n } from "../../i18n";
import { formatDateTime } from "../../lib/dates";
import { ItemMenu } from "./ItemMenu";

/** Removes an item with an Undo toast (from useUndoDelete). */
export type Remove = (id: string, del: () => Promise<unknown>) => void;

function Row({ icon, children, menu }: { icon: ReactNode; children: ReactNode; menu: ReactNode }) {
  return (
    <li className="flex items-start gap-3 border-t border-line bg-transparent py-3 sm:py-4">
      <span aria-hidden="true" className="mt-0.5 shrink-0 text-ink-muted">
        {icon}
      </span>
      <div className="min-w-0 flex-1">{children}</div>
      <div className="-my-1 shrink-0">{menu}</div>
    </li>
  );
}

function Meta({ children }: { children: ReactNode }) {
  return <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-ink-muted">{children}</p>;
}

const LINK = "font-semibold text-ink underline-offset-3 hover:underline";

export function ChatRow({ chat, remove }: { chat: ConversationSummary; remove: Remove }) {
  const { t, language } = useI18n();
  const { bump } = useLibrary();
  const patch = async (change: Parameters<typeof patchConversation>[1]) => {
    await patchConversation(chat.id, change);
    bump();
  };
  return (
    <Row
      icon={<MessageSquare size={20} />}
      menu={
        <ItemMenu
          title={chat.title}
          pinned={chat.pinned}
          onPin={(pinned) => void patch({ pinned })}
          onRename={(title) => patch({ title })}
          matterId={chat.matter_id}
          onMove={(matter_id) => patch({ matter_id })}
          onDelete={() => remove(chat.id, () => deleteConversation(chat.id))}
        />
      }
    >
      <Link to={`/ask/${chat.id}`} className={LINK}>
        {chat.title}
      </Link>
      <Meta>
        {chat.pinned && <Badge tone="brand">{t("pinned_badge")}</Badge>}
        {chat.turns === 0 ? (
          <Badge tone="info">{t("answer_in_progress")}</Badge>
        ) : (
          <span>{t("turns_count", { count: chat.turns })}</span>
        )}
        <span>{chat.lang.toUpperCase()}</span>
        <span>{t("changed_on", { date: formatDateTime(chat.updated_at, language) })}</span>
      </Meta>
    </Row>
  );
}

export function LetterRow({ letter, remove }: { letter: LetterSummary; remove: Remove }) {
  const { t, language } = useI18n();
  const { bump } = useLibrary();
  const patch = async (change: Parameters<typeof putLetter>[1]) => {
    await putLetter(letter.id, change);
    bump();
  };
  return (
    <Row
      icon={<FileText size={20} />}
      menu={
        <ItemMenu
          title={letter.title}
          pinned={letter.pinned}
          onPin={(pinned) => void patch({ pinned })}
          onRename={(title) => patch({ title })}
          matterId={letter.matter_id}
          onMove={(matter_id) => patch({ matter_id })}
          onDelete={() => remove(letter.id, () => deleteLetter(letter.id))}
        />
      }
    >
      <Link to={`/letters/${letter.id}`} className={LINK}>
        {letter.title}
      </Link>
      {letter.preview && <p className="mt-1 line-clamp-2 text-ink-muted">{letter.preview}</p>}
      <Meta>
        {letter.pinned && <Badge tone="brand">{t("pinned_badge")}</Badge>}
        <span>{t("version_label", { n: letter.version })}</span>
        <span>{t("changed_on", { date: formatDateTime(letter.updated_at, language) })}</span>
      </Meta>
    </Row>
  );
}

/** "Sample Act — s. 4: Title" (empty act: the section is no longer in the corpus). */
function bookmarkLabel(bookmark: Bookmark): string {
  const mark = bookmark.unit_type === "article" ? "Art." : bookmark.unit_type === "schedule" ? "" : "s.";
  const unit = [mark, bookmark.section_num].filter(Boolean).join(" ");
  return bookmark.act ? `${bookmark.act} — ${unit}: ${bookmark.section_title}` : bookmark.chunk_id;
}

export function BookmarkRow({ bookmark, remove }: { bookmark: Bookmark; remove: Remove }) {
  const { language } = useI18n();
  const { bump } = useLibrary();
  const label = bookmarkLabel(bookmark);
  return (
    <Row
      icon={<BookmarkIcon size={20} />}
      menu={
        <ItemMenu
          title={label}
          matterId={bookmark.matter_id}
          onMove={async (matter_id) => {
            await patchBookmark(bookmark.id, { matter_id });
            bump();
          }}
          onDelete={() => remove(bookmark.id, () => deleteBookmark(bookmark.id))}
        />
      }
    >
      <p className="font-semibold text-ink">{label}</p>
      <Meta>
        <span>{formatDateTime(bookmark.created_at, language)}</span>
      </Meta>
    </Row>
  );
}

export function NoteRow({ note, remove }: { note: Note; remove: Remove }) {
  const { t, language } = useI18n();
  const { bump } = useLibrary();
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(note.body);
  const save = async () => {
    await putNote(note.id, { body: text });
    setEditing(false);
    bump();
  };
  const firstLine = note.body.split("\n", 1)[0];
  return (
    <Row
      icon={<StickyNote size={20} />}
      menu={
        <ItemMenu
          title={firstLine}
          matterId={note.matter_id}
          onMove={async (matter_id) => {
            await putNote(note.id, { matter_id });
            bump();
          }}
          onDelete={() => remove(note.id, () => deleteNote(note.id))}
        />
      }
    >
      {editing ? (
        <div className="flex flex-col gap-2">
          <TextArea label={t("note_label")} value={text} onChange={(e) => setText(e.target.value)} />
          <div className="flex gap-2">
            <Button variant="primary" onClick={() => void save()} disabled={!text.trim()}>
              {t("save")}
            </Button>
            <Button onClick={() => (setEditing(false), setText(note.body))}>{t("cancel")}</Button>
          </div>
        </div>
      ) : (
        <>
          <p className="whitespace-pre-wrap text-ink">{note.body}</p>
          <Meta>
            <span>{t("changed_on", { date: formatDateTime(note.updated_at, language) })}</span>
            <Button variant="ghost" className="-my-2" onClick={() => setEditing(true)}>
              {t("edit")}
            </Button>
          </Meta>
        </>
      )}
    </Row>
  );
}
