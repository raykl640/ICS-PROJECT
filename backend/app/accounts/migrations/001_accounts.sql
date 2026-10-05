-- Local accounts (M13). Content columns (*_ct) hold AES-256-GCM ciphertext only; ids are UUID4 text; times UTC ISO.
CREATE TABLE users (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,          -- casefolded
    display_name TEXT NOT NULL,
    pw_hash TEXT NOT NULL,                  -- argon2id encoded hash
    kek_salt BLOB NOT NULL,
    dek_pw BLOB NOT NULL,                   -- DEK wrapped under the password-derived key
    rc_salt BLOB NOT NULL,
    dek_rc BLOB NOT NULL,                   -- DEK wrapped under the recovery-code-derived key
    prefs_json TEXT NOT NULL,               -- non-content preferences (save_history, auto_lock_minutes)
    created_at TEXT NOT NULL,
    failed_logins INTEGER NOT NULL DEFAULT 0,
    locked_until REAL NOT NULL DEFAULT 0    -- epoch seconds; login refused before this
);

CREATE TABLE profiles (
    user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    data_ct BLOB NOT NULL                   -- letter profile JSON (name, address, phone, email, id number)
);

-- Sign-in tokens survive a restart (only their sha256 is stored); the DEK never does, so a known token comes back locked.
CREATE TABLE auth_tokens (
    token_hash TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at REAL NOT NULL,
    expires_at REAL NOT NULL
);
CREATE INDEX auth_tokens_user ON auth_tokens(user_id);
