"""
Zentrale Konfiguration für das PV-Dach-Leads Dortmund MVP.
Alle Schwellenwerte/Parameter kommen von hier – keine Hard-Codes in Modulen.
"""

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


# OSM-Kategorien
LANDUSE_INCLUDE = ["industrial", "commercial"]
POI_NURSING_HOME = ["nursing_home", "social_facility"]
POI_HOSPITAL = ["hospital", "clinic"]

# POI (point of interest) Nähe: Gebäude gilt als "nahe POI", wenn Distanz <= Buffer
POI_BUFFER_M = 50

# Export: wieviele Leads sollen raus?
EXPORT_TOPK = 200

# Mindestdachfläche in m² für PV-Leads
MIN_FOOTPRINT_AREA_M2 = 500

#Flächen-Scoring-Parameter 
AREA_SCORE_MIN = 500    # 500m² → 0 Punkte
AREA_SCORE_MID = 1000   # 1000m² → 60 Punkte  
AREA_SCORE_MAX = 2000   # 2000m²+ → 100 Punkte

# Scoring-Klassen
SCORE_A_MIN = 75
SCORE_B_MIN = 55
# Score_C ist implizit: < SCORE_B_MIN


# total_score = WEIGHT_AREA * area_score + WEIGHT_ZONE * zone_score
WEIGHT_AREA = 0.60  # 60% des Scores kommt von der Dach-/Gebäudefläche
WEIGHT_ZONE = 0.40  # 40% des Scores kommt von der Zone/Zielgruppe

# Zone Scores (0..100 Skala, hier nutzen wir später 0..40 und normalisieren im Score-Modul)
ZONE_SCORE = {
    "industrial": 40,
    "commercial": 30,
    "nursing_home": 35,
}