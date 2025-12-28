# PV-Dach-Leads Dortmund

##  Projektziel

Systematische Identifikation der **Top 500 Gewerbe- und Industriedächer in Dortmund** mit dem größten Potenzial für Photovoltaik-Anlagen.

### Priorisierungskriterien
1. **Große Dachflächen** (≥ 500 m²)
2. **Zielgruppen:**
   - Gewerbe- und Industriegebäude
   - Soziale Einrichtungen (Pflegeheime, Bildungseinrichtungen)
   - Einzelhandel und Logistik
3. **Standortqualität** (Landnutzungszonen)

###  Outputs
- ✅ **Excel-Dateien:** `dortmund_top500_leads.xlsx` & `dortmund_top200_leads.xlsx`
- ✅ **PDF-Report:** Professioneller Report mit Luftbildern und Lead-Cards
- ✅ **HTML-Report:** Interaktive Web-Ansicht mit Filterfunktionen
- ✅ **Interaktive Karten:** Polygon-Karten mit Prioritätsvisualisierung
- ✅ **Luftbilder:** Hochauflösende NRW-Orthophotos pro Lead
- ✅ **GeoJSON:** Für GIS-Software (QGIS/ArcGIS)

##  Scope

- **Stadt:** Dortmund
- **Leads:** Top 500 (exportierbar auch Top 200)
- **Mindestfläche:** 500 m²
- **Koordinatensystem intern:** EPSG:25832 (UTM Zone 32N, metrisch)
- **Export-Koordinatensystem:** EPSG:4326 (WGS84, Lat/Lon)


##  Datenquellen

### 1. ALKIS-Gebäudedaten (Stadt Dortmund)
- **Quelle:** [Open Data Dortmund](https://open-data.dortmund.de/explore/dataset/liegenschaftskataster-gebaude-bauwerke/)
- **WFS-Service:** `https://geoweb1.digistadtdo.de/doris_gdi/geoserver/ALKIS_ADV/wfs`
- **Inhalt:** Präzise Gebäudegeometrien (amtliche Katasterdaten)
- **Verwendung:** Flächenberechnung und räumliche Filterung
- **Lizenz:** Datenlizenz Deutschland – Zero

### 2. OpenStreetMap (OSM)
- **Quelle:** Overpass API via [OSMnx](https://osmnx.readthedocs.io/)
- **Endpoint:** `https://overpass-api.de/api/interpreter`
- **Inhalt:**
  - Landnutzungszonen (industrial, commercial)
  - Points of Interest (POIs): Pflegeheime, Schulen, etc.
  - Gebäudetags und Adressen
- **Verwendung:** Zielgruppenfilterung und Kontaktdaten
- **Lizenz:** ODbL (Open Database License)

### 3. NRW-Luftbilder
- **Quelle:** WMS-Dienst NRW Geobasis (Digitale Orthophotos)
- **Service:** `https://www.wms.nrw.de/geobasis/wms_nw_dop`
- **Verwendung:** Hochauflösende Luftbilder für visuelle Dokumentation
- **Lizenz:** Datenlizenz Deutschland – dl-de/by-2-0

**Fallback-Quellen:**
- NRW-weit: [Open.NRW ALKIS-Daten](https://open.nrw/dataset/407373a2-422c-469c-a7e9-06a62b4d7d9a)
- OSM Offline: [Geofabrik NRW-Extracts](https://download.geofabrik.de/europe/germany/nordrhein-westfalen.html)


##  Datenverarbeitungs-Pipeline

### Phase 1: Datenakquise
**Module:** `acquire_osm.py`
- Lädt OSM-Daten für Dortmund (Landnutzungszonen, Gebäude, POIs)
- Output: `data/raw/dortmund/osm/*.geojson`

### Phase 2: Datenverarbeitung
**Module:** `process_data.py`, `normalize_alkis.py`
1. ALKIS-Import und Normalisierung
2. Projektion nach EPSG:25832 (metrische Flächenberechnung)
3. Zonenzuordnung (Spatial Join mit Landnutzungszonen)
4. Koordinatenextraktion (Zentroid-Berechnung)
- Output: `data/processed/dortmund/buildings_processed.geojson`

### Phase 3: Filterung
**Module:** `filter_area.py`, `filter_target.py`
1. **Größenfilter:** Nur Gebäude ≥ 500 m²
2. **Zielgruppenfilter:**
   - ✅ Industrial/Commercial Zonen
   - ✅ Pflegeheime, Sozialeinrichtungen
   - ✅ Bildungseinrichtungen, Sportstätten
   - ✅ Einzelhandel, Logistik
   - ❌ Krankenhäuser (ausgeschlossen)
- Output: `data/staging/dortmund/target_buildings.geojson`

### Phase 4: Scoring & Priorisierung
**Module:** `score_leads.py`
- **Scoring-System (0-100 Punkte):**
  - 60% Dachfläche (lineare Skalierung 500-5000 m²)
  - 40% Standortqualität (Zone + POI-Typ)
- **Prioritätsklassen:**
  - 🔴 A-Leads (≥75): Beste Prospects
  - 🟠 B-Leads (55-74): Gute Potenziale
  - 🟢 C-Leads (<55): Reserveliste
- Output: `data/staging/dortmund/scored_buildings.geojson`

### Phase 5: Export & Visualisierung
**Module:** `export_leads.py`, `download_aerial_images.py`, `create_html_report.py`
1. **Excel-Export:** Top 500/200 mit Ranking, Scores, Koordinaten, Links
2. **Luftbilder:** NRW WMS-Download (800x600px pro Gebäude)
3. **Karten:** Interaktive Folium-Karten mit Popups
4. **PDF-Report:** Professionelles Layout mit Lead-Cards
5. **HTML-Report:** Responsive Web-Ansicht mit Filterfunktion
- Output: `data/final/dortmund/*`


## Projektstruktur

```
pv-dach-leads-dortmund/
├── src/pv_roof_leads/              # Python-Module
│   ├── acquire_osm.py              # OSM-Datenakquise
│   ├── normalize_alkis.py          # ALKIS-Normalisierung
│   ├── process_data.py             # Hauptverarbeitung
│   ├── filter_area.py              # Größenfilter
│   ├── filter_target.py            # Zielgruppenfilter
│   ├── score_leads.py              # Scoring-Algorithmus
│   ├── export_leads.py             # Excel/GeoJSON-Export
│   ├── download_aerial_images.py   # Luftbilder-Download
│   ├── create_html_report.py       # HTML-Report-Generierung
│   ├── enrich_solar_potential.py   # Google Solar API (vorbereitet)
│   ├── config.py                   # Zentrale Konfiguration
│   └── paths.py                    # Pfad-Management
├── data/
│   ├── raw/dortmund/               # Rohdaten (OSM, ALKIS)
│   ├── processed/dortmund/         # Verarbeitete Daten
│   ├── staging/dortmund/           # Zwischenergebnisse
│   └── final/dortmund/             # Finale Outputs
│       ├── dortmund_top500_leads.xlsx
│       ├── dortmund_top200_leads.xlsx
│       ├── dortmund_leads_report_top500.pdf
│       ├── dortmund_leads_report_top500.html
│       ├── dortmund_roofs_map.html
│       └── luftbilder/             # 500 Luftbilder
├── cache/                          # API-Response-Cache
├── create_pdf_report.py            # PDF-Generierung (Hauptskript)
├── create_roof_map.py              # Polygon-Karte (Hauptskript)
├── requirements.txt                # Python-Dependencies
├── pyproject.toml                  # Projekt-Metadaten
└── README.md                       # Diese Datei
```

**Hinweis:** Dateien in `data/` sind nicht im Git-Repository (`.gitignore`).

##  Quickstart

### Installation

```bash
# Python-Umgebung erstellen
python -m venv .venv

# Umgebung aktivieren (Windows)
.venv\Scripts\activate

# Dependencies installieren
pip install -r requirements.txt
```

### Pipeline ausführen

```bash
# Gesamte Pipeline (in Reihenfolge)
python -m pv_roof_leads.acquire_osm           # 1. OSM-Daten laden
python -m pv_roof_leads.process_data          # 2. Daten verarbeiten
python -m pv_roof_leads.filter_target         # 3. Zielgruppen filtern
python -m pv_roof_leads.score_leads           # 4. Scoring durchführen
python -m pv_roof_leads.export_leads          # 5. Excel/Karten exportieren
python -m pv_roof_leads.download_aerial_images # 6. Luftbilder laden
python create_pdf_report.py                   # 7. PDF generieren
python -m pv_roof_leads.create_html_report    # 8. HTML-Report erstellen
```

### Konfiguration anpassen

Zentrale Parameter in `src/pv_roof_leads/config.py`:
```python
MIN_FOOTPRINT_AREA_M2 = 500  # Mindestfläche
EXPORT_TOPK = 500            # Anzahl exportierter Leads
CRS_INTERNAL = "EPSG:25832"  # Koordinatensystem
CITY_NAME = "Dortmund"       # Stadt
```

## 📈 Ergebnisse

### Statistiken
- **Analysierte Gebäude:** >10.000
- **Nach Größenfilter:** ~2.500 Gebäude ≥ 500 m²
- **Top 500 Leads:** Priorisiert nach Score
- **Durchschnittliche Dachfläche (Top 500):** ~1.850 m²
- **Größte Dachfläche:** >10.000 m²

### Prioritätsverteilung
- 🔴 **A-Leads (~16%):** Logistikzentren, große Produktionshallen
- 🟠 **B-Leads (~40%):** Einzelhandel, mittelgroße Gewerbe
- 🟢 **C-Leads (~44%):** Bildungseinrichtungen, kleinere Betriebe

### Typische Top-Leads
- Logistikzentren und Distributionshallen
- Produktionsbetriebe und Industrieanlagen
- Shopping-Center und Baumärkte
- Berufsschulen und Hochschulen

##  Zukünftige Erweiterungen

1. **Google Solar API Integration**
   - Präzise Sonneneinstrahlung (kWh/Jahr)
   - 3D-Verschattungsanalyse
   - Optimale Modulplatzierung
   - Dachneigung und Ausrichtung

2. **Energieverbrauchs-Datenintegration**
   - Stromverbrauchsschätzung nach Gebäudetyp
   - Smart-Meter-Datenanbindung
   - Bestandsanlagen-Erkennung (Marktstammdatenregister)
   - Repowering-Potenzial

3. **KI-basierte Dachflächenanalyse**
   - Computer Vision für Dachtyp-Erkennung
   - Dachzustandsbewertung
   - Hinderniserkennung (Gauben, Kamine)

4. **Eigentümer-Recherche**
   - Grundbuch-Integration
   - Handelsregister-Daten
   - Kontaktdaten-Anreicherung
   - Entscheider-Identifikation

5. **Automatisches Lead-Monitoring**
   - CRM-Integration (Pipedrive, HubSpot)
   - Status-Tracking
   - Follow-up-Automation
   - Conversion-Analytics

##  Technologie-Stack

- **Python 3.11+**
- **GeoPandas** (räumliche Operationen)
- **OSMnx** (OpenStreetMap-Integration)
- **Folium** (interaktive Karten)
- **ReportLab** (PDF-Generierung)
- **Requests** (WMS-Luftbilder)

## 📄 Lizenzierung & Datenschutz

### Datenlizenzen
- **ALKIS:** Datenlizenz Deutschland – Zero
- **OSM:** ODbL (Open Database License)
- **NRW-Luftbilder:** Datenlizenz Deutschland – dl-de/by-2-0

### Datenschutz
- ✅ Keine personenbezogenen Daten (nur Gebäude/Adressen)
- ✅ Alle Datenquellen sind Open Data
- ✅ DSGVO-konform (sensible Einrichtungen ausgeschlossen)

## 📧 Kontakt

Bei Fragen zur Implementierung oder für andere Städte:
- **Projekt:** PV-Dach-Leads Generator
- **Demo:** Öffnen Sie `data/final/dortmund/dortmund_leads_report_top500.html`
