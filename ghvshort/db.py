from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS links (
  slug TEXT PRIMARY KEY,
  url TEXT NOT NULL,
  code INTEGER NOT NULL CHECK (code IN (301, 302)),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  expires_at TEXT NULL,
  not_before_at TEXT NULL,
  hits INTEGER NOT NULL DEFAULT 0 CHECK (hits >= 0),
  last_access_at TEXT NULL,
  deleted_at TEXT NULL
);

CREATE INDEX IF NOT EXISTS idx_links_expires_at ON links(expires_at);
"""


def utc_now_iso() -> str:
    # ISO in UTC ohne Microseconds – robust & diff-freundlich
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def get_user_version(conn: sqlite3.Connection) -> int:
    return int(conn.execute("PRAGMA user_version").fetchone()[0])


def set_user_version(conn: sqlite3.Connection, version: int) -> None:
    conn.execute(f"PRAGMA user_version = {version}")


def migrate(conn: sqlite3.Connection) -> None:
    v = get_user_version(conn)
    if v >= SCHEMA_VERSION:
        return

    with conn:  # transaktional
        if v < 1:
            # 0 -> 1 (bestehende DB erweitern)
            conn.execute("ALTER TABLE links ADD COLUMN not_before_at TEXT")
            conn.execute("ALTER TABLE links ADD COLUMN last_access_at TEXT")
            conn.execute("ALTER TABLE links ADD COLUMN deleted_at TEXT")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_links_deleted_at ON links(deleted_at)")
            set_user_version(conn, 1)


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    migrate(conn)


@dataclass(frozen=True)
class Link:
    slug: str
    url: str
    code: int
    created_at: str
    updated_at: str
    not_before_at: Optional[str]
    expires_at: Optional[str]
    hits: int
    last_access_at: Optional[str]
    deleted_at: Optional[str]


class Repo:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        with self.connect() as conn:
            init_db(conn)

    def add_link(
        self,
        slug: str,
        url: str,
        code: int,
        expires_at: Optional[str],
        not_before_at: Optional[str],
    ) -> None:
        now = utc_now_iso()
        with self.connect() as conn, conn:
            conn.execute(
                """
                INSERT INTO links (
                    slug, url, code,
                    created_at, updated_at,
                    expires_at, not_before_at,
                    hits, last_access_at, deleted_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, NULL, NULL)
                """,
                (slug, url, code, now, now, expires_at, not_before_at),
            )

    def set_link(
        self,
        slug: str,
        url: Optional[str],
        code: Optional[int],
        not_before_at: Optional[str],
        no_not_before: bool,
        expires_at: Optional[str],
        no_expires: bool,
    ) -> int:
        now = utc_now_iso()
        fields = []
        params: list[object] = []

        if url is not None:
            fields.append("url = ?")
            params.append(url)

        if code is not None:
            fields.append("code = ?")
            params.append(code)

        if no_expires:
            fields.append("expires_at = NULL")
        elif expires_at is not None:
            fields.append("expires_at = ?")
            params.append(expires_at)

        if no_not_before:
            fields.append("not_before_at = NULL")
        elif not_before_at is not None:
            fields.append("not_before_at = ?")
            params.append(not_before_at)

        # immer updated_at
        fields.append("updated_at = ?")
        params.append(now)

        if not fields:
            return 0

        params.append(slug)

        with self.connect() as conn, conn:
            cur = conn.execute(
                f"UPDATE links SET {', '.join(fields)} WHERE slug = ?",
                params,
            )
            return int(cur.rowcount)

    def delete_link(self, slug: str) -> int:
        now = utc_now_iso()
        with self.connect() as conn, conn:
            cur = conn.execute(
                """
                UPDATE links
                SET deleted_at = ?, updated_at = ?
                WHERE slug = ?
                AND deleted_at IS NULL
                """,
                (now, now, slug),
            )
            return int(cur.rowcount)

    def purge_link(self, slug: str) -> int:
        with self.connect() as conn, conn:
            cur = conn.execute(
                "DELETE FROM links WHERE slug = ?",
                (slug,),
            )
            return int(cur.rowcount)

    def soft_delete(self, slug: str) -> int:
        now = utc_now_iso()
        with self.connect() as conn, conn:
            cur = conn.execute(
                "UPDATE links SET deleted_at = ?, updated_at = ? WHERE slug = ? AND deleted_at IS NULL",
                (now, now, slug),
            )
            return int(cur.rowcount)

    def cleanup_expired(self) -> int:
        """Markiert abgelaufene Links mit deleted_at (Soft-Delete)."""
        now = utc_now_iso()
        with self.connect() as conn, conn:
            cur = conn.execute(
                """
                UPDATE links
                SET deleted_at = ?, updated_at = ?
                WHERE deleted_at IS NULL
                  AND expires_at IS NOT NULL
                  AND expires_at <= ?
                """,
                (now, now, now),
            )
            return int(cur.rowcount)

    def get_link_active(self, slug: str) -> Optional[Link]:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT slug, url, code, created_at, updated_at, not_before_at, expires_at, hits, last_access_at, deleted_at
                FROM links
                WHERE slug = ?
                  AND deleted_at IS NULL
                """,
                (slug,),
            ).fetchone()
            if row is None:
                return None
            return Link(**dict(row))

    def get_link_any(self, slug: str) -> Optional[Link]:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT slug, url, code, created_at, updated_at, expires_at, not_before_at,
                    hits, last_access_at, deleted_at
                FROM links
                WHERE slug = ?
                """,
                (slug,),
            ).fetchone()
            if row is None:
                return None
            return Link(**dict(row))

    def list_active_links(self, now_iso: str) -> list[Link]:
        """
        Active = not deleted AND (not_before_at is NULL OR not_before_at <= now)
                        AND (expires_at is NULL OR expires_at > now)
        """
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT slug, url, code, created_at, updated_at, expires_at, not_before_at,
                    hits, last_access_at, deleted_at
                FROM links
                WHERE deleted_at IS NULL
                AND (not_before_at IS NULL OR not_before_at <= ?)
                AND (expires_at IS NULL OR expires_at > ?)
                ORDER BY slug
                """,
                (now_iso, now_iso),
            ).fetchall()
            return [Link(**dict(r)) for r in rows]

    def touch_hit(self, slug: str) -> None:
        now = utc_now_iso()
        with self.connect() as conn, conn:
            conn.execute(
                """
                UPDATE links
                SET hits = hits + 1,
                    last_access_at = ?,
                    updated_at = ?
                WHERE slug = ?
                  AND deleted_at IS NULL
                """,
                (now, now, slug),
            )

    def list_links(self, include_deleted: bool = False) -> list[Link]:
        where = "" if include_deleted else "WHERE deleted_at IS NULL"
        with self.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT slug, url, code, created_at, updated_at, not_before_at, expires_at, hits, last_access_at, deleted_at
                FROM links
                {where}
                ORDER BY slug
                """
            ).fetchall()
            return [Link(**dict(r)) for r in rows]
