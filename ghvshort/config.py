from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

try:
    import tomllib  # Python 3.11+
except Exception:  # pragma: no cover
    import tomli as tomllib  # type: ignore


@dataclass(frozen=True)
class Settings:
    base_url: str
    bind_host: str
    bind_port: int
    db_path: Path
    slug_re: re.Pattern[str]
    reserved_slugs: set[str]
    default_code: int
    export_json_path: Path | None


def load_settings() -> Settings:
    config_path = Path(os.environ.get("GHVSHORT_CONFIG", "/etc/ghvshort/config.toml"))
    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")

    data = tomllib.loads(config_path.read_text(encoding="utf-8"))

    server = data.get("server", {})
    storage = data.get("storage", {})
    slugs = data.get("slugs", {})
    export = data.get("export", {})

    pattern = slugs.get("pattern", r"^[a-z0-9][a-z0-9_-]{0,62}$")
    reserved = set(slugs.get("reserved", []))
    default_code = int(slugs.get("default_code", 302))

    base_url = str(server.get("base_url", "")).rstrip("/")
    if not base_url:
        raise ValueError("server.base_url must be set")

    bind_host = str(server.get("bind_host", "127.0.0.1"))
    bind_port = int(server.get("bind_port", 8731))

    db_path = Path(str(storage.get("db_path", "/var/lib/ghvshort/ghvshort.db")))

    if default_code not in (301, 302):
        raise ValueError("slugs.default_code must be 301 or 302")

    export_json_path_raw = export.get("json_path", "")
    export_json_path = (
        Path(str(export_json_path_raw)) if str(export_json_path_raw).strip() else None
    )

    try:
        slug_re = re.compile(pattern)
    except re.error as e:
        raise ValueError(f"Invalid slug regex in config: {e}") from e

    return Settings(
        base_url=base_url,
        bind_host=bind_host,
        bind_port=bind_port,
        db_path=db_path,
        slug_re=slug_re,
        reserved_slugs=reserved,
        default_code=default_code,
        export_json_path=export_json_path,
    )
