"""/api/conversations, /api/letters, /api/matters, /api/bookmarks, /api/notes (DESIGN_V2 "API v2"). Signed in and
unlocked only (401 / 423); another user's id is a 404. Lists take q, filters, sort, cursor and limit."""

from collections.abc import Mapping
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from backend.app.accounts.library import (
    BookmarkOut,
    ConversationDetail,
    ConversationOut,
    LetterDetail,
    LetterOut,
    Library,
    ListQuery,
    MatterDetail,
    MatterOut,
    MatterStatus,
    NoteOut,
    NoteTarget,
    Page,
    SortKey,
    VersionOut,
)
from backend.app.accounts.routes import Unlocked
from backend.app.accounts.service import AccountError
from backend.app.letter import docx_export, text_export
from backend.app.models import UserLanguage
from backend.app.sessions import SessionStore

DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
Id = Annotated[str, Field(max_length=64)]
library = APIRouter(prefix="/api")


def _library(request: Request) -> Library:
    found: Library | None = getattr(request.app.state, "library", None)
    if found is None:
        raise AccountError(503, "not_ready", "The service is still starting. Please try again shortly.")
    return found


Lib = Annotated[Library, Depends(_library)]


class _Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ConversationPatch(_Body):
    """Rename, pin, or file into a matter (matter_id null = unfile)."""

    title: str | None = Field(None, max_length=1000)
    pinned: bool | None = None
    matter_id: Id | None = None


class LetterIn(_Body):
    """A new letter: blank, the given body, or the letter section of a saved answer (turn_id)."""

    title: str = Field("", max_length=1000)
    body: str = Field("", max_length=100_000)
    turn_id: Id | None = None
    matter_id: Id | None = None


class LetterPut(_Body):
    """New text (saved as a version if it changed) and/or title, pin, matter."""

    title: str | None = Field(None, max_length=1000)
    body: str | None = Field(None, max_length=100_000)
    pinned: bool | None = None
    matter_id: Id | None = None


class MatterIn(_Body):
    """A new matter."""

    name: str = Field(max_length=1000)


class MatterPatch(_Body):
    """Rename and/or open/close."""

    name: str | None = Field(None, max_length=1000)
    status: MatterStatus | None = None


class BookmarkIn(_Body):
    """Bookmark a corpus section."""

    chunk_id: Id
    matter_id: Id | None = None


class BookmarkPatch(_Body):
    """File a bookmark into a matter (null = unfile)."""

    matter_id: Id | None = None


class NoteIn(_Body):
    """A new note about nothing in particular, or about one item."""

    body: str = Field(max_length=100_000)
    target_kind: NoteTarget = "none"
    target_id: Id | None = None
    matter_id: Id | None = None


class NotePut(_Body):
    """Edit a note's text and/or matter."""

    body: str | None = Field(None, max_length=100_000)
    matter_id: Id | None = None


class Running(BaseModel):
    """An answer still being written for this conversation."""

    session_id: str
    question: str
    status: str


class ConversationView(ConversationDetail):
    """GET /api/conversations/{id}: the saved thread plus answers in progress."""

    running: list[Running]


def _query(
    q: Annotated[str, Query(max_length=200)] = "",
    matter: Annotated[str | None, Query(max_length=64)] = None,
    lang: UserLanguage | None = None,
    act: Annotated[str | None, Query(max_length=80)] = None,
    pinned: bool | None = None,
    date_from: Annotated[str | None, Query(alias="from", pattern=r"^\d{4}-\d{2}-\d{2}$")] = None,
    date_to: Annotated[str | None, Query(alias="to", pattern=r"^\d{4}-\d{2}-\d{2}$")] = None,
    sort: SortKey = "updated",
    cursor: Annotated[str | None, Query(max_length=400)] = None,
    limit: Annotated[int | None, Query(gt=0)] = None,
) -> ListQuery:
    return ListQuery(q, matter, lang, act, pinned, date_from, date_to, sort, cursor, limit)


Q = Annotated[ListQuery, Depends(_query)]


def _changes(body: BaseModel) -> dict[str, Any]:
    """Only the fields the client sent (an explicit null matter_id unfiles; an absent one leaves it)."""
    return {name: getattr(body, name) for name in body.model_fields_set}


# --- conversations ------------------------------------------------------------------------------------------------


@library.get("/conversations")
def list_conversations(unlocked: Unlocked, lib: Lib, query: Q) -> Page[ConversationOut]:
    """Saved chats, pinned first."""
    session, dek = unlocked
    return lib.list_conversations(session.user_id, dek, query)


@library.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: str, request: Request, unlocked: Unlocked, lib: Lib) -> ConversationView:
    """The thread and any answers for it still being written."""
    session, dek = unlocked
    detail = lib.conversation(session.user_id, dek, conversation_id)
    sessions: SessionStore = request.app.state.sessions
    running = [
        Running(session_id=sid, question=data.question, status=data.status)
        for sid, data in sessions.live()
        if data.owner_id == session.user_id
        and data.conversation_id == conversation_id
        and data.status in ("pending", "running")
    ]
    return ConversationView(**detail.model_dump(), running=running)


@library.patch("/conversations/{conversation_id}")
def patch_conversation(
    conversation_id: str, body: ConversationPatch, unlocked: Unlocked, lib: Lib
) -> ConversationDetail:
    """Rename, pin/unpin or file the conversation."""
    session, dek = unlocked
    return lib.update_conversation(session.user_id, dek, conversation_id, _changes(body))


@library.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: str, unlocked: Unlocked, lib: Lib) -> dict[str, bool]:
    """Delete a conversation and its turns."""
    lib.delete_conversation(unlocked[0].user_id, conversation_id)
    return {"deleted": True}


# --- letters ------------------------------------------------------------------------------------------------------


@library.get("/letters")
def list_letters(unlocked: Unlocked, lib: Lib, query: Q) -> Page[LetterOut]:
    """Saved letters, pinned first."""
    session, dek = unlocked
    return lib.list_letters(session.user_id, dek, query)


@library.post("/letters")
def create_letter(body: LetterIn, unlocked: Unlocked, lib: Lib) -> LetterDetail:
    """A new letter (version 1)."""
    session, dek = unlocked
    return lib.create_letter(session.user_id, dek, body.title, body.body, body.turn_id, body.matter_id)


@library.get("/letters/{letter_id}")
def get_letter(letter_id: str, unlocked: Unlocked, lib: Lib) -> LetterDetail:
    """A letter with its latest text."""
    session, dek = unlocked
    return lib.letter(session.user_id, dek, letter_id)


@library.put("/letters/{letter_id}")
def put_letter(letter_id: str, body: LetterPut, unlocked: Unlocked, lib: Lib) -> LetterDetail:
    """Save the letter; changed text becomes a new version (the oldest beyond letter_versions_max is dropped)."""
    session, dek = unlocked
    return lib.update_letter(session.user_id, dek, letter_id, _changes(body))


@library.delete("/letters/{letter_id}")
def delete_letter(letter_id: str, unlocked: Unlocked, lib: Lib) -> dict[str, bool]:
    """Delete a letter and its versions."""
    lib.delete_letter(unlocked[0].user_id, letter_id)
    return {"deleted": True}


@library.get("/letters/{letter_id}/versions")
def letter_versions(letter_id: str, unlocked: Unlocked, lib: Lib) -> list[VersionOut]:
    """Kept versions, newest first."""
    session, dek = unlocked
    return lib.versions(session.user_id, dek, letter_id)


@library.post("/letters/{letter_id}/versions/{n}/restore")
def restore_version(letter_id: str, n: int, unlocked: Unlocked, lib: Lib) -> LetterDetail:
    """Bring back an older text as the newest version."""
    session, dek = unlocked
    return lib.restore_version(session.user_id, dek, letter_id, n)


@library.get("/letters/{letter_id}/export")
async def export_letter(
    letter_id: str,
    request: Request,
    unlocked: Unlocked,
    lib: Lib,
    fmt: Annotated[Literal["txt", "docx"], Query(alias="format")] = "txt",
    lang: UserLanguage = "en",
) -> Response:
    """The latest text as .txt or .docx with the disclaimer (in lang) at the end / in the footer."""
    session, dek = unlocked
    letter = await run_in_threadpool(lib.letter, session.user_id, dek, letter_id)
    ui: Mapping[str, Mapping[str, str]] = request.app.state.ui_strings
    disclaimer = ui[lang]["disclaimer"]
    headers = {"Content-Disposition": f'attachment; filename="letter.{fmt}"'}
    if fmt == "docx":
        content = await run_in_threadpool(docx_export, letter.body, disclaimer, letter.title)
        return Response(content, media_type=DOCX_MEDIA_TYPE, headers=headers)
    return PlainTextResponse(text_export(letter.body, disclaimer), headers=headers)


# --- matters ------------------------------------------------------------------------------------------------------


@library.get("/matters")
def list_matters(unlocked: Unlocked, lib: Lib, query: Q) -> Page[MatterOut]:
    """Matters, open ones first."""
    session, dek = unlocked
    return lib.list_matters(session.user_id, dek, query)


@library.post("/matters")
def create_matter(body: MatterIn, unlocked: Unlocked, lib: Lib) -> MatterOut:
    """A new open matter."""
    session, dek = unlocked
    return lib.create_matter(session.user_id, dek, body.name)


@library.get("/matters/{matter_id}")
def get_matter(matter_id: str, unlocked: Unlocked, lib: Lib) -> MatterDetail:
    """A matter with everything filed in it."""
    session, dek = unlocked
    return lib.matter(session.user_id, dek, matter_id)


@library.patch("/matters/{matter_id}")
def patch_matter(matter_id: str, body: MatterPatch, unlocked: Unlocked, lib: Lib) -> MatterOut:
    """Rename and/or open/close."""
    session, dek = unlocked
    return lib.update_matter(session.user_id, dek, matter_id, body.name, body.status)


@library.delete("/matters/{matter_id}")
def delete_matter(matter_id: str, unlocked: Unlocked, lib: Lib) -> dict[str, bool]:
    """Delete a matter; its items stay in the library."""
    lib.delete_matter(unlocked[0].user_id, matter_id)
    return {"deleted": True}


# --- bookmarks and notes ------------------------------------------------------------------------------------------


@library.get("/bookmarks")
def list_bookmarks(unlocked: Unlocked, lib: Lib, query: Q) -> Page[BookmarkOut]:
    """Saved sections, newest first."""
    session, dek = unlocked
    return lib.list_bookmarks(session.user_id, dek, query)


@library.post("/bookmarks")
def add_bookmark(body: BookmarkIn, unlocked: Unlocked, lib: Lib) -> BookmarkOut:
    """Bookmark a section (returns the existing bookmark if it is already saved)."""
    session, dek = unlocked
    return lib.add_bookmark(session.user_id, dek, body.chunk_id, body.matter_id)


@library.patch("/bookmarks/{bookmark_id}")
def patch_bookmark(bookmark_id: str, body: BookmarkPatch, unlocked: Unlocked, lib: Lib) -> BookmarkOut:
    """File a bookmark into a matter."""
    session, dek = unlocked
    return lib.move_bookmark(session.user_id, dek, bookmark_id, body.matter_id)


@library.delete("/bookmarks/{bookmark_id}")
def delete_bookmark(bookmark_id: str, unlocked: Unlocked, lib: Lib) -> dict[str, bool]:
    """Remove a bookmark."""
    lib.delete_bookmark(unlocked[0].user_id, bookmark_id)
    return {"deleted": True}


@library.get("/notes")
def list_notes(unlocked: Unlocked, lib: Lib, query: Q) -> Page[NoteOut]:
    """Notes, most recently edited first."""
    session, dek = unlocked
    return lib.list_notes(session.user_id, dek, query)


@library.post("/notes")
def create_note(body: NoteIn, unlocked: Unlocked, lib: Lib) -> NoteOut:
    """A new note."""
    session, dek = unlocked
    return lib.create_note(session.user_id, dek, body.body, body.target_kind, body.target_id, body.matter_id)


@library.put("/notes/{note_id}")
def put_note(note_id: str, body: NotePut, unlocked: Unlocked, lib: Lib) -> NoteOut:
    """Edit a note."""
    session, dek = unlocked
    return lib.update_note(session.user_id, dek, note_id, _changes(body))


@library.delete("/notes/{note_id}")
def delete_note(note_id: str, unlocked: Unlocked, lib: Lib) -> dict[str, bool]:
    """Delete a note."""
    lib.delete_note(unlocked[0].user_id, note_id)
    return {"deleted": True}
