"""
Flächenfilter: Filtert ALKIS-Gebäude nach Mindest-Dachfläche (≥500m²)
OPTIMIERT: Wird VOR process_data.py ausgeführt für schnellere Joins
"""

import geopandas as gpd
from pathlib import Path
import argparse

from pv_roof_leads.paths import STAGING_DORTMUND, PROCESSED_DORTMUND
from pv_roof_leads.config import MIN_FOOTPRINT_AREA_M2, CRS_INTERNAL

def filter_by_area(min_area_m2: float = MIN_FOOTPRINT_AREA_M2) -> Path:
    """
    Filtert ALKIS-Gebäude nach Mindestfläche (≥500m²).
    WICHTIG: Muss VOR process_data.py ausgeführt werden!
    """
    
    # ALKIS-Gebäude laden (normalisiert)
    input_path = STAGING_DORTMUND / "buildings.geoparquet"
    print(f"📂 Lade ALKIS-Gebäude von {input_path}")
    
    if not input_path.exists():
        raise FileNotFoundError(f"ALKIS-Daten nicht gefunden! Führe zuerst 'normalize_alkis.py' aus.")
    
    gdf = gpd.read_parquet(input_path)
    print(f"✓ {len(gdf):,} ALKIS-Gebäude geladen")
    
    # Prüfen ob CRS metrisch ist
    if gdf.crs != CRS_INTERNAL:
        print(f"⚠️  CRS ist nicht metrisch! Reprojiziere nach {CRS_INTERNAL}")
        gdf = gdf.to_crs(CRS_INTERNAL)
    else:
        print(f"✓ CRS ist metrisch ({CRS_INTERNAL})")
    
    # Fläche berechnen (falls nicht vorhanden)
    if 'area_m2' not in gdf.columns:
        print("🔢 Berechne Gebäudeflächen aus Geometrie...")
        gdf['area_m2'] = gdf.geometry.area
    
    print(f"\n📊 Flächenverteilung:")
    print(f"   Min: {gdf['area_m2'].min():.1f} m²")
    print(f"   Max: {gdf['area_m2'].max():.1f} m²")
    print(f"   Median: {gdf['area_m2'].median():.1f} m²")
    
    # Filtern nach Mindestfläche
    print(f"\n🎯 Filtere Gebäude >= {min_area_m2} m²...")
    vor_filter = len(gdf)
    gdf = gdf[gdf['area_m2'] >= min_area_m2].copy()
    nach_filter = len(gdf)
    
    ausgeschlossen = vor_filter - nach_filter
    print(f"✓ {nach_filter:,} Gebäude behalten")
    print(f"✗ {ausgeschlossen:,} Gebäude ausgeschlossen ({ausgeschlossen/vor_filter*100:.1f}%)")
    
    # Index zurücksetzen für spätere Joins
    gdf = gdf.reset_index(drop=True)
    
    # Als GeoParquet speichern (mit Geometrie für process_data.py)
    output_path = STAGING_DORTMUND / "buildings_filtered_area.geoparquet"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"\n💾 Speichere gefilterte Gebäude...")
    gdf.to_parquet(output_path)
    
    file_size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"✅ Gespeichert: {output_path}")
    print(f"   {nach_filter:,} Gebäude, {file_size_mb:.1f} MB")
    print(f"\n🚀 Bereit für process_data.py (Joins mit OSM-Daten)")
    
    return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Filtert Gebäude nach Mindest-Dachfläche"
    )
    parser.add_argument(
        "--min-area",
        type=float,
        default=MIN_FOOTPRINT_AREA_M2,
        help=f"Mindestfläche in m² (Standard: {MIN_FOOTPRINT_AREA_M2})"
    )
    
    args = parser.parse_args()
    filter_by_area(min_area_m2=args.min_area)
    
        