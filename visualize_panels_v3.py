"""
PV-Panel Visualisierung V3 - Mit exakten Google Panel-Koordinaten
Verwendet die solarPanels Array mit center-Koordinaten für jedes Panel.
"""

import requests
import json
import os
import numpy as np
from PIL import Image, ImageDraw
from pathlib import Path
from dotenv import load_dotenv
import rasterio
from rasterio.io import MemoryFile
from pyproj import Transformer

load_dotenv()
API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GOOGLE_SOLAR_API_KEY")

OUTPUT_DIR = Path("data/final/dortmund/panel_visualizations")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def create_panel_visualization_v3(lat: float, lon: float, building_id: str = "example", max_panels: int = None):
    """
    Erstellt Panel-Visualisierung mit exakten Google-Koordinaten.
    """
    
    print(f"\n🔆 Panel-Visualisierung V3 für {building_id}")
    print("=" * 50)
    
    # 1. Building Insights abrufen
    print("\n📊 Lade Building Insights...")
    url = "https://solar.googleapis.com/v1/buildingInsights:findClosest"
    params = {
        "location.latitude": lat,
        "location.longitude": lon,
        "requiredQuality": "LOW",
        "key": API_KEY
    }
    
    response = requests.get(url, params=params, timeout=30)
    if response.status_code != 200:
        print(f"❌ API-Fehler: {response.status_code}")
        return None
    
    data = response.json()
    solar = data.get("solarPotential", {})
    
    # Gebäude-Zentrum von Google (nicht unsere Eingabe!)
    building_center = data.get("center", {})
    building_lat = building_center.get("latitude", lat)
    building_lon = building_center.get("longitude", lon)
    
    print(f"   Gebäude-Zentrum (Google): {building_lat}, {building_lon}")
    
    # Panel-Spezifikationen
    panel_height = solar.get("panelHeightMeters", 1.879)
    panel_width = solar.get("panelWidthMeters", 1.045)
    panel_capacity = solar.get("panelCapacityWatts", 400)
    
    # Exakte Panel-Positionen
    solar_panels = solar.get("solarPanels", [])
    
    if not solar_panels:
        print("❌ Keine Panel-Positionen verfügbar")
        return None
    
    print(f"   Panel-Größe: {panel_width}m x {panel_height}m")
    print(f"   Verfügbare Panel-Positionen: {len(solar_panels)}")
    
    # Limitiere Panels falls gewünscht
    if max_panels and max_panels < len(solar_panels):
        solar_panels = solar_panels[:max_panels]
        print(f"   Limitiert auf: {max_panels} Panels")
    
    # 2. DataLayers (Luftbild) abrufen - WICHTIG: Gebäude-Zentrum verwenden!
    print("\n📥 Lade Luftbild...")
    
    # Berechne den benötigten Radius basierend auf Panel-Positionen
    transformer_check = Transformer.from_crs("EPSG:4326", "EPSG:32632", always_xy=True)
    
    # Finde die Ausdehnung aller Panels
    panel_lats = [p["center"]["latitude"] for p in solar_panels if "center" in p]
    panel_lons = [p["center"]["longitude"] for p in solar_panels if "center" in p]
    
    if panel_lats and panel_lons:
        min_lat, max_lat = min(panel_lats), max(panel_lats)
        min_lon, max_lon = min(panel_lons), max(panel_lons)
        
        # Zentrum aller Panels
        center_lat = (min_lat + max_lat) / 2
        center_lon = (min_lon + max_lon) / 2
        
        # Radius berechnen
        min_x, min_y = transformer_check.transform(min_lon, min_lat)
        max_x, max_y = transformer_check.transform(max_lon, max_lat)
        
        extent_x = max_x - min_x
        extent_y = max_y - min_y
        radius_needed = max(extent_x, extent_y) / 2 + 30  # 30m Puffer
        
        print(f"   Panel-Ausdehnung: {extent_x:.0f}m x {extent_y:.0f}m")
        print(f"   Benötigter Radius: {radius_needed:.0f}m")
    else:
        center_lat, center_lon = building_lat, building_lon
        radius_needed = 150
    
    layers_url = "https://solar.googleapis.com/v1/dataLayers:get"
    layers_params = {
        "location.latitude": center_lat,  # Zentrum aller Panels
        "location.longitude": center_lon,
        "radiusMeters": min(radius_needed, 300),  # Max 300m
        "view": "FULL_LAYERS",
        "requiredQuality": "LOW",
        "pixelSizeMeters": 0.25,  # 25cm/Pixel (Google Minimum)
        "key": API_KEY
    }
    
    layers_response = requests.get(layers_url, params=layers_params, timeout=60)
    if layers_response.status_code != 200:
        print(f"❌ DataLayers-Fehler: {layers_response.status_code}")
        return None
    
    layers_data = layers_response.json()
    rgb_url = layers_data.get("rgbUrl")
    
    if not rgb_url:
        print("❌ Kein RGB-Bild verfügbar")
        return None
    
    # RGB herunterladen
    rgb_response = requests.get(f"{rgb_url}&key={API_KEY}", timeout=60)
    if rgb_response.status_code != 200:
        print("❌ RGB-Download fehlgeschlagen")
        return None
    
    # 3. Bild laden
    with MemoryFile(rgb_response.content) as memfile:
        with memfile.open() as ds:
            width = ds.width
            height = ds.height
            bounds = ds.bounds
            pixel_size = (bounds.right - bounds.left) / width
            
            print(f"   Bildgröße: {width} x {height} Pixel")
            print(f"   Pixel-Größe: {pixel_size:.3f} m")
            
            # RGB lesen
            r = ds.read(1)
            g = ds.read(2)
            b = ds.read(3)
            rgb_array = np.stack([r, g, b], axis=-1)
    
    # 4. Koordinaten-Transformation
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:32632", always_xy=True)
    
    def geo_to_pixel(geo_lat, geo_lon):
        """Konvertiert Lat/Lon zu Pixel-Koordinaten."""
        x_utm, y_utm = transformer.transform(geo_lon, geo_lat)
        px = int((x_utm - bounds.left) / pixel_size)
        py = int((bounds.top - y_utm) / pixel_size)
        return px, py
    
    # 5. Panels zeichnen
    print("\n🔲 Zeichne Panels...")
    
    result_image = rgb_array.copy()
    
    # Panel-Größe in Pixeln
    panel_w_px = int(panel_width / pixel_size)
    panel_h_px = int(panel_height / pixel_size)
    
    print(f"   Panel in Pixeln: {panel_w_px} x {panel_h_px}")
    
    # Farben
    panel_color = np.array([35, 75, 155], dtype=np.float32)  # Dunkelblau
    frame_color = np.array([140, 160, 180], dtype=np.uint8)  # Silber
    cell_line_color = np.array([25, 55, 115], dtype=np.uint8)  # Dunklere Linien
    
    panels_drawn = 0
    
    for panel in solar_panels:
        center = panel.get("center", {})
        panel_lat = center.get("latitude")
        panel_lon = center.get("longitude")
        orientation = panel.get("orientation", "LANDSCAPE")
        
        if not panel_lat or not panel_lon:
            continue
        
        # Panel-Zentrum zu Pixel
        cx, cy = geo_to_pixel(panel_lat, panel_lon)
        
        # Panel-Ausrichtung
        if orientation == "PORTRAIT":
            pw, ph = panel_h_px, panel_w_px  # Gedreht
        else:
            pw, ph = panel_w_px, panel_h_px
        
        # Panel-Eckpunkte
        x1 = cx - pw // 2
        y1 = cy - ph // 2
        x2 = x1 + pw
        y2 = y1 + ph
        
        # Bildgrenzen prüfen
        if x1 < 0 or y1 < 0 or x2 >= width or y2 >= height:
            continue
        
        # Panel-Fläche zeichnen (semi-transparent)
        for c in range(3):
            result_image[y1:y2, x1:x2, c] = (
                0.75 * panel_color[c] + 
                0.25 * result_image[y1:y2, x1:x2, c]
            ).astype(np.uint8)
        
        # Rahmen
        result_image[y1, x1:x2, :] = frame_color
        result_image[y2-1, x1:x2, :] = frame_color
        result_image[y1:y2, x1, :] = frame_color
        result_image[y1:y2, x2-1, :] = frame_color
        
        # Zellen-Gitter (horizontal)
        for i in range(1, 6):
            hy = y1 + (ph * i) // 6
            if hy < y2:
                result_image[hy, x1:x2, :] = cell_line_color
        
        # Zellen-Gitter (vertikal)
        for i in range(1, 4):
            vx = x1 + (pw * i) // 4
            if vx < x2:
                result_image[y1:y2, vx, :] = cell_line_color
        
        panels_drawn += 1
    
    print(f"   ✅ {panels_drawn} Panels gezeichnet")
    
    # 6. Ergebnis speichern
    result_img = Image.fromarray(result_image)
    output_file = OUTPUT_DIR / f"{building_id}_panels_v3.png"
    result_img.save(output_file, "PNG", quality=95)
    print(f"\n💾 Gespeichert: {output_file}")
    
    # Original speichern
    original_img = Image.fromarray(rgb_array)
    original_file = OUTPUT_DIR / f"{building_id}_original_v3.png"
    original_img.save(original_file, "PNG")
    
    # Vergleichsbild
    comparison = Image.new('RGB', (width * 2 + 20, height), color=(40, 40, 40))
    comparison.paste(original_img, (0, 0))
    comparison.paste(result_img, (width + 20, 0))
    
    draw = ImageDraw.Draw(comparison)
    try:
        from PIL import ImageFont
        font = ImageFont.truetype("arial.ttf", 24)
    except:
        font = None
    
    kwp = panels_drawn * panel_capacity / 1000
    draw.text((10, 10), "Original", fill=(255, 255, 255), font=font)
    draw.text((width + 30, 10), f"{panels_drawn} Panels = {kwp:.1f} kWp", 
              fill=(255, 255, 255), font=font)
    
    comparison_file = OUTPUT_DIR / f"{building_id}_comparison_v3.png"
    comparison.save(comparison_file, "PNG")
    print(f"💾 Vergleich: {comparison_file}")
    
    # Statistik
    yearly_kwh = sum(p.get("yearlyEnergyDcKwh", 0) for p in solar_panels[:panels_drawn])
    
    print("\n" + "=" * 50)
    print("📊 ERGEBNIS")
    print("=" * 50)
    print(f"Gebäude: {building_id}")
    print(f"Position: {lat}, {lon}")
    print(f"Gezeichnete Panels: {panels_drawn}")
    print(f"Leistung: {kwp:.1f} kWp")
    print(f"Jahresertrag (Google): {yearly_kwh:,.0f} kWh")
    
    return str(comparison_file)


if __name__ == "__main__":
    # Test mit rank_002
    result = create_panel_visualization_v3(
        lat=51.564617, 
        lon=7.424936, 
        building_id="rank_002",
        max_panels=None  # Alle Panels
    )
    
    if result:
        import subprocess
        subprocess.run(["start", result], shell=True)
