-- Recent reads (M15): sections a signed-in user opened, newest kept up to reads_max, for Home "Continue reading".
CREATE TABLE reads (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    chunk_id_ct BLOB NOT NULL,
    at TEXT NOT NULL
);
CREATE INDEX reads_user ON reads(user_id, at);
