#!/usr/bin/env python3
"""
Script to match buildings by coordinates and update addresses
"""

import json
import sys
from pathlib import Path
from math import sqrt

def distance(lat1, lon1, lat2, lon2):
    """Calculate simple Euclidean distance"""
    return sqrt((lat1 - lat2)**2 + (lon1 - lon2)**2)

def main():
    base_dir = Path(__file__).parent
    
    # Load GeoJSON from processed directory
    geojson_path = base_dir / 'data' / 'processed' / 'dortmund' / 'buildings_complete.geojson'
    print(f"Lade GeoJSON von {geojson_path}...")
    
    with open(geojson_path, 'r', encoding='utf-8') as f:
        geojson = json.load(f)
    
    print(f"GeoJSON geladen: {len(geojson['features'])} Features")
    
    # Load existing JSON from final directory
    json_path = base_dir / 'data' / 'final' / 'dortmund' / 'buildings_complete.json'
    print(f"Lade JSON von {json_path}...")
    
    with open(json_path, 'r', encoding='utf-8') as f:
        buildings = json.load(f)
    
    print(f"JSON geladen: {len(buildings)} Gebäude")
    
    # Create lists for coordinate matching
    geojson_buildings = []
    for feature in geojson['features']:
        props = feature['properties']
        if props.get('lat') and props.get('lon'):
            geojson_buildings.append({
                'lat': props['lat'],
                'lon': props['lon'],
                'address': props.get('lagebeztxt', ''),
                'funktion': props.get('funktion', ''),
                'gebnutzbez': props.get('gebnutzbez', ''),
                'id': props.get('index__osm')
            })
    
    print(f"GeoJSON mit Koordinaten: {len(geojson_buildings)} Gebäude")
    
    # Match by coordinates (within threshold)
    threshold = 0.0001  # About 10 meters
    updated_count = 0
    matched_by_coords = 0
    
    for building in buildings:
        if not building.get('lat') or not building.get('lon'):
            continue
            
        # Skip if already has address
        if building.get('address') and building['address'].strip():
            continue
        
        # Find closest match in geojson
        best_match = None
        best_distance = threshold
        
        for geo_building in geojson_buildings:
            dist = distance(
                building['lat'], building['lon'],
                geo_building['lat'], geo_building['lon']
            )
            
            if dist < best_distance:
                best_distance = dist
                best_match = geo_building
        
        if best_match:
            building['address'] = best_match['address']
            building['funktion'] = best_match['funktion']
            building['gebnutzbez'] = best_match['gebnutzbez']
            matched_by_coords += 1
            updated_count += 1
    
    # Fix image paths - add luftbilder/ prefix if missing
    image_fix_count = 0
    for building in buildings:
        if building.get('image') and building['image']:
            # Check if path already starts with luftbilder/
            if not building['image'].startswith('luftbilder/'):
                building['image'] = 'luftbilder/' + building['image']
                image_fix_count += 1
    
    print(f"Fixed image paths: {image_fix_count} Gebäude")
    
    print(f"Matched by coordinates: {matched_by_coords} Gebäude")
    print(f"Total updated: {updated_count} Gebäude")
    
    # Save updated JSON to final directory
    output_path = base_dir / 'data' / 'final' / 'dortmund' / 'buildings_complete.json'
    print(f"Speichere zu {output_path}...")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(buildings, f, ensure_ascii=False, indent=2)
    
    print("✅ JSON-Datei gespeichert!")
    
    # Also create the JavaScript file
    js_output_path = base_dir / 'data' / 'final' / 'dortmund' / 'buildings_all_data.js'
    print(f"\nErstelle JavaScript-Datei: {js_output_path}...")
    
    with open(js_output_path, 'w', encoding='utf-8') as f:
        f.write('const buildingsData = ')
        json.dump(buildings, f, ensure_ascii=False, indent=2)
        f.write(';\n')
    
    print("✅ JavaScript-Datei erstellt!")
    
    # Show statistics
    with_address = sum(1 for b in buildings if b.get('address') and b['address'].strip())
    without_address = len(buildings) - with_address
    
    print(f"\n📊 Statistik:")
    print(f"  Gesamt: {len(buildings)} Gebäude")
    print(f"  Mit Adresse: {with_address} Gebäude ({with_address*100//len(buildings)}%)")
    print(f"  Ohne Adresse: {without_address} Gebäude")
    
    # Show examples
    print("\n📋 Beispiele mit Adresse:")
    count = 0
    for building in buildings:
        if building.get('address') and building['address'].strip():
            print(f"  Gebäude {building['id']}: {building['address']}")
            count += 1
            if count >= 5:
                break

if __name__ == '__main__':
    main()
