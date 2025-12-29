import sqlite3
from pathlib import Path

from ghvshort.db import get_user_version, init_db


def test_migration_to_v1(tmp_path: Path):
    db = tmp_path / "t.db"
    conn = sqlite3.connect(db)

    conn.executescript(
        """
        CREATE TABLE links (
          slug TEXT PRIMARY KEY,
          url TEXT NOT NULL,
          code INTEGER NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          expires_at TEXT NULL,
          hits INTEGER NOT NULL DEFAULT 0
        );
        PRAGMA user_version = 0;
        """
    )
    conn.commit()

    init_db(conn)

    cols = [r[1] for r in conn.execute("PRAGMA table_info(links)")]
    assert "not_before_at" in cols
    assert "last_access_at" in cols
    assert "deleted_at" in cols
    assert get_user_version(conn) == 1
