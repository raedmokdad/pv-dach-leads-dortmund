import json
import re

# Read report HTML
with open('deploy/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Extract allBuildings array
match = re.search(r'const allBuildings = (\[.*?\]);', html, re.DOTALL)
if not match:
    print("❌ Could not find allBuildings")
    exit(1)

buildings_json = match.group(1)
buildings = json.loads(buildings_json)

print(f"✅ Extracted {len(buildings)} buildings from report")
print(f"First building: {buildings[0].get('a', 'N/A')}")
print(f"Coordinates: lt={buildings[0].get('lt')}, ln={buildings[0].get('ln')}")

# Convert to full structure
map_buildings = []
for b in buildings:
    map_buildings.append({
        'id': b.get('id'),
        'lat': b.get('lt'),  # Use 'lt' from report
        'lon': b.get('ln'),  # Use 'ln' from report
        'address': b.get('a', ''),
        'funktion': b.get('f', ''),
        'image': b.get('i', ''),
        'solar': {
            'yearly_kwh': b.get('e', 0),
            'max_panels': b.get('p', 0),
            'area_m2': b.get('ar', 0),
            'sunshine_hours': b.get('sh', 0),
            'co2_offset_kg': b.get('co', 0),
            'total_roof_area_m2': b.get('tra', 0),
            'usable_roof_area_m2': b.get('ura', 0),
            'roof_type': b.get('df', 'N/A'),
            'pitch_degrees': b.get('pt', 0),
            'azimuth_degrees': b.get('az', 0),
            'orientation': b.get('au', 'N/A')
        },
        'gemini': {
            'roof_material': b.get('m', 'Unbekannt'),
            'roof_color': b.get('rc', 'Unbekannt'),
            'roof_condition': b.get('c', 'Mittel'),
            'usable_percentage': b.get('u', 0),
            'complexity': b.get('x', 'Mittel'),
            'obstacle_count': b.get('oc', 0),
            'obstacles': b.get('o', '').split(', ') if b.get('o') else [],
            'notes': ''
        },
        'existing_pv': {
            'has_pv': b.get('pv', 0) > 0
        }
    })

# Save to deploy
with open('deploy/buildings_all_data.js', 'w', encoding='utf-8') as f:
    f.write('const buildingsData = ')
    json.dump(map_buildings, f, ensure_ascii=False, indent=2)
    f.write(';\n')

print(f"✅ Saved {len(map_buildings)} buildings to deploy/buildings_all_data.js")
print(f"First building now: lat={map_buildings[0]['lat']}, lon={map_buildings[0]['lon']}")
