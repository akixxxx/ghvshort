from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse, RedirectResponse

from .config import load_settings
from .db import Repo

settings = load_settings()
repo = Repo(settings.db_path)
repo.init_db()

app = FastAPI(title="GHVShort", version="0.1.0")


@app.get("/health", response_class=PlainTextResponse)
def health() -> str:
    return "ok"


@app.get("/{slug}")
def redirect_slug(slug: str):
    if slug in settings.reserved_slugs:
        raise HTTPException(status_code=404, detail="Not found") from None
    if not settings.slug_re.match(slug):
        raise HTTPException(status_code=404, detail="Not found") from None

    try:
        link = repo.resolve_and_hit(slug)
    except KeyError as e:
        raise HTTPException(status_code=404, detail="Not found") from e
    except PermissionError as e:
        raise HTTPException(status_code=410, detail="Gone") from e

    return RedirectResponse(url=link.url, status_code=link.code)
