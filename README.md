# PV-Dach Leads Dortmund

**Automatisierte Lead-Generierung für PV-Anlagen auf Basis von Gebäudedaten, Google Solar API und KI-Analyse**

## 📋 Projektübersicht

Dieses Projekt analysiert Gebäude in Dortmund auf ihre Eignung für Photovoltaik-Anlagen. Es kombiniert:

- **ALKIS-Daten** (Katasteramt): Gebäudegeometrien, Adressen, Nutzungsarten
- **Google Solar API**: Solarpotenzial, Dachneigung, Ausrichtung, Panel-Kapazität
- **Gemini Vision AI**: Dachmaterial, Zustand, Hindernisse aus Luftbildern
- **MaStR-Daten**: Bestehende PV-Anlagen

---

## 📁 Projektstruktur

```
pv-dach-leads-dortmund/
│
├── src/pv_roof_leads/          # Haupt-Python-Module
├── data/                        # Alle Daten (roh, verarbeitet, final)
├── deploy/                      # Railway Deployment
├── docs/                        # Dokumentation
├── notebooks/                   # Jupyter Notebooks
└── requirements.txt             # Python-Abhängigkeiten
```

---

## 🐍 Python-Module (`src/pv_roof_leads/`)

### Kernmodule

| Datei | Beschreibung | Erzeugt |
|-------|--------------|---------|
| `paths.py` | Pfad-Definitionen für alle Ordner | - |
| `config.py` | Konfiguration (API-Keys, Parameter) | - |
| `normalize_alkis.py` | Normalisiert ALKIS-Gebäudedaten | `buildings_processed.geojson` |
| `acquire_osm.py` | Lädt OSM-Daten herunter | `data/raw/dortmund/osm/` |
| `extract_osm_pv.py` | Extrahiert PV-Anlagen aus OSM | `osm_pv_installations.geojson` |
| `check_existing_pv.py` | Prüft bestehende PV-Anlagen (MaStR) | `buildings_processed_with_pv_info.geojson` |
| `filter_area.py` | Filtert Gebäude nach Fläche | `buildings_processed_no_pv.geojson` |
| `filter_target.py` | Filtert nach Zielkriterien | `buildings_report_filtered.geojson` |

### Google Solar API

| Datei | Beschreibung | Erzeugt |
|-------|--------------|---------|
| `enrich_with_google_solar.py` | Ruft Google Solar API ab | `buildings_with_google_solar.geojson`, `google_solar_cache/` |
| `download_aerial_images.py` | Lädt Luftbilder herunter | `data/final/dortmund/luftbilder/` |

### KI-Analyse

| Datei | Beschreibung | Erzeugt |
|-------|--------------|---------|
| `analyze_roof_with_gemini.py` | Gemini Vision AI Dachanalyse | `gemini_roof_analysis.json` |

### Report-Generierung

| Datei | Beschreibung | Erzeugt |
|-------|--------------|---------|
| `create_complete_report.py` | **Haupt-Report** mit allen Daten | `complete_buildings_report.html` |
| `create_filtered_report.py` | Gefilterter Report | `buildings_report_filtered.html` |
| `export_to_excel.py` | Excel-Export | `dortmund_top500_leads.xlsx` |
| `export_leads.py` | Lead-Export | Verschiedene Formate |

### Wirtschaftlichkeit

| Datei | Beschreibung | Erzeugt |
|-------|--------------|---------|
| `economic_calculator.py` | ROI, Amortisation berechnen | `buildings_with_economics.geojson` |

---

## 📂 Datenstruktur

### `data/raw/dortmund/` - Rohdaten (Quellen)

| Datei/Ordner | Beschreibung | Quelle |
|--------------|--------------|--------|
| `alkis_buildings/` | ALKIS Gebäude-Shapefiles | Katasteramt NRW |
| `mastr_pv.csv` | Bestehende PV-Anlagen | Marktstammdatenregister |
| `osm/` | OpenStreetMap Daten | Overpass API |
| `osm_pv_installations.geojson` | PV aus OSM | `extract_osm_pv.py` |

### `data/processed/dortmund/` - Verarbeitete Daten

| Datei | Beschreibung | Erzeugt von |
|-------|--------------|-------------|
| `buildings_processed.geojson` | Normalisierte ALKIS-Daten | `normalize_alkis.py` |
| `buildings_processed_no_pv.geojson` | Ohne bestehende PV | `filter_area.py` |
| `buildings_processed_with_pv_info.geojson` | Mit PV-Status | `check_existing_pv.py` |
| `buildings_with_google_solar.geojson` | **Mit Google Solar Daten** ⭐ | `enrich_with_google_solar.py` |
| `buildings_with_economics.geojson` | Mit Wirtschaftlichkeit | `economic_calculator.py` |
| `google_solar_cache/` | 5.201 API-Response Cache | `enrich_with_google_solar.py` |
| `roof_segments_summary.json` | Dachsegment-Statistiken | `enrich_with_google_solar.py` |

### `data/final/dortmund/` - Finale Ergebnisse

| Datei/Ordner | Beschreibung | Erzeugt von |
|--------------|--------------|-------------|
| `luftbilder/` | 5.170 Luftbilder (JPEG) | `download_aerial_images.py` |
| `luftbilder_mit_panels/` | 4.758 Bilder mit PV-Panels | `draw_panels_v2.py` (Einmal-Skript) |
| `gemini_roof_analysis.json` | KI-Analyse aller Dächer | `analyze_roof_with_gemini.py` |
| `complete_buildings_report.html` | **Haupt-Report (HTML)** ⭐ | `create_complete_report.py` |
| `all_buildings_with_solar.geojson` | Kombinierte Daten (veraltet) | - |
| `dortmund_top500_leads.xlsx` | Top 500 Leads (Excel) | `export_to_excel.py` |
| `statistics.json` | Projekt-Statistiken | `create_complete_report.py` |

---

## 🚀 Ausführungsreihenfolge

### 1. Umgebung einrichten

```bash
# Virtual Environment erstellen
python -m venv .venv
.venv\Scripts\activate  # Windows

# Abhängigkeiten installieren
pip install -r requirements.txt

# .env Datei erstellen (API-Keys)
copy .env.example .env
# Dann GOOGLE_API_KEY und GEMINI_API_KEY eintragen
```

### 2. Daten verarbeiten (Pipeline)

```bash
# Schritt 1: ALKIS-Daten normalisieren
python -m src.pv_roof_leads.normalize_alkis

# Schritt 2: OSM-Daten laden
python -m src.pv_roof_leads.acquire_osm
python -m src.pv_roof_leads.extract_osm_pv

# Schritt 3: Bestehende PV-Anlagen prüfen
python -m src.pv_roof_leads.check_existing_pv

# Schritt 4: Nach Fläche filtern
python -m src.pv_roof_leads.filter_area

# Schritt 5: Google Solar API abrufen (benötigt API-Key!)
python -m src.pv_roof_leads.enrich_with_google_solar

# Schritt 6: Luftbilder herunterladen
python -m src.pv_roof_leads.download_aerial_images

# Schritt 7: KI-Analyse mit Gemini (benötigt API-Key!)
python -m src.pv_roof_leads.analyze_roof_with_gemini
```

### 3. Report generieren

```bash
# Haupt-Report erstellen
python -m src.pv_roof_leads.create_complete_report

# Excel-Export
python -m src.pv_roof_leads.export_to_excel
```

### 4. Deployment

```bash
# Report in deploy-Ordner kopieren
copy data\final\dortmund\complete_buildings_report.html deploy\index.html

# Zu GitHub pushen
cd deploy
git add .
git commit -m "Update Report"
git push origin main
```

---

## 📊 Datenfluss-Diagramm

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  ALKIS (NRW)    │    │  MaStR (Bund)   │    │  OSM (Online)   │
│  Katasterdaten  │    │  PV-Register    │    │  Gebäude/PV     │
└────────┬────────┘    └────────┬────────┘    └────────┬────────┘
         │                      │                      │
         ▼                      ▼                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                    normalize_alkis.py                            │
│                    check_existing_pv.py                          │
│                    extract_osm_pv.py                             │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
                ┌────────────────────────┐
                │  buildings_processed   │
                │      .geojson          │
                └───────────┬────────────┘
                            │
                            ▼
         ┌──────────────────────────────────────┐
         │      enrich_with_google_solar.py     │
         │      (Google Solar API)              │
         └──────────────────┬───────────────────┘
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
┌──────────────────┐ ┌─────────────┐ ┌──────────────┐
│ buildings_with_  │ │ google_     │ │ Luftbilder   │
│ google_solar     │ │ solar_cache │ │ (5.170 JPG)  │
│ .geojson ⭐      │ │ (5.201 JSON)│ │              │
└────────┬─────────┘ └─────────────┘ └──────┬───────┘
         │                                   │
         │                                   ▼
         │                    ┌──────────────────────────┐
         │                    │ analyze_roof_with_gemini │
         │                    │ (Gemini Vision AI)       │
         │                    └────────────┬─────────────┘
         │                                 │
         │                                 ▼
         │                    ┌──────────────────────────┐
         │                    │ gemini_roof_analysis     │
         │                    │ .json (5.170 Analysen)   │
         │                    └────────────┬─────────────┘
         │                                 │
         └────────────────┬────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │ create_complete_      │
              │ report.py             │
              └───────────┬───────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │ complete_buildings_   │
              │ report.html ⭐        │
              └───────────────────────┘
```

---

## 🔑 API-Keys

Die folgenden API-Keys werden benötigt (in `.env` Datei):

| Variable | Beschreibung | Wo bekommen? |
|----------|--------------|--------------|
| `GOOGLE_API_KEY` | Google Solar API | [Google Cloud Console](https://console.cloud.google.com/) |
| `GEMINI_API_KEY` | Gemini Vision AI | [Google AI Studio](https://makersuite.google.com/) |

**Beispiel `.env`:**
```
GOOGLE_API_KEY=AIzaSy...
GEMINI_API_KEY=AIzaSy...
```

---

## 📈 Statistiken (Stand: Januar 2026)

| Metrik | Wert |
|--------|------|
| Gebäude analysiert | 5.201 |
| Luftbilder | 5.170 |
| Gemini-Analysen | 5.170 |
| Bilder mit PV-Panels | 4.758 |
| Panels gezeichnet | 3.123.437 |

---

## 🌐 Deployment

Der Report ist auf Railway deployed:

- **Repository:** https://github.com/raedmokdad/pv-dach-report-deploy
- **Server:** Node.js Express (siehe `deploy/server.js`)

### Deploy-Struktur

```
deploy/
├── index.html              # Haupt-Report (Kopie von complete_buildings_report.html)
├── server.js               # Express Server
├── package.json            # Node.js Abhängigkeiten
├── luftbilder/             # Original-Luftbilder (5.170)
└── luftbilder_mit_panels/  # Bilder mit PV-Visualisierung (4.758)
```

---

## ⚠️ Wichtige Hinweise

### Korrekte Datenquelle

**Immer verwenden:** `data/processed/dortmund/buildings_with_google_solar.geojson`

Diese Datei enthält die korrekten, unveränderten Google Solar API Daten. Das Verhältnis von Grundfläche zu Dachfläche sollte etwa 1:1 sein.

### Cache

Google Solar API Responses werden in `google_solar_cache/` gecacht. Dies:
- Spart API-Kosten bei erneutem Ausführen
- Ermöglicht Offline-Zugriff auf API-Daten
- Enthält alle Panel-Positionen für Visualisierung

### Bilder

Die Panel-Visualisierungen werden aus `solarPotential.solarPanels` in den Cache-Dateien generiert. Jede Cache-Datei enthält die exakten Lat/Lon-Koordinaten aller möglichen Panel-Positionen.

---

## 🧹 Aufräumen

Temporäre Skripte wurden gelöscht. Falls Panel-Bilder neu generiert werden müssen:

```python
# In Python ausführen:
# 1. Cache-Dateien lesen
# 2. Panel-Koordinaten aus solarPotential.solarPanels extrahieren
# 3. Mit Bildname (building_X_LAT_LON.jpg) matchen
# 4. Panels auf Bild zeichnen (3x2 Pixel, Farbe: rgba(25, 55, 110, 240))
```

---

## 📄 Lizenz

Proprietär - Nur für interne Verwendung.

---

*Letzte Aktualisierung: 2. Januar 2026*
