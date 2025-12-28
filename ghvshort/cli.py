from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Optional
from urllib.parse import urlparse

import typer

from .config import Settings, load_settings
from .db import Repo

app = typer.Typer(add_completion=False)


def parse_expires(expires: Optional[str]) -> Optional[str]:
    """Akzeptiert 'YYYY-MM-DD' oder ISO8601. Speichert als UTC ISO ohne microseconds."""
    if expires is None:
        return None

    s = expires.strip()
    if len(s) == 10:  # YYYY-MM-DD
        dt = datetime.fromisoformat(s).replace(tzinfo=UTC)
    else:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        dt = dt.astimezone(UTC)

    return dt.replace(microsecond=0).isoformat()


def validate_url(url: str) -> None:
    p = urlparse(url)
    if p.scheme not in ("http", "https"):
        raise typer.BadParameter("URL must start with http:// or https://")
    if not p.netloc:
        raise typer.BadParameter("URL must include a host")


def get_repo() -> tuple[Repo, Settings]:
    settings = load_settings()
    repo = Repo(settings.db_path)
    repo.init_db()
    return repo, settings


def validate_slug(slug: str, settings: Settings) -> None:
    if slug in settings.reserved_slugs:
        raise typer.BadParameter("Slug is reserved")
    if not settings.slug_re.match(slug):
        raise typer.BadParameter("Invalid slug format")


@app.command("db-init")
def db_init():
    """Initialisiert die Datenbank (idempotent)."""
    repo, _ = get_repo()
    repo.init_db()
    typer.echo("DB initialized")


@app.command()
def add(
    slug: str,
    url: str,
    code: int = typer.Option(None, help="301 oder 302"),
    expires: Optional[str] = typer.Option(None, help='Ablauf: "YYYY-MM-DD" oder ISO8601'),
):
    repo, settings = get_repo()
    validate_slug(slug, settings)
    validate_url(url)

    use_code = code if code is not None else settings.default_code
    if use_code not in (301, 302):
        raise typer.BadParameter("code must be 301 or 302")

    expires_at = parse_expires(expires)

    try:
        repo.add_link(slug, url, use_code, expires_at)
    except Exception as e:
        typer.echo(f"Error adding link: {e}", err=True)
        raise typer.Exit(1) from e

    typer.echo(f"Added: {settings.base_url}/{slug} -> {url} ({use_code})")


@app.command()
def set(
    slug: str,
    url: Optional[str] = typer.Argument(None),
    code: Optional[int] = typer.Option(None, help="301 oder 302"),
    expires: Optional[str] = typer.Option(None, help='Ablauf: "YYYY-MM-DD" oder ISO8601'),
    no_expires: bool = typer.Option(False, help="Ablaufdatum entfernen"),
):
    repo, settings = get_repo()
    validate_slug(slug, settings)

    if url is not None:
        validate_url(url)

    if code is not None and code not in (301, 302):
        raise typer.BadParameter("code must be 301 or 302")

    expires_at = parse_expires(expires)

    try:
        repo.set_link(slug, url=url, code=code, expires_at=expires_at, no_expires=no_expires)
    except KeyError as e:
        typer.echo("Not found", err=True)
        raise typer.Exit(1) from e

    typer.echo("Updated")


@app.command("rm")
def rm_link(slug: str):
    repo, settings = get_repo()
    validate_slug(slug, settings)
    try:
        repo.delete_link(slug)
    except KeyError as e:
        typer.echo("Not found", err=True)
        raise typer.Exit(1) from e
    typer.echo("Deleted")


@app.command()
def show(slug: str):
    repo, settings = get_repo()
    validate_slug(slug, settings)
    try:
        link = repo.get_link(slug)
    except KeyError as e:
        typer.echo("Not found", err=True)
        raise typer.Exit(1) from e

    out = {
        "short": f"{settings.base_url}/{link.slug}",
        "slug": link.slug,
        "url": link.url,
        "code": link.code,
        "expires_at": link.expires_at,
        "hits": link.hits,
        "created_at": link.created_at,
        "updated_at": link.updated_at,
    }
    typer.echo(json.dumps(out, indent=2, ensure_ascii=False))


@app.command("ls")
def list_links(format: str = typer.Option("table", help="table|json")):
    repo, settings = get_repo()
    links = repo.list_links()

    if format == "json":
        out = [
            {
                "short": f"{settings.base_url}/{link.slug}",
                "slug": link.slug,
                "url": link.url,
                "code": link.code,
                "expires_at": link.expires_at,
                "hits": link.hits,
            }
            for link in links
        ]
        typer.echo(json.dumps(out, indent=2, ensure_ascii=False))
        return

    if not links:
        typer.echo("(no links)")
        return

    header = f"{'SLUG':<20} {'CODE':<4} {'HITS':<6} {'EXPIRES':<20} URL"
    typer.echo(header)
    typer.echo("-" * len(header))
    for link in links:
        exp = link.expires_at or "-"
        typer.echo(f"{link.slug:<20} {link.code:<4} {link.hits:<6} {exp:<20} {link.url}")


@app.command()
def serve(
    host: Optional[str] = typer.Option(None),
    port: Optional[int] = typer.Option(None),
):
    """Startet den HTTP-Dienst (für systemd)."""
    import uvicorn

    from .web import app as web_app  # lädt settings + init_db

    settings = load_settings()
    bind_host = host or settings.bind_host
    bind_port = port or settings.bind_port

    uvicorn.run(web_app, host=bind_host, port=bind_port, proxy_headers=True)
