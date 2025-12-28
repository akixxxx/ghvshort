# Contributing to ghvshort

Dieses Projekt ist ein **interner Vereinsdienst**.
Beiträge sollen **stabil, nachvollziehbar und wartbar** sein – nicht „clever“.

---

## Grundprinzipien

1. **Einfachheit vor Features**
   - ghvshort ist bewusst minimal
   - keine Web-GUI
   - keine automatische Magie

2. **Debian-Konformität**
   - systemd-Units nach `/lib/systemd/system`
   - Konfiguration nach `/etc`
   - Beispiele nach `/usr/share/doc`

3. **Betrieb vor Theorie**
   - Änderungen müssen im Alltagsbetrieb erklärbar sein
   - Jede Funktion muss dokumentierbar sein

---

## Beiträge (Code)

### Allgemeine Regeln
- Nur Python **stdlib** + explizit erlaubte Dependencies
- Keine neuen Abhängigkeiten ohne klare Begründung
- Keine stillen Verhaltensänderungen
- Lesbarkeit > Abstraktion

### Python-Stil
- Python ≥ 3.11
- Typannotationen verwenden, wo sinnvoll
- Keine „Magic“-Globals
- Fehler explizit behandeln

---

## CLI-Regeln

- CLI ist **primäres Interface**
- Befehle müssen:
  - eindeutig sein
  - skriptfähig sein
  - stabil bleiben (Breaking Changes vermeiden)

Beispiele:
- `ghvshort add …`
- `ghvshort set …`
- `ghvshort rm …`

---

## Slug-Regeln (verbindlich)

Slugs sind **öffentliche URLs** und damit langfristig relevant.

### Erlaubt
- Kleinbuchstaben: `a-z`
- Ziffern: `0-9`
- Bindestrich: `-`
- Unterstrich: `_`

### Verboten
- Großbuchstaben
- Umlaute / Sonderzeichen
- Leerzeichen
- Sehr kurze oder nichtssagende Slugs (`x`, `tmp`, `test`)

### Empfehlungen
- beschreibend, nicht technisch
- Beispiele:
  - `trainingplan`
  - `turnier-2026`
  - `jahresbeitrag`

---

## Redirect-Codes

### Standard
- **302** (temporär, änderbar)

### 301 (dauerhaft)
- nur verwenden, wenn das Ziel **wirklich dauerhaft** ist
- Beispiele:
  - Satzung (PDF)
  - feste Vereinsdokumente

**Regel:**
Wenn Unsicherheit besteht → **302 verwenden**.

---

## Ablaufdaten (`expires_at`)

- Optional
- Sinnvoll für:
  - Anmeldungen
  - zeitlich begrenzte Aktionen
- Nach Ablauf:
  - HTTP 410 (Gone)

---

## Datenbank

- SQLite (`/var/lib/ghvshort/ghvshort.db`)
- Änderungen am Schema:
  - nur bewusst
  - rückwärtskompatibel, wenn möglich
  - dokumentieren

---

## nginx

- ghvshort **konfiguriert nginx nicht automatisch**
- Beispielkonfiguration liegt unter:
```

/usr/share/doc/ghvshort/examples/nginx/

````
- Aktivierung erfolgt manuell durch den Admin

---

## Tests

Minimalanforderungen vor einem Merge:
- CLI-Befehl funktioniert:
- `db-init`
- `add`
- `ls`
- Redirect funktioniert lokal:
```bash
curl -i http://127.0.0.1:8731/<slug>
````

---

## Commits

* Kleine, verständliche Commits
* Aussagekräftige Commit-Messages
* Keine „WIP“-Commits im Main-Branch

---

## Fragen & Diskussionen

Bei Unsicherheit:

* lieber **fragen**
* lieber **weniger ändern**
* lieber **konservativ entscheiden**

Dieses Projekt soll in mehreren Jahren noch verständlich sein.
