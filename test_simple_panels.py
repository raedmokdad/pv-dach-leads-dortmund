"""
Einfache Panel-Visualisierung - Test
"""
import requests
import numpy as np
from PIL import Image
import os
from dotenv import load_dotenv
import rasterio
from rasterio.io import MemoryFile
from pyproj import Transformer
import subprocess

load_dotenv()
API_KEY = os.getenv('GOOGLE_SOLAR_API_KEY')

lat, lon = 51.564617, 7.424936

# Building Insights
resp = requests.get('https://solar.googleapis.com/v1/buildingInsights:findClosest', params={
    'location.latitude': lat, 'location.longitude': lon, 'requiredQuality': 'LOW', 'key': API_KEY
})
data = resp.json()
panels = data['solarPotential']['solarPanels']

# WICHTIG: Google-Gebäudezentrum verwenden, nicht Panel-Zentrum!
building_center = data.get('center', {})
google_lat = building_center.get('latitude', lat)
google_lon = building_center.get('longitude', lon)

print(f'Eingabe: {lat}, {lon}')
print(f'Google Gebäude-Zentrum: {google_lat}, {google_lon}')

# DataLayers mit GOOGLE-Koordinaten abfragen
layers = requests.get('https://solar.googleapis.com/v1/dataLayers:get', params={
    'location.latitude': google_lat,  # GOOGLE-Zentrum
    'location.longitude': google_lon,  # GOOGLE-Zentrum
    'radiusMeters': 120, 'view': 'FULL_LAYERS', 'requiredQuality': 'LOW',
    'pixelSizeMeters': 0.25, 'key': API_KEY
}).json()

rgb_url = layers['rgbUrl'] + "&key=" + API_KEY
rgb_resp = requests.get(rgb_url)

with MemoryFile(rgb_resp.content) as memfile:
    with memfile.open() as ds:
        bounds = ds.bounds
        width, height = ds.width, ds.height
        pixel_size = (bounds.right - bounds.left) / width
        r, g, b = ds.read(1), ds.read(2), ds.read(3)
        rgb = np.stack([r, g, b], axis=-1)

transformer = Transformer.from_crs('EPSG:4326', 'EPSG:32632', always_xy=True)

# Zeichne ALLE Panels als blaue Rechtecke
result = rgb.copy().astype(np.float32)

pw = int(1.045 / pixel_size)  # 4 Pixel
ph = int(1.879 / pixel_size)  # 7 Pixel

print(f'Bild: {width}x{height}, Panel: {pw}x{ph} Pixel')
print(f'Bounds: {bounds}')

count = 0
for panel in panels:
    plat = panel['center']['latitude']
    plon = panel['center']['longitude']
    orientation = panel.get('orientation', 'LANDSCAPE')
    
    # Portrait = gedreht
    if orientation == 'PORTRAIT':
        panel_w, panel_h = ph, pw
    else:
        panel_w, panel_h = pw, ph
    
    px_utm, py_utm = transformer.transform(plon, plat)
    cx = int((px_utm - bounds.left) / pixel_size)
    cy = int((bounds.top - py_utm) / pixel_size)
    
    x1 = cx - panel_w // 2
    y1 = cy - panel_h // 2
    x2 = x1 + panel_w
    y2 = y1 + panel_h
    
    # Clip to image bounds
    x1 = max(0, x1)
    y1 = max(0, y1)
    x2 = min(width, x2)
    y2 = min(height, y2)
    
    if x2 > x1 and y2 > y1:
        # Dunkelblau mit 80% Deckkraft
        result[y1:y2, x1:x2, 0] = 30   # R
        result[y1:y2, x1:x2, 1] = 50   # G
        result[y1:y2, x1:x2, 2] = 120  # B
        count += 1

print(f'{count} Panels gezeichnet')

output_path = 'data/final/dortmund/panel_visualizations/rank_002_TEST.png'
Image.fromarray(result.astype(np.uint8)).save(output_path)
print(f'Gespeichert: {output_path}')

# Öffne
subprocess.run(['start', output_path], shell=True)
