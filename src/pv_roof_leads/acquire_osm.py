"""
OSM-Datenerfassung: Landuse-Zonen, Gebäude und POIs für Dortmund
Nutzt OSMnx über Overpass API
"""

import geopandas as gpd
import pandas as pd
from pathlib import Path
from datetime import datetime

from pv_roof_leads.paths import RAW_DORTMUND
from pv_roof_leads.config import (
    USE_POLYGON,
    CITY_NAME_OSM,
    DORTMUND_BBOX,
    LANDUSE_INCLUDE,
    POI_NURSING_HOME,
    POI_HOSPITAL,
    POI_EDUCATION,
    POI_SPORTS,
    POI_RETAIL,
    POI_HOSPITALITY,
    POI_PUBLIC,
    POI_LOGISTICS,
    CRS_EXPORT,
    CRS_INTERNAL,
)

try:
    import osmnx as ox
    
    # Settings für große Abfragen (Polygon = ganzes Stadtgebiet)
    ox.settings.timeout = 900  # 15 Min für Polygon-Abfragen
    ox.settings.max_query_area_size = 5_000_000_000  # 500 km²
    ox.settings.use_cache = True
    
except ImportError:
    print("  OSMnx nicht installiert!")
    print("   Installiere mit: pip install osmnx")
    raise


def get_city_boundary():
    """
    Liefert die Stadtgrenze von Dortmund.
    
    Returns:
        shapely.Polygon oder tuple: Polygon (wenn USE_POLYGON=True) oder BBOX
    """
    if USE_POLYGON:
        print(f"⏳ Lade Stadtgrenze für: {CITY_NAME_OSM}")
        gdf = ox.geocode_to_gdf(CITY_NAME_OSM)
        print(f"✓ Stadtgrenze geladen (Polygon)")
        return gdf.geometry.iloc[0]
    else:
        print(f"✓ Nutze BBOX: {DORTMUND_BBOX}")
        return DORTMUND_BBOX


def load_landuse_zones():
    """
    Lädt industrial/commercial Zonen aus OSM.
    
    Returns:
        gpd.GeoDataFrame: Landnutzungszonen in CRS_INTERNAL
    """
    boundary = get_city_boundary()
    tags = {"landuse": LANDUSE_INCLUDE}
    
    print(f"⏳ Lade Landnutzungszonen...")
    if USE_POLYGON:
        gdf = ox.features_from_polygon(boundary, tags=tags)
    else:
        gdf = ox.features_from_bbox(boundary[3], boundary[1], boundary[2], boundary[0], tags=tags)
    
    gdf = gdf.to_crs(CRS_INTERNAL)
    print(f"✓ {len(gdf)} Landnutzungszonen geladen")
    return gdf


def load_buildings():
    """
    Lädt alle Gebäude aus OSM.
    
    Returns:
        gpd.GeoDataFrame: Gebäude in CRS_INTERNAL
    """
    boundary = get_city_boundary()
    tags = {"building": True}
    
    print(f"⏳ Lade Gebäude...")
    if USE_POLYGON:
        gdf = ox.features_from_polygon(boundary, tags=tags)
    else:
        gdf = ox.features_from_bbox(boundary[3], boundary[1], boundary[2], boundary[0], tags=tags)
    
    # Nur Polygone behalten
    gdf = gdf[gdf.geometry.type.isin(['Polygon', 'MultiPolygon'])]
    gdf = gdf.to_crs(CRS_INTERNAL)
    
    print(f"✓ {len(gdf)} Gebäude geladen")
    return gdf


def load_pois():
    """
    Lädt alle relevanten POIs aus OSM (Pflegeheime, Schulen, etc.).
    
    Returns:
        gpd.GeoDataFrame: POIs in CRS_INTERNAL mit Spalte 'poi_category'
    """
    boundary = get_city_boundary()
    
    # POI-Tags strukturieren
    poi_config = {
        "nursing_home": {"amenity": POI_NURSING_HOME},
        "hospital": {"amenity": POI_HOSPITAL},
        "education": {"amenity": POI_EDUCATION},
        "sports": {"leisure": POI_SPORTS},
        "retail": {"shop": POI_RETAIL},
        "hospitality": {"tourism": POI_HOSPITALITY},
        "public": {"amenity": POI_PUBLIC},
        "logistics": {"building": POI_LOGISTICS},
    }
    
    all_pois = []
    
    for category, tags in poi_config.items():
        print(f"⏳ Lade {category} POIs...")
        try:
            if USE_POLYGON:
                gdf = ox.features_from_polygon(boundary, tags=tags)
            else:
                gdf = ox.features_from_bbox(boundary[3], boundary[1], boundary[2], boundary[0], tags=tags)
            
            gdf['poi_category'] = category
            all_pois.append(gdf)
            print(f"✓ {len(gdf)} {category} POIs geladen")
        except Exception as e:
            print(f"⚠ Keine {category} POIs gefunden: {e}")
    
    if not all_pois:
        print("⚠ Keine POIs gefunden!")
        return gpd.GeoDataFrame()
    
    # Alle POIs zusammenführen
    pois = gpd.GeoDataFrame(pd.concat(all_pois, ignore_index=True))
    pois = pois.to_crs(CRS_INTERNAL)
    
    print(f"✓ Gesamt: {len(pois)} POIs geladen")
    return pois


def acquire_osm_data() -> tuple[Path, Path, Path]:
    """
    Lädt OSM-Daten (Landuse + Gebäude + POIs) und speichert sie als GeoJSON.
    
    Returns:
        tuple: (landuse_path, buildings_path, pois_path)
    """
    print("=" * 60)
    print("OSM-Datenerfassung für Dortmund")
    print("=" * 60)
    
    # Landuse laden
    gdf_zones = load_landuse_zones()
    
    # Gebäude laden
    gdf_buildings = load_buildings()
    
    # POIs laden
    gdf_pois = load_pois()
    
    # Output-Ordner mit Zeitstempel erstellen
    timestamp = datetime.now().strftime("%Y%m%d%")
    output_dir = RAW_DORTMUND / "osm" / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("\n" + "=" * 60)
    print("💾 Speichere Daten...")
    print("=" * 60)
    
    # Landuse-Zonen speichern
    landuse_path = output_dir / "landuse_zones.geojson"
    gdf_zones.to_file(landuse_path, driver="GeoJSON")
    print(f"✓ Landuse-Zonen: {landuse_path}")
    print(f"  {len(gdf_zones)} Zonen, {landuse_path.stat().st_size / (1024*1024):.2f} MB")
    
    # Gebäude speichern
    buildings_path = output_dir / "buildings.geojson"
    gdf_buildings.to_file(buildings_path, driver="GeoJSON")
    print(f"✓ Gebäude: {buildings_path}")
    print(f"  {len(gdf_buildings)} Gebäude, {buildings_path.stat().st_size / (1024*1024):.2f} MB")
    
    # POIs speichern
    pois_path = output_dir / "pois.geojson"
    if len(gdf_pois) > 0:
        gdf_pois.to_file(pois_path, driver='GeoJSON')
        print(f"✓ POIs: {pois_path}")
        print(f"  {len(gdf_pois)} POIs, {pois_path.stat().st_size / (1024*1024):.2f} MB")
        print(f"  Verteilung: {gdf_pois['poi_category'].value_counts().to_dict()}")
    else:
        pois_path = None
        print(f"⚠ Keine POIs zum Speichern")
    
    print("\n" + "=" * 60)
    print("✅ OSM-Datenerfassung abgeschlossen!")
    print("=" * 60)
    
    return landuse_path, buildings_path, pois_path


if __name__ == "__main__":
    acquire_osm_data()