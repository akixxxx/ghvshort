from ghvshort.config import load_settings


def test_config_loads_from_env(monkeypatch, tmp_path):
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        """
[server]
base_url = "https://go.example"
bind_host = "127.0.0.1"
bind_port = 8731

[storage]
db_path = "/tmp/ghvshort-test.db"

[slugs]
pattern = "^[a-z0-9][a-z0-9_-]{0,62}$"
reserved = ["health"]
default_code = 302
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("GHVSHORT_CONFIG", str(cfg))
    s = load_settings()
    assert s.base_url == "https://go.example"
    assert s.default_code == 302
