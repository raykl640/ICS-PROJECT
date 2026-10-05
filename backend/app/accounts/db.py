"""SQLite store for accounts: WAL, foreign keys, secure_delete, numbered migrations tracked in PRAGMA user_version."""

import re
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
_MIGRATION_NAME = re.compile(r"^(\d{3})_[a-z0-9_]+\.sql$")


def migrations(directory: Path = MIGRATIONS_DIR) -> list[tuple[int, Path]]:
    """(number, file) for every migration, in order; numbers must run 1, 2, 3, … without gaps."""
    found = sorted((int(m.group(1)), p) for p in directory.iterdir() if (m := _MIGRATION_NAME.match(p.name)))
    if [n for n, _ in found] != list(range(1, len(found) + 1)):
        raise RuntimeError(f"migrations in {directory} must be numbered 001, 002, … without gaps")
    return found


class Database:
    """One file, one short-lived connection per unit of work; writes are serialized in-process."""

    def __init__(self, path: Path, migrations_dir: Path = MIGRATIONS_DIR) -> None:
        self.path = path
        self._write_lock = threading.Lock()
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            self._migrate(conn, migrations_dir)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10, isolation_level=None, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA secure_delete=ON")
        return conn

    @staticmethod
    def _migrate(conn: sqlite3.Connection, directory: Path) -> None:
        current = conn.execute("PRAGMA user_version").fetchone()[0]
        for number, path in migrations(directory):
            if number <= current:
                continue
            # executescript commits any open transaction first, so the transaction lives inside the script.
            script = f"BEGIN IMMEDIATE;\n{path.read_text(encoding='utf-8')}\nPRAGMA user_version={number};\nCOMMIT;"
            try:
                conn.executescript(script)
            except sqlite3.Error:
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
                raise

    @property
    def version(self) -> int:
        """Applied schema version."""
        with self.read() as conn:
            version: int = conn.execute("PRAGMA user_version").fetchone()[0]
            return version

    @contextmanager
    def read(self) -> Iterator[sqlite3.Connection]:
        """A connection for reads."""
        conn = self._connect()
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def write(self) -> Iterator[sqlite3.Connection]:
        """A connection inside one IMMEDIATE transaction, committed on success, rolled back on error."""
        with self._write_lock:
            conn = self._connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                yield conn
                conn.execute("COMMIT")
            except BaseException:
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
                raise
            finally:
                conn.close()

    def compact(self) -> None:
        """Rewrite the file and empty the WAL so deleted rows leave no readable pages behind."""
        with self._write_lock:
            conn = self._connect()
            try:
                conn.execute("VACUUM")
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            finally:
                conn.close()
