"""
Task 5.1: Zielgruppenfilter entwickeln
Filtert Gebäude nach Business-Logik:
- Alle Gebäude IN industrial/commercial Zonen
- ODER Gebäude IST nursing_home/social_facility (höchste Priorität)
- ABER NICHT wenn Gebäude IST hospital/clinic
"""

import geopandas as gpd
from pathlib import Path
import pandas as pd

from pv_roof_leads.config import (
    CRS_INTERNAL,
    LANDUSE_INCLUDE,
    POI_NURSING_HOME,
    POI_HOSPITAL,
    POI_EDUCATION,
    POI_SPORTS,
    POI_RETAIL,
    POI_HOSPITALITY,
    POI_PUBLIC,
    POI_LOGISTICS
)
from pv_roof_leads.paths import PROCESSED_DORTMUND, STAGING_DORTMUND, RAW_DORTMUND

def load_processed_data() -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """Lädt die verarbeiteten Gebäude un POIs."""
    print("=" * 60)
    print("📊 Task 5.1: Zielgruppenfilter")
    print("=" * 60)
    
    # Gebaüde laden
    buildings_path = PROCESSED_DORTMUND / "buildings_processed.geojson"
    print(f"📂 Lade Gebäude: {buildings_path}")
    buildings = gpd.read_file(buildings_path)
    print(f"✓ {len(buildings)} Gebäude geladen")
    
    # POIs laden (neueste OSM-Daten)
    osm_dir = RAW_DORTMUND / "osm"
    latest_osm = sorted(osm_dir.glob("*"))[-1]
    pois_path = latest_osm / "pois.geojson"
    print(f"📂 Lade POIs: {pois_path}")
    pois = gpd.read_file(pois_path)
    print(f"✓ {len(pois)} POIs geladen")
    
    return buildings, pois


def find_pois_nearby(
    buildings: gpd.GeoDataFrame,
    pois: gpd.GeoDataFrame,
    poi_category: str,
    radius_m: float 
) -> pd.Series:
    """Findet Gebäude die POIs einer bestimmten Kategorie in der Nähe haben."""
    print(f"⏳ Suche {poi_category} in {radius_m}m Radius...")

    #POIs der gesuchten Kategorie filtern
    relevant_pois = pois[pois['poi_category'] == poi_category]
    if len(relevant_pois) == 0:
        print(f"⚠️  Keine {poi_category} POIs gefunden")
        return pd.Series([False] * len(buildings), index=buildings.index)
    
    print(f"   {len(relevant_pois)} {poi_category} POIs gefunden")

    #Buffer um pois erstellen - kreis mit radius_m
    buffer_pois = relevant_pois.geometry.buffer(radius_m)
    
    # Prüfen welche Gebäude in einem der Buffer liegen
    building_in_buffer = buildings.geometry.apply(
        lambda geom: buffer_pois.intersects(geom).any()
    )
    count_nearby = building_in_buffer.sum()
    print(f"✓ {count_nearby} Gebäude in {radius_m}m Nähe zu {poi_category}")
    return building_in_buffer


def apply_target_filter(buildings: gpd.GeoDataFrame, pois: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Wendet Business-Logik Filter an:
    - Alle Gebäude IN industrial/commercial Zonen (LANDUSE_INCLUDE)
    - ABER NICHT wenn Gebäude IST hospital/clinic (Ausschluss)
    """
    print("\n" + "=" * 60)
    print("🎯 Wende Filter-Regeln an")
    print("=" * 60)
    
    before = len(buildings)

    # Regel 1: Gebäude IN Gewerbegebieten (landuse-Spalte aus Task 4.2)
    in_commercial_zone = buildings['landuse'].isin(LANDUSE_INCLUDE)
    print(f"✓ {in_commercial_zone.sum()} Gebäude in Gewerbegebieten (industrial/commercial)")
    
    # Regel 2: Krankenhäuser/Kliniken AUSSCHLIESSEN
    print("\n🚫 Prüfe Ausschluss-Kriterien:")
    is_hospital = buildings['amenity'].isin(POI_HOSPITAL)
    print(f"⚠️  {is_hospital.sum()} Krankenhäuser/Kliniken (werden ausgeschlossen)")
    
    # Finale Filter-Regel: Gebäude in Gewerbezonen ABER NICHT Krankenhäuser
    target_filter = in_commercial_zone & ~is_hospital
    
    # Filtere Gebäude
    targets = buildings[target_filter].copy()
    
    print("\n" + "=" * 60)
    print(f"✅ Filter-Ergebnis: {before} → {len(targets)} Gebäude")
    print(f"   Nur Gebäude in industrial/commercial Zonen")
    print(f"   Krankenhäuser ausgeschlossen: {is_hospital.sum()}")
    print(f"   Reduktion: {(1 - len(targets)/before)*100:.1f}%")
    print("=" * 60)
    
    return targets


def filter_target_buildings() -> Path:
    """
    Filtert Gebäude nach Zielgruppen-Kriterien.
    """
    #Lade Daten
    buildings, pois = load_processed_data()
    
    #Filter anwenden
    targets = apply_target_filter(buildings, pois)
    
    #Speichern
    output_path = STAGING_DORTMUND / "target_buildings.geojson"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"\n💾 Speichere Ergebnis...")
    targets.to_file(output_path, driver="GeoJSON")
    
    print(f"\n✅ Task 5.1 abgeschlossen!")
    print(f"📁 Gespeichert: {output_path}")
    print(f"📊 {len(targets)} Zielgebäude bereit für Scoring (Task 5.2)")
    
    return output_path


if __name__ == "__main__":
    filter_target_buildings()