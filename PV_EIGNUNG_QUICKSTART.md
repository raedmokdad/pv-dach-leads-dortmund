# Quick Start: Dach-Eignungsbewertung

## 🚀 Schnellstart

### Schritt 1: Google Solar API aktivieren

Die Google Solar API ist bereits im Projekt integriert (`enrich_solar_potential.py`).

1. **API Key erstellen:**
   - Gehen Sie zu: https://console.cloud.google.com/
   - Erstellen Sie ein Projekt
   - Aktivieren Sie "Solar API"
   - Erstellen Sie einen API Key

2. **API Key setzen:**
   ```powershell
   $env:GOOGLE_SOLAR_API_KEY='your-api-key-here'
   ```

### Schritt 2: Solar-Daten abrufen

```bash
# Für Top 100 Leads
python -m pv_roof_leads.enrich_solar_potential
```

Dies erstellt: `data/staging/dortmund/solar_enriched_top100.geojson`

### Schritt 3: Eignungsbewertung durchführen

```python
import geopandas as gpd
import pandas as pd
from pv_roof_leads.assess_roof_suitability import assess_buildings_suitability

# Lade angereicherte Daten
buildings = gpd.read_file("data/staging/dortmund/solar_enriched_top100.geojson")

# Bewerte Eignung
buildings_scored = assess_buildings_suitability(buildings)

# Speichere Ergebnis
buildings_scored.to_file("data/staging/dortmund/buildings_with_suitability.geojson", 
                         driver='GeoJSON')
```

### Schritt 4: Ergebnisse analysieren

```python
# Top 10 nach Eignungs-Score
top_suitable = buildings_scored.nlargest(10, 'total_suitability_score')

print("Top 10 nach Eignungs-Score:")
for idx, row in top_suitable.iterrows():
    print(f"{row.get('name', 'Unbekannt')}: "
          f"Score {row['total_suitability_score']:.1f} "
          f"(Klasse {row['suitability_class']})")
```

---

## 📊 Bewertungskriterien

### Gewichtung
- **Ausrichtung (Azimut):** 30% - Kritischster Faktor
- **Verschattung:** 25% - Wichtig für Ertrag
- **Neigung:** 20% - Optimal 25-40°
- **Nutzbare Fläche:** 15% - Nach Hindernissen
- **Dachzustand:** 10% - Basierend auf Baujahr

### Eignungsklassen
- **A (≥80 Punkte):** Sehr gut geeignet
- **B (65-79 Punkte):** Gut geeignet
- **C (50-64 Punkte):** Akzeptabel
- **D (<50 Punkte):** Suboptimal

---

## 🔧 Integration in bestehende Pipeline

### Option 1: Nach Solar-Enrichment

```python
# In enrich_solar_potential.py erweitern
from pv_roof_leads.assess_roof_suitability import assess_buildings_suitability

# Nach Solar-Daten abrufen
enriched = enrich_with_solar_potential(buildings_gdf)

# Eignungsbewertung hinzufügen
enriched = assess_buildings_suitability(enriched)
```

### Option 2: In Scoring-System integrieren

```python
# In score_leads.py erweitern
from pv_roof_leads.assess_roof_suitability import calculate_solar_suitability_score

def apply_scoring(buildings):
    # ... bestehendes Scoring ...
    
    # Solar-Eignung hinzufügen (falls verfügbar)
    if 'solar_api_success' in buildings.columns:
        suitability_scores = []
        for idx, row in buildings.iterrows():
            if row.get('solar_api_success', False):
                solar_data = {
                    'solar_best_azimuth': row.get('solar_best_azimuth', 0),
                    'solar_best_pitch': row.get('solar_best_pitch', 0),
                    'solar_sunshine_hours_year': row.get('solar_sunshine_hours_year', 0),
                    'solar_max_array_m2': row.get('solar_max_array_m2', 0),
                    'solar_roof_area_m2': row.get('solar_roof_area_m2', 0),
                    'baujahr': row.get('baujahr', None)
                }
                scores = calculate_solar_suitability_score(solar_data)
                suitability_scores.append(scores)
            else:
                suitability_scores.append({'total_suitability_score': 0})
        
        suitability_df = pd.DataFrame(suitability_scores)
        buildings = pd.concat([buildings, suitability_df], axis=1)
    
    return buildings
```

---

## 📈 Erwartete Ergebnisse

### Beispiel-Output

```
Gebäude: Logistikzentrum Dortmund
- Ausrichtung: 180° (Süd) → Score: 100.0
- Neigung: 30° → Score: 100.0
- Verschattung: 1800h/Jahr → Score: 100.0
- Nutzbare Fläche: 85% → Score: 100.0
- Dachzustand: 15 Jahre → Score: 90.0
- Gesamt-Score: 98.0 (Klasse A)
```

---

## 💡 Tipps

1. **Priorisiere Top-Leads:** Nur Top 100-200 mit Solar-API analysieren (Kosten)
2. **Kombiniere Scores:** Solar-Eignung + bestehendes Scoring
3. **Visualisiere:** Zeige Eignungs-Scores in Excel/HTML-Report
4. **Filter:** Filtere nach `suitability_class == 'A'` für beste Leads

---

**Detaillierte Dokumentation:** Siehe `PV_DACH_EIGNUNG_BEWERTUNG.md`



