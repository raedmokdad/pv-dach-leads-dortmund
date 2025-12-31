import requests
from dotenv import load_dotenv

load_dotenv()
API_KEY = "AIzaSyCLZapYjUB0EyShc2-I0xqgDNhiEiaXSQc"

# Building Insights
resp = requests.get('https://solar.googleapis.com/v1/buildingInsights:findClosest', params={
    'location.latitude': 51.564617, 'location.longitude': 7.424936, 'requiredQuality': 'LOW', 'key': API_KEY
})
data = resp.json()

# Gebäude-Zentrum von Google
building_center = data.get('center', {})
building_lat = building_center.get('latitude')
building_lon = building_center.get('longitude')

print(f'Eingabe-Koordinaten: 51.564617, 7.424936')
print(f'Google Gebäude-Zentrum: {building_lat}, {building_lon}')

# Unterschied berechnen
lat_diff = building_lat - 51.564617
lon_diff = building_lon - 7.424936

print(f'Unterschied: {lat_diff:.8f}, {lon_diff:.8f}')
print(f'Abstand in Metern: ca. {abs(lat_diff) * 111000:.1f}m (lat), {abs(lon_diff) * 111000 * 0.6:.1f}m (lon)')

# Erste Panel-Position
panels = data['solarPotential']['solarPanels']
first_panel = panels[0]['center']
print(f'\nErstes Panel: {first_panel["latitude"]}, {first_panel["longitude"]}')

# Unterschied zum Gebäude-Zentrum
panel_lat_diff = first_panel['latitude'] - building_lat  
panel_lon_diff = first_panel['longitude'] - building_lon
print(f'Panel-Offset vom Gebäude: {panel_lat_diff:.8f}, {panel_lon_diff:.8f}')