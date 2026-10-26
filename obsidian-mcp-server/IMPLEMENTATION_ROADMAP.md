# Obsidian MCP Server – Vollständige Umsetzungs-Roadmap

**Ziel:** Die vereinbarten Obsidian-Funktionen vollständig und sicher implementieren. Das lokale Dateisystem-Backend wird zuerst vervollständigt; die Local REST API einschließlich API-Key-Konfiguration und Live-Test ist der letzte Implementierungsblock.

**Verbindliche Grenzen:** Python; TDD pro Verhalten; line- und branch coverage 100 %; keine Commits ohne Auftrag; keine Secrets in Dateien oder Ausgaben. Der produktive Vault wird nur für explizit read-only Smoke-Tests verwendet. Mutationstests laufen ausschließlich gegen temporäre Vaults. REST-Integrationstests verwenden einen isolierten Testbereich und nur operatorseitig bereitgestellte Credentials.

## Reihenfolge und Gates

### Phase 0 – Ist-Abgleich und Verträge
- Dokumentation und tatsächlich registrierte Tools/Resources abgleichen; widersprüchliche historische Statusangaben korrigieren.
- Capability-Matrix mit Backend-Unterstützung, Mutationsklasse, Operatorfreigabe und Testnachweis führen.
- Shared contracts festlegen für Pfade, Größen, Frontmatter, Timestamps, Fehler und Backend-Lücken.
- Gate: jeder vereinbarte Capability-Punkt hat ein prüfbares Kriterium; unbekannte externe API-Fähigkeiten bleiben als zu verifizieren markiert.

### Phase 1 – Lokales Dateisystem: sichere Schreiboperationen
- Descriptor-relative, no-follow und atomare lokale Dateioperationen ergänzen; Ziel bleibt auf geöffneten Vault-Root beschränkt.
- Operatorseitige lokale Schreibfreigabe getrennt von Tool-Argumenten; Migration bleibt zusätzlich separat, dry-run-by-default und exakt auf den konfigurierten Root begrenzt.
- Neue Notiz, explizites Überschreiben und Anhängen mit Frontmatter-Vertrag implementieren; Metadaten-/Tag-Änderungen und Audit-Migration durch denselben sicheren Write-Pfad leiten.
- Gate: RED/GREEN-Tests für no-clobber, explizites Overwrite, Größenlimits, Root-Austausch, Symlinks, konkurrierende/ersetzte Ziele, Fehler vor Veröffentlichung und unveränderte Ziele bei Ablehnung. Vollständige Suite/Coverage.

### Phase 2 – Lokale Capability-Vollständigkeit
- Tagesnotiz-Pfad/Datumsvorlagen konfigurieren oder explizit als nicht darstellbar ablehnen; niemals zufällige Obsidian-Plugin-Semantik behaupten.
- Such- und Tag-Semantik, Unicode/Case, Inline-Tags sowie Link-/Backlink-Auflösung definieren und parity-Tests ergänzen. Pfadauflösung berücksichtigt eindeutige Space/Underscore-Varianten; Mehrdeutigkeit bleibt ungelöst.
- Read-only Konsistenztools bereitstellen: begrenzter Vault-Scan und gezielter Datei-/Backlink-Check mit begrenzter rekursiver Link-Closure; Teilscans und Lesefehler müssen explizit unvollständig bleiben. Erledigt; verifiziert in `tests/test_local_consistency.py`.
- List-/Search-/Audit-Grenzen einschließlich großer Vaults und Fehler bei einzelnen Dateien festlegen.
- Gate: Vertragstests über echte MCP-Tool-Aufrufe gegen temporäre Vaults; keine stillen Datenverluste oder unmarkierten Teilergebnisse.

### Phase 3 – Vollständige MCP-Fläche und sichere Aktionen
- Capability-Referenz aus `obsidian-mcp-server2` gegen registrierte Tools/Resources prüfen.
- Fehlende Ressourcen und sichere präzise Bearbeitung ergänzen.
- Delete nur mit operatorseitiger Freigabe, eng begrenztem Pfad, no-follow unlink und expliziter Tool-Intent; verweigerte Aufrufe müssen ohne Seiteneffekt bleiben.
- Command-Palette nur aufnehmen, wenn die REST-API diese Capability tatsächlich liefert; ausschließlich konfigurationsseitige Allowlist, keine freie Modell-Command-ID. Sonst ausdrücklich als externe Capability-Lücke dokumentieren.
- Gate: Discovery, Annotationen, Argument-Schemas, Autorisierungs- und No-side-effect-Tests über den realen stdio-Prozess.

### Phase 4 – Produktionsqualität und unabhängige Gates
- Typprüfung und CI mit Python 3.12, Lockfile, Ruff, pytest und Branch-Coverage einrichten.
- Packaging/Build, Shutdown/Signalverhalten, stdout-Protokollreinheit, Secret-Redaction, Dependency- und Security-Prüfungen ergänzen.
- Security-Review der lokalen Root-/Descriptor-Grenze, Mutationspfade und MCP-Komposition.
- Gate: frischer Checkout, alle automatisierten Gates grün; Live-REST-Tests bleiben noch absichtlich aus.

### Phase 5 – Local REST API (zuletzt)
- Vorhandenen HTTP-Adapter gegen veröffentlichte Plugin-Version und tatsächliche Endpunkte prüfen; Auth, TLS, Timeouts, Redirects, Fehlerabbildung, URL-Encoding und Antwortlimits vervollständigen.
- Tagesnotiz-, Link-/Backlink-, UI-, Such- und Schreibsemantik für reale Plugin-Versionen prüfen. Unbelegte oder nicht verfügbare Plugin-Funktionen nicht vortäuschen.
- API-Key nur aus sicher bereitgestellter Laufzeitumgebung beziehen; nie anzeigen, loggen, speichern oder in Testdaten schreiben.
- Isolierten REST-Testbereich verwenden; mutierende Smoke-Tests nur mit ausdrücklicher Freigabe dieses konkreten Bereichs. Nach jedem Write exakten Zustand zurücklesen; Cleanup ausschließlich auf eigens erzeugte Testobjekte beschränken.
- Gate: erfolgreicher echter MCP-stdio→HTTP→Obsidian-End-to-End-Test mit dokumentierter Plugin-/Obsidian-Version. Ohne erreichbaren Dienst oder Key bleibt diese Phase offen; kein erfundener Erfolg.

### Phase 6 – Abschluss und Abnahme
- Capability-Matrix und README auf verifizierte Realität aktualisieren; Unit/Mock, lokaler echter stdio-Test und Live-REST-Test getrennt ausweisen.
- Gesamte Gates seriell ausführen: `uv run pytest -q`, Ruff lint/format, Typprüfung, `uv lock --check`, Build, `compileall`, `git diff --check`.
- Worktree prüfen; keine fremden/untracked Artefakte übernehmen und nichts committen.

## Aktueller Stand (2026-10-26)
- Phase 0: Capability-Matrix und sichere Nicht-Ziele dokumentiert in `CAPABILITY_MATRIX.md`.
- Phase 1: lokale sichere Create-only-Schreibpfade sind operatorseitig aktivierbar. Überschreiben bestehender Notizen/Daily Notes und Append auf vorhandene Notizen bleiben ohne zielgebundene Freigabe gesperrt. REST-Normalmutationen sind vor Backendzugriff gesperrt; ausschließlich der separate, exakt gescopte Migrationpfad bleibt mutierend verfügbar.
- Phase 2: Tagesnotiztemplate, Tags/Inline-Tags, Resources, begrenzte Suche, Link-/Backlink-Auflösung und read-only Vault-Konsistenzchecks sind vorhanden. Lokale Linkauflösung berücksichtigt Pfad-/Ordner-/Case-Verhalten. Semantik ist nicht vollständig identisch mit dem Obsidian-Plugin.
- Phase 3: registrierte Fläche umfasst 16 Tools/3 Resources. Die beiden neuen Konsistenzchecks sind lokal/read-only; Delete, Commands und mutierende Präzisionswerkzeuge bleiben bewusst nicht exponiert, da kein vertrauenswürdiger zielgebundener Approval-Pfad vorliegt.
- Phase 4: CI, Dependabot, Pyright, Ruff, `pip-audit`, Lockfile, Build und Compile-Gates sind eingerichtet. Der echte stdio-Unterprozess wird gegen temporäre Testdaten getestet.
- Phase 5 (REST zuletzt): HTTPX-Mocktests existieren; Live-Endpunkt, Plugin-Version und sicher bereitgestellter Key/Testbereich sind nicht verifiziert. Normale REST-Schreiboperationen bleiben fail-closed.
- Sicherheits-Nacharbeit (2026-10-26): REST-append wird schon im MCP-Handler vor jedem Backendzugriff abgewiesen; Daily-Note-Create/Replace sowie Note-Overwrite und normale REST-Note-Schreibvorgänge sind ebenfalls fail-closed. Nachweis: `uv run pytest -q` — 223 Tests, 100 % Statement- und Branch-Coverage; Ruff, Pyright, Lockfile, pip-audit, Build, compileall und `git diff --check` erfolgreich.
- Keine Gate-Passzahl aus einem früheren Lauf ist als aktueller Endnachweis zu verwenden. Nach Abschluss der verbleibenden Änderungen alle Gates erneut ausführen.
- Kein Commit erstellt; der produktive Vault wurde in dieser Umsetzungsrunde nicht beschrieben oder verändert.

## Abarbeitungsprotokoll
Jede neue Verhaltensänderung erfolgt als vertikaler TDD-Slice: Test schreiben, erwartetes RED beobachten, kleinste Implementierung, GREEN, dann relevante Suite und vollständige Qualitätsgates. Live-REST-Tests bleiben der letzte Implementierungsblock und verwenden nur sicher bereitgestellte Zugangsdaten sowie einen ausdrücklich freigegebenen isolierten Testbereich.
