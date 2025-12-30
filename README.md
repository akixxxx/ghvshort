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

[export]
json_path = "/var/lib/ghvshort/public/active-links.json
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

Gerne. Hier ist ein **kompaktes, sachliches README-Snippet**, das genau das neue Feature erklärt, ohne den Rest aufzublähen.
Du kannst es **1:1** an geeigneter Stelle (z. B. nach *HTTP-Verhalten* oder *CLI-Befehle*) einfügen.

---

## JSON-Export für Dokumentation (MkDocs)

`ghvshort` kann eine **maschinenlesbare Übersicht aller aktuell aktiven Links** als JSON-Datei erzeugen.
Diese ist für die Einbindung in die Vereinsdokumentation (z. B. MkDocs) gedacht.

### Eigenschaften

* enthält **nur aktive Links**

  * nicht gelöscht
  * `not-before` erreicht
  * nicht abgelaufen
* atomar geschrieben (keine halbfertigen Dateien)
* **world-readable** (`0644`)
* zyklisch per **systemd-Timer**
* zusätzlich aktualisiert nach Änderungen (`add`, `set`, `rm`, `purge`, `cleanup`)

---

### Konfiguration

In `/etc/ghvshort/config.toml`:

```toml
[export]
json_path = "/var/lib/ghvshort/public/links.json"
```

Wird `export.json_path` nicht gesetzt, ist der Export deaktiviert.

---

### Manuelles Erzeugen

```bash
ghvshort export-json
```

Erzeugt bzw. aktualisiert die konfigurierte JSON-Datei.

---

### Automatische Aktualisierung

Das Paket liefert einen systemd-Timer mit:

* **Service:** `ghvshort-export.service`
* **Timer:** `ghvshort-export.timer` (stündlich)

Aktivierung:

```bash
systemctl enable --now ghvshort-export.timer
```

---

### Berechtigungen für JSON-Export

Der JSON-Export wird standardmäßig unter `/var/lib/ghvshort/public/active-links.json` abgelegt.

Das Verzeichnis `/var/lib/ghvshort` ist bewusst **nicht world-readable**. Damit der Webserver (nginx) dennoch auf die Exportdatei zugreifen kann, muss der nginx-User Mitglied der Gruppe `ghvshort` sein.

Auf Debian (Standard: `www-data`):

```bash
usermod -aG ghvshort www-data
systemctl restart nginx
```

Nach diesem Schritt kann nginx die Datei lesen, ohne dass das Datenverzeichnis für alle Benutzer geöffnet wird.

---

### Einbindung über nginx

Beispiel-Snippet für einen bestehenden nginx-vHost:

```nginx
location = /links.json {
    default_type application/json;
    add_header Cache-Control "no-store";
    alias /var/lib/ghvshort/public/links.json;
}
```

Die Datei kann anschließend z. B. von MkDocs per JavaScript geladen und dargestellt werden.

---

### Format

Beispiel:

```json
{
  "generated_at": "2025-12-29T12:00:00+00:00",
  "base_url": "https://go.ghv-altstadt-mg.de",
  "count": 2,
  "links": [
    {
      "slug": "sommerfest",
      "short_url": "https://go.ghv-altstadt-mg.de/sommerfest",
      "url": "https://example.org/fest",
      "code": 302,
      "hits": 17,
      "not_before_at": null,
      "expires_at": "2026-06-03T00:00:00+00:00",
      "last_access_at": "2025-12-28T19:12:00+00:00"
    }
  ]
}
```

---

### Designentscheidung

Der Export erfolgt **nicht über HTTP-Endpoints**, sondern bewusst als Datei:

* kein zusätzlicher API-Angriffspunkt
* einfache Integration in statische Dokumentation
* robust gegenüber Neustarts und Deployments

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
