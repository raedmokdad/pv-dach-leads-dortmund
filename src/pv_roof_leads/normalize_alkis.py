"""
ALKIS-Normalisierung: GeoJSON → GeoParquet mit CRS EPSG:25832
"""

import geopandas as gpd
from pathlib import Path
import argparse

from pv_roof_leads.paths import RAW_DORTMUND, STAGING_DORTMUND
from pv_roof_leads.config import CRS_INTERNAL

def normalize_alkis(input_path: Path) -> Path:
    """Normalisiert ALKIS-Daten von GeoJSON zu GeoParquet mit definiertem CRS.

    Args:
        input_path (Path): Pfad zur Eingabe-GeoJSON-Datei.
        output_path (Path): Pfad zur Ausgabe-GeoParquet-Datei.
    """
    # GeoJSON-Datei
    gdf = gpd.read_file(input_path)
    print(f" {len(gdf)} Gebäude laden")
    print(f" CRS : {gdf.crs}")
    
    # Prüfen
    if gdf.crs != CRS_INTERNAL:
        print(f" Reprojiziere von {gdf.crs} nach {CRS_INTERNAL}")
        gdf = gdf.to_crs(CRS_INTERNAL)
        
    # Nur die wichtige Spalten behalten
    columns_to_keep = ['geometry']
    optional_columns = ['funktion', 'lagebeztxt', 'gebnutzbez', 'anzahlgs']
    
    for col in optional_columns:
        if col in gdf.columns:
            columns_to_keep.append(col)
            
    gdf = gdf[columns_to_keep]
    print(f" {len(columns_to_keep)} Spalten behalten: {columns_to_keep}")
    # Geometrien bereinigen
    gdf['geometry'] = gdf.geometry.make_valid()
    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty].copy()
    print(f" {len(gdf)} Gebäuden mit gültigen geometrien")
    
    # Als GeoParquet speichern
    output_path = STAGING_DORTMUND / "buildings.geoparquet"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Speichere nach {output_path}")
    gdf.to_parquet(output_path)

    file_size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"Fertig! {file_size_mb:.1f} MB gespeichert")

    return output_path

     
    
    
    
if __name__ == "__main__":
    pfad = RAW_DORTMUND / "alkis_buildings" / "20251222" / "liegenschaftskataster-gebaude-bauwerke.geojson"
    normalize_alkis(pfad)

   