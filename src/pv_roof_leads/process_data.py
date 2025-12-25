"""
Task 4.2: Data Processing
- Gebäude filtern (≥ 500m²)
- Flächen berechnen
- Landuse-Zonen zuordnen (spatial join)
"""


import geopandas as gpd
from pathlib import Path

from pv_roof_leads.config import MIN_FOOTPRINT_AREA_M2, CRS_INTERNAL
from pv_roof_leads.paths import RAW_DORTMUND, PROCESSED_DORTMUND

def load_latest_osm_data() -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """
    Lädt die neuesten OSM-Daten aus dem RAW-Ordner.
    
    Returns:
        tuple: (landuse_zones, buildings, pois)
    """
    # finde neusten Ordner
    osm_dir = RAW_DORTMUND / "osm"
    latest_dir = sorted(osm_dir.glob("*"))[-1]
    
    print(f"Lade Daten aus: {latest_dir}")
    
    zones = gpd.read_file(latest_dir / "landuse_zones.geojson")
    buildings = gpd.read_file(latest_dir / "buildings.geojson")
    
    # POIs nur laden wenn vorhanden
    pois_path = latest_dir / "pois.geojson"
    if pois_path.exists():
        pois = gpd.read_file(pois_path)
    else:
        pois = gpd.GeoDataFrame()
    
    print(f"{len(zones)} Zonen, {len(buildings)} Gebäude, {len(pois)} POIs")
    return zones, buildings, pois


def calculate_foot_print_area(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Berechnet Gebäudefläche in m² (in CRS_INTERNAL).
    
    Args:
        gdf: GeoDataFrame mit Gebäuden
        
    Returns:
        GeoDataFrame mit neuer Spalte 'footprint_area_m2'
    """
    print("Berechne Gebäudeflächen ... ")
    gdf['footprint_area_m2'] = gdf.geometry.area
    print(f"Flächen: {gdf['footprint_area_m2'].min():.1f} - {gdf['footprint_area_m2'].max():.1f} m²")
    return gdf

def filter_by_area(gdf: gpd.GeoDataFrame, min_area: float = MIN_FOOTPRINT_AREA_M2) -> gpd.GeoDataFrame:
    """
    Filtert Gebäude nach Mindestfläche (≥ 500m² aus config).
    
    Args:
        gdf: GeoDataFrame mit 'footprint_area_m2'
        min_area: Mindestfläche in m²
        
    Returns:
        Gefiltertes GeoDataFrame
    """
    before = len(gdf)
    gdf = gdf[gdf['footprint_area_m2'] >= min_area].copy()
    
    # WICHTIG: Index zurücksetzen für spatial join
    gdf = gdf.reset_index(drop=True)
    
    print(f"✓ Filter: {before} → {len(gdf)} Gebäude (≥ {min_area} m²)")
    return gdf

def assign_landuse_zone(buildings: gpd.GeoDataFrame, zones: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Ordnet jedem Gebäude die passende Landuse-Zone zu (spatial join).
    
    Args:
        buildings: GeoDataFrame mit Gebäuden (in CRS_INTERNAL)
        zones: GeoDataFrame mit Landuse-Zonen (industrial/commercial)
        
    Returns:
        GeoDataFrame mit neuer Spalte 'landuse'
    """
    print("⏳ Spatial Join: Gebäude → Landuse-Zonen...")
    
    # CRS angleichen: Zones ins interne CRS transformieren
    if zones.crs != CRS_INTERNAL:
        print(f"   Transformiere Zonen: {zones.crs} → {CRS_INTERNAL}")
        zones = zones.to_crs(CRS_INTERNAL)
    
    # Gebäude haben bereits 'landuse' Spalte aus OSM - umbenennen
    if 'landuse' in buildings.columns:
        buildings = buildings.rename(columns={'landuse': 'landuse_osm'})
    
    # Nur relevante Spalten aus Zonen
    zones_simple = zones[['landuse', 'geometry']].copy()
    
    # Spatial Join (intersects = Gebäude überschneidet sich mit Zone)
    # 'within' war zu strikt - Gebäude am Rand wurden nicht gefunden
    joined = gpd.sjoin(buildings, zones_simple, how='left', predicate='intersects')
    
    # Bei mehreren Matches: erste Zone nehmen
    if 'index_right' in joined.columns:
        joined = joined[~joined.index.duplicated(keep='first')] 
        joined = joined.drop(columns=['index_right'])
    
    # Sicherstellen dass 'landuse' Spalte existiert (auch wenn leer)
    if 'landuse' not in joined.columns:
        print("⚠️  Keine Gebäude in Zonen gefunden - füge leere 'landuse' Spalte hinzu")
        joined['landuse'] = None
    
    # Statistik
    in_zone = joined['landuse'].notna().sum()
    print(f"✓ {in_zone}/{len(joined)} Gebäude in industrial/commercial Zonen")
    
    return joined


def assign_cadastral_data(buildings: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Ordnet Gebäuden Flurstück-Informationen aus dem Liegenschaftskataster zu.
    Ermöglicht später Eigentümer-Kontakt.
    
    Args:
        buildings: GeoDataFrame mit Gebäuden
        
    Returns:
        GeoDataFrame mit Flurstück-IDs und Eigentümer-Infos
    """
    print("⏳ Lade Liegenschaftskataster...")
    
    # Suche neueste Kataster-Datei
    cadastral_dir = RAW_DORTMUND / "alkis_buildings" 
    cadastral_files = list(cadastral_dir.glob("**/liegenschaftskataster-gebaude-bauwerke.geojson"))
     
    if not cadastral_files:
        print("⚠️  Kein Liegenschaftskataster gefunden - überspringe Eigentümer-Zuordnung")
        buildings['flurstueck_id'] = None
        buildings['eigentuemer'] = None
        buildings['baujahr'] = None
        return buildings
    
    # Lade neueste Kataster-Datei
    cadastral_path = sorted(cadastral_files)[-1]
    print(f"📂 Nutze: {cadastral_path.name}")
    
    cadastral = gpd.read_file(cadastral_path)
    
    # Nur relevante Spalten (anpassen je nach Datensatz!)
    relevant_cols = ['geometry']
    if 'flurstueck_id' in cadastral.columns:
        relevant_cols.append('flurstueck_id')
    if 'eigentuemer' in cadastral.columns:
        relevant_cols.append('eigentuemer')
    if 'baujahr' in cadastral.columns:
        relevant_cols.append('baujahr')
    
    cadastral_simple = cadastral[relevant_cols].copy()
    # NEUE ZEILEN: Fläche aus Kataster-Geometrie berechnen
    print("⏳ Berechne Kataster-Gebäudeflächen...")
    cadastral_simple['cadastral_area_m2'] = cadastral_simple.geometry.area
    relevant_cols.append('cadastral_area_m2')
    
    # Spatial Join: OSM-Gebäude → Kataster-Flurstücke
    print(f"⏳ Spatial Join: {len(buildings)} Gebäude → {len(cadastral_simple)} Flurstücke...")
    print("   ⏰ Geschätzte Dauer: 5-10 Minuten (CPU-intensiv)")
    joined = gpd.sjoin(buildings, cadastral_simple, how='left', predicate='intersects')
    
    # Bei mehreren Matches: erstes Flurstück nehmen
    if 'index_right' in joined.columns:
        joined = joined[~joined.index.duplicated(keep='first')]  # <- FIXED
        joined = joined.drop(columns=['index_right'])
    
    # Sicherstellen dass Spalten existieren (auch wenn keine Matches)
    if 'flurstueck_id' not in joined.columns:
        joined['flurstueck_id'] = None
    if 'eigentuemer' not in joined.columns:
        joined['eigentuemer'] = None
    if 'baujahr' not in joined.columns:
        joined['baujahr'] = None
    
    # Statistik
    with_cadastral = joined['flurstueck_id'].notna().sum()
    print(f"✓ {with_cadastral}/{len(joined)} Gebäude mit Flurstück-Info")
    
    return joined

def process_osm_data() -> Path:
    """
    Hauptfunktion Task 4.2: Lädt OSM-Daten, filtert, berechnet, verknüpft.
    
    Returns:
        Path: Pfad zur verarbeiteten buildings.geojson
    """
    print("=" * 60)
    print("📊 Task 4.2: Data Processing")
    print("=" * 60)
    
    # 1. Daten laden
    zones, buildings, pois = load_latest_osm_data()
    
    # 2. Flächen berechnen
    buildings = calculate_foot_print_area(buildings)
    
    # 3. Nach Mindestfläche filtern (≥ 500m²)
    buildings = filter_by_area(buildings)
    
    # 4. Landuse-Zone zuordnen
    buildings = assign_landuse_zone(buildings, zones)
    
    # 5. Flurstück-Daten zuordnen (für Eigentümer-Kontakt)  
    buildings = assign_cadastral_data(buildings)              
    
    # 6. Speichern  
    output_path = PROCESSED_DORTMUND / "buildings_processed.geojson"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    buildings.to_file(output_path, driver="GeoJSON")
    
    print(f"\n✅ Processing abgeschlossen: {output_path}")
    print(f"   {len(buildings)} Gebäude bereit für Scoring")
    print(f"   In Zonen: {buildings['landuse'].notna().sum()}")
    
    return output_path

if __name__ == "__main__":
    process_osm_data()
    
