"""Typed queries over the library tables (migration 002). Like repo.py, content is sealed here: callers pass plaintext
and a Box holding the user's data key; only ciphertext bound to table:column:row_id reaches SQLite. Every query is
scoped by user_id (turns and versions through their owning conversation or letter)."""

import json
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from backend.app.accounts.crypto import decrypt_field, encrypt_field, field_aad


@dataclass(frozen=True)
class Box:
    """Seals and opens one user's content fields."""

    dek: bytes

    def seal(self, table: str, column: str, row_id: str, value: str) -> bytes:
        """Ciphertext of value for that table, column and row."""
        return encrypt_field(self.dek, value, field_aad(table, column, row_id))

    def open(self, table: str, column: str, row_id: str, sealed: bytes) -> str:
        """Plaintext of a stored field (CryptoError if it was moved or altered)."""
        return decrypt_field(self.dek, sealed, field_aad(table, column, row_id))

    def seal_json(self, table: str, column: str, row_id: str, value: Any) -> bytes:
        """Ciphertext of value as JSON."""
        return self.seal(table, column, row_id, json.dumps(value, ensure_ascii=False))

    def open_json(self, table: str, column: str, row_id: str, sealed: bytes) -> Any:
        """A stored JSON field, decrypted and parsed."""
        return json.loads(self.open(table, column, row_id, sealed))


@dataclass(frozen=True)
class MatterRow:
    """A case folder."""

    id: str
    name: str
    status: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class ConversationRow:
    """A saved chat (its turns are read separately)."""

    id: str
    matter_id: str | None
    title: str
    pinned: bool
    lang: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class TurnRow:
    """One question and its finished answer."""

    id: str
    conversation_id: str
    idx: int
    question: str
    answer: dict[str, Any]
    sources: list[dict[str, Any]]
    meta: dict[str, Any]
    null_response: bool
    created_at: str


@dataclass(frozen=True)
class LetterRow:
    """A letter (its text lives in versions)."""

    id: str
    matter_id: str | None
    conversation_id: str | None
    title: str
    pinned: bool
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class VersionRow:
    """One saved text of a letter; n grows by one per save."""

    id: str
    n: int
    body: str
    created_at: str


@dataclass(frozen=True)
class BookmarkRow:
    """A saved law section."""

    id: str
    chunk_id: str
    matter_id: str | None
    created_at: str


@dataclass(frozen=True)
class NoteRow:
    """A note, optionally attached to a conversation, letter, section or matter."""

    id: str
    target_kind: str
    target_id: str | None
    body: str
    matter_id: str | None
    created_at: str
    updated_at: str


def _update(conn: sqlite3.Connection, table: str, row_id: str, user_id: str, values: Mapping[str, object]) -> None:
    """UPDATE the given columns of one row owned by user_id (column names come from this module, never from input)."""
    columns = ", ".join(f"{name} = ?" for name in values)
    conn.execute(f"UPDATE {table} SET {columns} WHERE id = ? AND user_id = ?", (*values.values(), row_id, user_id))


def _delete(conn: sqlite3.Connection, table: str, row_id: str, user_id: str) -> bool:
    """Delete one row owned by user_id; True if it existed."""
    return conn.execute(f"DELETE FROM {table} WHERE id = ? AND user_id = ?", (row_id, user_id)).rowcount > 0


def owns(conn: sqlite3.Connection, table: str, row_id: str, user_id: str) -> bool:
    """True if the row exists and belongs to user_id."""
    found = conn.execute(f"SELECT 1 FROM {table} WHERE id = ? AND user_id = ?", (row_id, user_id)).fetchone()
    return found is not None


# --- matters ------------------------------------------------------------------------------------------------------


def _matter(row: sqlite3.Row, box: Box) -> MatterRow:
    name = box.open("matters", "name_ct", row["id"], row["name_ct"])
    return MatterRow(row["id"], name, row["status"], row["created_at"], row["updated_at"])


def insert_matter(conn: sqlite3.Connection, box: Box, user_id: str, matter_id: str, name: str, now: str) -> None:
    """A new open matter."""
    conn.execute(
        "INSERT INTO matters (id, user_id, name_ct, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (matter_id, user_id, box.seal("matters", "name_ct", matter_id, name), now, now),
    )


def matters(conn: sqlite3.Connection, box: Box, user_id: str) -> list[MatterRow]:
    """Every matter of the user."""
    rows = conn.execute("SELECT * FROM matters WHERE user_id = ?", (user_id,)).fetchall()
    return [_matter(row, box) for row in rows]


def matter(conn: sqlite3.Connection, box: Box, user_id: str, matter_id: str) -> MatterRow | None:
    """One matter of the user."""
    row = conn.execute("SELECT * FROM matters WHERE id = ? AND user_id = ?", (matter_id, user_id)).fetchone()
    return _matter(row, box) if row else None


def update_matter(
    conn: sqlite3.Connection, box: Box, user_id: str, matter_id: str, now: str, name: str | None, status: str | None
) -> None:
    """Rename and/or open/close a matter."""
    values: dict[str, object] = {"updated_at": now}
    if name is not None:
        values["name_ct"] = box.seal("matters", "name_ct", matter_id, name)
    if status is not None:
        values["status"] = status
    _update(conn, "matters", matter_id, user_id, values)


def delete_matter(conn: sqlite3.Connection, user_id: str, matter_id: str) -> bool:
    """Delete a matter; its items stay, detached (ON DELETE SET NULL)."""
    return _delete(conn, "matters", matter_id, user_id)


# --- conversations and turns --------------------------------------------------------------------------------------


def _conversation(row: sqlite3.Row, box: Box) -> ConversationRow:
    title = box.open("conversations", "title_ct", row["id"], row["title_ct"])
    return ConversationRow(
        row["id"], row["matter_id"], title, bool(row["pinned"]), row["lang"], row["created_at"], row["updated_at"]
    )


def insert_conversation(
    conn: sqlite3.Connection, box: Box, user_id: str, conversation_id: str, title: str, lang: str, now: str
) -> None:
    """A new, empty conversation."""
    conn.execute(
        "INSERT INTO conversations (id, user_id, title_ct, lang, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (conversation_id, user_id, box.seal("conversations", "title_ct", conversation_id, title), lang, now, now),
    )


def conversations(conn: sqlite3.Connection, box: Box, user_id: str) -> list[ConversationRow]:
    """Every conversation of the user."""
    rows = conn.execute("SELECT * FROM conversations WHERE user_id = ?", (user_id,)).fetchall()
    return [_conversation(row, box) for row in rows]


def conversation(conn: sqlite3.Connection, box: Box, user_id: str, conversation_id: str) -> ConversationRow | None:
    """One conversation of the user."""
    row = conn.execute(
        "SELECT * FROM conversations WHERE id = ? AND user_id = ?", (conversation_id, user_id)
    ).fetchone()
    return _conversation(row, box) if row else None


def update_conversation(
    conn: sqlite3.Connection, box: Box, user_id: str, conversation_id: str, changes: Mapping[str, object]
) -> None:
    """Apply title/pinned/matter_id/updated_at changes."""
    values = dict(changes)
    if "title" in values:
        values["title_ct"] = box.seal("conversations", "title_ct", conversation_id, str(values.pop("title")))
    _update(conn, "conversations", conversation_id, user_id, values)


def delete_conversation(conn: sqlite3.Connection, user_id: str, conversation_id: str) -> bool:
    """Delete a conversation and its turns."""
    return _delete(conn, "conversations", conversation_id, user_id)


def _turn(row: sqlite3.Row, box: Box) -> TurnRow:
    tid = row["id"]
    return TurnRow(
        id=tid,
        conversation_id=row["conversation_id"],
        idx=row["idx"],
        question=box.open("turns", "question_ct", tid, row["question_ct"]),
        answer=box.open_json("turns", "answer_ct", tid, row["answer_ct"]),
        sources=box.open_json("turns", "sources_ct", tid, row["sources_ct"]),
        meta=box.open_json("turns", "meta_ct", tid, row["meta_ct"]),
        null_response=bool(row["null_response"]),
        created_at=row["created_at"],
    )


@dataclass(frozen=True)
class TurnContent:
    """What a finished turn stores."""

    question: str
    answer: dict[str, Any]
    sources: list[dict[str, Any]]
    meta: dict[str, Any]
    null_response: bool


def insert_turn(
    conn: sqlite3.Connection, box: Box, conversation_id: str, turn_id: str, content: TurnContent, now: str
) -> int:
    """Append a turn (next idx) and bump the conversation's updated_at; returns the idx."""
    idx: int = conn.execute(
        "SELECT COALESCE(MAX(idx), -1) + 1 FROM turns WHERE conversation_id = ?", (conversation_id,)
    ).fetchone()[0]
    conn.execute(
        "INSERT INTO turns (id, conversation_id, idx, question_ct, answer_ct, sources_ct, meta_ct, null_response, "
        "created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            turn_id,
            conversation_id,
            idx,
            box.seal("turns", "question_ct", turn_id, content.question),
            box.seal_json("turns", "answer_ct", turn_id, content.answer),
            box.seal_json("turns", "sources_ct", turn_id, content.sources),
            box.seal_json("turns", "meta_ct", turn_id, content.meta),
            int(content.null_response),
            now,
        ),
    )
    conn.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (now, conversation_id))
    return idx


def turns(conn: sqlite3.Connection, box: Box, conversation_id: str) -> list[TurnRow]:
    """The turns of a conversation (ownership checked by the caller), oldest first."""
    rows = conn.execute("SELECT * FROM turns WHERE conversation_id = ? ORDER BY idx", (conversation_id,)).fetchall()
    return [_turn(row, box) for row in rows]


def all_turns(conn: sqlite3.Connection, box: Box, user_id: str) -> dict[str, list[TurnRow]]:
    """Every turn of the user, grouped by conversation id, oldest first."""
    rows = conn.execute(
        "SELECT t.* FROM turns t JOIN conversations c ON c.id = t.conversation_id WHERE c.user_id = ? "
        "ORDER BY t.conversation_id, t.idx",
        (user_id,),
    ).fetchall()
    grouped: dict[str, list[TurnRow]] = {}
    for row in rows:
        grouped.setdefault(row["conversation_id"], []).append(_turn(row, box))
    return grouped


def turn_count(conn: sqlite3.Connection, conversation_id: str) -> int:
    """How many turns a conversation has."""
    count: int = conn.execute("SELECT COUNT(*) FROM turns WHERE conversation_id = ?", (conversation_id,)).fetchone()[0]
    return count


# --- letters and versions -----------------------------------------------------------------------------------------


def _letter(row: sqlite3.Row, box: Box) -> LetterRow:
    title = box.open("letters", "title_ct", row["id"], row["title_ct"])
    return LetterRow(
        row["id"],
        row["matter_id"],
        row["conversation_id"],
        title,
        bool(row["pinned"]),
        row["created_at"],
        row["updated_at"],
    )


def insert_letter(conn: sqlite3.Connection, box: Box, user_id: str, letter: LetterRow, now: str) -> None:
    """A new letter (without versions)."""
    conn.execute(
        "INSERT INTO letters (id, user_id, matter_id, conversation_id, title_ct, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            letter.id,
            user_id,
            letter.matter_id,
            letter.conversation_id,
            box.seal("letters", "title_ct", letter.id, letter.title),
            now,
            now,
        ),
    )


def letters(conn: sqlite3.Connection, box: Box, user_id: str) -> list[LetterRow]:
    """Every letter of the user."""
    rows = conn.execute("SELECT * FROM letters WHERE user_id = ?", (user_id,)).fetchall()
    return [_letter(row, box) for row in rows]


def letter(conn: sqlite3.Connection, box: Box, user_id: str, letter_id: str) -> LetterRow | None:
    """One letter of the user."""
    row = conn.execute("SELECT * FROM letters WHERE id = ? AND user_id = ?", (letter_id, user_id)).fetchone()
    return _letter(row, box) if row else None


def update_letter(
    conn: sqlite3.Connection, box: Box, user_id: str, letter_id: str, changes: Mapping[str, object]
) -> None:
    """Apply title/pinned/matter_id/updated_at changes."""
    values = dict(changes)
    if "title" in values:
        values["title_ct"] = box.seal("letters", "title_ct", letter_id, str(values.pop("title")))
    _update(conn, "letters", letter_id, user_id, values)


def delete_letter(conn: sqlite3.Connection, user_id: str, letter_id: str) -> bool:
    """Delete a letter and its versions."""
    return _delete(conn, "letters", letter_id, user_id)


def _version(row: sqlite3.Row, box: Box) -> VersionRow:
    return VersionRow(
        row["id"], row["n"], box.open("letter_versions", "body_ct", row["id"], row["body_ct"]), row["created_at"]
    )


def insert_version(
    conn: sqlite3.Connection, box: Box, letter_id: str, version_id: str, body: str, now: str, keep: int
) -> int:
    """Append a version (next n), drop the oldest beyond keep, bump the letter's updated_at; returns n."""
    n: int = conn.execute(
        "SELECT COALESCE(MAX(n), 0) + 1 FROM letter_versions WHERE letter_id = ?", (letter_id,)
    ).fetchone()[0]
    conn.execute(
        "INSERT INTO letter_versions (id, letter_id, n, body_ct, created_at) VALUES (?, ?, ?, ?, ?)",
        (version_id, letter_id, n, box.seal("letter_versions", "body_ct", version_id, body), now),
    )
    conn.execute("DELETE FROM letter_versions WHERE letter_id = ? AND n <= ?", (letter_id, n - keep))
    conn.execute("UPDATE letters SET updated_at = ? WHERE id = ?", (now, letter_id))
    return n


def versions(conn: sqlite3.Connection, box: Box, letter_id: str) -> list[VersionRow]:
    """Kept versions of a letter (ownership checked by the caller), newest first."""
    rows = conn.execute("SELECT * FROM letter_versions WHERE letter_id = ? ORDER BY n DESC", (letter_id,)).fetchall()
    return [_version(row, box) for row in rows]


def latest_versions(conn: sqlite3.Connection, box: Box, user_id: str) -> dict[str, VersionRow]:
    """The newest version of every letter of the user, by letter id."""
    rows = conn.execute(
        "SELECT v.* FROM letter_versions v JOIN letters l ON l.id = v.letter_id WHERE l.user_id = ? "
        "AND v.n = (SELECT MAX(n) FROM letter_versions WHERE letter_id = v.letter_id)",
        (user_id,),
    ).fetchall()
    return {row["letter_id"]: _version(row, box) for row in rows}


# --- bookmarks and notes ------------------------------------------------------------------------------------------


def _bookmark(row: sqlite3.Row, box: Box) -> BookmarkRow:
    chunk_id = box.open("bookmarks", "chunk_id_ct", row["id"], row["chunk_id_ct"])
    return BookmarkRow(row["id"], chunk_id, row["matter_id"], row["created_at"])


def insert_bookmark(conn: sqlite3.Connection, box: Box, user_id: str, bookmark: BookmarkRow) -> None:
    """A new bookmark."""
    conn.execute(
        "INSERT INTO bookmarks (id, user_id, chunk_id_ct, matter_id, created_at) VALUES (?, ?, ?, ?, ?)",
        (
            bookmark.id,
            user_id,
            box.seal("bookmarks", "chunk_id_ct", bookmark.id, bookmark.chunk_id),
            bookmark.matter_id,
            bookmark.created_at,
        ),
    )


def bookmarks(conn: sqlite3.Connection, box: Box, user_id: str) -> list[BookmarkRow]:
    """Every bookmark of the user."""
    rows = conn.execute("SELECT * FROM bookmarks WHERE user_id = ?", (user_id,)).fetchall()
    return [_bookmark(row, box) for row in rows]


def update_bookmark(conn: sqlite3.Connection, user_id: str, bookmark_id: str, matter_id: str | None) -> None:
    """Move a bookmark into (or out of) a matter."""
    _update(conn, "bookmarks", bookmark_id, user_id, {"matter_id": matter_id})


def delete_bookmark(conn: sqlite3.Connection, user_id: str, bookmark_id: str) -> bool:
    """Delete one bookmark."""
    return _delete(conn, "bookmarks", bookmark_id, user_id)


def _note(row: sqlite3.Row, box: Box) -> NoteRow:
    nid = row["id"]
    target = box.open("notes", "target_ct", nid, row["target_ct"]) if row["target_ct"] is not None else None
    body = box.open("notes", "body_ct", nid, row["body_ct"])
    return NoteRow(nid, row["target_kind"], target, body, row["matter_id"], row["created_at"], row["updated_at"])


def insert_note(conn: sqlite3.Connection, box: Box, user_id: str, note: NoteRow) -> None:
    """A new note."""
    target = box.seal("notes", "target_ct", note.id, note.target_id) if note.target_id is not None else None
    conn.execute(
        "INSERT INTO notes (id, user_id, target_kind, target_ct, body_ct, matter_id, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            note.id,
            user_id,
            note.target_kind,
            target,
            box.seal("notes", "body_ct", note.id, note.body),
            note.matter_id,
            note.created_at,
            note.updated_at,
        ),
    )


def notes(conn: sqlite3.Connection, box: Box, user_id: str) -> list[NoteRow]:
    """Every note of the user."""
    rows = conn.execute("SELECT * FROM notes WHERE user_id = ?", (user_id,)).fetchall()
    return [_note(row, box) for row in rows]


def update_note(conn: sqlite3.Connection, box: Box, user_id: str, note_id: str, changes: Mapping[str, object]) -> None:
    """Apply body/matter_id/updated_at changes."""
    values = dict(changes)
    if "body" in values:
        values["body_ct"] = box.seal("notes", "body_ct", note_id, str(values.pop("body")))
    _update(conn, "notes", note_id, user_id, values)


def delete_note(conn: sqlite3.Connection, user_id: str, note_id: str) -> bool:
    """Delete one note."""
    return _delete(conn, "notes", note_id, user_id)
