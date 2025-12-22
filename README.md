# PV-Dach-Leads Dortmund (MVP)


## Ziel (MVP)
Die Applikation indentifiziert in Stadtgebiet Dortmund die **Top 200 Leads** als potentielle PV-Leads.
Priorität:
1. Grosse Dachflächen > 500 m2
2. passende Zielgruppe:
    a. Gewerbe, Industrie
    b. Ab einem bestimmten Ebergieverbrauch
    c. mittelstandfirmen, falls sie das Gebaüde besitzen und das Dach vermieten wollen, wenn das Dach für PV-Anlage geingnet ist
3. Dächer mit guter Eignung für PV-Anlagen (Sonneneinstrahlung, Neigung, Ausrichtung)  /// Später
4. Dächer ohne PV-Anlagen

Output:
- Liste der Top 200 Leads mit Adresse, Flächengrösse, Eignungskriterien
- Karte/GeoJSNO der besten Leads
- Dashboard zur Visualisierung der Ergebnisse


## Scope (pilot/MVP)
- Stadt: Dortmund
- Ranking: Top 200 Leads
- Mindestfläche: 500m2 (Dach)
- Koordinatensystem intern: **EPSG:25832** (metrisch, Flächenberechnung)
- Export-koordinatensystem: **EPSG:4326** (lat/lon für Karten)


## Inputs (Datenquellen)

1) **ALKIS Gebäude (Footprints)**
   - **Primärquelle (Dortmund Open Data – Datensatzseite):**
     https://open-data.dortmund.de/explore/dataset/liegenschaftskataster-gebaude-bauwerke/
   - **Dienste (WMS/WFS – OWS Endpoint):**
     https://geoweb1.digistadtdo.de/doris_gdi/geoserver/ALKIS_ADV/ows
   - **WFS GetCapabilities (direkt für QGIS/Code):**
     https://geoweb1.digistadtdo.de/doris_gdi/geoserver/ALKIS_ADV/wfs?Service=WFS&Request=GetCapabilities
   - **WMS GetCapabilities (für Visualisierung):**
     https://geoweb1.digistadtdo.de/doris_gdi/geoserver/ALKIS_ADV/wms?Service=WMS&Request=GetCapabilities
   - Formate (je nach Download/Service): GPKG / SHP / GeoJSON / (WFS häufig GML)
   - Zweck im MVP: Gebäudegeometrien → Flächenberechnung (m²) → Filter (≥ 500 m²)

   **Fallback / Alternative (NRW-weit):**
   - Open.NRW Datensatz (ALKIS NW Grundrissdaten):
     https://open.nrw/dataset/407373a2-422c-469c-a7e9-06a62b4d7d9a
   - WFS NW ALKIS vereinfacht (GetCapabilities):
     https://www.wfs.nrw.de/geobasis/wfs_nw_alkis_vereinfacht?SERVICE=WFS&REQUEST=GetCapabilities

2) **OSM Daten (Landnutzung + POIs)**
   - **Live-Abfrage (Overpass API, z. B. über OSMnx):**
     https://wiki.openstreetmap.org/wiki/Overpass_API
   - **Public Endpoint (typisch):**
     https://overpass-api.de/api/interpreter
   - **OSMnx Doku (Features/POIs & API-Nutzung):**
     https://osmnx.readthedocs.io/en/stable/user-reference.html
   - Zweck im MVP:
     - Landuse-Zonen (z. B. industrial, commercial)
     - POIs (z. B. nursing_home, hospital) + Nähe via Buffer (z. B. 50 m)

   **Fallback (Offline-Download, wenn Overpass limitiert/timeout):**
   - Geofabrik NRW-Extracts (PBF/Shapefiles):
     https://download.geofabrik.de/europe/germany/nordrhein-westfalen.html

   **Lizenz / Attribution (für Nutzung im Output/Reports):**
   - https://www.openstreetmap.org/copyright


   ## Outputs
   - **Top 200 Leads Liste (CSV/Excel)**
    Enthält u.a.: Lead-ID, Score, Klasse(A/B/C), Fläche(m2), lat/lon, Zielgruppen-merkmale
   - **Top200.geojson** 
    GeoJSON mit Geometrien der Top 200 Leads für Kartenvisualisierung (EPSG:4326)

    ## Ein/Ausschlusskriterien
    - **Einschluss:**
      - Gebäude mit Dachfläche ≥ 500 m²
      - Gebäude in Zielgruppen-Klassen (Gewerbe, Industrie, bestimmte POIs)

    - **Ausschluss**
      -   hospital auschliessen


## Datenfluss (Pipeline – MVP)
1) ALKIS importieren (GeoJSON/SHP/GPKG)
2) Normalisieren → `buildings.geoparquet` (EPSG:25832)
3) Flächen berechnen + Filtern (≥ 500 m²) → `candidates_area.parquet`
4) OSM Landuse + POIs laden → `osm_landuse.geoparquet`, `osm_pois.geoparquet`
5) Spatial Join (Gebäude ∩ Landuse, POI-Buffer 50m) → `candidates_enriched.parquet`
6) Zielgruppenfilter (industrial|commercial OR nursing_home) AND NOT hospital
7) Scoring (Fläche + Zone) → `leads_scored.parquet`
8) Export Top200 → CSV + GeoJSON (EPSG:4326)

## MVP-Scoring (0–100)
- 60% Fläche, 40% Zone
- Schwellen:
  - A ≥ 75
  - B ≥ 55
  - C < 55
- zone_score:
  - industrial = 40
  - commercial = 30
  - nursing_home = 35

## Projektstruktur (geplant)
- `src/pv_roof_leads/`  (Code)
- `data/raw/dortmund/`  (Rohdaten – NICHT in Git)
- `data/staging/dortmund/` (Zwischenstände – NICHT in Git)
- `data/curated/dortmund/` (Bereinigt – NICHT in Git)
- `data/exports/dortmund/` (Exports – ggf. NICHT in Git)

## Quickstart (wird in Sprint 7 vervollständigt)
```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
pip install -r requirements.txt


