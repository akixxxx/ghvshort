from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


def utcnow_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


@dataclass(frozen=True)
class Link:
    slug: str
    url: str
    code: int
    created_at: str
    updated_at: str
    expires_at: str | None
    hits: int


SCHEMA = """
CREATE TABLE IF NOT EXISTS links (
  slug TEXT PRIMARY KEY,
  url TEXT NOT NULL,
  code INTEGER NOT NULL CHECK (code IN (301, 302)),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  expires_at TEXT NULL,
  hits INTEGER NOT NULL DEFAULT 0 CHECK (hits >= 0)
);

CREATE INDEX IF NOT EXISTS idx_links_expires_at ON links(expires_at);
"""


class Repo:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        # bewährte Defaults
        con.execute("PRAGMA journal_mode=WAL;")
        con.execute("PRAGMA synchronous=NORMAL;")
        con.execute("PRAGMA foreign_keys=ON;")
        return con

    def init_db(self) -> None:
        with self.connect() as con:
            con.executescript(SCHEMA)

    def add_link(self, slug: str, url: str, code: int, expires_at: str | None) -> None:
        now = utcnow_iso()
        with self.connect() as con:
            con.execute(
                "INSERT INTO links(slug, url, code, created_at, updated_at, expires_at, hits) "
                "VALUES (?, ?, ?, ?, ?, ?, 0)",
                (slug, url, code, now, now, expires_at),
            )

    def set_link(
        self,
        slug: str,
        url: str | None,
        code: int | None,
        expires_at: str | None,
        no_expires: bool,
    ) -> None:
        now = utcnow_iso()
        with self.connect() as con:
            row = con.execute(
                "SELECT slug, url, code, expires_at FROM links WHERE slug = ?",
                (slug,),
            ).fetchone()
            if row is None:
                raise KeyError(slug)

            new_url = url if url is not None else row["url"]
            new_code = code if code is not None else row["code"]

            if no_expires:
                new_expires = None
            else:
                new_expires = expires_at if expires_at is not None else row["expires_at"]

            con.execute(
                "UPDATE links SET url = ?, code = ?, expires_at = ?, updated_at = ? WHERE slug = ?",
                (new_url, new_code, new_expires, now, slug),
            )

    def delete_link(self, slug: str) -> None:
        with self.connect() as con:
            cur = con.execute("DELETE FROM links WHERE slug = ?", (slug,))
            if cur.rowcount == 0:
                raise KeyError(slug)

    def get_link(self, slug: str) -> Link:
        with self.connect() as con:
            row = con.execute("SELECT * FROM links WHERE slug = ?", (slug,)).fetchone()
            if row is None:
                raise KeyError(slug)
            return Link(**dict(row))

    def list_links(self) -> list[Link]:
        with self.connect() as con:
            rows = con.execute("SELECT * FROM links ORDER BY slug ASC").fetchall()
            return [Link(**dict(r)) for r in rows]

    def resolve_and_hit(self, slug: str) -> Link:
        """Für Web-Requests: lesen + hits hochzählen (atomar)."""
        now = utcnow_iso()
        with self.connect() as con:
            con.execute("BEGIN IMMEDIATE;")
            row = con.execute("SELECT * FROM links WHERE slug = ?", (slug,)).fetchone()
            if row is None:
                raise KeyError(slug)

            expires_at = row["expires_at"]
            if expires_at is not None and expires_at <= now:
                raise PermissionError("expired")

            con.execute(
                "UPDATE links SET hits = hits + 1, updated_at = ? WHERE slug = ?",
                (now, slug),
            )
            row2 = con.execute("SELECT * FROM links WHERE slug = ?", (slug,)).fetchone()
            return Link(**dict(row2))
