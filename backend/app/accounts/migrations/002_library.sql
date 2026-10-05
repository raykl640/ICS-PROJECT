-- Library (M14): conversations and their turns, letters and their versions, matters, bookmarks and notes.
-- Content columns (*_ct) hold AES-256-GCM ciphertext only (AAD table:column:row_id); ownership is checked per user_id.
CREATE TABLE matters (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name_ct BLOB NOT NULL,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX matters_user ON matters(user_id);

CREATE TABLE conversations (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    matter_id TEXT REFERENCES matters(id) ON DELETE SET NULL,
    title_ct BLOB NOT NULL,
    pinned INTEGER NOT NULL DEFAULT 0,
    lang TEXT NOT NULL CHECK (lang IN ('en', 'sw')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX conversations_user ON conversations(user_id);

CREATE TABLE turns (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    idx INTEGER NOT NULL,
    question_ct BLOB NOT NULL,              -- the question as asked (user's language)
    answer_ct BLOB NOT NULL,                -- JSON: sections in the user's language + English answer
    sources_ct BLOB NOT NULL,               -- JSON: [{chunk_id, score}]
    meta_ct BLOB NOT NULL,                  -- JSON: English question, Acts, citation check, warnings, flags
    null_response INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (conversation_id, idx)
);

CREATE TABLE letters (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    matter_id TEXT REFERENCES matters(id) ON DELETE SET NULL,
    conversation_id TEXT REFERENCES conversations(id) ON DELETE SET NULL,
    title_ct BLOB NOT NULL,
    pinned INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX letters_user ON letters(user_id);

CREATE TABLE letter_versions (
    id TEXT PRIMARY KEY,
    letter_id TEXT NOT NULL REFERENCES letters(id) ON DELETE CASCADE,
    n INTEGER NOT NULL,
    body_ct BLOB NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (letter_id, n)
);

CREATE TABLE bookmarks (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    chunk_id_ct BLOB NOT NULL,
    matter_id TEXT REFERENCES matters(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX bookmarks_user ON bookmarks(user_id);

CREATE TABLE notes (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    target_kind TEXT NOT NULL CHECK (target_kind IN ('none', 'conversation', 'letter', 'chunk', 'matter')),
    target_ct BLOB,                         -- id of the target (NULL for 'none')
    body_ct BLOB NOT NULL,
    matter_id TEXT REFERENCES matters(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX notes_user ON notes(user_id);
