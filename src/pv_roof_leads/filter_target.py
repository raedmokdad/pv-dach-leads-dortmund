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
    print(" Task Zielgruppenfilter")
    print("=" * 60)
    
    # Gebaüde laden
    buildings_path = PROCESSED_DORTMUND / "buildings_processed.geojson"
    print(f" Lade Gebäude: {buildings_path}")
    buildings = gpd.read_file(buildings_path)
    print(f"✓ {len(buildings)} Gebäude geladen")
    
    # POIs laden (neueste OSM-Daten)
    osm_dir = RAW_DORTMUND / "osm"
    latest_osm = sorted(osm_dir.glob("*"))[-1]
    pois_path = latest_osm / "pois.geojson"
    print(f" Lade POIs: {pois_path}")
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
    - ODER Gebäude IST relevanter POI (auch außerhalb Gewerbezonen!)
    - ABER NICHT wenn Gebäude IST hospital/clinic (Ausschluss)
    
    POI-Kategorien (außerhalb Gewerbezonen erlaubt):
    - Krankenpflege (nursing_home, social_facility) - HÖCHSTE PRIORITÄT
    - Bildung (school, kindergarten, university, college)
    - Sport (sports_centre, swimming_pool, stadium, fitness_centre)
    - Einzelhandel (supermarket, mall, shopping_centre)
    - Gastgewerbe (hotel, hostel, guest_house)
    - Öffentlich (community_centre, townhall, library)
    - Logistik (warehouse)
    """
    print("\n" + "=" * 60)
    print("Filter-Regeln anwenden")
    print("=" * 60)
    
    before = len(buildings)

    # Regel 1: Gebäude IN Gewerbegebieten (landuse-Spalte aus Task 4.2)
    in_commercial_zone = buildings['landuse'].isin(LANDUSE_INCLUDE)
    print(f"✓ {in_commercial_zone.sum()} Gebaüde in Gewerbegebieten (industrial/commercial)")
    
    # Regel 2: Relevante POIs (auch außerhalb Gewerbezonen!)
    print("\n✓ Prüfe POI-Kategorien (auch außerhalb Gewerbezonen):")
    
    # POIs basierend auf verschiedenen OSM-Spalten
    is_nursing_home = buildings['amenity'].isin(POI_NURSING_HOME)
    is_education = buildings['amenity'].isin(POI_EDUCATION)
    is_sports = buildings['leisure'].isin(POI_SPORTS)
    is_retail = buildings['shop'].isin(POI_RETAIL)
    is_hospitality = buildings['tourism'].isin(POI_HOSPITALITY)
    is_public = buildings['amenity'].isin(POI_PUBLIC)
    is_logistics = buildings['building'].isin(POI_LOGISTICS)
    
    # Kombiniere alle POI-Kategorien
    is_relevant_poi = (
        is_nursing_home | is_education | is_sports | 
        is_retail | is_hospitality | is_public | is_logistics
    )
    
    # Statistiken pro Kategorie
    print(f"   • Krankenpflege: {is_nursing_home.sum()} (HÖCHSTE PRIORITÄT)")
    print(f"   • Bildung: {is_education.sum()}")
    print(f"   • Sport: {is_sports.sum()}")
    print(f"   • Einzelhandel: {is_retail.sum()}")
    print(f"   • Gastgewerbe: {is_hospitality.sum()}")
    print(f"   • Öffentlich: {is_public.sum()}")
    print(f"   • Logistik: {is_logistics.sum()}")
    print(f"   → Gesamt POIs: {is_relevant_poi.sum()}")
    
    # Regel 3: Krankenhäuser/Kliniken AUSSCHLIESSEN
    print("\n Prüfe Ausschluss-Kriterien:")
    is_hospital = buildings['amenity'].isin(POI_HOSPITAL)
    print(f"  {is_hospital.sum()} Krankenhäuser/Kliniken (werden ausgeschlossen)")
    
    # Finale Filter-Regel: (Gewerbezonen ODER POIs) ABER NICHT Krankenhäuser
    target_filter = (in_commercial_zone | is_relevant_poi) & ~is_hospital
    
    # Filtere Gebäude
    targets = buildings[target_filter].copy()
    
    # Detaillierte Statistik
    poi_in_commercial = (in_commercial_zone & is_relevant_poi).sum()
    poi_outside = (is_relevant_poi & ~in_commercial_zone).sum()
    only_commercial = (in_commercial_zone & ~is_relevant_poi).sum()
    
    print("\n" + "=" * 60)
    print(f" Filter-Ergebnis: {before} → {len(targets)} Gebäude")
    print(f"   - Nur Gewerbezone (kein POI): {only_commercial}")
    print(f"   - POIs in Gewerbezonen: {poi_in_commercial}")
    print(f"   - POIs außerhalb Gewerbezonen: {poi_outside}")
    print(f"   - Ausgeschlossen (Krankenhäuser): {is_hospital.sum()}")
    print(f"\n   Reduktion: {(1 - len(targets)/before)*100:.1f}%")
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
    
    print(f"\n Speichere Ergebnis...")
    targets.to_file(output_path, driver="GeoJSON")
    
    print(f"Gespeichert: {output_path}")
    print(f"{len(targets)} Zielgebäude bereit für Scoring ")
    
    return output_path


if __name__ == "__main__":
    filter_target_buildings()