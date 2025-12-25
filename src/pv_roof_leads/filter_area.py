"""
Flächenfilter: Filtert Gebäude nach Mindest-Dachfläche (≥500m²)
Fügt Spalte footprint_area_m2 hinzu
"""

import geopandas as gpd
from pathlib import Path
import argparse

from pv_roof_leads.paths import STAGING_DORTMUND, CURATED_DORTMUND
from pv_roof_leads.config import MIN_FOOTPRINT_AREA_M2, CRS_INTERNAL

def filter_by_area(min_area_m2: float = MIN_FOOTPRINT_AREA_M2) -> Path:
    """ Filtert nach mindesfläche und fügt footprint_area_m2 Spalte hinzu"""
    
    # Geoparquet file ladem
    input_path = STAGING_DORTMUND / "buildings.geoparquet"
    print(f" Lade Gebäude von {input_path}")
    gdf = gpd.read_parquet(input_path)
    print(f"{len(gdf)} Gebäude geladen")
    #print(f"CRS {gdf.crs}")
    
    # Prüfen oc crs Metrisch ist
    if gdf.crs != CRS_INTERNAL:
        print(f"CRS ist nicht metrisch! Reprojiziere nach {CRS_INTERNAL}")
        gdf = gdf.to_crs(CRS_INTERNAL)
    else:
        print(f"CRS ist metrisch ({CRS_INTERNAL})")
        
    # Dachfläche berechnen in m2
    print("Berechne Gebäudeflächen ...")
    gdf["footprint_area_m2"] = gdf.geometry.area
    print("Flächenberechnung abgeschlossen.")
    print(f"Min: {gdf["footprint_area_m2"].min():.1f} m2")
    print(f"Max: {gdf["footprint_area_m2"].max():.1f} m2")
    
    # Filtern nach mindesfläche
    print(f"Nur Gebäude >= {min_area_m2} m²...")
    vor_filter = len(gdf)
    gdf = gdf[gdf['footprint_area_m2'] >= min_area_m2]
    nach_filter = len(gdf)
    
    ausgeschlossen = vor_filter - nach_filter
    print(f"{nach_filter} Gebäude behalten")
    print(f"{ausgeschlossen} Gebäude ausgeschlossen ({ausgeschlossen/vor_filter*100:.1f}%)")
    
    # Als Parquet speichern - ohne Geometrien
    output_path = CURATED_DORTMUND / "candidates_area.parquet"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"Speichere nach {output_path}")
    gdf_output = gdf.drop(columns=['geometry'])
    gdf_output.to_parquet(output_path)   
    
    file_size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"Fertig! {nach_filter} Kandidaten, {file_size_mb:.1f} MB gespeichert")
    
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
    
        