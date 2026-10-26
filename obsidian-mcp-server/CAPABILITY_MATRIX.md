# Capability-Matrix

Stand: 2026-10-26. Grundlage: registrierte MCP-Fläche in `src/obsidian_mcp_server/server.py`, Local REST Adapter in `api.py`, Dateisystem-Adapter in `local_vault.py`, sowie isolierte Tests. „Unit/MCP“ bedeutet Tests mit temporärem Vault oder HTTPX-Transport; es bedeutet keinen Live-Nachweis für die Obsidian-Plugin-Version.

## Tools

| Tool | REST-Backend | Dateisystem-Backend | Sicherheit / Einschränkung | Evidenz |
|---|---|---|---|---|
| `obsidian_get_note` | Ja | Ja | Relative, sichtbare Markdown-Pfade; Inhalt auf 1 MiB begrenzt | `test_server.py`, `test_local_vault_server.py` |
| `obsidian_status` | Plugin-Status per HTTP | Lokaler Backend-/Read-only-Status | Live-REST-Erreichbarkeit nicht verifiziert | `test_api.py`, `test_local_vault_server.py` |
| `obsidian_list_notes` | Ja | Ja | Einzelnes Verzeichnis; max. 200 Ergebnisse | `test_server.py`, `test_local_vault.py` |
| `obsidian_search_notes` | Plugin-Suche | Lokaler Markdown-Scan | Einfache Textsuche; max. 200 ausgegebene Treffer | `test_server.py`, `test_local_vault.py` |
| `obsidian_write_note` | Nein (außer eng begrenzte Migration) | Create-only bei Operator-Freigabe; vorhandene Ziele gesperrt | REST fehlt atomare bedingte Erstellung; Overwrite benötigt zielgebundene Freigabe | `test_server.py`, `test_local_vault_write_server.py`, `test_api*.py` |
| `obsidian_append_to_note` | Nein | Neue lokale Datei kann erstellt werden; Append auf bestehende Ziele benötigt Freigabe und wird derzeit abgewiesen | Ablehnung vor REST-Backendzugriff; vorhandene Ziele nicht überschreibbar ohne Approval | `test_server.py`, `test_server_tools.py` |
| `obsidian_get_daily_note` | Plugin-Periodic-Route | Ja, mit konfiguriertem Pfadtemplate | Datum muss explizit sein; REST-Route/Companion-Plugin live ungeprüft | `test_local_daily_notes.py`, `test_api.py` |
| `obsidian_write_daily_note` | Nein | Lokales Anlegen mit Operator-Freigabe; Überschreiben gesperrt ohne zielgebundene Freigabe | REST-Create/Replace vor Backendzugriff gesperrt; bedingtes No-Clobber nicht verifiziert | `test_local_daily_notes.py`, `test_server.py`, `test_server_tools.py`, `test_api*.py` |
| `obsidian_list_tags` | Plugin-Tag-Endpunkt | Frontmatter- und Inline-Tags | REST-/lokale Inline-Tag-Parität nicht live belegt | `test_api.py`, `test_local_tag_integration.py` |
| `obsidian_manage_frontmatter` | Nur Lesen / Migration | Lesen; Änderungen an bestehenden Dateien benötigen noch zielgebundene Freigabe | Ungültiges YAML wird abgelehnt; normale REST-Mutationen gesperrt | `test_server.py`, `test_local_vault_write_server.py` |
| `obsidian_manage_tags` | Nur Lesen | Lesen; Mutationen an bestehenden Dateien benötigen noch zielgebundene Freigabe | Frontmatter-Tags; Inline-Tags zusätzlich beim Lesen erkannt; REST-Mutationen gesperrt | `test_server.py`, `test_local_tag_integration.py` |
| `obsidian_open_in_ui` | Ja, sofern Plugin-Funktion verfügbar | Nein; liefert klaren Fehler | API-Funktion nicht live bestätigt | `test_api.py`, `test_local_vault_edges.py` |
| `obsidian_get_note_links` | JSONLogic-Linkfelder oder markierter Parser-Fallback | Lokaler Parser mit Pfad-/Case-Auflösung und eindeutiger Space/Underscore-Normalisierung | REST-Metadaten abhängig von Plugin-Version; lokale Auflösung ist keine Obsidian-Indexabfrage | `test_server.py`, `test_local_vault_edges.py` |
| `obsidian_check_consistency` | Nein | Read-only, sichtbare Markdown-Notizen; Standard 50/max. 200 Notizen, 200 Verzeichnisse, 20 Ebenen | Bei Teilscan keine definitive Broken-Link-Klassifikation; Fehler/Trunkierung explizit ausgewiesen; „ohne Links“ ist nicht gleich verwaist | `test_local_consistency.py` |
| `obsidian_check_file_consistency` | Nein | Read-only Prüfung einer Note, rekursiv erreichbarer Links und höchstens `max_limit` Backlink-Kandidaten | Link-Closure ist auf `max_limit` begrenzt; Teilresultate durch `recursive_complete`/`backlinks_complete` markiert; keine Obsidian-Indexabfrage | `test_local_consistency.py` |
| `obsidian_audit_frontmatter` | Ja | Ja | Dry-run Standard; Apply separat freizugeben, exakter Root; keine Notiztexte im Auditbericht | `test_audit*.py`, `test_local_vault*.py` |

## Resources

| URI | REST | Dateisystem | Einschränkung / Evidenz |
|---|---|---|---|
| `obsidian://vault/{+path}` | Ja | Ja | Einzelne sichtbare Notiz; `test_server_resources.py` |
| `obsidian://tags` | Ja | Ja | API-Tag-Vertrag und lokale Inline-Erkennung können abweichen; `test_server_resources.py` |
| `obsidian://status` | Ja | Ja | REST-Version/Erreichbarkeit erfordert Live-Test; `test_server_resources.py` |

## Bewusst nicht registriert

- `obsidian_delete_note`: nicht implementiert. Das Repository besitzt keinen vertrauenswürdigen Approval-Produzenten, der Delete-Operation, kanonischen Vault-Root und exakten Zielpfad bindet. Ein `confirm=true`-Toolargument oder globales Environment-Flag wäre keine zielgebundene menschliche Freigabe.
- `obsidian_list_commands` / `obsidian_execute_command`: nicht implementiert. Plugin-Unterstützung ist live ungeprüft; freie Command-IDs dürfen nicht aus Modellargumenten ausführbar sein. Erst nach bestätigter Capability und operatorseitiger Allowlist mit vertrauenswürdigem Freigabemodell erneut bewerten.
- Präzise mutierende Tools `obsidian_patch_note` / `obsidian_replace_in_note`: nicht registriert. Es gibt noch keinen vertrauenswürdigen zielgebundenen Approval-Pfad; weitere Editier-Varianten würden dieselbe Autorisierungslücke vergrößern. Read-only- und Backend-Paritätsarbeit ist davon unabhängig.

## Noch nicht nachgewiesen

- Realer REST-Endpunkt, Plugin-Version, TLS-Zertifikat und Authentifizierung; nur isolierte HTTPX-Transporte sind getestet.
- REST-Tag-, Tagesnotiz- und Linkmetadaten-Semantik für die tatsächlich installierte Plugin-/Extension-Version.
- REST-E2E über MCP-stdio und einen operatorseitig bereitgestellten API-Key in einem ausdrücklich freigegebenen Testbereich.
- Zielgebundene Trusted-Approval-Architektur für überschreibende Schreibaktionen. `OBSIDIAN_ENABLE_WRITES` und `overwrite` begrenzen Konfiguration und Intent, ersetzen aber keine menschliche Autorisierung für einen konkreten Zielpfad.

Kein Inhalt des echten Vaults und keine Zugangsdaten sind Teil dieser Matrix.
