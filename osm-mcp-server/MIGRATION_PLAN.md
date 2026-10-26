# Migrationsplan: osm-mcp von TypeScript nach Python

## Ausgangslage und Bestand

Quelle: `../osm-mcp`, eigenständiger TypeScript-MCP-Server (Version 0.3.2) mit `@modelcontextprotocol/server` v2. Ziel: bislang leerer Ordner `osm-mcp-server/`; Quelle bleibt unverändert. Der Server ist vollständig read-only und liefert ausschließlich OpenStreetMap-basierte Ergebnisse. Bestehende Quelltests umfassen Tool-Endpunkte, Backends, Konfiguration, HTTP/Geo-Helfer, Serververhalten, Output-Formung und Filter.

### Vollständige Tooloberfläche (11)

| Bereich | Tool | Wesentliche Funktion |
| --- | --- | --- |
| Geocoding | `geocode` | Nominatim/Photon, Länderfilter, Sprache, Ergebnislimit |
| Geocoding | `reverse_geocode` | Koordinaten → nächster Ort/Adresse |
| Routing | `route` | geordnete Wegpunkte, Fuß/Auto/Rad, optionale Abbiegeschritte |
| Routing | `route_matrix` | Zeit-/Distanzmatrix für Ursprünge und Ziele |
| Routing | `optimize_route` | OSRM-Trips, optionale Rundtour |
| Routing | `isochrone` | Valhalla oder ORS, genau eines aus Zeit/Distanz |
| POI | `find_nearby_pois` | Overpass-Kategorien oder freie OSM-Tags, Distanzsortierung |
| POI | `poi_details` | einzelnes Node/Way/Relation mit begrenzten Tags |
| POI | `suggest_meeting_point` | Mittelpunkt, Kandidatenbewertung nach maximaler/gesamter Reisezeit |
| Helfer | `straight_line_distance` | Haversine-Entfernung |
| Helfer | `map_link` | OSM-Marker-/Wegbeschreibungslink |

Jedes Tool ist als read-only zu markieren und muss `untrusted: true`, `source: "openstreetmap"` enthalten. Die Essential-Auswahl besteht aus `geocode`, `reverse_geocode`, `find_nearby_pois`, `poi_details`, `route`, `map_link`.

### Abhängigkeiten und Konfiguration

Backends: Nominatim, Photon, FOSSGIS OSRM, mehrere Overpass-Endpunkte, Valhalla, optional OpenRouteService. Konfigurationsvariablen und Defaults sind in `osm-mcp/src/config.ts`; besonders wichtig sind User-Agent, 3600s Cache, rate-limits, bis zu acht Overpass-Spiegel sowie `ORS_API_KEY`. Schlüssel niemals in Diagnoseausgaben/Toolresultaten ausgeben; für Python nach dem Laden aus `os.environ` entfernen. ORS bei Schlüssel nur über HTTPS (außer Loopback) nutzen.

### Sicherheits- und Betriebsanforderungen

- MCP stdio: stdout ausschließlich JSON-RPC, Diagnose über stderr.
- Antworten aus OSM sind nicht vertrauenswürdig und dürfen nie als Instruktionen gelten.
- HTTP-Ziele nur http/https, keine URL-Credentials, Query oder Fragmente in Base-URLs.
- Benutzeragent für alle Dienste; identische Antworten im RAM cachen, Dienste fair takten.
- Keine Schreiboperationen an OSM. Keine unnötigen Retries; Overpass-Fallback auf Spiegel unter gemeinsamem Zeitbudget und begrenzter Parallelität.
- API-Key validieren, aus Prozessumgebung löschen, Fehlertexte und URLs redigieren.
- Geometrie-/Antwortbudgets beibehalten (Isochronen 500k Punkte, Route max. 100 Schritte, POI-Details max. 60 Tags und 500 Zeichen/Wert).

## Zielarchitektur

`pyproject.toml`, `src/osm_mcp/` (Konfiguration, Geo-/Shape-Helfer, HTTP-Client/Rate-Limiter, Resolver, Backendmodule, Toolregistrierung/Server/CLI), `tests/`. Python MCP SDK FastMCP wird für Registrierung und stdio verwendet; HTTP-Client synchron/asynchron ist injizierbar, damit Tests Netzwerk deterministisch faken. Toolnamen, Parameter, Defaults, Grenzen, Semantik und Rückgabefelder entsprechen der TypeScript-Quelle. Anbieterfehler werden als sichere verständliche Toolfehler zurückgegeben.

## Umsetzung in vertikalen TDD-Scheiben

1. **Projektbasis/Geometrie:** Python-Paket, Abhängigkeitsmanifest und Testlauf; RED/GREEN für Koordinatenparser, Wertebereiche, Haversine, Rundung/Formatierung und verschachtelte GeoJSON-Geometrien.
2. **Konfiguration/HTTP:** RED/GREEN für Defaults, ungültige URLs/TTL/ORS-Key, Geheimnisentfernung, Cache, Timeouts, Status-/JSON-Fehler und Redaction.
3. **Geocoding:** Nominatim/Photon-Shaping und Resolver: Koordinaten offline, Namen geokodieren, Sprache/Länder/Limit sowie klare Fehler bei keinem Treffer.
4. **Routing:** OSRM/ORS-URLs und Profile, route/legs/steps, Matrix, Trip-Reihenfolge, Isochronen und genaue Eingabevalidierung. Fixtures statt öffentlicher Netzaufrufe.
5. **POIs:** sichere Tag-Auswahl/Overpass-QL, Fallback, POI-Geometrie, Detailbudgets, Distanzsortierung und fairer Treffpunkt.
6. **MCP-Vertrag:** registrierte Toolliste und Schemas/Annotationen, Filter `OSM_ALLOW_TOOLS`/`OSM_DENY_TOOLS` einschließlich `essential`, MCP Client-Server-Tests und stdio-Handshake.
7. **Abschluss:** gesamter Python-Testlauf, Lint/Typecheck nach verfügbarer Projektkonfiguration, vorhandene TS-Tests als Referenz ausführen, genaue Inventar- und Funktionsparität erfassen. Keine echten öffentlichen Requests für Tests.

## Teststrategie und Abnahmekriterien

Striktes RED→GREEN→REFACTOR in kleinen Ende-zu-Ende-Slices: jeder neue Vertrag zuerst als einzelner Test, gezielter Testlauf mit erwarteter fachlicher Fehlermeldung, minimaler Code, gezielter grüner Lauf, danach Regressionstest. HTTP wird über injizierbare Fake-Transporte/Responses geprüft. Abnahme: 11/11 Tools verfügbar, Inputs und Limits abgebildet, Outputs mit OSM-Untrusted-Metadaten, alle Unit-/Integrations-/MCP-stdio-Tests grün, keine Secrets in Logs/Resultaten, Quellverzeichnis unverändert. Abweichungen oder nicht realisierbare Parität sind explizit auszuweisen.

## Reihenfolge der Implementierung

Geometrie und Konfiguration → HTTP/Cache → Geocoder/Resolver → OSRM/ORS/Valhalla → Overpass/Kategorien → Toolgruppen (Geocoding, Routing, POI, Helfer) → Filter/CLI/stdio → End-to-End-Abgleich. Dieses Dokument ist der Arbeitsplan; Fortschritt wird an den verifizierten Tests festgemacht.

## Umsetzungsstand (2026-10-24)

- Python-Paket und alle elf Toolnamen sind angelegt; jeder Toolpfad wird über deterministische Fixtures getestet.
- RED→GREEN ist für die nachträglich ergänzten ORS-Routen/Matrix, Tool-Allow/Deny-Filter, Profil-Enums, Rate-Limit und Secret-Redaction beobachtet worden.
- Konfigurationsschutz umfasst Base-URL-Form, Overpass-Endpunktzahl, ORS-Key-Header-Form/Entfernung aus `os.environ` und HTTPS für entfernte ORS-Hosts.
- Python-Suite: 20 Tests grün; zusätzlich wurde der echte `osm-mcp`-stdio-Einstieg gestartet und MCP `tools/list` lieferte alle elf Tools.
- TypeScript-Suite wurde in dieser Arbeitsumgebung nicht ausgeführt: `npm test` scheiterte zuvor, weil Vitest/Projektabhängigkeiten nicht installiert waren.

### Bekannte Paritätslücken — vor einer Behauptung vollständiger Gleichheit schließen

- TypeScript deklariert für jedes Tool ein detailliertes `outputSchema`; das Python-FastMCP-Port liefert derzeit unstrukturiert serialisierte Resultate ohne gleichwertiges Output-Schema.
- TypeScript begrenzt Cachegröße/-bytes, HTTP-Antwortgröße und Overpass-Fallback durch gemeinsames Zeitbudget/Queue-Limits. Python hat einen TTL-Cache und Endpunkt-Fallback, aber noch nicht dieselben Speicher- und Zeitbudgets.
- Die vorhandenen Python-Tests decken alle elf Erfolgspfade ab, aber nicht alle TypeScript-Grenz-/Fehlerfälle und Anbieter-spezifischen Fallbacks.

Diese Punkte sind ausdrücklich offene Arbeit; die verifizierte Tool-Inventar-Parität und die grüne Python-Suite belegen nicht die vollständige Protokoll-/Fehler-/Output-Schema-Parität.
