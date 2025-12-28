"""
Erweiterte Google Solar API Abfrage
Holt ALLE verfügbaren Daten für maximalen Geschäftswert:
- Panel-Positionen pro Segment
- Verschattungsanalyse
- Verschiedene Anlagenkonfigurationen
- Wirtschaftlichkeitsberechnungen (falls verfügbar)
"""

import geopandas as gpd
import json
import numpy as np
import pandas as pd
from pathlib import Path
from tqdm import tqdm
import os
from datetime import datetime
from dotenv import load_dotenv

from .config import PROCESSED_DORTMUND, FINAL_DORTMUND, CRS_EXPORT
from .google_solar_api import GoogleSolarAPI


class ExtendedJSONEncoder(json.JSONEncoder):
    """JSON Encoder der numpy/pandas-Typen korrekt serialisiert."""
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, np.bool_):
            return bool(obj)
        if isinstance(obj, (pd.Timestamp, datetime)):
            return obj.isoformat()
        if pd.isna(obj):
            return None
        return super().default(obj)

load_dotenv()


def fetch_extended_solar_data(
    max_buildings: int = None,
    force_refresh: bool = False
):
    """
    Holt erweiterte Solar-Daten für alle Gebäude.
    
    Args:
        max_buildings: Optional - Begrenze Anzahl (für Tests)
        force_refresh: True = Cache ignorieren, neu abrufen
    """
    print("\n" + "=" * 70)
    print("🌞 ERWEITERTE GOOGLE SOLAR API ABFRAGE")
    print("=" * 70)
    
    # API Key prüfen
    api_key = os.environ.get("GOOGLE_SOLAR_API_KEY")
    if not api_key:
        print("❌ FEHLER: GOOGLE_SOLAR_API_KEY nicht gesetzt!")
        print("\nSetze die Variable:")
        print('  $env:GOOGLE_SOLAR_API_KEY="dein-api-key"')
        return None
    
    # Cache-Verzeichnis
    cache_dir = PROCESSED_DORTMUND / "google_solar_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    print(f"📁 Cache-Verzeichnis: {cache_dir}")
    
    # API Client initialisieren
    client = GoogleSolarAPI(api_key, cache_dir=str(cache_dir))
    
    # Gebäude laden (mit bestehenden PV-Infos)
    input_file = PROCESSED_DORTMUND / "buildings_processed_with_pv_info.geojson"
    if not input_file.exists():
        input_file = PROCESSED_DORTMUND / "buildings_processed.geojson"
    
    print(f"\n📂 Lade Gebäude: {input_file}")
    buildings_gdf = gpd.read_file(input_file)
    print(f"   {len(buildings_gdf):,} Gebäude geladen")
    
    # In WGS84 transformieren für API
    if buildings_gdf.crs != CRS_EXPORT:
        buildings_gdf = buildings_gdf.to_crs(CRS_EXPORT)
    
    # Begrenzung für Tests
    if max_buildings:
        buildings_gdf = buildings_gdf.head(max_buildings)
        print(f"   ⚠️ Begrenzt auf {max_buildings} Gebäude (Test-Modus)")
    
    # Statistiken
    total = len(buildings_gdf)
    success_count = 0
    error_count = 0
    cached_count = 0
    
    # Konvertiere problematische Spaltentypen vor der JSON-Serialisierung
    for col in buildings_gdf.columns:
        if col == 'geometry':
            continue
        # Timestamps zu Strings konvertieren
        if buildings_gdf[col].dtype == 'datetime64[ns]' or buildings_gdf[col].apply(lambda x: isinstance(x, (pd.Timestamp, datetime))).any():
            buildings_gdf[col] = buildings_gdf[col].astype(str)
        # NaN zu None
        buildings_gdf[col] = buildings_gdf[col].where(pd.notna(buildings_gdf[col]), None)
    
    # Features als Liste für Verarbeitung
    features = json.loads(buildings_gdf.to_json())["features"]
    
    print(f"\n🔄 Starte API-Abfrage für {total:,} Gebäude...")
    print("   (Cache wird automatisch verwendet)")
    print()
    
    enriched_features = []
    
    # Fortschrittsanzeige
    for feature in tqdm(features, desc="Gebäude verarbeiten"):
        building_id = str(feature.get("properties", {}).get("id", "unknown"))
        
        # Prüfe ob bereits im Cache
        cache_file = cache_dir / f"{building_id}.json"
        if cache_file.exists() and not force_refresh:
            cached_count += 1
        
        try:
            # API-Aufruf (nutzt Cache automatisch)
            enriched = client.enrich_building_with_solar_data(feature)
            
            if enriched["properties"].get("google_solar_available"):
                success_count += 1
            
            enriched_features.append(enriched)
            
        except Exception as e:
            error_count += 1
            feature["properties"]["google_solar_available"] = False
            feature["properties"]["google_solar_error"] = str(e)
            enriched_features.append(feature)
    
    # GeoDataFrame erstellen
    enriched_gdf = gpd.GeoDataFrame.from_features(enriched_features, crs=CRS_EXPORT)
    
    # Speichern
    output_file = PROCESSED_DORTMUND / "buildings_with_google_solar.geojson"
    enriched_gdf.to_file(output_file, driver="GeoJSON")
    
    # Auch erweiterte Segment-Daten separat speichern
    segments_data = {}
    for feature in enriched_features:
        props = feature.get("properties", {})
        building_id = str(props.get("id", ""))
        if props.get("google_solar_segments"):
            segments_data[building_id] = {
                "segments": props.get("google_solar_segments", []),
                "imageryQuality": props.get("google_solar_data_quality", ""),
                "usable_pct": props.get("google_solar_usable_roof_pct", 0),
                "total_panels": props.get("google_solar_panels_max", 0),
                "configs": props.get("google_solar_configs", []),
            }
    
    segments_file = FINAL_DORTMUND / "roof_segments_extended.json"
    with open(segments_file, 'w', encoding='utf-8') as f:
        json.dump(segments_data, f, ensure_ascii=False, indent=2, cls=ExtendedJSONEncoder)
    
    # Zusammenfassung
    print("\n" + "=" * 70)
    print("📊 ZUSAMMENFASSUNG")
    print("=" * 70)
    print(f"   Gesamt verarbeitet:  {total:,}")
    print(f"   ✅ Mit Solar-Daten:   {success_count:,} ({success_count/total*100:.1f}%)")
    print(f"   📁 Aus Cache:         {cached_count:,}")
    print(f"   ❌ Fehler/Keine Daten: {error_count + (total - success_count - error_count):,}")
    print()
    print(f"   💾 Gespeichert: {output_file}")
    print(f"   💾 Segmente:    {segments_file}")
    print("=" * 70)
    
    return enriched_gdf


def main():
    """Hauptfunktion."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Erweiterte Google Solar API Abfrage")
    parser.add_argument("--max", type=int, help="Max. Anzahl Gebäude (für Tests)")
    parser.add_argument("--refresh", action="store_true", help="Cache ignorieren")
    args = parser.parse_args()
    
    fetch_extended_solar_data(
        max_buildings=args.max,
        force_refresh=args.refresh
    )


if __name__ == "__main__":
    main()
