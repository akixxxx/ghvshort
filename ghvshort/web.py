from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse

from .config import load_settings
from .db import Repo

app = FastAPI()


def _is_expired(expires_at: Optional[str]) -> bool:
    if not expires_at:
        return False
    # Wir speichern ISO8601 in UTC. datetime.fromisoformat kann das lesen.
    try:
        exp = datetime.fromisoformat(expires_at)
    except ValueError:
        # Wenn Daten kaputt sind, lieber 500 vermeiden: dann als "nicht abgelaufen" behandeln.
        return False
    # naive vs aware: wenn naive, behandeln wir es als UTC-naiv
    now = datetime.utcnow() if exp.tzinfo is None else datetime.now(exp.tzinfo)
    return exp <= now


def _not_yet_valid(not_before_at: Optional[str]) -> bool:
    if not not_before_at:
        return False
    try:
        nb = datetime.fromisoformat(not_before_at)
    except ValueError:
        return False

    now = datetime.utcnow() if nb.tzinfo is None else datetime.now(nb.tzinfo)
    return now < nb


@app.get("/health")
def health(request: Request):
    # Defense-in-depth: health soll lokal sein (nginx blockt extern sowieso).
    client = request.client.host if request.client else None
    if client not in ("127.0.0.1", "::1"):
        raise HTTPException(status_code=404)
    return {"status": "ok"}


@app.api_route("/{slug}", methods=["GET", "HEAD"])
def redirect_slug(slug: str):
    settings = load_settings()
    repo = Repo(str(settings.db_path))

    link = repo.get_link_active(slug)
    if link is None:
        raise HTTPException(status_code=404)

    if _not_yet_valid(link.not_before_at):
        raise HTTPException(status_code=404)

    if _is_expired(link.expires_at):
        raise HTTPException(status_code=410)

    repo.touch_hit(slug)
    return RedirectResponse(url=link.url, status_code=link.code)
