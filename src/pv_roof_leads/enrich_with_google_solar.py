"""
Optimiertes Google Solar API Modul
Holt in einem Durchgang:
- Building Insights (Solar-Potenzial + Panel-Positionen)
- Data Layers (RGB-Luftbilder)
"""

import geopandas as gpd
import pandas as pd
from pathlib import Path
from tqdm import tqdm
import time
import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

from pv_roof_leads.paths import PROCESSED_DORTMUND, STAGING_DORTMUND, FINAL_DORTMUND
from pv_roof_leads.config import CRS_EXPORT


def fetch_building_insights(lat: float, lon: float, api_key: str) -> dict:
    """
    Ruft Building Insights von Google Solar API ab.
    Enthält: Solar-Potenzial + Panel-Positionen + Roof Segments
    """
    url = "https://solar.googleapis.com/v1/buildingInsights:findClosest"
    params = {
        "location.latitude": lat,
        "location.longitude": lon,
        "requiredQuality": "HIGH",
        "key": api_key
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        if response.status_code == 200:
            data = response.json()
            solar_potential = data.get('solarPotential', {})
            
            # Hole ALLE Panel-Positionen
            solar_panels = solar_potential.get('solarPanels', [])
            roof_segments = solar_potential.get('roofSegmentStats', [])
            
            return {
                'maxArrayPanelsCount': solar_potential.get('maxArrayPanelsCount'),
                'maxArrayAreaMeters2': solar_potential.get('maxArrayAreaMeters2'),
                'maxSunshineHoursPerYear': solar_potential.get('maxSunshineHoursPerYear'),
                'carbonOffsetFactorKgPerMwh': solar_potential.get('carbonOffsetFactorKgPerMwh'),
                'panelCapacityWatts': solar_potential.get('panelCapacityWatts', 400),
                'solarPanels': solar_panels,  # Liste mit center + orientation
                'roofSegmentStats': roof_segments,
                'panelCount': len(solar_panels)
            }
        return None
    except Exception as e:
        print(f"  ⚠️ Building Insights Fehler: {e}")
        return None


def fetch_data_layers(lat: float, lon: float, api_key: str, output_path: Path, radius_meters: int = 100) -> bool:
    """
    Ruft RGB Data Layer (Dachbild) von Google Solar API ab.
    """
    url = "https://solar.googleapis.com/v1/dataLayers:get"
    params = {
        "location.latitude": lat,
        "location.longitude": lon,
        "radiusMeters": radius_meters,
        "view": "IMAGERY_AND_ANNUAL_FLUX_LAYERS",
        "requiredQuality": "HIGH",
        "pixelSizeMeters": 0.5,
        "key": api_key
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        if response.status_code != 200:
            return False
        
        data = response.json()
        rgb_url = data.get('rgbUrl')
        
        if not rgb_url:
            return False
        
        # API-Key zur URL hinzufügen
        if 'key=' not in rgb_url:
            rgb_url = f"{rgb_url}&key={api_key}"
        
        # Bild herunterladen
        img_response = requests.get(rgb_url, timeout=30)
        if img_response.status_code == 200:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'wb') as f:
                f.write(img_response.content)
            return True
        
        return False
        
    except Exception as e:
        print(f"  ⚠️ Data Layers Fehler: {e}")
        return False


def select_buildings(n=None):
    """
    Lädt Gebäude ohne PV, optional Top N nach Fläche.
    
    Args:
        n: Anzahl der Gebäude (None = alle)
    
    Returns:
        GeoDataFrame mit Gebäuden
    """
    print("=" * 70)
    if n:
        print(f"🏢 Top {n} Dächer auswählen (nach Fläche)")
    else:
        print(f"🏢 ALLE Dächer laden")
    print("=" * 70)
    
    # Lade Gebäude ohne PV
    input_path = PROCESSED_DORTMUND / "buildings_processed_no_pv.geojson"
    print(f"\n📂 Lade: {input_path}")
    
    if not input_path.exists():
        raise FileNotFoundError(
            f"Gebäude ohne PV nicht gefunden!\n"
            f"Führe zuerst 'check_existing_pv.py' aus."
        )
    
    buildings = gpd.read_file(input_path)
    print(f"✓ {len(buildings):,} Gebäude ohne PV geladen")
    
    # Area prüfen
    if 'area_m2' not in buildings.columns:
        print("⚠️  Spalte 'area_m2' fehlt - berechne aus Geometrie...")
        buildings['area_m2'] = buildings.geometry.area
    
    # Nach Fläche sortieren
    buildings_sorted = buildings.sort_values('area_m2', ascending=False)
    
    # Top N oder alle
    if n:
        result = buildings_sorted.head(n).copy()
        print(f"\n📊 Top {n} ausgewählt:")
    else:
        result = buildings_sorted.copy()
        print(f"\n📊 Alle {len(result):,} Gebäude:")
    
    print(f"   Min. Fläche: {result['area_m2'].min():.0f} m²")
    print(f"   Max. Fläche: {result['area_m2'].max():.0f} m²")
    print(f"   Ø Fläche: {result['area_m2'].mean():.0f} m²")
    
    return result


def enrich_with_google_solar(buildings: gpd.GeoDataFrame, images_subdir: str = "luftbilder"):
    """
    Reichert Gebäude mit Google Solar API Daten an.
    Holt in EINEM Durchgang: Building Insights + RGB-Bilder
    
    Args:
        buildings: GeoDataFrame mit Gebäuden
        images_subdir: Unterordner für Bilder (Standard: "luftbilder")
        
    Returns:
        GeoDataFrame mit Solar-Daten und Panel-Positionen
    """
    print("\n" + "=" * 70)
    print("☀️ Google Solar API Integration (Optimiert)")
    print("=" * 70)
    
    # API Key prüfen
    api_key = os.getenv('GOOGLE_SOLAR_API_KEY')
    if not api_key:
        raise ValueError(
            "GOOGLE_SOLAR_API_KEY nicht in .env gefunden!\n"
            "Bitte setzen: GOOGLE_SOLAR_API_KEY=your-key-here"
        )
    
    print(f"\n✓ API Key gefunden")
    print(f"📊 Verarbeite {len(buildings)} Gebäude...")
    print(f"\n💰 Geschätzte Kosten:")
    print(f"   Building Insights: ${len(buildings) * 0.006:.2f} (${0.006}/Request)")
    print(f"   Data Layers:       ${len(buildings) * 0.015:.2f} (${0.015}/Request)")
    print(f"   GESAMT:            ${len(buildings) * 0.021:.2f}")
    
    # Koordinaten für API (WGS84)
    if buildings.crs != CRS_EXPORT:
        print(f"\n🔄 Transformiere: {buildings.crs} → {CRS_EXPORT}")
        buildings = buildings.to_crs(CRS_EXPORT)
    
    # Centroid berechnen
    centroids = buildings.geometry.centroid
    buildings['lat'] = centroids.y
    buildings['lon'] = centroids.x
    
    # Ausgabe-Verzeichnis für RGB-Bilder
    images_dir = FINAL_DORTMUND / images_subdir
    images_dir.mkdir(parents=True, exist_ok=True)
    
    # Solar-Daten sammeln
    solar_data = []
    failed_count = 0
    
    print(f"\n🚀 Starte API-Abfragen...")
    print(f"   Rate Limit: 1 Request/Sekunde")
    print(f"   Bilder in: {images_dir}")
    
    # Prüfe bereits heruntergeladene Bilder (für Resume)
    existing_images = set(f.name for f in images_dir.glob("building_*.jpg"))
    skipped_count = 0
    
    for idx, row in tqdm(buildings.iterrows(), total=len(buildings), desc="Google Solar API"):
        lat, lon = row['lat'], row['lon']
        image_filename = f"building_{idx}_{lat:.6f}_{lon:.6f}.jpg"
        
        # Skip wenn bereits heruntergeladen
        if image_filename in existing_images:
            # Markiere als erfolgreich (bereits vorhanden)
            solar_data.append({
                'solar_rgb_image': image_filename,
                'solar_api_success': True,
                'solar_skipped': True
            })
            skipped_count += 1
            continue
        
        try:
            # 1. Building Insights abrufen (enthält Panel-Positionen!)
            insights = fetch_building_insights(lat, lon, api_key)
            
            if insights:
                # 2. Data Layers (RGB-Bild) abrufen
                image_filename = f"building_{idx}_{lat:.6f}_{lon:.6f}.jpg"
                image_path = images_dir / image_filename
                
                rgb_success = fetch_data_layers(
                    lat, lon, api_key,
                    output_path=image_path,
                    radius_meters=100
                )
                
                # Daten zusammenstellen
                solar_panels_list = insights.get('solarPanels', [])
                roof_segments_list = insights.get('roofSegmentStats', [])
                
                solar_info = {
                    'solar_max_array_panels_count': insights.get('maxArrayPanelsCount'),
                    'solar_max_array_area_m2': insights.get('maxArrayAreaMeters2'),
                    'solar_max_sunshine_hours_per_year': insights.get('maxSunshineHoursPerYear'),
                    'solar_carbon_offset_kg_per_mwh': insights.get('carbonOffsetFactorKgPerMwh'),
                    'solar_panel_capacity_watts': insights.get('panelCapacityWatts', 400),
                    'solar_panels': json.dumps(solar_panels_list),  # JSON String
                    'solar_roof_segments': json.dumps(roof_segments_list),  # JSON String
                    'solar_has_existing_panels': len(solar_panels_list) > 0,
                    'solar_existing_panels_count': len(solar_panels_list),
                    'solar_rgb_image': image_filename if rgb_success else None,  # Nur Filename!
                    'solar_api_success': True
                }
            else:
                # API-Fehler
                solar_info = {
                    'solar_api_success': False
                }
                failed_count += 1
            
            solar_data.append(solar_info)
            
            # Rate Limiting: 1 Request/Sekunde
            time.sleep(1.1)
            
        except Exception as e:
            print(f"\n⚠️  Fehler bei Gebäude {idx}: {e}")
            solar_data.append({'solar_api_success': False})
            failed_count += 1
            time.sleep(1.1)
    
    # Solar-Daten zu GeoDataFrame hinzufügen
    solar_df = pd.DataFrame(solar_data)
    buildings_enriched = pd.concat([buildings.reset_index(drop=True), solar_df], axis=1)
    
    # Als GeoDataFrame
    buildings_enriched = gpd.GeoDataFrame(buildings_enriched, geometry='geometry', crs=buildings.crs)
    
    print(f"\n" + "=" * 70)
    print(f"✅ Google Solar API abgeschlossen")
    print(f"=" * 70)
    print(f"   Erfolgreich: {len(buildings) - failed_count}/{len(buildings)}")
    print(f"   Übersprungen (bereits vorhanden): {skipped_count}")
    print(f"   Fehlgeschlagen: {failed_count}")
    print(f"   RGB-Bilder: {images_dir}")
    
    return buildings_enriched


def main():
    """Hauptfunktion: Alle Gebäude mit Google Solar API anreichern"""
    
    # 1. ALLE Gebäude laden (n=None für alle)
    buildings = select_buildings(n=None)
    
    # 2. Mit Google Solar API anreichern (in einem Durchgang!)
    buildings_enriched = enrich_with_google_solar(buildings, images_subdir="luftbilder")
    
    # 3. Speichern
    output_path = FINAL_DORTMUND / "all_buildings_with_solar.geojson"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"\n💾 Speichere Ergebnis...")
    buildings_enriched.to_file(output_path, driver="GeoJSON")
    
    print(f"✅ Gespeichert: {output_path}")
    print(f"\n📊 Statistik:")
    
    total = len(buildings_enriched)
    successful = buildings_enriched['solar_api_success'].sum()
    
    print(f"   API-Erfolg: {successful}/{total}")
    
    if successful > 0:
        with_panels = buildings_enriched['solar_has_existing_panels'].sum()
        avg_panels = buildings_enriched[buildings_enriched['solar_api_success']]['solar_max_array_panels_count'].mean()
        avg_sunshine = buildings_enriched[buildings_enriched['solar_api_success']]['solar_max_sunshine_hours_per_year'].mean()
        
        print(f"   Mit Panel-Daten: {with_panels}")
        print(f"   Ø Max. Panels: {avg_panels:.0f}")
        print(f"   Ø Sonnenstunden/Jahr: {avg_sunshine:.0f}h")
    
    print(f"\n🎉 Fertig! Alle {total} Gebäude mit Solar-Daten bereit.")
    print(f"   Bilder in: {FINAL_DORTMUND / 'luftbilder'}")


if __name__ == "__main__":
    main()
