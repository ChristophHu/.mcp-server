# osm-mcp-server (Python)

Python-Port des TypeScript-Servers `../osm-mcp`. Stellt dieselben elf MCP-Tools für Geocoding, Routing, Isochronen und OpenStreetMap-POIs bereit.

## Installation / Start

Python 3.11 oder neuer:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/osm-mcp
```

Der Server nutzt MCP über stdio. MCP-Protokollausgabe bleibt auf stdout, Diagnosen werden nach stderr geschrieben.

## Konfiguration

Optionale Umgebungsvariablen: `OSM_USER_AGENT`, `OSM_CACHE_TTL` (Sekunden, Default 3600), `NOMINATIM_BASE_URL`, `PHOTON_BASE_URL`, `OSRM_BASE_URL`, `OVERPASS_BASE_URL` (kommagetrennte Liste mit 1–8 Endpunkten), `VALHALLA_BASE_URL`, `ORS_BASE_URL`, `ORS_API_KEY`. Der ORS-Schlüssel wird beim Start aus der Umgebung entfernt und nur über HTTPS versendet.

## Tests

```sh
python3 -m pip install -e '.[test]'
python3 -m pytest -q
```

Tests sollen keine öffentlichen OSM-Endpunkte aufrufen; Netzwerkantworten werden gefaked. Vollständige Funktions-/Paritätsplanung: `MIGRATION_PLAN.md`.

Die Tests in `tests/` prüfen Geometrie und Eingaberegeln, die exakte Liste der elf Tools und Toolpfade mit deterministischen Upstream-Fixtures. `pytest` erzwingt 100 % Statement- und Branch-Coverage des Pakets `osm_mcp`; es wird kein öffentlicher OSM-Endpunkt kontaktiert.
