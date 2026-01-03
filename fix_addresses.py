#!/usr/bin/env python3
"""
Script to update buildings_complete.json with addresses from GeoJSON
"""

import json
import sys
from pathlib import Path

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
    
    # Create mapping from ID to address
    address_map = {}
    for feature in geojson['features']:
        props = feature['properties']
        building_id = props.get('index__osm')
        address = props.get('lagebeztxt', '')
        funktion = props.get('funktion', '')
        gebnutzbez = props.get('gebnutzbez', '')
        
        if building_id:
            address_map[building_id] = {
                'address': address,
                'funktion': funktion,
                'gebnutzbez': gebnutzbez
            }
    
    print(f"Address-Map erstellt: {len(address_map)} Einträge")
    
    # Update buildings with addresses
    updated_count = 0
    for building in buildings:
        building_id = building.get('id')
        if building_id in address_map:
            building['address'] = address_map[building_id]['address']
            building['funktion'] = address_map[building_id]['funktion']
            building['gebnutzbez'] = address_map[building_id]['gebnutzbez']
            updated_count += 1
    
    print(f"Aktualisiert: {updated_count} Gebäude mit Adressen")
    
    # Save updated JSON to final directory
    output_path = base_dir / 'data' / 'final' / 'dortmund' / 'buildings_complete.json'
    print(f"Speichere zu {output_path}...")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(buildings, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Fertig!")
    
    # Also create the JavaScript file
    js_output_path = base_dir / 'data' / 'final' / 'dortmund' / 'buildings_all_data.js'
    print(f"\nErstelle JavaScript-Datei: {js_output_path}...")
    
    with open(js_output_path, 'w', encoding='utf-8') as f:
        f.write('const buildingsData = ')
        json.dump(buildings, f, ensure_ascii=False, indent=2)
        f.write(';\n')
    
    print("✅ JavaScript-Datei erstellt!")
    
    # Show some examples
    print("\n📋 Beispiele:")
    for i, building in enumerate(buildings[:5]):
        if building.get('address'):
            print(f"  Gebäude {building['id']}: {building.get('address', 'Keine Adresse')}")
    
    print(f"\n📊 Statistik:")
    print(f"  Gesamt: {len(buildings)} Gebäude")
    print(f"  Mit Adresse: {sum(1 for b in buildings if b.get('address'))} Gebäude")
    print(f"  Ohne Adresse: {sum(1 for b in buildings if not b.get('address'))} Gebäude")

if __name__ == '__main__':
    main()
