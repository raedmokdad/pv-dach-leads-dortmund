# PV-Dach-Eignung: Kriterien & Tools

## 🎯 Übersicht

Die Bewertung der Eignung eines Daches für PV-Anlagen basiert auf **mehreren technischen Kriterien**, die die Energieausbeute und Wirtschaftlichkeit beeinflussen.

---

## 📊 Relevante Kriterien

### 1. **Ausrichtung (Azimut)** ⭐⭐⭐⭐⭐
**Kritischster Faktor**

#### Optimal
- **Süd (180°):** Beste Ausbeute, ~100% des Potenzials
- **Südost/Südwest (135-225°):** Sehr gut, ~90-95% des Potenzials

#### Akzeptabel
- **Ost/West (90°/270°):** Geeignet, ~75-85% des Potenzials
- **Südost/Südwest (45-135°/225-315°):** Noch nutzbar, ~60-75%

#### Suboptimal
- **Nord (0°/360°):** Nicht geeignet, <30% des Potenzials

#### Bewertung
```python
def score_azimuth(azimuth: float) -> float:
    """
    Bewertet Ausrichtung (0-100 Punkte).
    
    Args:
        azimuth: Azimut in Grad (0°=Nord, 90°=Ost, 180°=Süd, 270°=West)
    """
    # Normalisiere auf 0-360
    azimuth = azimuth % 360
    
    # Optimal: 150-210° (Süd ±30°)
    if 150 <= azimuth <= 210:
        return 100.0
    # Sehr gut: 120-150° oder 210-240° (Südost/Südwest)
    elif 120 <= azimuth < 150 or 210 < azimuth <= 240:
        return 90.0
    # Gut: 90-120° oder 240-270° (Ost/West)
    elif 90 <= azimuth < 120 or 240 < azimuth <= 270:
        return 75.0
    # Akzeptabel: 60-90° oder 270-300°
    elif 60 <= azimuth < 90 or 270 < azimuth <= 300:
        return 60.0
    # Suboptimal: 30-60° oder 300-330°
    elif 30 <= azimuth < 60 or 300 < azimuth <= 330:
        return 40.0
    # Schlecht: Nord (0-30° oder 330-360°)
    else:
        return 20.0
```

---

### 2. **Dachneigung (Pitch/Tilt)** ⭐⭐⭐⭐
**Wichtig für Energieausbeute**

#### Optimal
- **30-35°:** Ideal für Deutschland (51° Breitengrad)
- **20-40°:** Sehr gut, minimaler Verlust

#### Akzeptabel
- **15-20° oder 40-50°:** Geeignet, ~5-10% Verlust
- **10-15° oder 50-60°:** Noch nutzbar, ~10-15% Verlust

#### Suboptimal
- **<10° (Flachdach):** Braucht Aufständerung, ~15-20% Verlust
- **>60° (Steil):** Sehr steil, ~20-30% Verlust

#### Bewertung
```python
def score_pitch(pitch: float) -> float:
    """
    Bewertet Dachneigung (0-100 Punkte).
    
    Args:
        pitch: Neigungswinkel in Grad (0°=flach, 90°=senkrecht)
    """
    # Optimal: 25-40° für Deutschland
    if 25 <= pitch <= 40:
        return 100.0
    # Sehr gut: 20-25° oder 40-45°
    elif 20 <= pitch < 25 or 40 < pitch <= 45:
        return 90.0
    # Gut: 15-20° oder 45-50°
    elif 15 <= pitch < 20 or 45 < pitch <= 50:
        return 80.0
    # Akzeptabel: 10-15° oder 50-55°
    elif 10 <= pitch < 15 or 50 < pitch <= 55:
        return 65.0
    # Suboptimal: 5-10° oder 55-60°
    elif 5 <= pitch < 10 or 55 < pitch <= 60:
        return 50.0
    # Schlecht: <5° (Flachdach) oder >60°
    else:
        return 30.0
```

---

### 3. **Verschattung (Shading)** ⭐⭐⭐⭐⭐
**Kritisch für Ertrag**

#### Verschattungsquellen
- **Bäume:** Statische Verschattung (ganztägig)
- **Nachbargebäude:** Statische Verschattung (morgens/abends)
- **Gauben, Kamine:** Lokale Verschattung
- **Antennen, Satellitenschüsseln:** Kleine Hindernisse

#### Bewertung
```python
def score_shading(sunshine_hours_per_year: float, 
                  max_sunshine_hours: float = 2000) -> float:
    """
    Bewertet Verschattung basierend auf Sonnenstunden.
    
    Args:
        sunshine_hours_per_year: Tatsächliche Sonnenstunden/Jahr
        max_sunshine_hours: Theoretisches Maximum (ca. 2000h für Deutschland)
    """
    if sunshine_hours_per_year >= max_sunshine_hours * 0.9:  # >1800h
        return 100.0  # Keine/minimale Verschattung
    elif sunshine_hours_per_year >= max_sunshine_hours * 0.8:  # >1600h
        return 85.0  # Geringe Verschattung
    elif sunshine_hours_per_year >= max_sunshine_hours * 0.7:  # >1400h
        return 70.0  # Moderate Verschattung
    elif sunshine_hours_per_year >= max_sunshine_hours * 0.6:  # >1200h
        return 55.0  # Stärkere Verschattung
    elif sunshine_hours_per_year >= max_sunshine_hours * 0.5:  # >1000h
        return 40.0  # Starke Verschattung
    else:
        return 20.0  # Sehr starke Verschattung
```

---

### 4. **Nutzbare Dachfläche** ⭐⭐⭐⭐
**Wichtig für Anlagengröße**

#### Kriterien
- **Gesamtfläche:** Größer = besser (mehr Module)
- **Nutzbare Fläche:** Nach Abzug von Hindernissen
- **Segmentierung:** Viele kleine Segmente = komplizierter

#### Bewertung
```python
def score_usable_area(usable_area_m2: float, 
                     total_roof_area_m2: float) -> float:
    """
    Bewertet nutzbare Dachfläche.
    
    Args:
        usable_area_m2: PV-nutzbare Fläche (nach Hindernissen)
        total_roof_area_m2: Gesamte Dachfläche
    """
    if total_roof_area_m2 == 0:
        return 0.0
    
    # Verhältnis nutzbar/gesamt
    ratio = usable_area_m2 / total_roof_area_m2
    
    # Optimal: >80% nutzbar
    if ratio >= 0.8:
        return 100.0
    # Sehr gut: 70-80%
    elif ratio >= 0.7:
        return 90.0
    # Gut: 60-70%
    elif ratio >= 0.6:
        return 80.0
    # Akzeptabel: 50-60%
    elif ratio >= 0.5:
        return 65.0
    # Suboptimal: 40-50%
    elif ratio >= 0.4:
        return 50.0
    # Schlecht: <40%
    else:
        return 30.0
```

---

### 5. **Hindernisse auf dem Dach** ⭐⭐⭐
**Reduziert nutzbare Fläche**

#### Typische Hindernisse
- **Gauben (Dormer):** Reduzieren Fläche
- **Kamine:** Kleine Flächenverluste
- **Antennen/Satellitenschüsseln:** Lokale Verschattung
- **Lüftungsanlagen:** Flächenverlust
- **Aufzugsmaschinenhäuser:** Große Flächenverluste

#### Erkennung
- **Google Solar API:** Erkennt automatisch Hindernisse
- **Computer Vision:** ML-basierte Erkennung in Luftbildern
- **Manuelle Prüfung:** Bei Top-Leads

---

### 6. **Dachzustand & Statik** ⭐⭐⭐
**Wichtig für Installation**

#### Kriterien
- **Dachalter:** Neuere Dächer bevorzugt
- **Dachmaterial:** Eignung für PV-Montage
- **Statik:** Tragfähigkeit für PV-Module (~15-20 kg/m²)

#### Bewertung (Heuristik)
```python
def score_roof_condition(baujahr: int = None) -> float:
    """
    Bewertet Dachzustand basierend auf Baujahr (Heuristik).
    
    Args:
        baujahr: Baujahr des Gebäudes
    """
    if baujahr is None:
        return 70.0  # Neutral, wenn unbekannt
    
    current_year = 2025
    age = current_year - baujahr
    
    # Optimal: <10 Jahre alt
    if age <= 10:
        return 100.0
    # Sehr gut: 10-20 Jahre
    elif age <= 20:
        return 90.0
    # Gut: 20-30 Jahre
    elif age <= 30:
        return 80.0
    # Akzeptabel: 30-40 Jahre
    elif age <= 40:
        return 65.0
    # Suboptimal: 40-50 Jahre
    elif age <= 50:
        return 50.0
    # Schlecht: >50 Jahre
    else:
        return 35.0
```

---

### 7. **Lokale Sonneneinstrahlung** ⭐⭐⭐⭐
**Regionale Unterschiede**

#### Deutschland
- **Süden (Bayern, Baden-Württemberg):** ~1100-1200 kWh/m²/Jahr
- **Mitte (NRW, Hessen):** ~1000-1100 kWh/m²/Jahr
- **Norden (Schleswig-Holstein):** ~950-1050 kWh/m²/Jahr

#### Bewertung
```python
def score_irradiation(irradiation_kwh_m2_year: float) -> float:
    """
    Bewertet lokale Sonneneinstrahlung.
    
    Args:
        irradiation_kwh_m2_year: kWh/m²/Jahr
    """
    # Optimal: >1150 kWh/m²/Jahr
    if irradiation_kwh_m2_year >= 1150:
        return 100.0
    # Sehr gut: 1100-1150
    elif irradiation_kwh_m2_year >= 1100:
        return 90.0
    # Gut: 1050-1100
    elif irradiation_kwh_m2_year >= 1050:
        return 85.0
    # Akzeptabel: 1000-1050
    elif irradiation_kwh_m2_year >= 1000:
        return 75.0
    # Suboptimal: 950-1000
    elif irradiation_kwh_m2_year >= 950:
        return 65.0
    # Schlecht: <950
    else:
        return 50.0
```

---

## 🛠️ Verfügbare Tools & APIs

### 1. **Google Solar API** ⭐⭐⭐⭐⭐
**Beste Lösung für automatische Bewertung**

#### Vorteile
✅ **Automatische 3D-Analyse** - erkennt Dachform, Neigung, Ausrichtung  
✅ **Verschattungsanalyse** - berücksichtigt Bäume, Gebäude  
✅ **Hinderniserkennung** - Gauben, Kamine automatisch erkannt  
✅ **Dachsegmente** - detaillierte Analyse pro Segment  
✅ **Sonnenstunden** - präzise Berechnung pro Jahr  
✅ **Einfache Integration** - bereits im Projekt vorhanden

#### Verfügbare Daten
- `maxArrayAreaMeters2` - Maximale nutzbare Fläche
- `maxArrayPanelsCount` - Maximale Anzahl Module
- `maxSunshineHoursPerYear` - Sonnenstunden/Jahr
- `roofSegmentStats` - Detaillierte Segment-Analyse
  - `pitchDegrees` - Neigung
  - `azimuthDegrees` - Ausrichtung
  - `areaMeters2` - Fläche
  - `stats.sunshineQuantiles` - Verschattungsanalyse

#### Kosten
- **Free Tier:** 500 Requests/Monat
- **Paid:** $0.10 pro 1000 Requests

#### Implementierung
```python
# Bereits vorhanden in enrich_solar_potential.py
from pv_roof_leads.enrich_solar_potential import get_solar_potential

solar_data = get_solar_potential(lat, lon, api_key)
# Enthält alle relevanten Metriken
```

---

### 2. **PVGIS (Photovoltaic Geographical Information System)** ⭐⭐⭐⭐
**Kostenlos, EU-weit**

#### Vorteile
✅ **Kostenlos** - keine API-Kosten  
✅ **Präzise Daten** - EU-weite Abdeckung  
✅ **Historische Daten** - Langzeit-Analysen  
✅ **Verschiedene Modelle** - verschiedene PV-Technologien

#### Nachteile
⚠️ **Keine Dach-Analyse** - nur Strahlungsdaten  
⚠️ **Keine API** - nur Web-Interface/CSV-Download  
⚠️ **Manuelle Koordinaten** - pro Gebäude einzeln

#### Verfügbare Daten
- Global Horizontal Irradiation (GHI)
- Direct Normal Irradiation (DNI)
- Diffuse Horizontal Irradiation (DHI)
- Optimal tilt angle
- Optimal azimuth

#### URL
- **Web:** https://re.jrc.ec.europa.eu/pvg_tools/en/
- **API:** https://re.jrc.ec.europa.eu/api/v5_2/

#### Implementierung
```python
import requests

def get_pvgis_data(lat: float, lon: float, 
                   tilt: float = 35, azimuth: float = 180):
    """
    Ruft PVGIS-Daten ab.
    """
    url = "https://re.jrc.ec.europa.eu/api/v5_2/PVcalc"
    
    params = {
        'lat': lat,
        'lon': lon,
        'peakpower': 1,  # 1 kWp für Normalisierung
        'loss': 14,  # Standard-Verluste
        'mountingplace': 'free',  # Freistehend
        'angle': tilt,
        'aspect': azimuth,
        'outputformat': 'json'
    }
    
    response = requests.get(url, params=params)
    data = response.json()
    
    return {
        'yearly_energy_kwh': data['outputs']['totals']['fixed']['E_y'],
        'yearly_irradiation_kwh_m2': data['outputs']['totals']['fixed']['H(i)_y']
    }
```

---

### 3. **Solargis** ⭐⭐⭐
**Professionell, kostenpflichtig**

#### Vorteile
✅ **Sehr präzise** - hochauflösende Daten  
✅ **API verfügbar** - automatisierbar  
✅ **Detaillierte Analysen** - Verschattung, Ertragsprognose

#### Nachteile
❌ **Kostenpflichtig** - ab ~€500/Jahr  
❌ **Komplex** - mehr Setup nötig

#### URL
- **Web:** https://solargis.com/
- **API:** https://api.solargis.com/

---

### 4. **OpenSolar / Helioscope** ⭐⭐⭐
**Für detaillierte Planung**

#### Vorteile
✅ **3D-Modellierung** - detaillierte Dach-Modelle  
✅ **Verschattungsanalyse** - präzise Schattenberechnung  
✅ **Layout-Planung** - optimale Modulplatzierung

#### Nachteile
❌ **Manuell** - nicht für Batch-Processing  
❌ **Kostenpflichtig** - für professionelle Nutzung

---

### 5. **Computer Vision auf Luftbildern** ⭐⭐⭐
**Für Hinderniserkennung**

#### Vorteile
✅ **Automatisch** - ML-basierte Erkennung  
✅ **Detailliert** - erkennt Gauben, Kamine, etc.  
✅ **Bereits vorhanden** - Luftbilder werden bereits geladen

#### Implementierung
```python
# Beispiel mit TensorFlow/Keras
def detect_roof_obstacles(image_path: str) -> dict:
    """
    Erkennt Hindernisse auf Dach (Gauben, Kamine, etc.).
    """
    # ML-Modell für Objekterkennung
    # z.B. YOLO, Faster R-CNN
    pass
```

---

## 🎯 Empfohlene Lösung für Ihr Projekt

### **Kombination: Google Solar API + Erweiterte Bewertung**

#### Phase 1: Google Solar API (bereits vorhanden)
- ✅ Automatische Dach-Analyse
- ✅ Verschattungsberechnung
- ✅ Hinderniserkennung
- ✅ Dachsegmente mit Neigung/Ausrichtung

#### Phase 2: Erweiterte Bewertung
- Erweitere `score_leads.py` um Solar-Kriterien
- Kombiniere mit bestehendem Scoring

---

## 📝 Implementierung: Erweitertes Scoring-System

### Neues Modul: `assess_roof_suitability.py`

```python
"""
Erweiterte Dach-Eignungsbewertung basierend auf Solar-Daten.
"""

def calculate_solar_suitability_score(solar_data: dict) -> dict:
    """
    Berechnet Eignungs-Score basierend auf allen Kriterien.
    
    Returns:
        Dict mit einzelnen Scores und Gesamt-Score
    """
    scores = {}
    
    # 1. Ausrichtung (30% Gewichtung)
    azimuth = solar_data.get('solar_best_azimuth', 0)
    scores['azimuth_score'] = score_azimuth(azimuth)
    scores['azimuth_weight'] = 0.30
    
    # 2. Neigung (20% Gewichtung)
    pitch = solar_data.get('solar_best_pitch', 0)
    scores['pitch_score'] = score_pitch(pitch)
    scores['pitch_weight'] = 0.20
    
    # 3. Verschattung (25% Gewichtung)
    sunshine_hours = solar_data.get('solar_sunshine_hours_year', 0)
    scores['shading_score'] = score_shading(sunshine_hours)
    scores['shading_weight'] = 0.25
    
    # 4. Nutzbare Fläche (15% Gewichtung)
    usable_area = solar_data.get('solar_max_array_m2', 0)
    total_area = solar_data.get('solar_roof_area_m2', 0)
    scores['area_score'] = score_usable_area(usable_area, total_area)
    scores['area_weight'] = 0.15
    
    # 5. Dachzustand (10% Gewichtung) - falls verfügbar
    baujahr = solar_data.get('baujahr', None)
    scores['condition_score'] = score_roof_condition(baujahr)
    scores['condition_weight'] = 0.10
    
    # Gesamt-Score (gewichteter Durchschnitt)
    total_score = (
        scores['azimuth_score'] * scores['azimuth_weight'] +
        scores['pitch_score'] * scores['pitch_weight'] +
        scores['shading_score'] * scores['shading_weight'] +
        scores['area_score'] * scores['area_weight'] +
        scores['condition_score'] * scores['condition_weight']
    )
    
    scores['total_suitability_score'] = total_score
    
    return scores
```

---

## 🔗 Nützliche Ressourcen

### Google Solar API
- **Dokumentation:** https://developers.google.com/maps/documentation/solar
- **Beispiele:** https://github.com/googlemaps/solar-api-examples

### PVGIS
- **Web-Interface:** https://re.jrc.ec.europa.eu/pvg_tools/en/
- **API-Dokumentation:** https://joint-research-centre.ec.europa.eu/pvgis-photovoltaic-geographical-information-system/getting-started-pvgis/api-non-interactive-service_en

### Solargis
- **Web:** https://solargis.com/
- **API:** https://solargis.com/docs/api/

### Computer Vision
- **DeepSolar:** https://github.com/stanford-futuredata/DeepSolar
- **YOLO für Objekterkennung:** https://github.com/ultralytics/yolov8

---

## 💡 Quick Win: Sofort umsetzbar

1. **Google Solar API erweitern** (bereits vorhanden)
   - Nutze bereits vorhandene Daten aus `enrich_solar_potential.py`
   - Erweitere um Bewertungs-Funktionen

2. **Scoring-System erweitern**
   - Integriere Solar-Kriterien in `score_leads.py`
   - Kombiniere mit bestehendem Scoring

3. **Ergebnisse visualisieren**
   - Zeige Eignungs-Scores in Excel/HTML-Report
   - Farbcodierung: Grün (gut) → Rot (schlecht)

---

*Dokument erstellt: 2025-01-XX*  
*Nächste Schritte: Erweiterte Bewertungs-Funktionen implementieren*



