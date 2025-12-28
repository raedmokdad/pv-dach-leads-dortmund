"""
Google Solar API Integration
Reichert Top-Leads mit Solarpotenzial-Daten an (Dachneigung, Ausrichtung, Sonnenstunden).
"""

import geopandas as gpd
import pandas as pd
import requests
from pathlib import Path
from tqdm import tqdm
from time import sleep
import sys

from .config import (
    STAGING_DORTMUND,
    CRS_EXPORT,
    GOOGLE_SOLAR_API_KEY,
    SOLAR_API_RATE_LIMIT_DELAY
)
from .paths import ensure_dirs


def get_solar_potential(lat: float, lon: float, api_key: str) -> dict:
    """
    Ruft Solarpotenzial für Gebäude ab via Google Solar API.
    
    Args:
        lat: Breitengrad (WGS84)
        lon: Längengrad (WGS84)
        api_key: Google Solar API Key
    
    Returns:
        Dict mit relevanten Solar-Metriken oder None bei Fehler
    
    API Dokumentation:
        https://developers.google.com/maps/documentation/solar
    """
    if not api_key:
        raise ValueError(
            "GOOGLE_SOLAR_API_KEY nicht gesetzt!\n"
            "Bitte setzen: export GOOGLE_SOLAR_API_KEY='your-key-here'\n"
            "API Key erstellen: https://console.cloud.google.com/"
        )
    
    url = "https://solar.googleapis.com/v1/buildingInsights:findClosest"
    
    params = {
        "location.latitude": lat,
        "location.longitude": lon,
        "requiredQuality": "HIGH",
        "key": api_key
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            sp = data.get('solarPotential', {})
            
            # Extrahiere relevante Daten
            result = {
                'solar_max_array_m2': sp.get('maxArrayAreaMeters2', 0),
                'solar_max_panels': sp.get('maxArrayPanelsCount', 0),
                'solar_sunshine_hours_year': sp.get('maxSunshineHoursPerYear', 0),
                'solar_carbon_offset_kg_mwh': sp.get('carbonOffsetFactorKgPerMwh', 0),
                'solar_roof_area_m2': sp.get('wholeRoofStats', {}).get('areaMeters2', 0),
                'solar_num_roof_segments': len(sp.get('roofSegmentStats', [])),
                'solar_api_success': True,
                'solar_api_error': None
            }
            
            # Dachsegmente analysieren (Neigung & Azimut)
            segments = sp.get('roofSegmentStats', [])
            if segments:
                pitches = [seg.get('pitchDegrees', 0) for seg in segments]
                azimuths = [seg.get('azimuthDegrees', 0) for seg in segments]
                areas = [seg.get('stats', {}).get('areaMeters2', 0) for seg in segments]
                
                # Gewichteter Durchschnitt (nach Fläche)
                total_area = sum(areas) if areas else 1
                result['solar_avg_pitch'] = sum(p * a for p, a in zip(pitches, areas)) / total_area if total_area > 0 else 0
                result['solar_avg_azimuth'] = sum(az * a for az, a in zip(azimuths, areas)) / total_area if total_area > 0 else 0
                
                # Bestes Segment (größte Fläche)
                if areas:
                    best_idx = areas.index(max(areas))
                    result['solar_best_pitch'] = pitches[best_idx]
                    result['solar_best_azimuth'] = azimuths[best_idx]
                    result['solar_best_area_m2'] = areas[best_idx]
            else:
                result['solar_avg_pitch'] = 0
                result['solar_avg_azimuth'] = 0
                result['solar_best_pitch'] = 0
                result['solar_best_azimuth'] = 0
                result['solar_best_area_m2'] = 0
            
            return result
            
        elif response.status_code == 404:
            # Kein Gebäude gefunden
            return {
                'solar_api_success': False,
                'solar_api_error': 'NOT_FOUND',
                **{k: 0 for k in ['solar_max_array_m2', 'solar_max_panels', 
                                   'solar_sunshine_hours_year', 'solar_carbon_offset_kg_mwh',
                                   'solar_roof_area_m2', 'solar_num_roof_segments',
                                   'solar_avg_pitch', 'solar_avg_azimuth',
                                   'solar_best_pitch', 'solar_best_azimuth', 'solar_best_area_m2']}
            }
        else:
            return {
                'solar_api_success': False,
                'solar_api_error': f'HTTP_{response.status_code}',
                **{k: 0 for k in ['solar_max_array_m2', 'solar_max_panels', 
                                   'solar_sunshine_hours_year', 'solar_carbon_offset_kg_mwh',
                                   'solar_roof_area_m2', 'solar_num_roof_segments',
                                   'solar_avg_pitch', 'solar_avg_azimuth',
                                   'solar_best_pitch', 'solar_best_azimuth', 'solar_best_area_m2']}
            }
            
    except Exception as e:
        return {
            'solar_api_success': False,
            'solar_api_error': str(e)[:100],  # Kürzen für Speicherung
            **{k: 0 for k in ['solar_max_array_m2', 'solar_max_panels', 
                               'solar_sunshine_hours_year', 'solar_carbon_offset_kg_mwh',
                               'solar_roof_area_m2', 'solar_num_roof_segments',
                               'solar_avg_pitch', 'solar_avg_azimuth',
                               'solar_best_pitch', 'solar_best_azimuth', 'solar_best_area_m2']}
        }


def enrich_with_solar_potential(buildings_gdf: gpd.GeoDataFrame, 
                                 limit: int = None,
                                 test_mode: bool = False) -> gpd.GeoDataFrame:
    """
    Reichert GeoDataFrame mit Google Solar API Daten an.
    
    Args:
        buildings_gdf: GeoDataFrame mit Top-Leads
        limit: Max. Anzahl Gebäude (None = alle)
        test_mode: Wenn True, zeige detaillierte Ausgaben für ersten Request
    
    Returns:
        Angereichertes GeoDataFrame mit Solar-Spalten
    """
    print("\n" + "=" * 60)
    print("☀️  Solar Potential Enrichment (Google Solar API)")
    print("=" * 60)
    
    # Check API Key
    if not GOOGLE_SOLAR_API_KEY:
        print("\n❌ FEHLER: GOOGLE_SOLAR_API_KEY nicht gesetzt!")
        print("\n📋 So richten Sie den API Key ein:")
        print("   1. Gehen Sie zu: https://console.cloud.google.com/")
        print("   2. Erstellen Sie ein Projekt (falls noch nicht vorhanden)")
        print("   3. Aktivieren Sie 'Solar API' im API-Bereich")
        print("   4. Erstellen Sie unter 'Credentials' einen API Key")
        print("   5. Setzen Sie in PowerShell:")
        print("      $env:GOOGLE_SOLAR_API_KEY='your-api-key-here'")
        print("\n💡 Dann erneut ausführen:")
        print("   python -m pv_roof_leads.enrich_solar_potential")
        sys.exit(1)
    
    # Zu WGS84 konvertieren
    if buildings_gdf.crs != CRS_EXPORT:
        print(f"   Konvertiere von {buildings_gdf.crs} → {CRS_EXPORT}")
        buildings_gdf = buildings_gdf.to_crs(CRS_EXPORT)
    
    # Zentroide berechnen
    buildings_gdf['centroid'] = buildings_gdf.geometry.centroid
    buildings_gdf['lat'] = buildings_gdf.centroid.y
    buildings_gdf['lon'] = buildings_gdf.centroid.x
    
    # Limit anwenden
    if limit:
        buildings_gdf = buildings_gdf.head(limit).copy()
        print(f"   Limit: {limit} Gebäude")
    
    print(f"\n📍 Rufe Solar-Daten für {len(buildings_gdf)} Gebäude ab...")
    estimated_time = len(buildings_gdf) * SOLAR_API_RATE_LIMIT_DELAY
    print(f"   Rate: {1/SOLAR_API_RATE_LIMIT_DELAY:.1f} Request/Sekunde")
    print(f"   Geschätzte Dauer: ~{estimated_time/60:.1f} Minuten")
    
    # Solar-Daten abrufen
    solar_data = []
    errors = 0
    not_found = 0
    
    for idx, row in tqdm(buildings_gdf.iterrows(), total=len(buildings_gdf), desc="Google Solar API"):
        data = get_solar_potential(row['lat'], row['lon'], GOOGLE_SOLAR_API_KEY)
        
        # Test-Modus: Zeige ersten Request detailliert
        if test_mode and idx == buildings_gdf.index[0]:
            print("\n" + "=" * 60)
            print("🔍 TEST-MODUS: Erster API-Call Details")
            print("=" * 60)
            print(f"   Gebäude: {row.get('name', 'Unbekannt')}")
            print(f"   Koordinaten: {row['lat']:.6f}, {row['lon']:.6f}")
            print(f"   Fläche: {row.get('footprint_area_m2', 0):.0f} m²")
            print("\n📊 API Response:")
            for key, value in data.items():
                if isinstance(value, float):
                    print(f"   {key}: {value:.2f}")
                else:
                    print(f"   {key}: {value}")
            print("=" * 60 + "\n")
        
        solar_data.append(data)
        
        # Statistik
        if not data.get('solar_api_success'):
            if data.get('solar_api_error') == 'NOT_FOUND':
                not_found += 1
            else:
                errors += 1
        
        # Rate limiting
        sleep(SOLAR_API_RATE_LIMIT_DELAY)
    
    print(f"\n✓ API-Abfragen abgeschlossen:")
    print(f"   ✓ Erfolgreich: {len(buildings_gdf) - errors - not_found}")
    print(f"   ⚠️  Nicht gefunden (404): {not_found}")
    print(f"   ✗ Fehler: {errors}")
    
    # Merge zurück
    solar_df = pd.DataFrame(solar_data)
    enriched = pd.concat([buildings_gdf.reset_index(drop=True), solar_df], axis=1)
    
    # Statistiken
    successful = enriched['solar_api_success'].sum()
    if successful > 0:
        print(f"\n📊 Solar-Statistiken (von {successful} erfolgreichen Requests):")
        print(f"   Ø PV-nutzbare Fläche: {enriched[enriched['solar_api_success']]['solar_max_array_m2'].mean():.1f} m²")
        print(f"   Ø Dachneigung: {enriched[enriched['solar_api_success']]['solar_avg_pitch'].mean():.1f}°")
        print(f"   Ø Azimut: {enriched[enriched['solar_api_success']]['solar_avg_azimuth'].mean():.1f}° (180°=Süd)")
        print(f"   Ø Sonnenstunden/Jahr: {enriched[enriched['solar_api_success']]['solar_sunshine_hours_year'].mean():.0f} h")
        print(f"   Ø Dachsegmente: {enriched[enriched['solar_api_success']]['solar_num_roof_segments'].mean():.1f}")
    
    return enriched


def main():
    """
    Hauptfunktion: Lädt Top-Leads und reichert mit Solar-Daten an.
    """
    ensure_dirs()
    
    print("\n" + "=" * 60)
    print("📊 Google Solar API Integration")
    print("=" * 60)
    
    # Lade gescorte Gebäude
    scored_file = STAGING_DORTMUND / "scored_buildings.geojson"
    print(f"\n📂 Lade gescorte Gebäude: {scored_file}")
    
    if not scored_file.exists():
        print(f"\n❌ FEHLER: Datei nicht gefunden!")
        print(f"   Bitte erst Task 5.2 ausführen:")
        print(f"   python -m pv_roof_leads.score_leads")
        sys.exit(1)
    
    buildings = gpd.read_file(scored_file)
    print(f"✓ {len(buildings)} Gebäude geladen")
    
    # Nehme nur Top 100 (um API-Kosten zu sparen im MVP)
    top_n = 100
    top_buildings = buildings.head(top_n).copy()
    print(f"✓ Top {top_n} Leads ausgewählt für Solar-Analyse")
    
    # Frage ob Test-Modus
    print(f"\n💡 Möchten Sie zuerst einen Test mit 5 Gebäuden durchführen?")
    print(f"   (Empfohlen beim ersten Mal)")
    response = input("   Test-Modus? (j/n): ").strip().lower()
    
    if response in ['j', 'y', 'ja', 'yes']:
        print("\n🧪 Starte TEST-MODUS mit 5 Gebäuden...")
        enriched = enrich_with_solar_potential(top_buildings, limit=5, test_mode=True)
        
        # Speichern
        output_file = STAGING_DORTMUND / "solar_enriched_test.geojson"
        enriched.to_file(output_file, driver="GeoJSON")
        print(f"\n💾 Test-Ergebnisse gespeichert: {output_file}")
        
        print("\n" + "=" * 60)
        print("✅ Test abgeschlossen!")
        print("=" * 60)
        print("\n💡 Möchten Sie jetzt alle 100 Leads verarbeiten?")
        response2 = input("   Vollständiger Run? (j/n): ").strip().lower()
        
        if response2 not in ['j', 'y', 'ja', 'yes']:
            print("\n👋 Abgebrochen. Führen Sie später erneut aus für vollständigen Run.")
            sys.exit(0)
        
        top_buildings = buildings.head(top_n).copy()
    
    # Vollständiger Run
    print("\n🚀 Starte vollständigen Run für Top 100...")
    enriched = enrich_with_solar_potential(top_buildings, limit=100, test_mode=False)
    
    # Speichern
    output_file = STAGING_DORTMUND / "solar_enriched_top100.geojson"
    enriched.to_file(output_file, driver="GeoJSON")
    print(f"\n💾 Gespeichert: {output_file}")
    
    # Auch als CSV für Excel
    csv_file = STAGING_DORTMUND / "solar_enriched_top100.csv"
    # Entferne Geometrie-Spalte für CSV
    enriched_csv = enriched.drop(columns=['geometry', 'centroid'], errors='ignore')
    enriched_csv.to_csv(csv_file, index=False, encoding='utf-8-sig')
    print(f"💾 CSV gespeichert: {csv_file}")
    
    print("\n" + "=" * 60)
    print("✅ Solar Enrichment abgeschlossen!")
    print("=" * 60)
    print(f"\n📁 Ergebnisse:")
    print(f"   • GeoJSON: {output_file}")
    print(f"   • CSV: {csv_file}")
    print(f"\n💡 Nächster Schritt:")
    print(f"   • Prüfen Sie die Ergebnisse in Excel/QGIS")
    print(f"   • Integration in Scoring-System (Sprint 4)")


if __name__ == '__main__':
    main()
