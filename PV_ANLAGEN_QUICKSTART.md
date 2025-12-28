# Quick Start: PV-Anlagen-Erkennung

## 🚀 Schnellstart (5 Minuten)

### Schritt 1: MaStR-Daten herunterladen

1. Gehen Sie zu: https://www.marktstammdatenregister.de/MaStR/
2. **Datendownload** → **Einheiten** → **CSV-Export**
3. Filter: **Energieträger = Solare Strahlungsenergie**
4. Filter: **Bundesland = Nordrhein-Westfalen** (optional, für kleinere Datei)
5. Download starten
6. Datei speichern als: `data/raw/dortmund/mastr_pv.csv`

### Schritt 2: Pipeline erweitern

Die neue Funktion kann in die Pipeline integriert werden:

```bash
# Bestehende Pipeline
python -m pv_roof_leads.acquire_osm
python -m pv_roof_leads.process_data

# NEU: PV-Anlagen prüfen
python -m pv_roof_leads.check_existing_pv

# Weiter mit bestehender Pipeline
python -m pv_roof_leads.filter_target
python -m pv_roof_leads.score_leads
# ...
```

### Schritt 3: Automatische Integration

Oder integrieren Sie es direkt in `process_data.py`:

```python
# Am Ende von process_data.py
from pv_roof_leads.check_existing_pv import (
    load_mastr_pv_installations,
    check_buildings_for_existing_pv,
    filter_buildings_without_pv
)

# Nach Datenverarbeitung
mastr_pv = load_mastr_pv_installations()
buildings = check_buildings_for_existing_pv(buildings, mastr_pv)
buildings = filter_buildings_without_pv(buildings)
```

---

## 📊 Erwartete Ergebnisse

- **Gebäude mit PV:** ~10-20% der analysierten Gebäude
- **Lead-Reduktion:** Fokus auf echte Potenziale
- **Datenqualität:** ~90-95% Abdeckung (MaStR)

---

## 🔧 Konfiguration

In `config.py`:

```python
MASTR_CSV_PATH = RAW_DORTMUND / "mastr_pv.csv"
PV_DETECTION_BUFFER_M = 50.0  # Buffer in Metern
```

---

## 📝 Nächste Schritte

1. ✅ MaStR-Daten herunterladen
2. ✅ Modul testen: `python -m pv_roof_leads.check_existing_pv`
3. ✅ In Pipeline integrieren
4. ⏭️ Optional: OSM-Tags hinzufügen (siehe `PV_ANLAGEN_ERKENNUNG.md`)

---

**Detaillierte Dokumentation:** Siehe `PV_ANLAGEN_ERKENNUNG.md`



