# Lösungen zur Erkennung bestehender PV-Anlagen

## 🎯 Problemstellung

Für die Lead-Generierung ist es wichtig, Gebäude **auszuschließen**, auf deren Dächern bereits PV-Anlagen installiert sind. Dies verhindert:
- ❌ Doppelte Ansprache von bereits versorgten Gebäuden
- ❌ Verschwendung von Ressourcen
- ✅ Fokus auf echte Potenziale

---

## 📊 Verfügbare Lösungsansätze

### 1. **Marktstammdatenregister (MaStR)** ⭐⭐⭐⭐⭐
**Beste Lösung für Deutschland**

#### Beschreibung
Das **Marktstammdatenregister** ist die offizielle Datenbank der Bundesnetzagentur für alle Energieanlagen in Deutschland. Seit 2019 müssen alle PV-Anlagen dort registriert werden.

#### Vorteile
✅ **Offizielle Datenquelle** - höchste Zuverlässigkeit  
✅ **Vollständig** - alle Anlagen > 1 kWp müssen registriert sein  
✅ **Koordinaten verfügbar** - für räumliche Zuordnung  
✅ **Kostenlos** - öffentliche Datenbank  
✅ **Aktuell** - regelmäßige Updates

#### Nachteile
⚠️ **API-Limits** - keine offizielle API, nur CSV-Download  
⚠️ **Datenqualität** - Koordinaten teilweise ungenau  
⚠️ **Verarbeitung** - große CSV-Dateien (~500MB+)

#### Datenzugriff
- **Web-Interface:** https://www.marktstammdatenregister.de/MaStR/
- **CSV-Export:** Manueller Download möglich
- **API:** Keine offizielle API, aber CSV-Downloads automatisierbar

#### Implementierung
```python
# Beispiel: MaStR-Daten laden und mit Gebäuden matchen
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point

def load_mastr_pv_installations(mastr_csv_path: str) -> gpd.GeoDataFrame:
    """
    Lädt PV-Anlagen aus MaStR CSV.
    
    CSV-Spalten (Beispiel):
    - EinheitMastrNummer
    - Registrierungsdatum
    - Inbetriebnahmedatum
    - InstallierteLeistung
    - Breitengrad, Längengrad
    - Postleitzahl, Ort
    """
    df = pd.read_csv(mastr_csv_path, sep=';', encoding='utf-8')
    
    # Filtere nur PV-Anlagen
    pv_df = df[df['Energieträger'] == 'Solare Strahlungsenergie'].copy()
    
    # Erstelle GeoDataFrame
    geometry = [Point(lon, lat) for lon, lat in 
                zip(pv_df['Längengrad'], pv_df['Breitengrad'])]
    gdf = gpd.GeoDataFrame(pv_df, geometry=geometry, crs='EPSG:4326')
    
    return gdf

def filter_buildings_with_pv(buildings: gpd.GeoDataFrame, 
                             mastr_gdf: gpd.GeoDataFrame,
                             buffer_m: float = 50) -> gpd.GeoDataFrame:
    """
    Filtert Gebäude heraus, die bereits PV-Anlagen haben.
    
    Args:
        buildings: Gebäude-GeoDataFrame
        mastr_gdf: MaStR PV-Anlagen
        buffer_m: Buffer in Metern für räumliche Zuordnung
    """
    # Transformiere zu metrischem CRS für Buffer
    buildings_utm = buildings.to_crs('EPSG:25832')
    mastr_utm = mastr_gdf.to_crs('EPSG:25832')
    
    # Buffer um PV-Anlagen
    mastr_buffered = mastr_utm.geometry.buffer(buffer_m)
    
    # Spatial Join: Welche Gebäude überschneiden sich mit PV-Anlagen?
    buildings_with_pv = gpd.sjoin(
        buildings_utm, 
        gpd.GeoDataFrame(geometry=mastr_buffered),
        how='inner',
        predicate='intersects'
    )
    
    # Entferne Duplikate
    buildings_with_pv = buildings_with_pv[~buildings_with_pv.index.duplicated(keep='first')]
    
    # Filtere aus Original-Datenframe
    buildings_without_pv = buildings[~buildings.index.isin(buildings_with_pv.index)]
    
    return buildings_without_pv
```

#### Datenquellen
- **MaStR Web:** https://www.marktstammdatenregister.de/MaStR/
- **CSV-Download:** Über Web-Interface (manuell oder automatisiert)
- **Datenformat:** CSV mit Semikolon-Trennung, UTF-8

#### Kosten
💰 **Kostenlos** (öffentliche Daten)

#### Genauigkeit
🎯 **Sehr hoch** (offizielle Registrierungspflicht)

---

### 2. **OpenStreetMap (OSM) Tags** ⭐⭐⭐
**Schnelle, aber unvollständige Lösung**

#### Beschreibung
OpenStreetMap hat Tags für PV-Anlagen:
- `generator:source=solar`
- `power=generator` + `generator:type=solar_photovoltaic_panel`
- `roof:material=solar_panels`

#### Vorteile
✅ **Sofort verfügbar** - bereits in OSM-Daten  
✅ **Kostenlos** - Open Data  
✅ **Einfach zu integrieren** - bereits OSMnx im Projekt

#### Nachteile
⚠️ **Unvollständig** - nicht alle Anlagen erfasst  
⚠️ **Ungenau** - freiwillige Eintragungen  
⚠️ **Verzögerung** - nicht immer aktuell

#### Implementierung
```python
# In acquire_osm.py erweitern
import osmnx as ox

def get_solar_panels_from_osm(place: str) -> gpd.GeoDataFrame:
    """
    Lädt PV-Anlagen aus OSM.
    """
    # Suche nach generator:source=solar
    tags = {
        'generator:source': 'solar',
        'power': 'generator'
    }
    
    gdf = ox.features_from_place(place, tags=tags)
    
    return gdf

def check_buildings_for_osm_pv(buildings: gpd.GeoDataFrame, 
                               osm_pv: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Prüft ob Gebäude PV-Anlagen aus OSM haben.
    """
    # Spatial Join mit Buffer
    buildings_utm = buildings.to_crs('EPSG:25832')
    osm_pv_utm = osm_pv.to_crs('EPSG:25832')
    
    # Buffer um PV-Anlagen (10m)
    pv_buffered = osm_pv_utm.geometry.buffer(10)
    
    # Finde Überschneidungen
    has_pv = gpd.sjoin(
        buildings_utm,
        gpd.GeoDataFrame(geometry=pv_buffered),
        how='left',
        predicate='intersects'
    )
    
    # Markiere Gebäude mit PV
    buildings['has_pv_osm'] = buildings.index.isin(has_pv.index)
    
    return buildings
```

#### Genauigkeit
🎯 **Mittel** (ca. 30-50% Abdeckung)

---

### 3. **Computer Vision auf Luftbildern** ⭐⭐⭐⭐
**Moderne, aber aufwändige Lösung**

#### Beschreibung
Automatische Erkennung von PV-Modulen in Luftbildern mit Machine Learning / Computer Vision.

#### Vorteile
✅ **Visuell bestätigt** - direkter Nachweis  
✅ **Aktuell** - basierend auf neuesten Bildern  
✅ **Detailliert** - genaue Position auf Dach

#### Nachteile
⚠️ **Aufwändig** - ML-Modell nötig  
⚠️ **Rechenintensiv** - viele Bilder zu verarbeiten  
⚠️ **Fehleranfällig** - False Positives möglich

#### Implementierung
```python
# Beispiel mit TensorFlow/Keras
import tensorflow as tf
from PIL import Image
import requests
from io import BytesIO

def detect_solar_panels_in_image(image_url: str, model_path: str) -> bool:
    """
    Erkennt PV-Anlagen in Luftbild mit ML-Modell.
    
    Modelle:
    - Pre-trained: DeepSolar (Stanford)
    - Custom: Eigenes Modell trainieren
    """
    # Lade Bild
    response = requests.get(image_url)
    img = Image.open(BytesIO(response.content))
    
    # Preprocessing
    img = img.resize((224, 224))
    img_array = np.array(img) / 255.0
    img_array = np.expand_dims(img_array, axis=0)
    
    # Lade Modell
    model = tf.keras.models.load_model(model_path)
    
    # Prediction
    prediction = model.predict(img_array)
    
    return prediction[0][0] > 0.5  # Threshold

def check_buildings_with_cv(buildings: gpd.GeoDataFrame,
                            aerial_images_dir: Path) -> gpd.GeoDataFrame:
    """
    Prüft Luftbilder aller Gebäude auf PV-Anlagen.
    """
    buildings['has_pv_cv'] = False
    
    for idx, row in buildings.iterrows():
        image_path = aerial_images_dir / f"{idx}.jpg"
        
        if image_path.exists():
            has_pv = detect_solar_panels_in_image(str(image_path), "solar_detector.h5")
            buildings.loc[idx, 'has_pv_cv'] = has_pv
    
    return buildings
```

#### Verfügbare Modelle
- **DeepSolar:** Stanford-Projekt (https://github.com/stanford-futuredata/DeepSolar)
- **PyPVRoof:** Python-Paket für PV-Erkennung
- **Custom Training:** Eigenes Modell mit Labeled Data

#### Genauigkeit
🎯 **Hoch** (80-95% bei gutem Modell)

---

### 4. **Google Solar API** ⭐⭐
**Nur indirekt hilfreich**

#### Beschreibung
Die Google Solar API zeigt **Potenzial**, nicht bestehende Anlagen. Sie kann aber indirekt helfen:
- Wenn `maxArrayAreaMeters2` sehr klein ist → möglicherweise bereits belegt
- Vergleich: Potenzial vs. tatsächliche Fläche

#### Vorteile
✅ **Bereits implementiert** - `enrich_solar_potential.py` vorhanden  
✅ **Einfach** - nur API-Call

#### Nachteile
❌ **Nicht direkt** - zeigt nur Potenzial  
❌ **Ungenau** - keine zuverlässige Erkennung

#### Implementierung
```python
# Erweiterung von enrich_solar_potential.py
def check_existing_installations(solar_data: dict, 
                                 building_area_m2: float) -> bool:
    """
    Heuristik: Wenn nutzbare Fläche deutlich kleiner als Gebäudefläche,
    könnte bereits etwas installiert sein.
    """
    max_array_area = solar_data.get('solar_max_array_m2', 0)
    
    # Wenn nutzbare Fläche < 30% der Gebäudefläche
    # könnte bereits PV installiert sein
    if max_array_area > 0:
        ratio = max_array_area / building_area_m2
        if ratio < 0.3:
            return True  # Verdacht auf bestehende Anlage
    
    return False
```

#### Genauigkeit
🎯 **Niedrig** (nur Heuristik)

---

### 5. **Satellitenbilder + ML** ⭐⭐⭐
**Für große Gebiete**

#### Beschreibung
Ähnlich wie Computer Vision, aber mit Satellitenbildern (z.B. Sentinel-2, Landsat).

#### Vorteile
✅ **Großflächig** - ganze Städte auf einmal  
✅ **Kostenlos** - Sentinel-2 Daten frei verfügbar

#### Nachteile
⚠️ **Niedrige Auflösung** - 10m Pixel (Sentinel-2)  
⚠️ **Wolken** - Wetterabhängig  
⚠️ **Komplex** - Spezialwissen nötig

#### Implementierung
```python
import rasterio
from sentinelhub import SentinelHubRequest, DataCollection

def detect_pv_from_satellite(bbox, time_interval):
    """
    Lädt Sentinel-2 Daten und erkennt PV-Anlagen.
    """
    # Sentinel Hub API (kostenloser Account nötig)
    request = SentinelHubRequest(
        evalscript=PV_DETECTION_SCRIPT,
        input_data=[
            SentinelHubRequest.input_data(
                data_collection=DataCollection.SENTINEL2_L2A,
                time_interval=time_interval
            )
        ],
        responses=[SentinelHubRequest.output_response('default', MimeType.TIFF)],
        bbox=bbox,
        size=(512, 512)
    )
    
    return request.get_data()
```

#### Genauigkeit
🎯 **Mittel-Hoch** (70-85% bei guter Auflösung)

---

## 🏆 Empfohlene Lösung für Ihr Projekt

### **Kombination: MaStR + OSM + Heuristik**

#### Phase 1: MaStR-Integration (Priorität 1)
1. **MaStR-Daten herunterladen**
   - CSV-Export von https://www.marktstammdatenregister.de/
   - Filter: Nur PV-Anlagen in NRW/Dortmund
   - Regelmäßige Updates (monatlich)

2. **Spatial Join implementieren**
   - PV-Anlagen mit Gebäuden matchen (50m Buffer)
   - Gebäude mit PV-Anlagen markieren

3. **Filter in Pipeline integrieren**
   - Nach `process_data.py`, vor `filter_target.py`
   - Ausschluss von Gebäuden mit PV

#### Phase 2: OSM-Erweiterung (Priorität 2)
- OSM-Tags für PV-Anlagen in `acquire_osm.py` hinzufügen
- Zusätzliche Validierung neben MaStR

#### Phase 3: Computer Vision (Optional, später)
- Für Validierung und Qualitätskontrolle
- Bei Bedarf für spezielle Fälle

---

## 📝 Implementierungsplan

### Schritt 1: MaStR-Modul erstellen
```python
# src/pv_roof_leads/check_existing_pv.py

def load_mastr_data(mastr_csv_path: Path) -> gpd.GeoDataFrame:
    """Lädt MaStR CSV und konvertiert zu GeoDataFrame"""
    pass

def filter_buildings_with_existing_pv(
    buildings: gpd.GeoDataFrame,
    mastr_pv: gpd.GeoDataFrame
) -> gpd.GeoDataFrame:
    """Filtert Gebäude mit bestehenden PV-Anlagen heraus"""
    pass
```

### Schritt 2: Pipeline erweitern
```python
# In process_data.py oder neues Modul
# Nach process_data.py, vor filter_target.py

buildings = process_osm_data()
buildings = check_existing_pv(buildings)  # NEU
buildings = filter_target_buildings(buildings)
```

### Schritt 3: Konfiguration
```python
# In config.py
MASTR_CSV_PATH = DATA_DIR / "raw" / "dortmund" / "mastr_pv.csv"
PV_DETECTION_BUFFER_M = 50  # Buffer für räumliche Zuordnung
```

---

## 🔗 Nützliche Ressourcen

### MaStR
- **Web-Interface:** https://www.marktstammdatenregister.de/MaStR/
- **Dokumentation:** https://www.marktstammdatenregister.de/MaStR/Datendownload
- **CSV-Format:** Semikolon-getrennt, UTF-8

### Computer Vision
- **DeepSolar:** https://github.com/stanford-futuredata/DeepSolar
- **PyPVRoof:** https://github.com/... (Python-Paket)
- **Paper:** "DeepSolar: A Machine Learning Framework to Efficiently Construct a Solar Deployment Database in the United States"

### OSM
- **OSM Wiki:** https://wiki.openstreetmap.org/wiki/Tag:generator:source%3Dsolar
- **Overpass API:** https://overpass-turbo.eu/

---

## 💡 Quick Win: Sofort umsetzbar

**Minimaler Aufwand, maximaler Nutzen:**

1. **MaStR CSV manuell herunterladen** (5 Minuten)
2. **Einfaches Python-Skript** zum Spatial Join (30 Minuten)
3. **In Pipeline integrieren** (15 Minuten)

**Ergebnis:** Sofortige Filterung von ~10-20% der Leads (Gebäude mit bestehenden Anlagen)

---

## 📊 Erwartete Ergebnisse

### Datenqualität
- **MaStR:** ~90-95% aller Anlagen erfasst
- **OSM:** ~30-50% zusätzliche Erfassung
- **Kombination:** ~95-98% Abdeckung

### Performance-Impact
- **MaStR Spatial Join:** +2-5 Minuten Processing-Zeit
- **OSM-Check:** +1-2 Minuten
- **Gesamt:** Minimaler Overhead

### Lead-Reduktion
- **Erwartung:** 10-20% der Gebäude haben bereits PV
- **Ergebnis:** Fokus auf echte Potenziale

---

*Dokument erstellt: 2025-01-XX*  
*Nächste Schritte: MaStR-Integration implementieren*



