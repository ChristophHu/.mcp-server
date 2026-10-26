# TypeScript/Python-Funktionsparität – Umsetzungsplan

> **For Hermes:** Diesen Plan in Reihenfolge abarbeiten, jede Verhaltensänderung strikt RED→GREEN testen und die TypeScript-Referenz unverändert lassen.

**Goal:** Die Python-Portierung an das beobachtbare Verhalten der TypeScript-Referenz angleichen: MCP-Vertrag, Eingaben, Ergebnis-Shaping, HTTP/Cache/Limits, Providerwahl und Fehlerverhalten.

**Architecture:** Kleine gemeinsame Shaping-/Sanitizer-Helfer in `src/osm_mcp/`, danach Transport-/Backend-Policy in `http.py`, anschließend die vorhandenen Toolpfade in `server.py`. Fixtures bleiben offline; Testfälle orientieren sich an den vorhandenen TypeScript-Kontrakten und prüfen Request-Shape, Ergebnis und Fehler.

**Tech Stack:** Python 3.14 (`.venv314`), FastMCP/Pydantic, httpx, pytest/pytest-cov/respx.

---

## Baseline und Grenzen

- TypeScript-Referenz bleibt unverändert. Vor jedem Abschnitt `git status` prüfen; keine Commits/Staging.
- Letzter verifizierter Python-Gate-Lauf: 51 Tests, 100 % Statements/Branches (415 Statements, 156 Branches).
- TypeScript-Tests derzeit blockiert: `npm test` → `vitest: command not found`; Paketmanifest/Lockfile existieren, `node_modules` jedoch nicht nachgewiesen. Keine ungefragte Installation oder Änderung der TS-Seite.
- Abnahmekriterium ist Verhaltensparität an den dokumentierten Schnittstellen, nicht identischer interner Aufbau. Jede nicht identisch realisierbare SDK-Schema-Eigenschaft wird als Restabweichung dokumentiert.

## Aufgaben

### 1. MCP-Input-/Serververtrag

**Dateien:** `src/osm_mcp/server.py`, `src/osm_mcp/output.py`, `tests/test_tools.py`, `tests/test_server_edges.py`.

- Zuerst Tests für Eingabegrenzen/Regexe der TS-Quelle: Sprache `[a-zA-Z-]{2,10}`, Waypoints 1–300 Zeichen, Geocode-Limit Integer 1–10, Countrycodes-Format/Länge, POI- und Meetingpoint-Kategorien, Integer-/Range-Grenzen und alle Profile auch bei direktem Funktionsaufruf.
- MCP-Input-JSON-Schemas müssen Spiegelgrenzen/Enumnamen enthalten; fehlende Tests dafür ergänzen.
- Annotationen: `readOnlyHint=true`, `destructiveHint=false`, `idempotentHint=true`, `openWorldHint=true`. Server-Metadaten soweit FastMCP unterstützt an TS-Identität angleichen; unsupported Felder präzise dokumentieren.
- Verify: gezielte Tests, `tools/list`-Schemavergleich und vollständige Python-Suite.

### 2. Geometrie, Provider-Shaping und Ergebnis-Sanitizing

**Dateien:** neue `src/osm_mcp/shaping.py` oder gezielte Helfer in `geo.py`; `server.py`, `output.py`; neue/ergänzte Tests für Shaping und Tools.

- TDD: endliche/globale Koordinaten, `-0`, begrenzte Strings, Measures 0…1e12, sichere Integer-IDs, Tag-Key/-Value-Budgets, ungültige Elemente isoliert verwerfen, `numberMatrix`-artige Nullzellen.
- TS-kompatible Rundung (JS `Math.round` semantics) statt Python bankers-rounding für Koordinaten, Distanz-/Zeitformatierung und Matrixzellen.
- Nominatim: Felder `osm` und `kind`, Koordinaten prüfen/runden, Labels auf 500 Zeichen begrenzen.
- Photon: erlaubte Sprachen en/de/fr, Labels aus name/street + housenumber, postcode/city, state, country sowie `osm`/`kind`; direkte Koordinatenbehandlung nur dort beibehalten, wo die TS-Referenz sie bietet.
- Sanitizer: rekursive Secret-Redaktion, gefährliche Steuer-/Bidi-Zeichen entfernen, `__proto__`-Felder ausschließen, beide strukturierten/textuellen Resultatkanäle konsistent halten. `untrusted/source` kann Upstream nicht überschreiben.

### 3. HTTP-, Cache-, Rate-/Deadline- und Fehlerverhalten

**Dateien:** `src/osm_mcp/http.py`, Tests `test_http.py`/`test_http_edges.py`; falls nötig `pyproject.toml`.

- TDD für TS-Limits: 30s Default-Timeout, Response-Cap 8 MiB, Error-Body-Cap 64 KiB und Bereinigung/2000-Zeichen-Cap; keine Redirects; `Accept: application/json`.
- TTL-Cache: max 500 Entries, max 32 MiB gesamt, max 1 MiB je cachebarer Response, LRU/älteste zuerst, abgelaufene Entries entfernen; Service/Method/URL/Body als stabilen Key verwenden; Overpass-Runtime-Fehler nicht cachen.
- RateLimiter als service-spezifische FIFO-Queue mit Mindestintervallen (Nominatim/Photon/OSRM/Valhalla/Overpass 1100ms, ORS 1600ms), Queue-Maximum 32; parallele HTTP-Requests derselben Queue dürfen Slots nicht überholen.
- Fehlerobjekt mit HTTP-Status, Service, sicherer Endpoint-Origin, sanitisiertem Body; ORS 403/429-Hinweise und generischer 429-Hinweis wie TS. Kein Secret in Logs, Fehlern oder Toolresultaten.
- Toolaufruf-Deadline 120s; bei Deadline MCP-Fehlerresultat statt hängender Anfrage. Tests mit Fake-Clock/Transport, keine echten Services.
- Konfiguration angleichen: TTL als nichtnegative Dezimal-Ganzzahl, URL-Normalisierung/-Validierung, sichere Loopback-Erkennung, Remote-HTTP-Warnung, ORS-Key-Form und HTTPS-Regel.

### 4. Overpass-Fallback und Datenmodell

**Dateien:** `server.py`, `http.py` (ggf. neues `backends/overpass.py` bei klarer Entkopplung), `tests/test_server_edges.py`, neue Backendtests.

- Query-Shaping validiert Elementtyp/ID, finite globale Koordinaten, Center-Fallback, bounded string tags; ungültiges Element überspringen.
- Spiegelstrategie: höchstens 8 Endpunkte, 50s gemeinsames Budget, min. 20s/max. 40s je Versuch, 1s * Index Wartezeit, max. zwei parallele Queries; HTTP 400 nicht retryen, andere HTTP-/Netzwerk-/Timeout-/Overpass-Runtime-Fehler mit sicheren Diagnosen weiterreichen.
- `find_nearby_pois`: Query-Cap, stabile Distanzsortierung, CORE_TAGS und Attributwerte aus bereinigtem Poi-Objekt.
- `poi_details`: 60 Tags, max. 500 Zeichen/Wert, nur sichere gültige Tags/Koordinaten, identische Map-/OSM-Form.
- `suggest_meeting_point`: 30 Overpass-Treffer nach Distanz sortieren, höchstens 8 in Matrix aufnehmen; Kandidatenranking (max Zeit, dann Summe) und unerreichbare Zeiten exakt wie TS.

### 5. Routing-/Isochrone-/Meetingpoint-Toolparität

**Dateien:** `server.py`, `geo.py`, `output.py`, Tests `test_server_edges.py`/`test_tools.py` plus neue provider-specific fixtures.

- OSRM-/ORS-Antworten sicher shapen; fehlende/ungültige Measures, fehlende Route/Trip, Matrixzellen und Trip-Permutation mit TS-Fehlersemantik abdecken.
- `route`: ORS/OSRM-Profilpfade, Legs, Via-Summary, Anleitungslänge 300 Zeichen, maximal 100 Steps und `steps_truncated`; bei 3+ Wegpunkten Legs.
- `route_matrix`: 12 je Seite, zusammen max. 25; Null-Zellen; identische JS-Rundung.
- `optimize_route`: stets OSRM, korrekte validierte Permutation, roundtrip/non-roundtrip und passende Legs.
- `isochrone`: ORS mit Key, sonst Valhalla; alle gültigen GeoJSON-Punktformen, max. 500k Punkte, leere Kontur und Bounding Box wie TS.
- `suggest_meeting_point`: ORS-Matrix wenn ORS aktiv; OSRM sonst. Ungültiges Profil, leere/unreachable Kandidaten, Zeitdarstellung und Alternativen an Referenz angleichen.
- `straight_line_distance`/`map_link`: TS-Rundung, Alias `from`, erlaubte Profiles und identische Linkparameter/Encoding prüfen.

### 6. MCP-Ergebnisformen und Abschlussbelege

**Dateien:** `output.py`, `server.py`, `tests/test_tools.py`, `README.md`, dieser Plan.

- Alle 11 Output-Schemas gegen `src/output-schema.ts` und Tool-Schemas vergleichen; offene zusätzliche Properties (POI/OSM-Tags) bewusst erlauben.
- Text und `structuredContent` müssen denselben bereinigten Untrusted-Datensatz enthalten; Fehler korrekt als `isError` zurückgeben.
- Abschluss: Python-Gesamtsuite mit konfiguriertem 100%-Statement-/Branch-Gate, stdio `tools/list` + reale Tool-Call-Fakes, `git diff --check`; TypeScript tests versuchen, aber Abhängigkeiten nicht stillschweigend installieren.
- Paritätsmatrix mit Datei-/Testreferenzen und allen verbleibenden technischen Grenzen aktualisieren. Keine vollständige Paritätsbehauptung, solange ein Pflichtpunkt fehlschlägt oder ungetestet ist.

## Umsetzungsstatus (2026-10-24)

Die folgenden Änderungen sind begonnen und gezielt gegen Fixtures geprüft; dieser Abschnitt ist kein Abnahmebeleg. TypeScript bleibt unverändert.

### Umgesetzt in diesem Durchlauf

- `route_matrix`: Einheitenkorrektur (Sekunden→Minuten, Meter→Kilometer) mit JS-kompatibler Dezimalrundung; Regressionen decken 3 Sekunden und bestehende 10-Minuten-Antwort ab.
- `suggest_meeting_point`: ORS-Matrix bei gesetztem Key, OSRM ohne Key, Distanzsortierung/Begrenzung auf acht Kandidaten, robuste Kandidaten-Shapes und `unknown` bei nicht erreichbaren Teilnehmenden.
- POI-/Meetingpoint-Shaping: ungültige Elemente, IDs, Koordinaten und Tags werden isoliert verworfen/gebunden; Details verwenden Center-Fallback und globale Koordinatenvalidierung.
- Overpass: Failover ist auf HTTP-Fehler (außer 400), httpx-Netzwerk-/Timeout-Fehler und Runtime-`remark` begrenzt; beliebige Programmierfehler werden nicht mehr als Netzwerkfehler verschluckt.
- HTTP: `Accept: application/json`, Cache-Key um Service und Methode ergänzt, ORS-Ratenintervall 1,6 s und übrige Dienste 1,1 s.
- Veraltete Fixture-Erwartungen für Validierungs-/Offline-/Unreachable-Fehler wurden gegen die beobachtete Referenzsemantik korrigiert.

### Noch offen / Gate blockiert

1. Routing-Backend-Shaping: ungültige Measures in Legs/Steps sowie fehlende/invalide Matrix-/Trip-Strukturen vollständig nach TS-Backendverhalten prüfen und angleichen.
2. HTTP: Error-Hints/-Redaktion, Body-Limitpfade, Queue-FIFO/Queue-Cap, Gesamt-Cachebudget/Cachebarkeit/TTL, methodenidentische Keys und alle Timeout-/Fallbackpfade mit deterministischen Tests belegen.
3. Konfiguration: URL-Normalisierung, Loopback-Klassifizierung (inkl. IPv4-mapped IPv6), Cache-TTL-Form und User-Agent-Default gegen `config.ts` vergleichen.
4. Overpass: gemeinsames Deadline-Verhalten, Timeout-Allokation, Zeitbudget-Fallback, Fehlerdiagnosen und Nicht-Caching von Runtime-`remark` vollständig testen.
5. Tool-/MCP-Vertrag: alle elf Input-/Output-Schemas, Titles, Annotations, Serveridentität, Result-Text plus `structuredContent`, Fehler-`isError` und `tools/list` per strukturellem Vergleich nachweisen.
6. Tool-Details: Photon-/Nominatim-Grenzfälle, OSRM/ORS Legs/Steps, Optimize-Route-Permutation/Legs, Isochrone-Punktformen/500k-Cap, `map_link`/Distance-Details weiter vergleichen.
7. Gesamtverifikation: Python-Suite aktuell 71 Tests bestanden, aber Coverage-Gate **fehlgeschlagen** (90,96 %; verlangt 100 % Statements und Branches). TS-Tests/Build sind separat zu versuchen; keine vollständige Parität behaupten, bis alle Gates belegt sind.

### Nächste TDD-Scheiben

1. Test-first für HTTP: Fake-Stream (Response-/Error-Cap), ORS-Intervall, Cachebytebudget, Schlüssel-Identität und Queue-Überlastung; jeweils RED→GREEN.
2. Test-first für Overpass: HTTP-400 ohne Retry, Timeout/Netzwerk/Runtime-`remark` mit Retry, nicht-retrybare lokale Fehler ohne Retry, Deadline-Stop und Runtime-Response nicht im Cache.
3. Test-first für Backend-Shaping: ungültige Matrixzellen, Routenbeine/-schritte, Trip Legs und leere/kaputte Isochrone.
4. Struktureller MCP-Vergleich und restliche Tool-Tests; dann Gesamtgate seriell mit Branch-Coverage.
