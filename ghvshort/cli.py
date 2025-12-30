from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import typer

from .config import Settings, load_settings
from .db import Repo

app = typer.Typer(add_completion=False)


def _write_json_atomically(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.chmod(tmp, 0o644)  # world-readable
    os.replace(tmp, path)  # atomic on POSIX


def _maybe_export_after_change(settings: Settings, repo: Repo) -> None:
    if settings.export_json_path is None:
        return
    try:
        now_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        links = repo.list_active_links(now_iso)
        payload = {
            "generated_at": now_iso,
            "base_url": settings.base_url,
            "count": len(links),
            "links": [
                {
                    "slug": link.slug,
                    "short_url": f"{settings.base_url}/{link.slug}",
                    "url": link.url,
                    "code": link.code,
                    "hits": 0,
                    "not_before_at": link.not_before_at,
                    "expires_at": link.expires_at,
                    "last_access_at": None,
                }
                for link in links
            ],
        }
        _write_json_atomically(settings.export_json_path, json.dumps(payload, indent=2) + "\n")
    except Exception as e:
        # IMPORTANT: cli commands should not fail because of missing config
        typer.echo(f"Warning: export-json failed: {e}", err=True)


def _print_table(headers: list[str], rows: list[list[str]], max_width: int = 120) -> None:
    widths = [len(h) for h in headers]
    for r in rows:
        for i, c in enumerate(r):
            widths[i] = max(widths[i], len(c))

    # shorten last column with table grows to much
    total = sum(widths) + 3 * (len(widths) - 1)
    if total > max_width and widths:
        overflow = total - max_width
        last = len(widths) - 1
        widths[last] = max(20, widths[last] - overflow)

        def trim(s: str, w: int) -> str:
            if len(s) <= w:
                return s
            if w <= 1:
                return s[:w]
            return s[: w - 1] + "…"
    else:

        def trim(s: str, w: int) -> str:
            return s

    def fmt_row(r: list[str]) -> str:
        return " | ".join(trim(c, widths[i]).ljust(widths[i]) for i, c in enumerate(r))

    typer.echo(fmt_row(headers))
    typer.echo("-+-".join("-" * w for w in widths))
    for r in rows:
        typer.echo(fmt_row(r))


def parse_expires(expires: Optional[str]) -> Optional[str]:
    """Akzeptiert YYYY-MM-DD oder ISO8601, speichert als UTC ISO ohne Microseconds."""
    if expires is None:
        return None

    if len(expires) == 10 and expires[4] == "-" and expires[7] == "-":
        dt = datetime.fromisoformat(expires).replace(tzinfo=timezone.utc)
        return dt.replace(microsecond=0).isoformat()

    dt = datetime.fromisoformat(expires)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def get_repo() -> tuple[Repo, Settings]:
    settings = load_settings()
    repo = Repo(str(settings.db_path))
    repo.init_db()
    return repo, settings


def validate_slug(slug: str, settings: Settings) -> None:
    if slug in settings.reserved_slugs:
        raise typer.BadParameter("Slug ist reserviert.")
    if not settings.slug_re.match(slug):
        raise typer.BadParameter("Slug passt nicht zum Pattern.")


def validate_url(url: str) -> None:
    u = urlparse(url)
    if u.scheme not in ("http", "https"):
        raise typer.BadParameter("URL muss http oder https sein.")


@app.command("db-init")
def db_init() -> None:
    repo, _ = get_repo()
    repo.init_db()
    typer.echo("OK")


@app.command("add")
def add(
    slug: str,
    url: str,
    code: Optional[int] = typer.Option(None, help="301 oder 302"),
    not_before: Optional[str] = typer.Option(None, help='Gültig ab: "YYYY-MM-DD" oder ISO8601'),
    expires: Optional[str] = typer.Option(None, help='Ablauf: "YYYY-MM-DD" oder ISO8601'),
) -> None:
    repo, settings = get_repo()
    validate_slug(slug, settings)
    validate_url(url)

    use_code = code if code is not None else settings.default_code
    if use_code not in (301, 302):
        raise typer.BadParameter("code muss 301 oder 302 sein.")

    not_before_at = parse_expires(not_before)
    expires_at = parse_expires(expires)

    try:
        repo.add_link(
            slug=slug, url=url, code=use_code, not_before_at=not_before_at, expires_at=expires_at
        )
    except Exception as e:
        typer.echo(f"Error adding link: {e}", err=True)
        raise typer.Exit(1) from e

    typer.echo(f"Added: {settings.base_url}/{slug} -> {url} ({use_code})")
    _maybe_export_after_change(settings, repo)


@app.command("export-json")
def export_json() -> None:
    repo, settings = get_repo()
    if settings.export_json_path is None:
        typer.echo("export.json_path not set; nothing to do.", err=True)
        raise typer.Exit(1)

    now_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    links = repo.list_active_links(now_iso)
    payload = {
        "generated_at": now_iso,
        "base_url": settings.base_url,
        "count": len(links),
        "links": [
            {
                "slug": link.slug,
                "short_url": f"{settings.base_url}/{link.slug}",
                "url": link.url,
                "code": link.code,
                "hits": link.hits,
                "not_before_at": link.not_before_at,
                "expires_at": link.expires_at,
                "last_access_at": link.last_access_at,
            }
            for link in links
        ],
    }

    _write_json_atomically(settings.export_json_path, json.dumps(payload, indent=2) + "\n")
    typer.echo(f"Wrote: {settings.export_json_path}")


@app.command("set")
def set_link(
    slug: str,
    url: Optional[str] = typer.Argument(None),
    code: Optional[int] = typer.Option(None, help="301 oder 302"),
    not_before: Optional[str] = typer.Option(None),
    no_not_before: bool = typer.Option(False, help="Startdatum entfernen"),
    expires: Optional[str] = typer.Option(None, help='Ablauf: "YYYY-MM-DD" oder ISO8601'),
    no_expires: bool = typer.Option(False, help="Ablaufdatum entfernen"),
) -> None:
    repo, settings = get_repo()
    validate_slug(slug, settings)

    if url is not None:
        validate_url(url)

    if code is not None and code not in (301, 302):
        raise typer.BadParameter("code muss 301 oder 302 sein.")

    expires_at = parse_expires(expires)
    changed = repo.set_link(slug, url, code, not_before, no_not_before, expires_at, no_expires)
    if changed == 0:
        typer.echo("Nothing changed.", err=True)
        raise typer.Exit(1) from None

    typer.echo(f"Updated: {settings.base_url}/{slug}")
    _maybe_export_after_change(settings, repo)


@app.command("rm")
def rm(slug: str) -> None:
    repo, settings = get_repo()
    validate_slug(slug, settings)

    deleted = repo.delete_link(slug)
    if deleted == 0:
        typer.echo("Not found or already deleted.", err=True)
        raise typer.Exit(1) from None

    typer.echo(f"Deleted (soft): {settings.base_url}/{slug}")
    _maybe_export_after_change(settings, repo)


@app.command("purge")
def purge(
    slug: str,
    yes: bool = typer.Option(
        False,
        "--yes",
        help="Endgültig löschen (ohne Rückfrage)",
    ),
) -> None:
    repo, settings = get_repo()
    validate_slug(slug, settings)

    if not yes:
        typer.echo(
            f"WARNING: This will permanently delete {settings.base_url}/{slug}\n"
            "Re-run with --yes to confirm.",
            err=True,
        )
        raise typer.Exit(1)

    removed = repo.purge_link(slug)
    if removed == 0:
        typer.echo("Not found.", err=True)
        raise typer.Exit(1)

    typer.echo(f"Purged: {settings.base_url}/{slug}")
    _maybe_export_after_change(settings, repo)


@app.command("ls")
def ls(
    format: str = typer.Option("table", help="table|json|tsv"),
    include_deleted: bool = typer.Option(False),
) -> None:
    repo, _ = get_repo()
    links = repo.list_links(include_deleted=include_deleted)

    if format == "json":
        typer.echo(json.dumps([link.__dict__ for link in links], indent=2))
        return

    if format == "tsv":
        typer.echo(
            "\t".join(["slug", "code", "hits", "not_before_at", "expires_at", "deleted_at", "url"])
        )
        for link in links:
            typer.echo(
                "\t".join(
                    [
                        link.slug,
                        str(link.code),
                        str(link.hits),
                        link.not_before_at or "",
                        link.expires_at or "",
                        link.deleted_at or "",
                        link.url,
                    ]
                )
            )
        return

    # table
    headers = ["slug", "code", "hits", "not_before", "expires", "deleted", "url"]
    rows = [
        [
            link.slug,
            str(link.code),
            str(link.hits),
            link.not_before_at or "",
            link.expires_at or "",
            link.deleted_at or "",
            link.url,
        ]
        for link in links
    ]
    _print_table(headers, rows)


@app.command("status")
def status(
    slug: Optional[str] = typer.Option(None, help="Nur einen Slug anzeigen"),
    include_deleted: bool = typer.Option(True, help="Gelöschte Links mit anzeigen"),
    format: str = typer.Option("table", help="table|json|tsv"),
) -> None:
    repo, _ = get_repo()
    now = datetime.now(timezone.utc).replace(microsecond=0)

    def parse_dt(s: Optional[str]) -> Optional[datetime]:
        if not s:
            return None
        try:
            dt = datetime.fromisoformat(s)
        except ValueError:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    def classify(link) -> str:
        if link.deleted_at:
            return "deleted"
        nb = parse_dt(link.not_before_at)
        if nb and now < nb:
            return "planned"
        exp = parse_dt(link.expires_at)
        if exp and exp <= now:
            return "expired"
        return "active"

    def to_tsv_row(link) -> list[str]:
        return [
            link.slug,
            classify(link),
            str(link.code),
            str(link.hits),
            link.not_before_at or "",
            link.expires_at or "",
            link.deleted_at or "",
            link.last_access_at or "",
            link.url,
        ]

    # --- Single slug ---
    if slug is not None:
        link = repo.get_link_any(slug)
        if link is None:
            typer.echo("Not found.", err=True)
            raise typer.Exit(1)

        st = classify(link)

        if format == "json":
            typer.echo(json.dumps({"status": st, **link.__dict__}, indent=2))
            return

        if format == "tsv":
            typer.echo(
                "\t".join(
                    [
                        "slug",
                        "status",
                        "code",
                        "hits",
                        "not_before_at",
                        "expires_at",
                        "deleted_at",
                        "last_access_at",
                        "url",
                    ]
                )
            )
            typer.echo("\t".join(to_tsv_row(link)))
            return

        # table
        headers = [
            "slug",
            "status",
            "code",
            "hits",
            "not_before",
            "expires",
            "deleted",
            "last_access",
            "url",
        ]
        rows = [
            [
                link.slug,
                st,
                str(link.code),
                str(link.hits),
                link.not_before_at or "",
                link.expires_at or "",
                link.deleted_at or "",
                link.last_access_at or "",
                link.url,
            ]
        ]
        _print_table(headers, rows)
        return

    # --- Full list ---
    links = repo.list_links(include_deleted=include_deleted)

    if format == "json":
        typer.echo(
            json.dumps(
                [{"status": classify(link), **link.__dict__} for link in links],
                indent=2,
            )
        )
        return

    if format == "tsv":
        typer.echo(
            "\t".join(
                [
                    "slug",
                    "status",
                    "code",
                    "hits",
                    "not_before_at",
                    "expires_at",
                    "deleted_at",
                    "last_access_at",
                    "url",
                ]
            )
        )
        for link in links:
            typer.echo("\t".join(to_tsv_row(link)))
        return

    # table (pretty, grouped)
    from collections import defaultdict

    grouped = defaultdict(list)
    for link in links:
        grouped[classify(link)].append(link)

    order = ["active", "planned", "expired", "deleted"]
    headers = ["slug", "code", "hits", "not_before", "expires", "deleted", "last_access", "url"]

    for k in order:
        items = grouped.get(k, [])
        if not items:
            continue

        typer.echo(f"\n== {k} ({len(items)}) ==")
        rows = [
            [
                link.slug,
                str(link.code),
                str(link.hits),
                link.not_before_at or "",
                link.expires_at or "",
                link.deleted_at or "",
                link.last_access_at or "",
                link.url,
            ]
            for link in items
        ]
        _print_table(headers, rows)


@app.command("cleanup")
def cleanup() -> None:
    repo, _ = get_repo()
    n = repo.cleanup_expired()
    typer.echo(f"Marked expired links: {n}")


@app.command("serve")
def serve(
    host: Optional[str] = typer.Option(None),
    port: Optional[int] = typer.Option(None),
) -> None:
    settings = load_settings()
    bind_host = host if host is not None else settings.bind_host
    bind_port = port if port is not None else settings.bind_port

    import uvicorn

    uvicorn.run("ghvshort.web:app", host=bind_host, port=bind_port, reload=False)
