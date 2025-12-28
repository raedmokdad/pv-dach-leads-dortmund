"""
Zentrale Konfiguration für das PV-Dach-Leads Dortmund MVP.
Alle Schwellenwerte/Parameter kommen von hier – keine Hard-Codes in Modulen.
"""

import os
from pathlib import Path

# Pfade
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
STAGING_DIR = DATA_DIR / "staging"
FINAL_DIR = DATA_DIR / "final"

# Stadt-spezifische Pfade
RAW_DORTMUND = RAW_DIR / "dortmund"
PROCESSED_DORTMUND = PROCESSED_DIR / "dortmund"
STAGING_DORTMUND = STAGING_DIR / "dortmund"
FINAL_DORTMUND = FINAL_DIR / "dortmund"


USE_POLYGON = True
CITY_NAME_OSM = "Dortmund, Germany"


CITY = "DORTMUND"

# Dortmund Bounding Box (lon_min, lat_min, lon_max, lat_max) nach EPSG:4326
DORTMUND_BBOX_DICT = {
    "lon_min": 7.3,
    "lat_min": 51.4,
    "lon_max": 7.7,
    "lat_max": 51.6,
}
DORTMUND_BBOX = (7.3, 51.4, 7.7, 51.6)  

# CRS-Definitionen
CRS_INTERNAL = "EPSG:25832"  # Für Flächenberechnung
CRS_EXPORT = "EPSG:4326"     # Für GeoJSON/CSV Export

# PLZ-Filter für Dortmund
DORTMUND_PLZ_PREFIXES = ['44']  # Dortmund PLZ-Bereich: 44xxx


# OSM-Kategorien
LANDUSE_INCLUDE = ["industrial", "commercial"]
POI_NURSING_HOME = ["nursing_home", "social_facility"]
POI_HOSPITAL = ["hospital", "clinic"]
POI_EDUCATION = ["school", "kindergarten", "university", "college"]
POI_SPORTS = ["sports_centre", "swimming_pool", "stadium", "fitness_centre"]
POI_RETAIL = ["supermarket", "mall", "shopping_centre"]
POI_HOSPITALITY = ["hotel", "hostel", "guest_house"]
POI_PUBLIC = ["community_centre", "townhall", "library"]
POI_LOGISTICS = ["warehouse"]  

# Hinweis: OSM-Tag-Kategorien
# - amenity: POI_NURSING_HOME, POI_HOSPITAL, POI_EDUCATION, POI_PUBLIC
# - leisure: POI_SPORTS
# - shop: POI_RETAIL
# - tourism: POI_HOSPITALITY
# - building: POI_LOGISTICS

# Scoring-Gewichte (für später in Sprint 5)
POI_SCORES = {
    "nursing_home": 35,      # Höchste Priorität
    "education": 30,         # Schulen, Unis
    "sports": 25,            # Sportzentren, Schwimmbäder
    "hospitality": 30,       # Hotels
    "retail": 25,            # Supermärkte, Einkaufszentren
    "public": 20,            # Öffentliche Gebäude
    "logistics": 35,         # Lagerhallen (großer Energiebedarf)
    "hospital": -100,        # Ausschluss (Konkurrenz)
}

# POI (point of interest) Nähe: Gebäude gilt als "nahe POI", wenn Distanz <= Buffer
POI_BUFFER_M = 50

# Export: wieviele Leads sollen raus?
EXPORT_TOPK = 500

# Mindestdachfläche in m² für PV-Leads
MIN_FOOTPRINT_AREA_M2 = 500

#Flächen-Scoring-Parameter 
AREA_SCORE_MIN = 500    # 500m² → 0 Punkte
AREA_SCORE_MID = 1000   # 1000m² → 60 Punkte  
AREA_SCORE_MAX = 2000   # 2000m²+ → 100 Punkte




# total_score = WEIGHT_AREA * area_score + WEIGHT_ZONE * zone_score
WEIGHT_AREA = 0.60  # 60% des Scores kommt von der Dach-/Gebäudefläche
WEIGHT_ZONE = 0.40  # 40% des Scores kommt von der Zone/Zielgruppe

# Zone Scores (0..100 Skala, hier nutzen wir später 0..40 und normalisieren im Score-Modul)
ZONE_SCORES = {
    # Landuse-Zonen
    'industrial': 40,
    'commercial': 30,
    
    # POI-Kategorien (nach amenity/leisure/shop/tourism/building)
    'nursing_home': 40,
    'social_facility': 40,
    'school': 25,
    'kindergarten': 25,
    'university': 25,
    'college': 25,
    'sports_centre': 25,
    'swimming_pool': 25,
    'stadium': 25,
    'fitness_centre': 25,
    'supermarket': 20,
    'mall': 20,
    'shopping_centre': 20,
    'hotel': 20,
    'hostel': 20,
    'guest_house': 20,
    'community_centre': 15,
    'townhall': 15,
    'library': 15,
    'warehouse': 15,
    
    # Fallback
    'default': 10
}

# Prioritäts-Schwellenwerte
PRIORITY_THRESHOLDS = {
    'A': 75,  # Score ≥ 75
    'B': 55,  # Score 55-74
    'C': 0    # Score < 55
}

# Google Solar API
# Get your API key from: https://console.cloud.google.com/
# Enable "Solar API" and create credentials
GOOGLE_SOLAR_API_KEY = os.getenv("GOOGLE_SOLAR_API_KEY", "")

# Solar API Limits
SOLAR_API_MAX_REQUESTS_FREE = 500  # Free tier: 500 requests/month
SOLAR_API_RATE_LIMIT_DELAY = 1.0   # Delay between requests in seconds

# PV-Anlagen-Erkennung (bestehende Installationen)
# MaStR (Marktstammdatenregister) - offizielle PV-Anlagen-Datenbank
MASTR_CSV_PATH = RAW_DORTMUND / "mastr_pv.csv"  # Pfad zur MaStR CSV-Datei
PV_DETECTION_BUFFER_M = 50.0  # Buffer in Metern für räumliche Zuordnung Gebäude ↔ PV-Anlagen