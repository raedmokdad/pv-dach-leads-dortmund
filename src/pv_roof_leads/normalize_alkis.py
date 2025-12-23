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


def find_latest_alkis_file() -> Path:
    """Findet die neueste ALKIS-Datei in raw/dortmund/alkis_buildings/"""
    alkis_dir = RAW_DORTMUND / "alkis_buildings"
    
    if not alkis_dir.exists():
        raise FileNotFoundError(f"Kein ALKIS-Ordner gefunden: {alkis_dir}")
    
    # Alle GeoJSON/GPKG/SHP Dateien finden
    files = []
    for pattern in ['**/*.geojson', '**/*.gpkg', '**/*.shp']:
        files.extend(alkis_dir.glob(pattern))
    
    if not files:
        raise FileNotFoundError(f"Keine ALKIS-Dateien in {alkis_dir}")
    
    # Neueste Datei (nach Änderungsdatum)
    latest = max(files, key=lambda p: p.stat().st_mtime)
    return latest
        



     
    
    
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="ALKIS-Daten normalisieren (GeoJSON → GeoParquet)"
    )
    parser.add_argument(
        "--input",
        type=Path,
        help="Pfad zur ALKIS-Datei (falls nicht angegeben: automatisch neueste)"
    )
    
    args = parser.parse_args()
    
    # Input-Datei bestimmen
    if args.input:
        input_path = args.input
    else:
        print("🔍 Suche neueste ALKIS-Datei...")
        input_path = find_latest_alkis_file()
        print(f"   Gefunden: {input_path}")
    
    # Normalisierung ausführen
    normalize_alkis(input_path)

   