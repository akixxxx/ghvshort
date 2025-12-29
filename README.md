# ghvshort

![Debian package](https://img.shields.io/badge/deb-2025.12.29--1-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)

Ein schlanker, selbst betriebener Link-Shortener für den **GHV Altstadt/MG-Bettrath e.V.**

Kein Webinterface, keine Cloud-Abhängigkeiten – Verwaltung erfolgt ausschließlich über eine CLI.
Der Dienst ist für den dauerhaften Betrieb auf einem Debian-Server ausgelegt und wird als `.deb`-Paket ausgeliefert.

---

## Eigenschaften

- HTTP-Redirects (301 / 302)
- Eigene Slugs
- SQLite (stdlib), keine externen DB-Abhängigkeiten
- CLI-Verwaltung (`ghvshort`)
- Zeitsteuerung:
  - `not-before` (Link ist erst ab Datum gültig)
  - `expires` (Link läuft ab)
- Zugriffszähler (`hits`)
- Soft-Delete + Cleanup
- Status-Übersicht (aktiv / geplant / abgelaufen / gelöscht)
- Systemd-Service + nginx-Integration
- Automatische Schema-Migrationen (SQLite)

---

## Installation

```bash
apt install ghvshort
````

Nach der Installation läuft der Dienst standardmäßig lokal auf `127.0.0.1` und wird über nginx exponiert.

---

## Konfiguration

Standardpfad:

```text
/etc/ghvshort/config.toml
```

Beispiel:

```toml
[server]
base_url = "https://go.ghv-altstadt-mg.de"
bind_host = "127.0.0.1"
bind_port = 8731

[storage]
db_path = "/var/lib/ghvshort/ghvshort.db"

[slugs]
pattern = "^[a-z0-9][a-z0-9_-]{0,62}$"
reserved = ["health"]
default_code = 302
```

Alle Zeitangaben erfolgen in **UTC** und werden als **ISO8601** gespeichert.

---

## CLI-Befehle

### Datenbank initialisieren / migrieren

```bash
ghvshort db-init
```

Wird automatisch bei Installation und Start ausgeführt.
SQLite-Migrationen laufen **vorwärts-only** über `PRAGMA user_version`.

---

### Link anlegen

```bash
ghvshort add <slug> <url> [OPTIONS]
```

Beispiele:

```bash
# sofort gültig
ghvshort add sommerfest https://example.org/fest

# erst ab Datum gültig
ghvshort add sommerfest https://example.org/fest \
  --not-before 2026-06-01

# mit Ablaufdatum
ghvshort add sommerfest https://example.org/fest \
  --expires 2026-06-03

# mit beidem
ghvshort add sommerfest https://example.org/fest \
  --not-before 2026-06-01 \
  --expires 2026-06-03
```

Optionen:

* `--code 301|302`
* `--not-before YYYY-MM-DD | ISO8601`
* `--expires YYYY-MM-DD | ISO8601`

---

### Link ändern

```bash
ghvshort set <slug> [OPTIONS]
```

Beispiele:

```bash
# URL ändern
ghvshort set sommerfest https://neue-url.example

# Ablaufdatum entfernen
ghvshort set sommerfest --no-expires

# Startdatum entfernen
ghvshort set sommerfest --no-not-before
```

---

### Link löschen (Soft-Delete)

```bash
ghvshort rm <slug>
```

Markiert den Link als gelöscht (Soft-Delete). Der Eintrag bleibt für Status und Audit erhalten.

### Link endgültig entfernen

```bash
ghvshort purge <slug> --yes
````

Löscht den Link unwiderruflich aus der Datenbank.

---

### Auflisten aller Links

```bash
ghvshort ls
```

Formate:

```bash
ghvshort ls --format table   # Standard, menschenlesbar
ghvshort ls --format tsv     # für Skripte
ghvshort ls --format json
```

---

### Statusübersicht

```bash
ghvshort status
```

Status-Kategorien:

* `active` – aktuell gültig
* `planned` – `not-before` liegt in der Zukunft
* `expired` – Ablaufdatum überschritten
* `deleted` – manuell gelöscht

Beispiele:

```bash
ghvshort status
ghvshort status --slug sommerfest
ghvshort status --format tsv
```

---

### Cleanup abgelaufener Links

```bash
ghvshort cleanup
```

Markiert abgelaufene Links (`expires_at <= now`) als gelöscht (`deleted_at`).

Ein späteres Hard-Delete ist optional und nicht standardmäßig aktiv.

---

## HTTP-Verhalten

| Zustand                          | HTTP-Code |
| -------------------------------- | --------- |
| aktiv                            | 301 / 302 |
| noch nicht gültig (`not-before`) | 404       |
| abgelaufen                       | 410       |
| gelöscht                         | 404       |

---

## Migrationen

* SQLite-Schema-Versionierung über `PRAGMA user_version`
* Migrationen laufen automatisch bei:
  * `ghvshort db-init`
  * Paket-Installation / Upgrade
* Migrationen sind:
  * vorwärts-only
  * transaktional
  * idempotent über Versionsnummer

---

## Entwicklung

```bash
make dev     # Dev-Umgebung (uv)
make test    # pytest
make check   # ruff + mypy
```

Hinweis:
Bei Schemaänderungen kann die lokale Dev-DB gefahrlos gelöscht werden:

```bash
rm -f .local/ghvshort.db
```

---

## Lizenz

MIT License
Siehe `LICENSE`.

---

## Projektziel

`ghvshort` ist bewusst **klein**, **wartbar** und **vorhersagbar** gehalten.
Kein Feature ohne klaren Vereinsnutzen.

> Stabilität schlägt Komfort.
> Betrieb schlägt Spielerei.
