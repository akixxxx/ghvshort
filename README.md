# ghvshort

![Debian](https://img.shields.io/badge/Debian-12%20(bookworm)-A81D33?logo=debian&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Style](https://img.shields.io/badge/Code%20Style-ruff-black)
![Type%20Checked](https://img.shields.io/badge/Type%20Checked-mypy-blueviolet)

**ghvshort** ist ein minimaler, vereinsinterner Link-Shortener ohne Web-Admin-Oberfläche.
Er besteht aus einem kleinen HTTP-Redirect-Dienst und einer CLI zur Verwaltung.

Das Projekt ist bewusst:
- **konservativ**
- **Debian-konform**
- **wartbar über Jahre**
- **ohne unnötige Abhängigkeiten**

---

## Eigenschaften

- Redirect-Service (FastAPI)
- Verwaltung ausschließlich per CLI
- Eigene Slugs (`trainingplan`, `turnier-2026`, …)
- SQLite (eine Datei)
- systemd-Service mit Härtung
- Reverse-Proxy via nginx
- Debian-Paket (`.deb`)
- Dev-Workflow mit `uv`, ruff, mypy, pytest, pre-commit

---

## Architektur

```

Internet
│
│ HTTPS
▼
nginx (TLS, Logs, Hardening)
│
│ HTTP (127.0.0.1)
▼
ghvshort (FastAPI)
│
▼
SQLite (/var/lib/ghvshort/ghvshort.db)

````

---

## Verzeichnisstruktur (Installation)

| Pfad | Zweck |
|----|----|
| `/usr/bin/ghvshort` | CLI & Server |
| `/etc/ghvshort/config.toml` | Konfiguration |
| `/var/lib/ghvshort/` | SQLite-Daten |
| `/lib/systemd/system/ghvshort.service` | systemd-Unit |
| `/usr/share/doc/ghvshort/examples/nginx/` | nginx-Beispiel |

---

## Konfiguration

### `/etc/ghvshort/config.toml` (Produktion)

```toml
[server]
base_url = "https://go.ghv-altstadt-mg.de"
bind_host = "127.0.0.1"
bind_port = 8731

[storage]
db_path = "/var/lib/ghvshort/ghvshort.db"

[slugs]
pattern = "^[a-z0-9][a-z0-9_-]{0,62}$"
reserved = ["health", "metrics", "favicon.ico", "robots.txt"]
default_code = 302
````

---

## CLI-Verwendung

### DB initialisieren (idempotent)

```bash
ghvshort db-init
```

### Link anlegen

```bash
ghvshort add trainingplan https://example.org/training.pdf
```

Mit Redirect-Code:

```bash
ghvshort add satzung https://example.org/satzung.pdf --code 301
```

Mit Ablaufdatum:

```bash
ghvshort add anmeldung https://example.org/form --expires 2026-03-01
```

### Anzeigen / ändern / löschen

```bash
ghvshort ls
ghvshort show trainingplan
ghvshort set trainingplan https://example.org/v2.pdf
ghvshort rm trainingplan
```

---

## Betrieb (systemd)

```bash
systemctl status ghvshort
journalctl -u ghvshort -f
systemctl restart ghvshort
```

Der Dienst läuft als **User `ghvshort`** und kann **nur** nach `/var/lib/ghvshort` schreiben.

---

## nginx

Beispielkonfiguration liegt unter:

```
/usr/share/doc/ghvshort/examples/nginx/go.ghv-altstadt-mg.de.conf
```

Aktivierung erfolgt **bewusst manuell**:

```bash
cp /usr/share/doc/ghvshort/examples/nginx/go.ghv-altstadt-mg.de.conf \
   /etc/nginx/sites-available/

ln -s /etc/nginx/sites-available/go.ghv-altstadt-mg.de.conf \
      /etc/nginx/sites-enabled/

nginx -t
systemctl reload nginx
```

---

## TLS / Let’s Encrypt (certbot)

Webroot-Methode (keine automatische nginx-Manipulation):

```bash
apt install certbot
mkdir -p /var/www/_letsencrypt

certbot certonly \
  --webroot \
  -w /var/www/_letsencrypt \
  -d go.ghv-altstadt-mg.de
```

Zertifikate liegen danach unter:

```
/etc/letsencrypt/live/go.ghv-altstadt-mg.de/
```

---

## Entwicklung (macOS / lokal)

### Dev-Config

`etc/ghvshort/config.dev.toml`:

```toml
[server]
base_url = "http://localhost:8731"
bind_host = "127.0.0.1"
bind_port = 8731

[storage]
db_path = ".local/ghvshort.db"

[slugs]
pattern = "^[a-z0-9][a-z0-9_-]{0,62}$"
reserved = ["health"]
default_code = 302
```

### Workflow

```bash
make dev
make run
make check
```

---

## Tooling

* **ruff** – Lint & Format
* **mypy** – Typprüfung
* **pytest** – Tests
* **pre-commit** – lokale Quality-Gates

```bash
make precommit
pre-commit run --all-files
```

---

## Debian-Build (Docker, Debian 12 / bookworm)

### Versionierung

Debian-Versionen werden im Format gebaut:

```
YYYY.MM.DD-1
```

Setzen:

```bash
make deb-version
git commit -am "Release $(date +%Y.%m.%d)-1"
```

### Build

```bash
make deb-docker-dist
```

Artefakte liegen danach unter:

```
dist/
  ghvshort_*.deb
  ghvshort_*.buildinfo
  ghvshort_*.changes
```

---

## Backup / Restore

```bash
systemctl stop ghvshort
cp /var/lib/ghvshort/ghvshort.db /backup/
systemctl start ghvshort
```

---

## Design-Entscheidungen

* keine Web-GUI
* CLI als primäres Interface
* SQLite statt Server-DB
* nginx nicht automatisch konfiguriert
* Debian-Konventionen strikt eingehalten

---

## Lizenz

Dieses Projekt steht unter der **MIT-Lizenz**.
Siehe Datei [`LICENSE`](LICENSE).

Copyright © 2026
Christian Schneider
