# Obsidian MCP Server

Leichtgewichtiger Python-MCP-Server für Obsidian mit Local-REST-API- oder lokalem Dateisystem-Backend.

## Voraussetzungen

- Python 3.11 oder neuer (empfohlen: Python 3.12)
- uv
- Für das REST-Backend: Obsidian mit Local REST API Plugin und Plugin-API-Key
- Für das Dateisystem-Backend: lokaler Pfad zur Vault; Obsidian selbst muss nicht laufen

## Konfiguration

```sh
export OBSIDIAN_API_URL="https://127.0.0.1:27124"
export OBSIDIAN_API_KEY="<dein-plugin-api-key>"
uv sync
uv run obsidian-mcp-server
```

Für eine lokale Vault ohne REST-Plugin/API-Adresse genügt stattdessen:

```sh
export OBSIDIAN_VAULT_PATH="$HOME/dev-obsidian"
uv run obsidian-mcp-server
```

`OBSIDIAN_VAULT_PATH` wählt das lokale Dateisystem-Backend und hat Vorrang vor
REST-Einstellungen. Es ist standardmäßig read-only. Lokale Schreiboperationen lassen
sich ausschließlich operatorseitig mit `OBSIDIAN_ENABLE_WRITES=true` freigeben;
Migration benötigt zusätzlich `OBSIDIAN_ENABLE_FRONTMATTER_MIGRATION=true` und eine
exakte `OBSIDIAN_FRONTMATTER_MIGRATION_ROOT`.

Für lokale Tagesnotizen muss außerdem ein relatives Markdown-Pfadtemplate mit genau
einem `{date}` konfiguriert sein, zum Beispiel:

```sh
export OBSIDIAN_DAILY_NOTE_PATH_TEMPLATE="Journal/{date}.md"
```

`{date}` wird als explizites Datum `YYYY-MM-DD` eingesetzt. Der Zielordner muss
bereits existieren. Perioden außer Tagesnotizen und UI-Steuerung benötigen weiterhin
das REST-Backend. Symlinks und versteckte Vault-Pfade werden nicht verfolgt.

Die URL kann das HTTP- oder HTTPS-Endpunkt des Local REST API Plugins sein. TLS-Zertifikate werden standardmäßig validiert; für lokal selbstsignierte Zertifikate kann `OBSIDIAN_VERIFY_TLS=false` gesetzt werden. Keine Secrets in Repo-Dateien ablegen.

MCP-Client-Konfiguration (Beispiel):

```json
{
  "mcpServers": {
    "obsidian": {
      "command": "/absoluter/pfad/zu/uv",
      "args": ["--directory", "/absoluter/pfad/zu/obsidian-mcp-server", "run", "obsidian-mcp-server"],
      "env": {
        "OBSIDIAN_API_URL": "https://127.0.0.1:27124",
        "OBSIDIAN_API_KEY": "<dein-plugin-api-key>"
      }
    }
  }
}
```

## Implementierte Tools

- `obsidian_get_note`, `obsidian_list_notes` (ein Verzeichnis, nicht rekursiv),
  `obsidian_search_notes` (einfache Textsuche), `obsidian_status`
- `obsidian_get_daily_note` und `obsidian_write_daily_note` (Datum muss explizit als `YYYY-MM-DD` übergeben werden)
- `obsidian_write_note`, `obsidian_append_to_note`, `obsidian_manage_frontmatter`,
  `obsidian_manage_tags`, `obsidian_list_tags`
- `obsidian_get_note_links`, `obsidian_open_in_ui`, `obsidian_audit_frontmatter`
- `obsidian_check_consistency` (begrenzter lokaler Vollscan) und
  `obsidian_check_file_consistency` (eine Note plus Backlinks); beide sind
  read-only und derzeit nur mit dem Dateisystem-Backend verfügbar.

Alle REST-Antworten werden während des HTTP-Streams auf 1 MiB begrenzt. Der Client
fordert unkomprimierte Antworten an und lehnt unerwartete HTTP-Kompression ab,
damit die Byte-Grenze nicht erst nach einer unbeschränkten Dekompression greift.
Listen- und Suchantworten sind auf höchstens 200 Ergebnisse begrenzt (Standard 50).
Versteckte Pfade einschließlich `.obsidian/` sind gesperrt.

Vollständige Link-/Backlink-/unresolved-Link-Metadaten benötigen eine Local-REST-API-
Version, die diese Felder in JSONLogic-Suchergebnissen bereitstellt. Fehlen diese
Felder, liefert das Link-Tool nur aus dem Markdown extrahierte ausgehende Wikilinks;
Backlinks und ungelöste Ziele sind dann ausdrücklich `null` und `metadata_complete`
ist `false`. Der lokale Resolver bevorzugt exakte/case-insensitive Pfade und
akzeptiert Space/Underscore-Varianten nur bei eindeutigem Ziel; mehrdeutige
Treffer bleiben ungelöst. Der Parser ignoriert fenced und einfache Inline-Code-Beispiele,
ersetzt aber keine Obsidian-Indexauflösung.

Die Konsistenztools prüfen sichtbare Markdown-Dateien und Wikilinks lokal; sie
ändern keine Dateien und benötigen keinen REST-Zugriff. Der Vollscan akzeptiert
`limit` von 1 bis `max_limit` (Standard 50, Maximum 200), zusätzlich höchstens
200 Verzeichnisabfragen und 20 Ebenen. Die gezielte Prüfung scannt höchstens
`max_limit` Dateien für Backlinks und die rekursive Verfolgung ausgehender Links.
`complete`, `truncated`, `link_targets_complete`, `backlinks_complete` und
`recursive_complete` kennzeichnen Grenzen und Lesefehler; `linked_notes` und
`recursive_broken_links` beschreiben die erreichte Link-Closure. Bei unvollständigem Zielinventar werden ungelöste Links nicht als
definitiv kaputt ausgegeben; gefundene Backlinks können eine Teilliste sein.
`notes_without_outgoing_links` bedeutet nur „keine ausgehenden Wikilinks“, nicht
automatisch eine verwaiste Note. Berichte enthalten keine Notizinhalte. Der
Dateisystem-Scan ist kein Ersatz für Obsidian-Index-/Backlink-Semantik.

`obsidian_audit_frontmatter` scannt Markdown-Notizen rekursiv und ist standardmäßig
ein Dry-Run. Es meldet Status, konkrete `proposed_fields`, fehlende/ungültige
Felder und unbekanntes `createdAt`, gibt aber keine Notizinhalte aus. `.obsidian/`
und alle versteckten Pfade werden übersprungen. Der Scan ist auf 200 Notizen,
200 Verzeichnisabfragen und 20 Verzeichnisebenen begrenzt (Standard `max_files=50`); bei unvollständigem
Scan oder Lesefehlern wird Apply blockiert. Fehlerhaftes YAML, ungültige Werte,
BOM oder mehrere Frontmatter-Blöcke werden nur als `needs_review` gemeldet.

Migration ist separat und enger freizugeben; dafür ist `OBSIDIAN_ENABLE_WRITES`
nicht erforderlich und bleibt für die normalen Schreibtools deaktiviert:

```sh
export OBSIDIAN_ENABLE_FRONTMATTER_MIGRATION=true
export OBSIDIAN_FRONTMATTER_MIGRATION_ROOT="Notes/Legacy"
```

Danach nur mit `apply=true` und `path="Notes/Legacy"` ausführen; der MCP-Pfad
muss exakt mit der operatorseitigen Scope-Wurzel übereinstimmen. Vor jedem Apply
werden alle Kandidaten erneut gelesen; bei Konflikten erfolgt kein Write. Die
Local REST API bietet keine Transaktion: Scheitert ein PUT nach bereits
erfolgreichen PUTs, meldet das Tool `partial_failure` und führt keinen unsicheren
Rollback aus. Fehlendes historisches `createdAt` wird als YAML-`null` ergänzt,
nie mit einer erfundenen Zeit.

`obsidian_write_daily_note` verlangt ein explizites Datum. Lokal kann eine fehlende
Tagesnotiz mit dem Standard-Frontmatter erstellt werden. Überschreiben ist derzeit
gesperrt, weil kein vertrauenswürdiger, zielgebundener Freigabepfad existiert.
REST-Daily-Note-Schreibvorgänge sind bis zum Nachweis eines atomaren No-Clobber-
Verhaltens gesperrt. Es gibt bewusst keinen impliziten „heute“-Wert.

Die REST-Read-Route verwendet `/periodic/daily/YYYY/M/D/`. Diese Route ist nicht
in jeder Plugin-Version vorhanden:
Local REST API v5.0.2 entfernte die eingebauten `/periodic/`-Routen; die
Companion-Extension `local-rest-api-periodic-notes` stellt sie wieder bereit.
Der Adapter erkennt die fehlende Extension noch nicht vorab; ein nicht
verfügbarer Endpunkt schlägt mit HTTP 404 fehl. Live-Verifikation steht aus.

Die Route ist nur durch Mock-Tests abgedeckt; Live-Verifikation steht aus.

## Sicherheit

Normale MCP-Schreibtools verlangen `OBSIDIAN_ENABLE_WRITES=true` (Standard:
deaktiviert). Zusätzlich bleiben REST-Schreibvorgänge bis zum Nachweis bedingter,
atomarer No-Clobber-Semantik gesperrt. Lokales Ersetzen vorhandener Notizen und
Daily Notes bleibt gesperrt, bis ein vertrauenswürdiger, zielgebundener Approval-
Pfad existiert. Lokales Anlegen neuer Notizen ist davon getrennt; Append auf
vorhandene Notizen benötigt ebenfalls Ersetzungsfreigabe. Die eng begrenzte
Frontmatter-Migration ist separat freizugeben und auf den konfigurierten Root
beschränkt. Es gibt kein Lösch- oder Command-Palette-Tool. Der Server weist
unsichere Pfade ab und protokolliert keine API-Key-Werte. Er bindet selbst keinen
Netzwerk-Port.

## Entwicklung

```sh
uv sync --all-groups
uv lock --check
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run pyright src tests
uv run pip-audit
uv build
uv run python -m compileall -q src tests
git diff --check
```

Die GitHub-Actions-Pipeline führt dieselben Gates bei Push und Pull Request aus;
Dependabot prüft die uv-Abhängigkeiten wöchentlich. Der Coverage-Gate verlangt
100 % Statement- und Branch-Coverage. `CAPABILITY_MATRIX.md` dokumentiert
Backend-Unterschiede, Evidenz und bewusst nicht registrierte gefährliche Tools.
Tests verwenden temporäre Vaults bzw. isolierte HTTPX-Transporte. Ein echter
Live-Vault-/REST-Test ist davon getrennt und benötigt einen ausdrücklich
bereitgestellten API-Key sowie einen freigegebenen Testbereich.
