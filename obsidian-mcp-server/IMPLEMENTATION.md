# Leichtgewichtiger Obsidian MCP-Server – Umsetzungsplan

Stand: 2026-10-25
Referenz: `../obsidian-mcp-server2` (Version 3.7.1)
Zielordner: `obsidian-mcp-server/` (bei der Inventur leer)

## Ziel und Leitplanken

Ein eigener, bewusst schlanker MCP-Server, mit dem sich Obsidian nicht nur als Markdown-Dateiablage, sondern als Wissenssystem gut bedienen lässt: Notizen verwalten, Tagesnotizen nutzen, Links/Backlinks nachvollziehen, die Obsidian-Oberfläche öffnen und ausgewählte Befehle ausführen. Die Referenz bietet eine breite API über Obsidian Local REST API; wir übernehmen sinnvolle Fähigkeiten, nicht ihre gesamte Framework-, Transport- und Konfigurationskomplexität. Kein Kopieren von Referenzcode ohne Prüfung von Lizenz und Abhängigkeiten.

**Frontmatter ist ein verbindlicher Bestandteil des Inhaltsmodells:** jede Markdown-Notiz im Vault soll standardisiertes YAML-Frontmatter mit mindestens `title`, `tags`, `createdAt`, `updatedAt` und `status` haben. Neu erstellte Notizen erhalten es automatisch. Bestehende Notizen werden nicht beim Lesen still verändert, sondern über einen separaten, zunächst nur berichtenden Migrations-/Audit-Workflow kontrolliert ergänzt.

Vorgeschlagenes Schema (optionale Werte wie `aliases`/`type` nur setzen, wenn bekannt):

```yaml
---
title: "Aus dem Dateinamen abgeleiteter Titel"
tags: []
createdAt: "2026-10-25T12:00:00Z"
updatedAt: "2026-10-25T12:00:00Z"
status: active
---
```

Zeitwerte im Beispiel sind nur Schemaillustration; zur Laufzeit immer aktuelle UTC-Zeit einsetzen. `createdAt` unbekannter Altnotizen wird als YAML-`null` gespeichert und im Audit als unbekannt ausgewiesen.

Empfohlene erste Ausbaustufe: ein einzelner Python-Prozess und schlanke Abhängigkeiten, stdio-Transport als Startpunkt, Zugriff über Obsidian Local REST API (API-Key nur aus Umgebungsvariable), klarer Service-Layer, sichere Vault-Pfadgrenzen. Python ist die verbindliche Implementierungssprache. Kein HTTP-Transport, Telemetrie, Auth-Framework oder austauschbarer Storage im MVP.

## Vollständiges Capability-Inventar der Referenz

Die Referenz registriert **14 Tools** (12 regulär + 2 opt-in) und **3 Resources**. Es gibt keine Prompts. „Priorität“ ist unsere Empfehlung für den eigenen Server, nicht die Einstufung der Referenz.

| Priorität | Kategorie | Tool / Resource | Fähigkeit | MVP? |
|---|---|---|---|---|
| P0 | Lesen / Navigation | `obsidian_get_note` | Notiz lesen; Inhalt, strukturierte Form, Dokumentübersicht oder Abschnitt; aktive/periodische Notiz als Ziel | Ja; Tagesnotiz-Ziel ausdrücklich aufnehmen |
| P0 | Lesen / Navigation | `obsidian_list_notes` | Dateien/Ordner mit Tiefe und Filtern auflisten | Ja |
| P0 | Suche | `obsidian_search_notes` | Textsuche; Referenz zusätzlich JSONLogic und optional Omnisearch/BM25 | Ja: einfache Textsuche |
| P0 | Schreiben | `obsidian_write_note` | Notiz anlegen/überschreiben oder gezielt Abschnitt ersetzen | Ja: anlegen, explizites Überschreiben |
| P0 | Schreiben | `obsidian_append_to_note` | An Datei oder Abschnitt anhängen, bei Bedarf erstellen | Ja |
| P1 | Metadaten | `obsidian_list_tags` | Vault-Tags mit Häufigkeit, Filter und Begrenzung | Ja, nach Kern-MVP |
| P1 | Metadaten | `obsidian_manage_frontmatter` | Frontmatter-Schlüssel lesen, setzen, löschen | Ja, nach Kern-MVP |
| P1 | Metadaten | `obsidian_manage_tags` | Tags in Frontmatter/Inline-Tags auf Notiz verwalten | Ja, nach Kern-MVP |
| P0 | Metadaten / Schema | Frontmatter-Standard | Jede Markdown-Notiz erhält validiertes YAML mit Pflichtfeldern; neue Notizen automatisch, bestehender Vault über Audit/Migration; Updates pflegen `updatedAt` | Ja, ab Phase 2 plus Migrationsphase |
| P1 | Präzise Bearbeitung | `obsidian_patch_note` | Anfügen, voranstellen oder Abschnitt/Block ersetzen | Später; nur falls einfacher Append/Write nicht genügt |
| P1 | Präzise Bearbeitung | `obsidian_replace_in_note` | Literal-/Regex-Ersetzungen in Notiz, optional Frontmatter | Später; Regex-Sicherheitsgrenzen nötig |
| P2 | Entfernen | `obsidian_delete_note` | Notiz dauerhaft löschen; optionale explizite Nutzerbestätigung | Später, standardmäßig aus bzw. streng abgesichert |
| P1 | Obsidian-App | `obsidian_open_in_ui` | Notiz in Obsidian öffnen, optional neues Pane | M5, sofern M0 Plugin/API-Unterstützung bestätigt |
| P1 | Wissensgraph | `obsidian_search_notes` (JSONLogic-Modus) | Nach Links, Backlinks, ungelösten Links und strukturierten Notizdaten filtern, sofern Plugin/API-Version dies unterstützt | Ja, als Link-/Backlink-Use-Case prüfen |
| P1 | Tagesnotizen | `obsidian_get_note` (periodic target) | Tages-/Wochen-/Monats-/Quartals-/Jahresnotiz über Perioden-Ziel und Datum ansprechen | Ja; Tagesnotiz ist Kernworkflow |
| P3 | Plugin-Kommandos | `obsidian_list_commands` | verfügbare Command-Palette-Befehle auflisten | Nicht im MVP; opt-in |
| P3 | Plugin-Kommandos | `obsidian_execute_command` | Command-Palette-Befehl ausführen | Nicht im MVP; opt-in und potenziell destruktiv |
| P1 | Resource | `obsidian://vault/{+path}` | Notizinhalte, Frontmatter, Tags und Dateimetadaten als Resource | Optional nach den P0-Tools |
| P1 | Resource | `obsidian://tags` | vollständige Tag-Übersicht mit Häufigkeit | Optional; gegenüber Tag-Tool wenig Zusatznutzen |
| P2 | Diagnose | `obsidian://status` | Plugin-Erreichbarkeit, Authentifizierung, Versionen und API-Erweiterungen | Empfohlen als schlanke Diagnose |

### Priorisierung

- **P0 – Notizen verlässlich verwalten:** lesen, listen, suchen, erstellen/ändern/anhängen und Metadaten pflegen.
- **P1 – Obsidian als Wissenssystem bedienen:** Tagesnotizen und andere periodische Notizen, Link-/Backlink-Auswertung, UI öffnen und Diagnose.
- **P2 – optionale weitreichende Aktionen:** Command-Palette nur mit expliziter Opt-in-Allowlist; Löschen bleibt separat und streng begrenzt.

## Sicherheits- und Qualitätsanforderungen

1. **Fail closed:** fehlende/ungültige Konfiguration, unerreichbares Plugin oder Auth-Fehler führen zu klaren Fehlern, nie zu stiller Fallback-Ausführung.
2. **API-Key:** ausschließlich `OBSIDIAN_API_KEY` aus Prozessumgebung; niemals loggen oder in Fehlertexte aufnehmen. Die lokale REST API erwartet Bearer-Auth; Basis-URL/Port/HTTPS des Plugins müssen konfigurierbar oder als dokumentierte Defaults festgelegt sein.
3. **Pfadgrenzen:** alle Pfade relativ zum Vault interpretieren; Traversal (`..`), absolute Pfade und Symlink-Ausbrüche ablehnen. Lese-/Schreibgrenzen getrennt konfigurierbar; read-only-Modus muss Schreibtools blockieren.
4. **Destruktive Aktionen:** Delete und Command-Execution nicht im MVP. Später nur eng begrenzt und mit dokumentierter Freigabe/Bestätigung.
5. **Überschreiben:** Schreiben auf bestehende Notizen standardmäßig ablehnen; Überschreiben nur über expliziten Parameter.
6. **Eingaben begrenzen:** Suche und Listen standardmäßig höchstens 50 Einträge, konfigurierbares `limit` bis maximal 200; einzelner Notizinhalt maximal 1 MiB. Regex-Längen- und Ausführungsgrenzen, keine unbeschränkten rekursiven Scans.
7. **MCP-stdio:** stdout bleibt ausschließlich MCP-Protokoll; Logs und Diagnosen nach stderr.
8. **Tests:** Pfad-Traversal, Read-only, Auth-/Netzwerkfehler, fehlende Notiz, bestehende Notiz, YAML-Fehler und MCP-Tool-Schemas abdecken.
9. **Deployment-Trust-Boundary:** stdio ist lokal, aber jeder verbundene MCP-Client erhält faktisch Vault-Rechte. Server nicht ungeschützt als Netzwerkdienst exponieren; wenn später HTTP hinzukommt, Authentifizierung, Bind-Adresse, TLS/Reverse-Proxy und Client-Autorisierung sind eigene Release-Blocker.
10. **Konsistenz bei Konkurrenz:** Create-only/Overwrite muss gegen parallele Änderungen bestmöglich abgesichert werden (ETag/Revision/If-Match falls API unterstützt); andernfalls Rennen dokumentieren und keine falsche atomare Garantie geben.
11. **Betriebsverhalten:** Versions-/Plugin-Voraussetzungen, Timeout, Request- und Antwortgrößenlimits, User-Agent sowie klare Unterscheidung von 401/403, 404, 429 und 5xx festlegen. Keine unbegrenzten automatischen Retries bei Schreiboperationen.
12. **Tool-Ausgaben:** Inhalte aus Notizen sind nicht vertrauenswürdige Daten. Tool-Antworten klar als Vault-Inhalt abgrenzen; eingebettete Anweisungen nie als Agentenanweisungen behandeln. Fehler sollen keine unnötigen Notizinhalte zurückspiegeln.
13. **Datei-/Markdown-Semantik:** Zeilenenden, UTF-8/BOM, leere Dateien, Unicode-Pfade, Dateiendungen und Konflikte mit Obsidian-Namensauflösung testen; Frontmatter-Änderungen dürfen den übrigen Notizinhalt nicht unbeabsichtigt normalisieren.
14. **Frontmatter-Vertrag:** Alle vom Server erstellten Markdown-Dateien haben gültiges YAML-Frontmatter und die erforderlichen Felder. Vorhandene Werte und unbekannte zusätzliche Schlüssel bleiben bei Updates erhalten. `createdAt` wird beim Anlegen gesetzt und nie still geändert; `updatedAt` ändert sich nur bei tatsächlicher Inhaltsänderung durch den MCP-Server. Ungültiges YAML führt bei Metadatenänderungen zu einem Fehler ohne Schreibvorgang.
15. **Zeit und Tags:** `createdAt`/`updatedAt` sind ISO-8601 UTC-Zeitstempel mit `Z`. `tags` ist stets eine YAML-Liste stabiler Obsidian-Tags ohne führendes `#`, eindeutig und normalisiert; keine erfundenen Tags. `title` standardmäßig aus dem Notiznamen ableiten, außer ein expliziter Titel wurde angegeben. `status` ist eines von `active`, `in-progress`, `done`, `archived`; Default `active`.

## Verbindlicher Entwicklungsablauf

### TDD pro Verhalten und Tool

Für jedes Tool und jede eigenständige Funktion gilt strikt **RED → GREEN → REFACTOR**: Test zuerst schreiben, den erwarteten Fehlschlag tatsächlich sehen, minimal implementieren, gezielt grün testen und erst dann refaktorisieren. Keine Produktionsänderung ohne vorherigen roten Verhaltenstest. Tests werden versioniert im Repository gespeichert.

Pro vertikalem Slice: (1) ein Verhalten auswählen, (2) Test mit aussagekräftigem Namen schreiben, (3) gezielten Testlauf mit erwartetem fachlichem Fehler prüfen, (4) minimale Implementierung, (5) gezielten Test grün prüfen, (6) betroffene Suite und Linter/Typprüfung, (7) Ergebnis und offene Grenzen dokumentieren. Nicht alle Tests vorab in einem Batch schreiben.

### Testumfang und Qualitätssicherung

- Je Tool: Schema-/Eingabevalidierung, Erfolg, Fehler, Limits und Seiteneffekt-/Sicherheitsgrenzen. Service-Tests ergänzen Tooltests; MCP-stdio-Integration prüft Discovery und JSON-RPC-Aufruf.
- Reale Tool-Logik, Pfadpolicy und Frontmatter-Regeln ausführen. HTTP-Mocks sind für reproduzierbare Netzwerkfehler zulässig; nur Mock-Aufruf-Erwartungen reichen nicht.
- Test-Vault ausschließlich temporär/isoliert; nie den produktiven Vault oder echte API-Schlüssel in Tests, Fixtures, Snapshots oder Logs verwenden.
- Schreibtests müssen bei Fehler/Scope-Verstoß nachweisen, dass keine Änderung erfolgt. Frontmatter-Testmatrix umfasst neue, gültige, fehlende und fehlerhafte Metadaten sowie Erhalt unbekannter Felder und des Body.
- Qualitätsgate pro Meilenstein: Format/Lint, Typprüfung, gezielte Tests, gesamte Suite, MCP-Protokoll-Smoke-Test. Security-/Dependency-Checks nur wenn im Projekt eingerichtet; andernfalls als nicht vorhanden ausweisen, nicht als bestanden behaupten.
- Tests laufen in CI für relevante Änderungen. Coverage wird berichtet, aber nicht als Ersatz für Verhaltensabdeckung verwendet. RED/GREEN-Läufe werden in PR/Arbeitsbericht knapp mit Testname und Ergebnis festgehalten.

## Abarbeitungsreihenfolge und Gates

Die Reihenfolge ist absichtlich abhängigkeitsorientiert. Ein Gate muss erfüllt sein, bevor der nächste Meilenstein beginnt. Optionale Fähigkeiten kommen erst nach dem funktionsfähigen, getesteten Kern.

### M0 – Entscheidungen und API-Spike (keine Produktions-Tools)

1. Zielbackend verbindlich festlegen: Local REST API als einziges MVP-Backend; kein paralleler direkter Dateisystem-Backend.
2. Im Referenzprojekt `obsidian-mcp-server2/docs/openapi.yaml`, `README.md` und Implementierung die konkret benötigten Routen/Versionen prüfen: Health/Auth, Datei lesen/listen/suchen/schreiben, periodische Notiz, Linkdaten und UI-Öffnen. In einem isolierten Test-Vault einen kurzen manuellen Spike ausführen.
3. Belegen, welche Operationen atomar sind und welche API-/Plugin-Mindestversionen nötig sind. Create-only ohne atomare API-Garantie nicht als zugesichert spezifizieren.
4. Frontmatter-Audit/Migration schließt `.obsidian/` und versteckte Pfade aus. Vertragliche Defaults sind bereits entschieden: Status `active|in-progress|done|archived` (Default `active`), UTC ISO-8601 mit `Z`, unbekanntes Legacy-`createdAt` wird `null`.
5. Auf Basis des Spikes endgültig festlegen, ob Links/Backlinks und UI-Öffnen zuverlässig im MVP liegen oder ob API-Erweiterung/Plugin-Voraussetzung nötig ist.

**Gate M0:** kurze Entscheidungstabelle mit Endpunkt, getesteter Plugin-Version, Ergebnis, Limit und offenem Risiko liegt vor; keine angenommene REST-Fähigkeit bleibt unbelegt. Bei Blockade Entscheidung dokumentieren und betreffende Funktion aus dem MVP nehmen, nicht mit spekulativem Fallback weiterbauen.

### M1 – Projektgerüst und Qualitätsgates

1. Python 3.11+ verwenden: offizieller MCP Python SDK v2 verlangt diese Version. Vorhanden sind Python 3.11, 3.12 und 3.14; für deterministische Entwicklung Python 3.12 mit uv-verwalteter Projekt-venv wählen. System-Python 3.9 nicht verändern.
2. `pyproject.toml`, `uv.lock`, Ruff und pytest einrichten. MCP-Server über `mcp.server.MCPServer` und stdio bereitstellen; Local REST API über einen asynchronen HTTP-Client kapseln.
3. Minimalen MCP-stdio-Server mit einer health/status-Fähigkeit erstellen. Zuerst Integrationstest für `tools/list` und `tools/call` rot/grün durchziehen.
4. Konfiguration validieren (API-Basis-URL, API-Key, Timeout, read-only/scopes); HTTP-Client zentral kapseln, Bearer-Auth, Signal/Timeout und Secret-Redaction testen.

**Gate M1:** frischer Checkout kann mit dokumentiertem Befehl Tests, Lint und Typprüfung ausführen; MCP stdio liefert gültiges Protokoll ohne Nicht-MCP-Ausgabe auf stdout; Secret taucht in keiner Ausgabe auf.

### M2 – Sicherer Lese-Kern (jeweils eigener TDD-Slice)

In dieser Reihenfolge implementieren und prüfen:
1. `obsidian_get_note` für konkreten Pfad, einfache Markdown-Ausgabe.
2. `obsidian_list_notes` mit Default-Limit 50, Maximum 200 und sicherem Pfadfilter.
3. `obsidian_search_notes` als einfache Textsuche mit Pfadfilter, Kontext und Default-Limit 50/Maximum 200.
4. Periodische Notiz lesen, zunächst Tagesnotiz mit explizitem Datum; „heute“ erst nach geklärter Vault-Zeitzone.

**Gate M2:** pro Tool rote/grüne Tests vorhanden; Auth-, Timeout-, 404-, Pfad-Scope- und Grenzfälle abgedeckt; vollständige Suite grün; manueller Smoke-Test gegen Test-Vault protokolliert.

### M3 – Frontmatter-Kern und sichere Schreibwerkzeuge

1. Reine Frontmatter-Parser/Serializer-Funktion mit Tests für gültiges, fehlendes, fehlerhaftes, BOM-/Zeilenenden- und unbekannte-Felder-Szenario implementieren.
2. `obsidian_write_note`: neue `.md`-Dateien erhalten Pflichtschema; Überschreiben ist standardmäßig aus und nur explizit möglich. Semantik bei API-Upsert/Concurrency nur so stark versprechen, wie M0 belegt.
3. `obsidian_append_to_note`: vorhandene Notiz ändern oder explizit neue Notiz erstellen; bei Neuanlage Frontmatter vor Body setzen, nicht duplizieren.
4. `updatedAt` nur dann aktualisieren, wenn der MCP-Server den Notizinhalt tatsächlich ändert; externe Obsidian-Änderungen bleiben unberücksichtigt. `createdAt` nie bei bestehenden Notizen ändern. Unbekannte Schlüssel und Body-Inhalt erhalten.
5. Read-only und Write-Scope zentral vor jeder Mutation durchsetzen.

**Gate M3:** Schreibfehler/Scope-Verstoß verursachen keinen Seiteneffekt; Schema, Timestamps und Body bleiben korrekt; alle Tests inkl. gesamter Suite grün.

### M4 – Metadaten-Tools

1. `obsidian_manage_frontmatter` (get/set/delete) mit Schutz gegen versehentliches Entfernen/Entwerten von Pflichtfeldern.
2. `obsidian_manage_tags` und `obsidian_list_tags` mit einheitlicher Normalisierung/Deduplizierung.
3. Entscheiden und testen, wie man Pflichtfelder repariert; gewöhnliches Set/Delete darf keine stillen Reparaturen vornehmen.

**Gate M4:** YAML-Roundtrip und ungültiges YAML ohne Schreibvorgang; unbekannte Felder erhalten; Tags konsistent; volle Qualitätsgates grün.

### M5 – Obsidian-spezifische Bedienung

1. Implementiert: Tagesnotiz über Periodic-Note-Funktion anlegen oder mit `overwrite=true` vollständig ersetzen; Datum ist explizit `YYYY-MM-DD`, „heute“ wird ohne bestätigte Vault-Zeitzone nicht geraten.
2. Ausgehende Wikilinks, Backlinks und ungelöste Ziele liefern, nur wenn M0 eine verlässliche Quelle bestätigt. Parser-Fallback separat begrenzen und als unvollständig kennzeichnen.
3. `obsidian_open_in_ui` nur mit belegter Plugin-Funktion einbauen.
4. Status/Diagnose so anbieten, dass API-/Plugin-Erreichbarkeit und Version schnell erkennbar sind.

**Gate M5:** Links mit Alias, Heading, mehrfachen Basenames und ungelöstem Ziel; Periodic-Note-Route, fehlende Extension und Plugin-Mindestversion live prüfen. Create/Replace sind wegen fehlender API-Revision nicht atomar bei parallelen Schreibern.

### M6 – Frontmatter-Audit und Altbestand-Migration

1. Implementiert: rekursives Audit mit versteckte Pfade/`.obsidian/` ausgeschlossen; Dry-Run ist Standard und gibt keine Notizinhalte aus.
2. Implementiert: fehlende Pflichtfelder werden als konkrete `proposed_fields` ausgegeben. Unbekanntes historisches `createdAt` wird als YAML-`null` vorgeschlagen und als unbekannt markiert.
3. Implementiert: Apply erfordert separates Betreiber-Flag und eine exakt konfigurierte Scope-Wurzel; unvollständige Scans und Preflight-Konflikte blockieren alle Writes. Fehlerhaftes YAML, ungültige Werte, BOM und mehrere Frontmatter-Blöcke werden nicht automatisch geändert.
4. Begrenzungen: maximal 200 Markdown-Dateien, 200 Verzeichnisabfragen und 20 Verzeichnisebenen; `max_files` default 50, maximal 200. Da die Local REST API keine Transaktion anbietet, kann ein Fehler nach einem erfolgreichen PUT eine Teilmigration hinterlassen; das Tool meldet `partial_failure`, versucht aber keinen unsicheren Rollback.
5. Getestet: Dry-Run ohne PUT, Apply mit Re-Read/Conflict-Abbruch, unbekanntes `createdAt`, Migration ohne globale Write-Freigabe, exakter Scope, Scan-Limit, Idempotenz und gemeldeter Teilfehler.

**Gate M6:** Dry-Run hat null Schreibeffekte; wiederholter Apply ist idempotent; Konflikte/unvollständige Scans verursachen null Writes; ein Upstream-Fehler nach erfolgtem Write wird als Teilmigration ausgewiesen. Atomarität über mehrere Notizen ist durch die API nicht gewährleistet.

### M7 – Optionale Erweiterungen (einzeln priorisieren)

Nur mit konkretem Nutzerbedarf und eigener Sicherheits-/TDD-Gate: `obsidian_patch_note`, `obsidian_replace_in_note`, Delete, Command-Palette. Freie Command-ID-Ausführung ist ausgeschlossen; Befehle müssen operatorseitig allowlisted sein. Jede Erweiterung ist separat abschaltbar und darf Kern-Tools nicht destabilisieren.

## Abschlusskriterien je Meilenstein

Ein Meilenstein gilt nur dann als abgeschlossen, wenn alle Punkte erfüllt sind:

- Akzeptanzkriterien und API-Voraussetzungen dokumentiert.
- Für jeden implementierten Verhaltenstracer existiert ein versionierter Test, der zuerst rot und danach grün lief.
- Gezielte Tests, vollständige Test-Suite, Formatter/Linter und Typprüfung sind grün; nicht ausgeführte Gates bleiben ausdrücklich offen.
- MCP-stdio-Integration getestet; bei API-Funktionen zusätzlich Test-Vault-Smoke-Test mit Ergebnis dokumentiert.
- Sicherheits- und Fehlerverhalten geprüft; keine Secrets in Dateien/Logs.
- README/Konfiguration/Testbefehle so aktualisiert, dass frischer Checkout nachvollziehbar ist.
- Keine Commits ohne ausdrücklichen Auftrag.

## Vorgeschlagene Tool-Form des MVP

| Tool | Eingabe (Entwurf) | Ergebnis |
|---|---|---|
| `obsidian_list_notes` | `path?`, `recursive?`, `limit?`, `extension?` | Einträge mit Pfad/Typ, Trunkierungsindikator |
| `obsidian_get_note` | `path` | Pfad und Markdown-Inhalt |
| `obsidian_search_notes` | `query`, `pathPrefix?`, `limit?` | Treffer mit Pfad und kurzen Kontexten |
| `obsidian_write_note` | `path`, `content`, `overwrite?` | Erfolg, Pfad, erstellt/aktualisiert |
| `obsidian_append_to_note` | `path`, `content`, `createIfMissing?` | Erfolg, Pfad, erstellt/angehängt |
| Frontmatter-Standard (integral zu allen Markdown-Schreibtools) | `title?`, `tags?`, `status?`; Zeiten automatisch verwaltet | Pflichtfelder `title`, `tags`, `createdAt`, `updatedAt`, `status`; Altnotizen über separates Audit/Migration |
| Periodic-Note-Fähigkeit | `period: "daily"`, `date?` | Tagesnotiz lesen/anlegen oder gezielt bearbeiten; genauer Zuschnitt API-abhängig |
| Link-/Backlink-Abfrage | `path`, optional `direction` | ausgehende/eingehende/ungelöste Links; nur bei verlässlicher Datenquelle |
| `obsidian_open_in_ui` | `path`, `newLeaf?` | Öffnungsstatus bzw. klarer Fehler, wenn UI-Bridge fehlt |

Die finale Eingabe-/Ergebnisform ist erst nach Prüfung der gewählten MCP-SDK- und Local-REST-API-Version festzulegen. Insbesondere „create-only“ kann bei einer API, die nur PUT/Upsert anbietet, ohne atomare Bedingung nicht sicher garantiert werden. Namen sind an der Referenz orientiert; sie begründen keine Kompatibilitätsgarantie.

## Festgelegte Produktverträge

- Backend: Local REST API oder lokales Dateisystem (`OBSIDIAN_VAULT_PATH`); lokale Schreiboperationen sind operatorseitig opt-in, Migration zusätzlich separat begrenzt. Für das Dateisystem-Backend muss Obsidian nicht laufen.
- Frontmatter: Pflichtfelder `title`, `tags`, `createdAt`, `updatedAt`, `status`; Statuswerte `active`, `in-progress`, `done`, `archived`, Default `active`. Audit/Migration ignoriert `.obsidian/` und versteckte Pfade.
- Timestamps: ISO-8601 UTC mit `Z`. Bei unbekanntem Legacy-`createdAt` YAML-`null` und Audit-Hinweis `unknown`, keine erfundene Historie.
- `updatedAt`: nur bei tatsächlicher Inhaltsänderung durch den MCP-Server; externe Änderungen werden nicht gespiegelt.
- Release-Umfang: Notizen/Suche/Metadaten, Tagesnotizen, Links/Backlinks und UI-Öffnen, sofern M0 API-Unterstützung belegt. Keine Command-Palette im ersten Release.
- Antwortgrenzen: Suche/Listen Default 50 und Maximum 200 Einträge; einzelne Notiz maximal 1 MiB.

## Kritische Lücken / offene Architekturentscheidungen

- **Backend-Entscheidung:** REST bleibt für UI-Öffnen sowie pluginabhängige Tagesnotizen nötig. Das lokale Dateisystem-Backend unterstützt sichere Reads und operatorseitig freigeschaltete Writes/Migration mit eigenen temporären Vault-Tests; die Freigabeschalter ersetzen noch keinen zielgebundenen menschlichen Approval-Pfad.
- **Suchfähigkeit:** Die REST API muss für echte Volltextsuche ggf. das Vault scannen; Aufwand und Grenzen gegen gewünschte Vault-Größe messen. Omnisearch bleibt optionale Plugin-Integration, nicht implizit verfügbar.
- **Pfadpolicy bei REST:** Server-seitige Grenzen vor jedem Aufruf prüfen und API-Pfade korrekt percent-encoden; URL-Encoding allein ist keine Autorisierung. Pfadnormalisierung und Unicode-/Case-Verhalten explizit testen.
- **Schreibbestätigung:** „Overwrite=true“ ist nur explizites Werkzeug-Intent, keine vertrauenswürdige Nutzerfreigabe. MCP-Argumente können vom Modell stammen; falls ein konkreter destruktiver Einsatz abgesichert werden muss, muss die Freigabe außerhalb nicht vertrauenswürdiger Tool-Argumente erfolgen.
- **MCP-Kompatibilität:** SDK-Version, Inspector-/Client-Test und sauberes Shutdown/Signalverhalten fehlen als explizites Gate. Protokollfehler dürfen nicht in stdout gelangen.
- **Akzeptanzkriterien:** MVP benötigt konkrete Definitionen (max. Such-/List-Größe, erwartete Latenz/Vault-Größe, getestete Obsidian-/Plugin-Versionen, Verhalten bei Offline-Obsidian) statt nur „Tests bestehen“.
- **Command-Sicherheit:** Freie `commandId`-Ausführung aus Tool-Argumenten ist zu weitreichend. Eine Allowlist muss operator-konfiguriert und nicht durch das Modell veränderbar sein; nicht erlaubte Befehle dürfen nicht in `tools/list` als ausführbar erscheinen.
- **Tool-Fläche:** Fünf P0-Tools plus periodische Notizen, Linkabfragen und UI-Steuerung sind nicht mehr der kleinste CRUD-MVP, aber ein plausibler schlanker Obsidian-Assistent. Begrenzung über ein gemeinsames, kleines Tool-Set statt beliebiger Kommandos. Diagnose über Status-Resource oder Health-Tool vorsehen.
- **Frontmatter-Policy:** Statuswerte und Default, UTC-Zeitstempel, `createdAt: null` bei unbekanntem Altbestand sowie Ausschluss von `.obsidian/` und versteckten Pfaden sind entschieden. Migration bleibt separat und dry-run-fähig.
- **Zeitsemantik:** `updatedAt` ändert sich nur bei tatsächlichen Inhaltsänderungen durch den MCP-Server; Änderungen außerhalb des MCP-Servers werden nicht abgebildet. Idempotente Schreibversuche ohne Inhaltsänderung ändern den Wert nicht.

## Referenzumfang und Prüfbasis

- Tool-Namen und Capability-Zusammenfassungen wurden mit `obsidian-mcp-server2/README.md` (Tool-Tabelle und Capability-Referenz) abgeglichen.
- Registrierte Tool-Gruppen wurden zusätzlich in `src/mcp-server/tools/definitions/index.ts` geprüft: vier allgemeine Read-Tools (Search wird separat gebaut), sechs Write-Tools, zwei Command-Tools sowie separat gebaute Search- und Delete-Tools = **14**.
- Resource-Namen aus `src/mcp-server/resources/definitions/index.ts`: **3**. `src/mcp-server/prompts/definitions/index.ts` exportiert eine leere Liste: **0 Prompts**.
- Diese Datei ist ein Plan, keine Implementierung oder Kompatibilitäts-/Sicherheitsaudit-Zusage.

## Implementierungsstatus (2026-10-26)

- Registriert sind 14 MCP-Tools und 3 Resources. Das Backend-Inventar, die Testevidenz und bewusste Nicht-Ziele stehen in `CAPABILITY_MATRIX.md`.
- Lokales Dateisystem-Backend: descriptor-relative/no-follow Reads und Writes, versteckte Pfade gesperrt, atomare lokale Create/Replace, Schreibfreigabe standardmäßig aus; Tagesnotizen benötigen ein Operator-Pfadtemplate. Lokale Linkauflösung berücksichtigt qualifizierte und ordnerlokale Ziele, eindeutige globale Basenames und case-insensitive Pfade.
- REST-Backend: HTTPX-Transporttests decken Auth-, Limit-, Fehler- und Request-Verhalten ab. Kein Live-Nachweis von API-Key, Plugin-Version, TLS oder realen Routen; der letzte REST-Block bleibt deshalb offen.
- Vollständige Live-/Read-only-Belege für den echten Vault sind historische Befunde und gelten nicht als aktueller Abnahmelauf. Neue Mutationstests verwenden temporäre Vaults. Ein echter stdio-Unterprozess wird gegen einen temporären Vault getestet.
- In Arbeit: vollständige Backend-Parität. REST-Tag-/Link-/Periodic-Semantik ist versionsabhängig. UI-Steuerung ist nur für REST verfügbar. Delete, Command-Palette und zusätzliche präzise Editier-Tools sind nicht registriert, weil ein vertrauenswürdiger, zielgebundener Approval-Pfad fehlt.
- CI und wöchentliche uv-Dependency-Updates sind unter `.github/` eingerichtet. Gates: pytest mit 100 % Line-/Branch-Coverage, Ruff lint/format, Pyright, `pip-audit`, Lockfile, Build, Compile und `git diff --check`.
- Aktuelle Gate-Ergebnisse müssen dem unmittelbar nach der letzten Codeänderung ausgeführten Endlauf entnommen werden; historische Coverage- oder Testzahlen sind kein Ersatz.
- Kein Commit erstellt. Die Live-REST-Abnahme bleibt bis zu sicher bereitgestelltem API-Key und explizit freigegebenem isoliertem Testbereich ausstehend.
