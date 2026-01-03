"""
Task 4.2: Data Processing
- Gebäude filtern (≥ 500m²)
- Flächen berechnen
- Landuse-Zonen zuordnen (spatial join)
"""


import geopandas as gpd
from pathlib import Path

from pv_roof_leads.config import MIN_FOOTPRINT_AREA_M2, CRS_INTERNAL
from pv_roof_leads.paths import RAW_DORTMUND, PROCESSED_DORTMUND, STAGING_DORTMUND

def load_filtered_alkis_buildings() -> gpd.GeoDataFrame:
    """
    Lädt gefilterte ALKIS-Gebäude (≥500m²) aus filter_area.py.
    
    Returns:
        GeoDataFrame mit gefilterten Gebäuden
    """
    buildings_path = STAGING_DORTMUND / "buildings_filtered_area.geoparquet"
    
    if not buildings_path.exists():
        raise FileNotFoundError(
            f"Gefilterte Gebäude nicht gefunden: {buildings_path}\n"
            f"Führe zuerst 'filter_area.py' aus!"
        )
    
    print(f"📂 Lade gefilterte ALKIS-Gebäude: {buildings_path}")
    buildings = gpd.read_parquet(buildings_path)
    print(f"✓ {len(buildings):,} Gebäude geladen (bereits nach Fläche gefiltert)")
    
    return buildings


def load_latest_osm_data() -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """
    Lädt die neuesten OSM-Daten (Zonen und Gebäude) aus dem RAW-Ordner.
    
    Returns:
        tuple: (landuse_zones, osm_buildings)
    """
    # finde neusten Ordner
    osm_dir = RAW_DORTMUND / "osm"
    latest_dir = sorted(osm_dir.glob("*"))[-1]
    
    print(f"📂 Lade OSM-Daten aus: {latest_dir}")
    
    zones = gpd.read_file(latest_dir / "landuse_zones.geojson")
    osm_buildings = gpd.read_file(latest_dir / "buildings.geojson")
    
    print(f"✓ {len(zones)} Zonen, {len(osm_buildings):,} OSM-Gebäude")
    return zones, osm_buildings


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


def enrich_with_osm_attributes(alkis_buildings: gpd.GeoDataFrame, osm_buildings: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Fügt OSM-Gebäude-Attribute zu ALKIS-Gebäuden hinzu (für filter_target.py).
    Matched ALKIS ← OSM per Spatial Join (intersects).
    
    Args:
        alkis_buildings: GeoDataFrame mit ALKIS-Gebäuden (präzise Geometrien)
        osm_buildings: GeoDataFrame mit OSM-Gebäuden (mit POI-Attributen)
        
    Returns:
        GeoDataFrame mit amenity, leisure, shop, tourism, building Spalten
    """
    print("⏳ Reichere ALKIS-Gebäude mit OSM-Attributen an...")
    print(f"   {len(alkis_buildings):,} ALKIS ← {len(osm_buildings):,} OSM-Gebäude")
    
    # CRS angleichen
    if osm_buildings.crs != alkis_buildings.crs:
        print(f"   Transformiere OSM: {osm_buildings.crs} → {alkis_buildings.crs}")
        osm_buildings = osm_buildings.to_crs(alkis_buildings.crs)
    
    # OSM-Attribute die wir brauchen
    osm_cols = ['amenity', 'leisure', 'shop', 'tourism', 'building']
    available_cols = [c for c in osm_cols if c in osm_buildings.columns]
    
    if not available_cols:
        print("⚠️  Keine OSM-Attribute gefunden - füge leere Spalten hinzu")
        for col in osm_cols:
            alkis_buildings[col] = None
        return alkis_buildings
    
    print(f"   Verfügbare OSM-Attribute: {available_cols}")
    
    # Nur relevante OSM-Spalten + Geometrie
    osm_simple = osm_buildings[['geometry'] + available_cols].copy()
    
    # WICHTIG: Original-Index speichern vor Join
    alkis_buildings['_original_idx'] = alkis_buildings.index
    
    # Spatial Join: ALKIS ← OSM (left join, damit alle ALKIS behalten werden)
    joined = gpd.sjoin(alkis_buildings, osm_simple, how='left', predicate='intersects', rsuffix='_osm')
    
    # Statistik VOR Duplikat-Entfernung
    before_dedup = len(joined)
    total_matches = joined['index_right'].notna().sum() if 'index_right' in joined.columns else 0
    
    # Bei mehreren OSM-Matches pro ALKIS: erstes nehmen (basierend auf Original-Index)
    joined = joined.sort_values('_original_idx')  # Sortieren für konsistente Reihenfolge
    joined = joined.drop_duplicates(subset='_original_idx', keep='first')
    joined = joined.drop(columns=['_original_idx'])
    
    if 'index_right' in joined.columns:
        joined = joined.drop(columns=['index_right'])
    
    # Statistik NACH Duplikat-Entfernung
    after_dedup = len(joined)
    duplicates_removed = before_dedup - after_dedup
    
    print(f"   ✓ {total_matches:,} ALKIS-OSM Übereinstimmungen")
    print(f"   ✓ {duplicates_removed:,} Duplikate entfernt → {after_dedup:,} finale Gebäude")
    
    # Fehlende Spalten mit None füllen
    for col in osm_cols:
        if col not in joined.columns:
            joined[col] = None
    
    # Statistik pro Attribut
    print(f"   📊 Angereicherte Gebäude:")
    for col in osm_cols:
        if col in joined.columns:
            count = joined[col].notna().sum()
            pct = count / len(joined) * 100 if len(joined) > 0 else 0
            print(f"      • {col}: {count:,} ({pct:.1f}%)")
    
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
        joined = joined[~joined.index.duplicated(keep='first')]  
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
    Hauptfunktion Task 4.2: Joined gefilterte ALKIS-Gebäude mit OSM-Daten.
    OPTIMIERT: Arbeitet nur mit bereits gefilterten Gebäuden (≥500m²)
    
    Returns:
        Path: Pfad zur verarbeiteten buildings.geojson
    """
    print("=" * 60)
    print("📊 Task 4.2: Data Processing (OPTIMIERT)")
    print("=" * 60)
    
    # 1. Gefilterte ALKIS-Gebäude laden (≥500m², aus filter_area.py)
    buildings = load_filtered_alkis_buildings()
    
    # 2. OSM-Daten laden (Zonen und Gebäude)
    zones, osm_buildings = load_latest_osm_data()
    
    # 3. Landuse-Zone zuordnen
    buildings = assign_landuse_zone(buildings, zones)
    
    # 4. OSM-Gebäude-Attribute hinzufügen (für filter_target.py)
    buildings = enrich_with_osm_attributes(buildings, osm_buildings)
    
    # 5. Speichern  
    output_path = PROCESSED_DORTMUND / "buildings_processed.geojson"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    buildings.to_file(output_path, driver="GeoJSON")
    
    print(f"\n✅ Processing abgeschlossen: {output_path}")
    print(f"   {len(buildings):,} Gebäude bereit für Zielgruppenfilter")
    print(f"   In Zonen: {buildings['landuse'].notna().sum()}")
    
    return output_path

if __name__ == "__main__":
    process_osm_data()
    
