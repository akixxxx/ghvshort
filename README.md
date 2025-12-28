# ghvshort

**ghvshort** ist ein minimaler, vereinsinterner Link-Shortener ohne Web-Admin-Oberfläche.
Verwaltung erfolgt ausschließlich über eine CLI, der HTTP-Dienst liefert nur Redirects.

Ziel ist ein **robuster, wartbarer Dienst** für wenige, kontrollierte Kurzlinks
(z. B. Turniere, Trainingspläne, Dokumente).

---

## Eigenschaften

- HTTP-Redirect-Dienst (FastAPI)
- Verwaltung ausschließlich per CLI
- Eigene Slugs (`trainingplan`, `turnier-2026`, …)
- SQLite als Datenbank (eine Datei)
- systemd-Service
- Reverse-Proxy-fähig (nginx empfohlen, aber nicht erzwungen)
- Debian-konform paketierbar

---

## Architektur (Überblick)

```

Internet
│
│ HTTPS
▼
nginx (TLS, Logs, Rate Limit)
│
│ HTTP (localhost)
▼
ghvshort (FastAPI)
│
▼
SQLite (/var/lib/ghvshort/ghvshort.db)

```

---

## Verzeichnisstruktur (Installation)

| Pfad | Zweck |
|-----|------|
| `/usr/bin/ghvshort` | CLI & Server |
| `/etc/ghvshort/config.toml` | Konfiguration |
| `/var/lib/ghvshort/` | SQLite-Datenbank |
| `/lib/systemd/system/ghvshort.service` | systemd Unit |
| `/usr/share/doc/ghvshort/examples/nginx/` | nginx-Beispielkonfiguration |

---

## Konfiguration

### `/etc/ghvshort/config.toml`

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

**Hinweise:**

* `default_code = 302` ist bewusst gewählt (Links können sich ändern)
* `301` nur verwenden, wenn ein Ziel wirklich dauerhaft ist
* Slugs sind absichtlich eingeschränkt (keine Großbuchstaben, keine Sonderzeichen)

---

## CLI-Verwendung

Alle Befehle erfolgen über das Kommando `ghvshort`.

### Datenbank initialisieren (idempotent)

```bash
ghvshort db-init
```

### Link anlegen

```bash
ghvshort add trainingplan https://example.org/training.pdf
```

Mit festem Redirect-Code:

```bash
ghvshort add turnier https://example.org/info --code 301
```

Mit Ablaufdatum:

```bash
ghvshort add anmeldung https://example.org/form --expires 2026-03-01
```

---

### Link ändern

```bash
ghvshort set trainingplan https://example.org/training-v2.pdf
```

Ablaufdatum entfernen:

```bash
ghvshort set anmeldung --no-expires
```

---

### Link löschen

```bash
ghvshort rm trainingplan
```

---

### Anzeigen

```bash
ghvshort show trainingplan
```

---

### Alle Links auflisten

```bash
ghvshort ls
```

Als JSON:

```bash
ghvshort ls --format json
```

---

## Betrieb (systemd)

### Status

```bash
systemctl status ghvshort
```

### Logs

```bash
journalctl -u ghvshort -f
```

### Neustart

```bash
systemctl restart ghvshort
```

---

## nginx (Reverse Proxy)

ghvshort bringt **keine aktive nginx-Konfiguration** mit.
Eine Beispielkonfiguration liegt unter:

```
/usr/share/doc/ghvshort/examples/nginx/go.ghv-altstadt-mg.de.conf
```

### Aktivierung (manuell, bewusst)

```bash
cp /usr/share/doc/ghvshort/examples/nginx/go.ghv-altstadt-mg.de.conf \
   /etc/nginx/sites-available/

ln -s /etc/nginx/sites-available/go.ghv-altstadt-mg.de.conf \
      /etc/nginx/sites-enabled/

nginx -t
systemctl reload nginx
```

TLS (z. B. via Certbot) wird **nicht** vom Paket konfiguriert.

---

## Monitoring & Statistik

* Jeder Redirect erhöht einen internen `hits`-Zähler
* Zusätzlich stehen nginx Access Logs zur Verfügung
* Auswertung kann z. B. über:

  * klassische Logfiles
  * Matomo (Log-Import)
  * eigene Skripte
    erfolgen

---

## Backup & Restore

### Backup

```bash
systemctl stop ghvshort
cp /var/lib/ghvshort/ghvshort.db /backup/ghvshort.db
systemctl start ghvshort
```

### Restore

```bash
systemctl stop ghvshort
cp /backup/ghvshort.db /var/lib/ghvshort/ghvshort.db
chown ghvshort:ghvshort /var/lib/ghvshort/ghvshort.db
systemctl start ghvshort
```

---

## Entwicklung (lokal, mit uv)

```bash
uv init --app --package ghvshort
uv add fastapi uvicorn typer

export GHVSHORT_CONFIG=$PWD/etc/ghvshort/config.toml

uv run ghvshort db-init
uv run ghvshort add test https://example.org
uv run ghvshort serve
```

Test:

```bash
curl -i http://127.0.0.1:8731/test


## Design-Entscheidungen (bewusst)

* **keine Web-GUI** → weniger Angriffsfläche
* **SQLite** → einfach, robust, ausreichend
* **keine automatische nginx-Aktivierung** → Debian-konform
* **CLI-only** → klare Verantwortlichkeiten

---

## Lizenz / Betrieb

Internes Vereinsprojekt.
Keine öffentliche API, kein Mehrmandantenbetrieb.
