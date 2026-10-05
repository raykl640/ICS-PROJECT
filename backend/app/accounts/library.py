"""The signed-in user's library: conversations and turns, letters with versions, matters, bookmarks and notes.

Rows are decrypted in memory and searched, filtered, sorted and paged there (DESIGN_V2: hundreds of rows per user).
Every id belongs to one user; another user's id is answered exactly like an unknown one (404).
"""

import base64
import binascii
import json
import time
import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any, Generic, Literal, Protocol, TypeVar

from pydantic import BaseModel

from backend.app.accounts import library_repo as repo
from backend.app.accounts.db import Database
from backend.app.accounts.service import AccountError
from backend.app.config import Settings
from backend.app.models import CitationCheck, LegalChunk, SourceChunk, UserLanguage
from backend.app.security import strip_invisible, strip_invisible_block

T = TypeVar("T")


class _Dated(Protocol):
    """What the library sort needs of a row."""

    @property
    def id(self) -> str: ...
    @property
    def created_at(self) -> str: ...
    @property
    def updated_at(self) -> str: ...


R = TypeVar("R", bound=_Dated)
SortKey = Literal["updated", "created", "title"]
NoteTarget = Literal["none", "conversation", "letter", "chunk", "matter"]
MatterStatus = Literal["open", "closed"]
NO_MATTER = "none"
ChunkLookup = Callable[[str], LegalChunk | None]


class Page(BaseModel, Generic[T]):
    """One page of a list; pass next_cursor back to get the following page (null on the last one)."""

    items: list[T]
    next_cursor: str | None


class Sections(BaseModel):
    """The three answer sections in the user's language."""

    rights: str = ""
    steps: str = ""
    letter: str = ""


class TurnOut(BaseModel):
    """A saved question and answer, with its sources resolved to verbatim sections."""

    id: str
    idx: int
    question: str
    sections: Sections
    null_response: bool
    lang: UserLanguage
    citation_check: CitationCheck
    format_ok: bool
    warnings: list[str]
    untranslated: list[str]
    sources: list[SourceChunk]
    session_id: str | None
    created_at: str


class ConversationOut(BaseModel):
    """A conversation in a list."""

    id: str
    title: str
    pinned: bool
    matter_id: str | None
    lang: UserLanguage
    acts: list[str]
    turns: int
    created_at: str
    updated_at: str


class ConversationDetail(ConversationOut):
    """A conversation with its turns, oldest first."""

    thread: list[TurnOut]


class LetterOut(BaseModel):
    """A letter in a list (preview = start of the latest text)."""

    id: str
    title: str
    pinned: bool
    matter_id: str | None
    conversation_id: str | None
    version: int
    preview: str
    created_at: str
    updated_at: str


class LetterDetail(LetterOut):
    """A letter with its latest text."""

    body: str


class VersionOut(BaseModel):
    """A kept version of a letter."""

    n: int
    body: str
    created_at: str


class MatterOut(BaseModel):
    """A matter (case folder)."""

    id: str
    name: str
    status: MatterStatus
    created_at: str
    updated_at: str


class BookmarkOut(BaseModel):
    """A saved section; act/num/title are empty if the corpus no longer has it."""

    id: str
    chunk_id: str
    act: str
    unit_type: str
    section_num: str
    section_title: str
    matter_id: str | None
    created_at: str


class ReadOut(BaseModel):
    """A recently opened section (only ones still in the corpus are listed)."""

    chunk_id: str
    act: str
    unit_type: str
    section_num: str
    section_title: str
    at: str


class NoteOut(BaseModel):
    """A note."""

    id: str
    target_kind: NoteTarget
    target_id: str | None
    body: str
    matter_id: str | None
    created_at: str
    updated_at: str


class MatterDetail(MatterOut):
    """A matter with everything filed in it."""

    conversations: list[ConversationOut]
    letters: list[LetterOut]
    bookmarks: list[BookmarkOut]
    notes: list[NoteOut]


@dataclass(frozen=True)
class ListQuery:
    """Search, filters, sort and page position for a library list."""

    q: str = ""
    matter: str | None = None
    lang: UserLanguage | None = None
    act: str | None = None
    pinned: bool | None = None
    date_from: str | None = None
    date_to: str | None = None
    sort: SortKey = "updated"
    cursor: str | None = None
    limit: int | None = None


@dataclass(frozen=True)
class NewTurn:
    """A finished answer to save."""

    question: str
    question_en: str
    lang: UserLanguage
    sections: Sections
    answer_en: str
    sources: list[tuple[str, float | None]]
    acts: list[str]
    citation_check: CitationCheck
    format_ok: bool
    warnings: list[str]
    truncated_chunks: list[str]
    untranslated: list[str]
    null_response: bool
    session_id: str


def not_found(kind: str) -> AccountError:
    """The 404 for an unknown or someone else's id."""
    return AccountError(404, f"{kind}_not_found", "Not found. It may have been deleted.")


def _clean_line(text: str, limit: int) -> str:
    """One line of user text: invisible characters removed, whitespace collapsed, capped."""
    return " ".join(strip_invisible(text).split())[:limit]


def _clean_block(text: str, limit: int, kind: str) -> str:
    """Multi-line user text: invisible characters removed, line breaks kept; 422 when longer than limit."""
    cleaned = strip_invisible_block(text)
    if len(cleaned) > limit:
        raise AccountError(422, f"{kind}_too_long", f"That is longer than {limit} characters.")
    return cleaned


def title_from(question: str, limit: int) -> str:
    """Conversation title: the first question on one line, cut to limit characters (with an ellipsis)."""
    line = " ".join(question.split())
    return line if len(line) <= limit else line[: limit - 1].rstrip() + "…"


def _encode_cursor(last_id: str, offset: int) -> str:
    raw = json.dumps([last_id, offset]).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode_cursor(cursor: str) -> tuple[str, int]:
    try:
        last_id, offset = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
        return str(last_id), int(offset)
    except (binascii.Error, ValueError, TypeError) as exc:
        raise AccountError(422, "invalid_cursor", "The page cursor is not valid.") from exc


def paginate(items: list[T], ids: list[str], cursor: str | None, limit: int) -> Page[T]:
    """The page after cursor: it resumes after the last id seen, or at its offset if that row is gone."""
    start = 0
    if cursor:
        last_id, offset = _decode_cursor(cursor)
        start = ids.index(last_id) + 1 if last_id in ids else max(0, offset)
    end = start + limit
    page = items[start:end]
    more = end < len(items) and bool(page)
    return Page[T](items=page, next_cursor=_encode_cursor(ids[end - 1], end) if more else None)


def drain(fetch: Callable[[str | None], Page[T]]) -> list[T]:
    """Every item of a paged list, following next_cursor to the end."""
    items: list[T] = []
    cursor: str | None = None
    while True:
        page = fetch(cursor)
        items.extend(page.items)
        if page.next_cursor is None:
            return items
        cursor = page.next_cursor


def _matches(text_parts: Iterable[str], q: str) -> bool:
    """Case-insensitive substring search over the decrypted text."""
    needle = q.casefold().strip()
    return not needle or any(needle in part.casefold() for part in text_parts)


def _in_dates(created_at: str, query: ListQuery) -> bool:
    """Created on or after date_from and on or before date_to (YYYY-MM-DD, UTC)."""
    day = created_at[:10]
    return (not query.date_from or day >= query.date_from) and (not query.date_to or day <= query.date_to)


def _in_matter(matter_id: str | None, query: ListQuery) -> bool:
    """Filter by matter id, or NO_MATTER for unfiled items."""
    if query.matter is None:
        return True
    return matter_id is None if query.matter == NO_MATTER else matter_id == query.matter


class Library:
    """Library operations for one database; lookup resolves chunk ids against the loaded corpus."""

    def __init__(
        self, settings: Settings, db: Database, lookup: ChunkLookup, clock: Callable[[], float] = time.time
    ) -> None:
        self.settings = settings
        self.db = db
        self.lookup = lookup
        self.clock = clock

    def _now(self) -> str:
        return datetime.fromtimestamp(self.clock(), UTC).isoformat(timespec="seconds")

    def _limit(self, query: ListQuery) -> int:
        return min(query.limit or self.settings.library_page_size, self.settings.library_page_size)

    @staticmethod
    def _sorted(items: list[R], query: ListQuery, title: Callable[[R], str], pinned: Callable[[R], bool]) -> list[R]:
        """Pinned first, then by the chosen key (newest first for dates, A to Z for titles); ties by id."""
        ordered = sorted(items, key=lambda item: item.id)
        if query.sort == "updated":
            ordered.sort(key=lambda item: item.updated_at, reverse=True)
        elif query.sort == "created":
            ordered.sort(key=lambda item: item.created_at, reverse=True)
        else:
            ordered.sort(key=lambda item: title(item).casefold())
        ordered.sort(key=lambda item: not pinned(item))
        return ordered

    def _check_matter(self, conn: Any, user_id: str, matter_id: str | None) -> None:
        if matter_id is not None and not repo.owns(conn, "matters", matter_id, user_id):
            raise not_found("matter")

    # --- sources ------------------------------------------------------------------------------------------------

    def _sources(self, refs: list[dict[str, Any]], truncated: list[str]) -> list[SourceChunk]:
        """Saved chunk ids as verbatim source cards (ids missing from a rebuilt corpus are skipped)."""
        cards = []
        for rank, ref in enumerate(refs, 1):
            chunk = self.lookup(str(ref["chunk_id"]))
            if chunk is None:
                continue
            cards.append(
                SourceChunk(
                    chunk_id=chunk.chunk_id,
                    act=chunk.act,
                    unit_type=chunk.unit_type,
                    section_num=chunk.section_num,
                    section_title=chunk.section_title,
                    part=chunk.part,
                    page=chunk.page,
                    text=chunk.text,
                    truncated=chunk.chunk_id in truncated,
                    rank=rank,
                )
            )
        return cards

    # --- conversations ------------------------------------------------------------------------------------------

    def create_conversation(self, user_id: str, dek: bytes, question: str, lang: UserLanguage) -> str:
        """A new conversation titled after its first question."""
        conversation_id = str(uuid.uuid4())
        title = title_from(question, self.settings.title_max_chars)
        with self.db.write() as conn:
            repo.insert_conversation(conn, repo.Box(dek), user_id, conversation_id, title, lang, self._now())
        return conversation_id

    def earlier_questions(self, user_id: str, dek: bytes, conversation_id: str) -> list[str]:
        """English questions of the last followup_context_turns turns (404 if not the user's conversation)."""
        box = repo.Box(dek)
        with self.db.read() as conn:
            if repo.conversation(conn, box, user_id, conversation_id) is None:
                raise not_found("conversation")
            rows = repo.turns(conn, box, conversation_id)
        n = self.settings.followup_context_turns
        return [str(t.meta.get("question_en", "")) for t in rows[-n:]] if n else []

    def add_turn(self, user_id: str, dek: bytes, conversation_id: str, turn: NewTurn) -> str:
        """Save a finished turn at the end of the conversation (404 if it was deleted meanwhile)."""
        content = repo.TurnContent(
            question=turn.question,
            answer={"sections": turn.sections.model_dump(), "answer_en": turn.answer_en},
            sources=[{"chunk_id": cid, "score": score} for cid, score in turn.sources],
            meta={
                "question_en": turn.question_en,
                "lang": turn.lang,
                "acts": turn.acts,
                "citation_check": turn.citation_check.model_dump(),
                "format_ok": turn.format_ok,
                "warnings": turn.warnings,
                "truncated_chunks": turn.truncated_chunks,
                "untranslated": turn.untranslated,
                "session_id": turn.session_id,
            },
            null_response=turn.null_response,
        )
        turn_id = str(uuid.uuid4())
        with self.db.write() as conn:
            if not repo.owns(conn, "conversations", conversation_id, user_id):
                raise not_found("conversation")
            repo.insert_turn(conn, repo.Box(dek), conversation_id, turn_id, content, self._now())
        return turn_id

    def drop_if_empty(self, user_id: str, conversation_id: str) -> None:
        """Delete a conversation whose first answer never finished."""
        with self.db.write() as conn:
            if repo.turn_count(conn, conversation_id) == 0:
                repo.delete_conversation(conn, user_id, conversation_id)

    def _turn_out(self, row: repo.TurnRow) -> TurnOut:
        meta = row.meta
        return TurnOut(
            id=row.id,
            idx=row.idx,
            question=row.question,
            sections=Sections(**row.answer.get("sections", {})),
            null_response=row.null_response,
            lang=meta.get("lang", "en"),
            citation_check=CitationCheck(**meta.get("citation_check", {})),
            format_ok=bool(meta.get("format_ok", True)),
            warnings=list(meta.get("warnings", [])),
            untranslated=list(meta.get("untranslated", [])),
            sources=self._sources(row.sources, list(meta.get("truncated_chunks", []))),
            session_id=meta.get("session_id"),
            created_at=row.created_at,
        )

    @staticmethod
    def _conversation_out(row: repo.ConversationRow, turns: list[repo.TurnRow]) -> ConversationOut:
        acts = list(dict.fromkeys(act for t in turns for act in t.meta.get("acts", [])))
        return ConversationOut(
            id=row.id,
            title=row.title,
            pinned=row.pinned,
            matter_id=row.matter_id,
            lang="sw" if row.lang == "sw" else "en",
            acts=acts,
            turns=len(turns),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _all_conversations(self, conn: Any, box: repo.Box, user_id: str) -> list[tuple[ConversationOut, list[str]]]:
        """Every conversation with its searchable text (title, questions, answer sections)."""
        grouped = repo.all_turns(conn, box, user_id)
        result = []
        for row in repo.conversations(conn, box, user_id):
            turns = grouped.get(row.id, [])
            text = [row.title]
            for t in turns:
                text.append(t.question)
                text.extend(str(v) for v in t.answer.get("sections", {}).values())
            result.append((self._conversation_out(row, turns), text))
        return result

    def list_conversations(self, user_id: str, dek: bytes, query: ListQuery) -> Page[ConversationOut]:
        """Search, filter, sort and page the user's conversations."""
        with self.db.read() as conn:
            rows = self._all_conversations(conn, repo.Box(dek), user_id)
        kept = [
            c
            for c, text in rows
            if _matches(text, query.q)
            and _in_matter(c.matter_id, query)
            and _in_dates(c.created_at, query)
            and (query.lang is None or c.lang == query.lang)
            and (query.act is None or query.act in c.acts)
            and (query.pinned is None or c.pinned == query.pinned)
        ]
        ordered = self._sorted(kept, query, lambda c: c.title, lambda c: c.pinned)
        return paginate(ordered, [c.id for c in ordered], query.cursor, self._limit(query))

    def conversation(self, user_id: str, dek: bytes, conversation_id: str) -> ConversationDetail:
        """One conversation with its thread."""
        box = repo.Box(dek)
        with self.db.read() as conn:
            row = repo.conversation(conn, box, user_id, conversation_id)
            if row is None:
                raise not_found("conversation")
            turns = repo.turns(conn, box, conversation_id)
        summary = self._conversation_out(row, turns)
        return ConversationDetail(**summary.model_dump(), thread=[self._turn_out(t) for t in turns])

    def update_conversation(
        self, user_id: str, dek: bytes, conversation_id: str, changes: dict[str, Any]
    ) -> ConversationDetail:
        """Rename, pin/unpin or file into a matter (matter_id None = unfile)."""
        values: dict[str, object] = {}
        if "title" in changes:
            title = _clean_line(str(changes["title"]), self.settings.title_max_chars)
            if not title:
                raise AccountError(422, "empty_title", "The title is empty.")
            values["title"] = title
        if "pinned" in changes:
            values["pinned"] = int(bool(changes["pinned"]))
        with self.db.write() as conn:
            if not repo.owns(conn, "conversations", conversation_id, user_id):
                raise not_found("conversation")
            if "matter_id" in changes:
                self._check_matter(conn, user_id, changes["matter_id"])
                values["matter_id"] = changes["matter_id"]
            if values:
                repo.update_conversation(conn, repo.Box(dek), user_id, conversation_id, values)
        return self.conversation(user_id, dek, conversation_id)

    def delete_conversation(self, user_id: str, conversation_id: str) -> None:
        """Delete a conversation and its turns (letters made from it stay)."""
        with self.db.write() as conn:
            if not repo.delete_conversation(conn, user_id, conversation_id):
                raise not_found("conversation")

    # --- letters ------------------------------------------------------------------------------------------------

    @staticmethod
    def _letter_out(row: repo.LetterRow, latest: repo.VersionRow | None) -> LetterOut:
        body = latest.body if latest else ""
        return LetterOut(
            id=row.id,
            title=row.title,
            pinned=row.pinned,
            matter_id=row.matter_id,
            conversation_id=row.conversation_id,
            version=latest.n if latest else 0,
            preview=" ".join(body.split())[:160],
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _letter_from_turn(self, conn: Any, box: repo.Box, user_id: str, turn_id: str) -> tuple[str, str]:
        """(conversation id, letter section) of one of the user's turns."""
        row = conn.execute(
            "SELECT t.conversation_id FROM turns t JOIN conversations c ON c.id = t.conversation_id "
            "WHERE t.id = ? AND c.user_id = ?",
            (turn_id, user_id),
        ).fetchone()
        if row is None:
            raise not_found("turn")
        turn = next(t for t in repo.turns(conn, box, row["conversation_id"]) if t.id == turn_id)
        return row["conversation_id"], str(turn.answer.get("sections", {}).get("letter", ""))

    def create_letter(
        self,
        user_id: str,
        dek: bytes,
        title: str,
        body: str,
        turn_id: str | None = None,
        matter_id: str | None = None,
    ) -> LetterDetail:
        """A new letter: blank, the given text, or the letter section of a saved answer (turn_id)."""
        box = repo.Box(dek)
        letter_id = str(uuid.uuid4())
        now = self._now()
        conversation_id = None
        text = _clean_block(body, self.settings.letter_max_chars, "letter")
        with self.db.write() as conn:
            self._check_matter(conn, user_id, matter_id)
            if turn_id is not None:
                conversation_id, text = self._letter_from_turn(conn, box, user_id, turn_id)
            name = _clean_line(title, self.settings.title_max_chars) or "Letter"
            row = repo.LetterRow(letter_id, matter_id, conversation_id, name, False, now, now)
            repo.insert_letter(conn, box, user_id, row, now)
            repo.insert_version(conn, box, letter_id, str(uuid.uuid4()), text, now, self.settings.letter_versions_max)
        return self.letter(user_id, dek, letter_id)

    def list_letters(self, user_id: str, dek: bytes, query: ListQuery) -> Page[LetterOut]:
        """Search, filter, sort and page the user's letters."""
        box = repo.Box(dek)
        with self.db.read() as conn:
            latest = repo.latest_versions(conn, box, user_id)
            rows = repo.letters(conn, box, user_id)
        kept = [
            self._letter_out(row, latest.get(row.id))
            for row in rows
            if _matches([row.title, latest[row.id].body if row.id in latest else ""], query.q)
            and _in_matter(row.matter_id, query)
            and _in_dates(row.created_at, query)
            and (query.pinned is None or row.pinned == query.pinned)
        ]
        ordered = self._sorted(kept, query, lambda r: r.title, lambda r: r.pinned)
        return paginate(ordered, [r.id for r in ordered], query.cursor, self._limit(query))

    def letter(self, user_id: str, dek: bytes, letter_id: str) -> LetterDetail:
        """One letter with its latest text."""
        box = repo.Box(dek)
        with self.db.read() as conn:
            row = repo.letter(conn, box, user_id, letter_id)
            if row is None:
                raise not_found("letter")
            kept = repo.versions(conn, box, letter_id)
        latest = kept[0] if kept else None
        return LetterDetail(**self._letter_out(row, latest).model_dump(), body=latest.body if latest else "")

    def update_letter(self, user_id: str, dek: bytes, letter_id: str, changes: dict[str, Any]) -> LetterDetail:
        """Save new text (a new version, if it changed), rename, pin or file the letter."""
        box = repo.Box(dek)
        values: dict[str, object] = {}
        if "title" in changes:
            title = _clean_line(str(changes["title"]), self.settings.title_max_chars)
            if not title:
                raise AccountError(422, "empty_title", "The title is empty.")
            values["title"] = title
        if "pinned" in changes:
            values["pinned"] = int(bool(changes["pinned"]))
        body = (
            _clean_block(str(changes["body"]), self.settings.letter_max_chars, "letter") if "body" in changes else None
        )
        with self.db.write() as conn:
            if not repo.owns(conn, "letters", letter_id, user_id):
                raise not_found("letter")
            if "matter_id" in changes:
                self._check_matter(conn, user_id, changes["matter_id"])
                values["matter_id"] = changes["matter_id"]
            if values:
                repo.update_letter(conn, box, user_id, letter_id, values | {"updated_at": self._now()})
            current = repo.versions(conn, box, letter_id)
            if body is not None and (not current or current[0].body != body):
                now = self._now()
                repo.insert_version(
                    conn, box, letter_id, str(uuid.uuid4()), body, now, self.settings.letter_versions_max
                )
        return self.letter(user_id, dek, letter_id)

    def versions(self, user_id: str, dek: bytes, letter_id: str) -> list[VersionOut]:
        """Kept versions, newest first."""
        box = repo.Box(dek)
        with self.db.read() as conn:
            if not repo.owns(conn, "letters", letter_id, user_id):
                raise not_found("letter")
            rows = repo.versions(conn, box, letter_id)
        return [VersionOut(n=v.n, body=v.body, created_at=v.created_at) for v in rows]

    def restore_version(self, user_id: str, dek: bytes, letter_id: str, n: int) -> LetterDetail:
        """Make an older version the newest one (saved as a new version, so nothing is lost)."""
        old = next((v for v in self.versions(user_id, dek, letter_id) if v.n == n), None)
        if old is None:
            raise not_found("version")
        return self.update_letter(user_id, dek, letter_id, {"body": old.body})

    def delete_letter(self, user_id: str, letter_id: str) -> None:
        """Delete a letter and its versions."""
        with self.db.write() as conn:
            if not repo.delete_letter(conn, user_id, letter_id):
                raise not_found("letter")

    # --- matters ------------------------------------------------------------------------------------------------

    @staticmethod
    def _matter_out(row: repo.MatterRow) -> MatterOut:
        status: MatterStatus = "closed" if row.status == "closed" else "open"
        return MatterOut(id=row.id, name=row.name, status=status, created_at=row.created_at, updated_at=row.updated_at)

    def _matter_name(self, name: str) -> str:
        clean = _clean_line(name, self.settings.matter_name_max_chars)
        if not clean:
            raise AccountError(422, "empty_name", "Give the matter a name.")
        return clean

    def list_matters(self, user_id: str, dek: bytes, query: ListQuery) -> Page[MatterOut]:
        """Search, sort and page the user's matters (open ones first, as if pinned)."""
        with self.db.read() as conn:
            rows = repo.matters(conn, repo.Box(dek), user_id)
        kept = [self._matter_out(row) for row in rows if _matches([row.name], query.q)]
        ordered = self._sorted(kept, query, lambda m: m.name, lambda m: m.status == "open")
        return paginate(ordered, [m.id for m in ordered], query.cursor, self._limit(query))

    def create_matter(self, user_id: str, dek: bytes, name: str) -> MatterOut:
        """A new open matter."""
        matter_id = str(uuid.uuid4())
        with self.db.write() as conn:
            repo.insert_matter(conn, repo.Box(dek), user_id, matter_id, self._matter_name(name), self._now())
        return self._get_matter(user_id, dek, matter_id)

    def _get_matter(self, user_id: str, dek: bytes, matter_id: str) -> MatterOut:
        with self.db.read() as conn:
            row = repo.matter(conn, repo.Box(dek), user_id, matter_id)
        if row is None:
            raise not_found("matter")
        return self._matter_out(row)

    def matter(self, user_id: str, dek: bytes, matter_id: str) -> MatterDetail:
        """A matter with its conversations, letters, bookmarks and notes."""
        summary = self._get_matter(user_id, dek, matter_id)
        q = ListQuery(matter=matter_id)
        return MatterDetail(
            **summary.model_dump(),
            conversations=drain(lambda c: self.list_conversations(user_id, dek, replace(q, cursor=c))),
            letters=drain(lambda c: self.list_letters(user_id, dek, replace(q, cursor=c))),
            bookmarks=drain(lambda c: self.list_bookmarks(user_id, dek, replace(q, cursor=c))),
            notes=drain(lambda c: self.list_notes(user_id, dek, replace(q, cursor=c))),
        )

    def update_matter(
        self, user_id: str, dek: bytes, matter_id: str, name: str | None, status: MatterStatus | None
    ) -> MatterOut:
        """Rename and/or open/close a matter."""
        clean = self._matter_name(name) if name is not None else None
        with self.db.write() as conn:
            if not repo.owns(conn, "matters", matter_id, user_id):
                raise not_found("matter")
            repo.update_matter(conn, repo.Box(dek), user_id, matter_id, self._now(), clean, status)
        return self._get_matter(user_id, dek, matter_id)

    def delete_matter(self, user_id: str, matter_id: str) -> None:
        """Delete a matter; what was filed in it stays in the library."""
        with self.db.write() as conn:
            if not repo.delete_matter(conn, user_id, matter_id):
                raise not_found("matter")

    # --- bookmarks ----------------------------------------------------------------------------------------------

    def _bookmark_out(self, row: repo.BookmarkRow) -> BookmarkOut:
        chunk = self.lookup(row.chunk_id)
        return BookmarkOut(
            id=row.id,
            chunk_id=row.chunk_id,
            act=chunk.act if chunk else "",
            unit_type=chunk.unit_type if chunk else "",
            section_num=chunk.section_num if chunk else "",
            section_title=chunk.section_title if chunk else "",
            matter_id=row.matter_id,
            created_at=row.created_at,
        )

    def list_bookmarks(self, user_id: str, dek: bytes, query: ListQuery) -> Page[BookmarkOut]:
        """Search, filter and page the user's bookmarks (newest first)."""
        with self.db.read() as conn:
            rows = repo.bookmarks(conn, repo.Box(dek), user_id)
        kept = [
            b
            for b in map(self._bookmark_out, rows)
            if _matches([b.act, b.section_num, b.section_title, b.chunk_id], query.q)
            and _in_matter(b.matter_id, query)
            and _in_dates(b.created_at, query)
            and (query.act is None or b.chunk_id.startswith(f"{query.act}-"))
        ]
        ordered = sorted(sorted(kept, key=lambda b: b.id), key=lambda b: b.created_at, reverse=True)
        return paginate(ordered, [b.id for b in ordered], query.cursor, self._limit(query))

    def add_bookmark(self, user_id: str, dek: bytes, chunk_id: str, matter_id: str | None) -> BookmarkOut:
        """Bookmark a corpus section (the existing bookmark if it is already saved)."""
        if self.lookup(chunk_id) is None:
            raise not_found("section")
        box = repo.Box(dek)
        with self.db.write() as conn:
            self._check_matter(conn, user_id, matter_id)
            existing = next((b for b in repo.bookmarks(conn, box, user_id) if b.chunk_id == chunk_id), None)
            if existing is not None:
                return self._bookmark_out(existing)
            row = repo.BookmarkRow(str(uuid.uuid4()), chunk_id, matter_id, self._now())
            repo.insert_bookmark(conn, box, user_id, row)
        return self._bookmark_out(row)

    def move_bookmark(self, user_id: str, dek: bytes, bookmark_id: str, matter_id: str | None) -> BookmarkOut:
        """File a bookmark into a matter (None = unfile)."""
        box = repo.Box(dek)
        with self.db.write() as conn:
            if not repo.owns(conn, "bookmarks", bookmark_id, user_id):
                raise not_found("bookmark")
            self._check_matter(conn, user_id, matter_id)
            repo.update_bookmark(conn, user_id, bookmark_id, matter_id)
            row = next(b for b in repo.bookmarks(conn, box, user_id) if b.id == bookmark_id)
        return self._bookmark_out(row)

    def delete_bookmark(self, user_id: str, bookmark_id: str) -> None:
        """Remove a bookmark."""
        with self.db.write() as conn:
            if not repo.delete_bookmark(conn, user_id, bookmark_id):
                raise not_found("bookmark")

    # --- notes --------------------------------------------------------------------------------------------------

    @staticmethod
    def _note_out(row: repo.NoteRow) -> NoteOut:
        return NoteOut(
            id=row.id,
            target_kind=row.target_kind,
            target_id=row.target_id,
            body=row.body,
            matter_id=row.matter_id,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _check_target(self, conn: Any, user_id: str, kind: NoteTarget, target_id: str | None) -> None:
        """A note's target must be the user's own item or a corpus section ('none' has no target)."""
        if kind == "none":
            if target_id is not None:
                raise AccountError(422, "invalid_target", "A note without a target cannot name one.")
            return
        if target_id is None:
            raise AccountError(422, "invalid_target", "Say what the note is about.")
        if kind == "chunk":
            if self.lookup(target_id) is None:
                raise not_found("section")
        elif not repo.owns(conn, f"{kind}s", target_id, user_id):
            raise not_found(kind)

    def list_notes(self, user_id: str, dek: bytes, query: ListQuery) -> Page[NoteOut]:
        """Search, filter, sort and page the user's notes."""
        with self.db.read() as conn:
            rows = repo.notes(conn, repo.Box(dek), user_id)
        kept = [
            self._note_out(n)
            for n in rows
            if _matches([n.body], query.q) and _in_matter(n.matter_id, query) and _in_dates(n.created_at, query)
        ]
        ordered = self._sorted(kept, query, lambda n: n.body, lambda n: False)
        return paginate(ordered, [n.id for n in ordered], query.cursor, self._limit(query))

    def create_note(
        self, user_id: str, dek: bytes, body: str, kind: NoteTarget, target_id: str | None, matter_id: str | None
    ) -> NoteOut:
        """A new note."""
        text = _clean_block(body, self.settings.note_max_chars, "note")
        if not text.strip():
            raise AccountError(422, "empty_note", "The note is empty.")
        now = self._now()
        row = repo.NoteRow(str(uuid.uuid4()), kind, target_id, text, matter_id, now, now)
        with self.db.write() as conn:
            self._check_target(conn, user_id, kind, target_id)
            self._check_matter(conn, user_id, matter_id)
            repo.insert_note(conn, repo.Box(dek), user_id, row)
        return self._note_out(row)

    def update_note(self, user_id: str, dek: bytes, note_id: str, changes: dict[str, Any]) -> NoteOut:
        """Edit a note's text and/or matter."""
        box = repo.Box(dek)
        values: dict[str, object] = {"updated_at": self._now()}
        if "body" in changes:
            text = _clean_block(str(changes["body"]), self.settings.note_max_chars, "note")
            if not text.strip():
                raise AccountError(422, "empty_note", "The note is empty.")
            values["body"] = text
        with self.db.write() as conn:
            if not repo.owns(conn, "notes", note_id, user_id):
                raise not_found("note")
            if "matter_id" in changes:
                self._check_matter(conn, user_id, changes["matter_id"])
                values["matter_id"] = changes["matter_id"]
            repo.update_note(conn, box, user_id, note_id, values)
            row = next(n for n in repo.notes(conn, box, user_id) if n.id == note_id)
        return self._note_out(row)

    def delete_note(self, user_id: str, note_id: str) -> None:
        """Delete a note."""
        with self.db.write() as conn:
            if not repo.delete_note(conn, user_id, note_id):
                raise not_found("note")

    # --- export -------------------------------------------------------------------------------------------------

    def export(self, user_id: str, dek: bytes) -> dict[str, Any]:
        """Everything in the library, decrypted (for the account export)."""
        conversations = [
            self.conversation(user_id, dek, c.id).model_dump(exclude={"thread": {"__all__": {"sources"}}})
            for c in drain(lambda c: self.list_conversations(user_id, dek, ListQuery(cursor=c)))
        ]
        letters = [
            {**letter.model_dump(), "versions": [v.model_dump() for v in self.versions(user_id, dek, letter.id)]}
            for letter in drain(lambda c: self.list_letters(user_id, dek, ListQuery(cursor=c)))
        ]
        return {
            "conversations": conversations,
            "letters": letters,
            "matters": [m.model_dump() for m in drain(lambda c: self.list_matters(user_id, dek, ListQuery(cursor=c)))],
            "bookmarks": [
                b.model_dump() for b in drain(lambda c: self.list_bookmarks(user_id, dek, ListQuery(cursor=c)))
            ],
            "notes": [n.model_dump() for n in drain(lambda c: self.list_notes(user_id, dek, ListQuery(cursor=c)))],
            "reads": [r.model_dump() for r in self.recent_reads(user_id, dek, self.settings.reads_max)],
        }

    # --- recent reads -------------------------------------------------------------------------------------------

    def record_read(self, user_id: str, dek: bytes, chunk_id: str) -> None:
        """Move a section to the top of the user's recent reads, keeping the newest reads_max."""
        if self.lookup(chunk_id) is None:
            raise not_found("section")
        box = repo.Box(dek)
        with self.db.write() as conn:
            rows = repo.reads(conn, box, user_id)
            others = [r for r in rows if r.chunk_id != chunk_id]
            for row in [r for r in rows if r.chunk_id == chunk_id] + others[self.settings.reads_max - 1 :]:
                repo.delete_read(conn, user_id, row.id)
            repo.insert_read(conn, box, user_id, repo.ReadRow(str(uuid.uuid4()), chunk_id, self._now()))

    def recent_reads(self, user_id: str, dek: bytes, limit: int) -> list[ReadOut]:
        """The user's recent reads, newest first, skipping sections a rebuilt corpus no longer has."""
        with self.db.read() as conn:
            rows = repo.reads(conn, repo.Box(dek), user_id)
        out = []
        for row in rows:
            chunk = self.lookup(row.chunk_id)
            if chunk is not None:
                out.append(
                    ReadOut(
                        chunk_id=chunk.chunk_id,
                        act=chunk.act,
                        unit_type=chunk.unit_type,
                        section_num=chunk.section_num,
                        section_title=chunk.section_title,
                        at=row.at,
                    )
                )
        return out[:limit]
