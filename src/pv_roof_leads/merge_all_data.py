"""
Merge All Data - Führt alle Datenquellen zusammen mit Validierung

Dieses Modul ersetzt die Fix-Scripte und sollte nach enrich_with_google_solar.py
ausgeführt werden.

Datenquellen:
1. buildings_processed.geojson (ALKIS - Grunddaten + Fläche)
2. all_buildings_with_solar.geojson (Google Solar API Daten)
3. gemini_roof_analysis.json (Gemini Dachanalyse)
4. luftbilder/ (Bilder)

Validierungen:
- Panel-Fläche darf nicht größer als 1.5x Gebäudefläche sein
- Koordinaten-Matching mit KDTree (max. 50m Toleranz)
"""
import json
from pathlib import Path
from pyproj import Transformer
import numpy as np
from scipy.spatial import cKDTree
import geopandas as gpd

from pv_roof_leads.paths import FINAL_DORTMUND, PROCESSED_DORTMUND


# Konfiguration
MAX_DISTANCE_DEGREES = 0.0005  # ~50m Toleranz für Koordinaten-Matching
MAX_PANEL_AREA_FACTOR = 1.5    # Panel-Fläche max. 1.5x Gebäudefläche

# CRS Transformer für UTM → WGS84
TRANSFORMER = Transformer.from_crs("EPSG:25832", "EPSG:4326", always_xy=True)


def load_base_buildings(city: str = "dortmund") -> dict:
    """Lädt die Basis-Gebäude-Daten (ALKIS normalisiert)"""
    base_path = Path(f"data/processed/{city}/buildings_processed.geojson")
    
    if not base_path.exists():
        # Fallback auf buildings_processed_no_pv wenn vorhanden
        alt_path = Path(f"data/processed/{city}/buildings_processed_no_pv.geojson")
        if alt_path.exists():
            base_path = alt_path
        else:
            raise FileNotFoundError(f"Keine Gebäude-Daten gefunden: {base_path}")
    
    print(f"📂 Lade Basis-Gebäude: {base_path}")
    with open(base_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    print(f"   ✓ {len(data['features'])} Gebäude geladen")
    return data


def load_solar_data(city: str = "dortmund") -> tuple:
    """Lädt Solar-Daten und erstellt KDTree für Matching"""
    solar_path = Path(f"data/final/{city}/all_buildings_with_solar.geojson")
    
    if not solar_path.exists():
        print(f"   ⚠️ Keine Solar-Daten: {solar_path}")
        return None, None, None
    
    print(f"📂 Lade Solar-Daten: {solar_path}")
    with open(solar_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Erstelle KDTree
    coords = []
    props_list = []
    for feat in data['features']:
        props = feat['properties']
        lat = props.get('lat')
        lon = props.get('lon')
        if lat and lon:
            coords.append([lat, lon])
            props_list.append(props)
    
    if not coords:
        print(f"   ⚠️ Keine Koordinaten in Solar-Daten")
        return None, None, None
    
    coords_array = np.array(coords)
    tree = cKDTree(coords_array)
    
    print(f"   ✓ {len(coords)} Solar-Einträge")
    has_panels = sum(1 for p in props_list 
                     if p.get('solar_max_array_panels_count', 0) and p.get('solar_max_array_panels_count', 0) > 0)
    print(f"   ✓ {has_panels} mit Panels > 0")
    
    return tree, coords_array, props_list


def load_gemini_data(city: str = "dortmund") -> tuple:
    """Lädt Gemini-Analysedaten und erstellt KDTree"""
    gemini_path = Path(f"data/final/{city}/gemini_roof_analysis.json")
    
    if not gemini_path.exists():
        print(f"   ⚠️ Keine Gemini-Daten: {gemini_path}")
        return None, None, None
    
    print(f"📂 Lade Gemini-Daten: {gemini_path}")
    with open(gemini_path, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)
    
    coords = []
    data_list = []
    for key, analysis in raw_data.items():
        # Key Format: building_0_51.479992_7.449345.jpg
        parts = key.replace('.jpg', '').split('_')
        if len(parts) >= 4:
            try:
                lat = float(parts[2])
                lon = float(parts[3])
                coords.append([lat, lon])
                data_list.append(analysis)
            except ValueError:
                pass
    
    if not coords:
        print(f"   ⚠️ Keine Koordinaten in Gemini-Daten")
        return None, None, None
    
    coords_array = np.array(coords)
    tree = cKDTree(coords_array)
    
    print(f"   ✓ {len(coords)} Gemini-Analysen")
    return tree, coords_array, data_list


def load_images(city: str = "dortmund") -> tuple:
    """Lädt Bild-Pfade und erstellt KDTree"""
    images_path = Path(f"data/final/{city}/luftbilder")
    
    if not images_path.exists():
        print(f"   ⚠️ Kein Bilder-Ordner: {images_path}")
        return None, None, None
    
    print(f"📂 Lade Bilder: {images_path}")
    
    coords = []
    paths_list = []
    for img_file in images_path.glob("building_*.jpg"):
        # Format: building_123_51.479992_7.449345.jpg
        parts = img_file.stem.split('_')
        if len(parts) >= 4:
            try:
                lat = float(parts[2])
                lon = float(parts[3])
                coords.append([lat, lon])
                paths_list.append(f"luftbilder/{img_file.name}")
            except ValueError:
                pass
    
    if not coords:
        print(f"   ⚠️ Keine Bilder mit Koordinaten")
        return None, None, None
    
    coords_array = np.array(coords)
    tree = cKDTree(coords_array)
    
    print(f"   ✓ {len(coords)} Bilder")
    return tree, coords_array, paths_list


def get_centroid_wgs84(geometry: dict) -> tuple:
    """Berechnet Zentroid und transformiert von EPSG:25832 nach WGS84"""
    geom_type = geometry['type']
    
    if geom_type == 'Polygon':
        coords = geometry['coordinates'][0]
        utm_x = sum(c[0] for c in coords) / len(coords)
        utm_y = sum(c[1] for c in coords) / len(coords)
    elif geom_type == 'MultiPolygon':
        all_coords = []
        for poly in geometry['coordinates']:
            all_coords.extend(poly[0])
        utm_x = sum(c[0] for c in all_coords) / len(all_coords)
        utm_y = sum(c[1] for c in all_coords) / len(all_coords)
    else:
        return None, None
    
    # Transformiere von EPSG:25832 nach EPSG:4326 (WGS84)
    lon, lat = TRANSFORMER.transform(utm_x, utm_y)
    return lat, lon


def validate_solar_match(building_area: float, panel_area: float) -> bool:
    """
    Validiert ob Solar-Daten zu diesem Gebäude passen.
    
    Returns:
        True wenn valide, False wenn Panel-Fläche zu groß
    """
    if building_area <= 0 or panel_area <= 0:
        return True  # Kann nicht validieren, erlaube
    
    # Panel-Fläche sollte nicht größer als 1.5x Gebäudefläche sein
    if panel_area > building_area * MAX_PANEL_AREA_FACTOR:
        return False
    
    return True


def merge_all_data(city: str = "dortmund"):
    """
    Hauptfunktion: Führt alle Datenquellen zusammen.
    
    Args:
        city: Stadt (z.B. "dortmund", "bonn")
    """
    print("\n" + "=" * 70)
    print(f"🔗 MERGE ALL DATA - {city.upper()}")
    print("=" * 70)
    
    # 1. Lade alle Datenquellen
    base_data = load_base_buildings(city)
    solar_tree, solar_coords, solar_props = load_solar_data(city)
    gemini_tree, gemini_coords, gemini_data = load_gemini_data(city)
    image_tree, image_coords, image_paths = load_images(city)
    
    # Statistiken
    stats = {
        'total': len(base_data['features']),
        'matched_solar': 0,
        'matched_solar_valid': 0,
        'matched_solar_invalid': 0,
        'matched_gemini': 0,
        'matched_images': 0
    }
    
    print("\n🔄 Führe Daten zusammen...")
    
    # 2. Iteriere über alle Basis-Gebäude
    for feat in base_data['features']:
        props = feat['properties']
        
        # Berechne Zentroid in WGS84
        lat, lon = get_centroid_wgs84(feat['geometry'])
        if lat is None:
            continue
        
        props['lat'] = round(lat, 6)
        props['lon'] = round(lon, 6)
        
        query_point = np.array([lat, lon])
        building_area = props.get('area_m2', 0) or 0
        
        # 3. Match Solar-Daten
        if solar_tree is not None:
            dist, idx = solar_tree.query(query_point)
            if dist < MAX_DISTANCE_DEGREES:
                solar_match = solar_props[idx]
                panel_area = solar_match.get('solar_max_array_area_m2', 0) or 0
                
                # VALIDIERUNG
                if validate_solar_match(building_area, panel_area):
                    stats['matched_solar_valid'] += 1
                    stats['matched_solar'] += 1
                    
                    # Übertrage alle Solar-Felder
                    solar_fields = [
                        'solar_max_array_panels_count',
                        'solar_max_array_area_m2',
                        'solar_max_sunshine_hours_per_year',
                        'solar_carbon_offset_kg_per_mwh',
                        'solar_panel_capacity_watts',
                        'solar_api_success',
                        'google_solar_best_pitch',
                        'google_solar_best_azimuth',
                        'google_solar_total_roof_area_m2',
                        'google_solar_usable_roof_pct'
                    ]
                    for field in solar_fields:
                        if field in solar_match:
                            props[field] = solar_match[field]
                    
                    # Übertrage auch roof_ Felder
                    for field in solar_match:
                        if field.startswith('roof_') and field not in props:
                            props[field] = solar_match[field]
                else:
                    # Ungültige Zuordnung - Skip
                    stats['matched_solar_invalid'] += 1
        
        # 4. Match Bilder
        if image_tree is not None:
            dist, idx = image_tree.query(query_point)
            if dist < MAX_DISTANCE_DEGREES:
                stats['matched_images'] += 1
                props['solar_rgb_image'] = image_paths[idx]
        
        # 5. Match Gemini-Daten
        if gemini_tree is not None:
            dist, idx = gemini_tree.query(query_point)
            if dist < MAX_DISTANCE_DEGREES:
                stats['matched_gemini'] += 1
                gemini_match = gemini_data[idx]
                
                # Übertrage Gemini-Felder
                gemini_fields = {
                    'roof_material': 'Unbekannt',
                    'roof_condition': 'Unbekannt',
                    'roof_color': 'Unbekannt',
                    'has_existing_pv': False,
                    'obstacles': [],
                    'obstacle_count': 0,
                    'usable_roof_percentage': 0,
                    'installation_complexity': 'Unbekannt'
                }
                for field, default in gemini_fields.items():
                    props[field] = gemini_match.get(field, default)
    
    # 6. Speichern
    output_path = Path(f"data/processed/{city}/buildings_complete.geojson")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(base_data, f, ensure_ascii=False)
    
    # 7. Statistiken ausgeben
    print("\n" + "=" * 70)
    print(f"✅ MERGE COMPLETE")
    print("=" * 70)
    print(f"   Gesamt Gebäude:     {stats['total']:,}")
    print(f"   Mit Solar-Daten:    {stats['matched_solar']:,} (valide)")
    print(f"   Ungültige Solar:    {stats['matched_solar_invalid']:,} (übersprungen)")
    print(f"   Mit Gemini-Analyse: {stats['matched_gemini']:,}")
    print(f"   Mit Bild:           {stats['matched_images']:,}")
    print(f"\n💾 Gespeichert: {output_path}")
    
    return output_path, stats


def main():
    """CLI Hauptfunktion"""
    import argparse
    parser = argparse.ArgumentParser(description='Merge all data sources')
    parser.add_argument('--city', default='dortmund', help='Stadt (default: dortmund)')
    args = parser.parse_args()
    
    merge_all_data(args.city)


if __name__ == "__main__":
    main()
