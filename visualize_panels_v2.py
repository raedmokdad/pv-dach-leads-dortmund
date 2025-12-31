"""
PV-Panel Visualisierung V2 - Korrekte Platzierung auf dem Dach
Verwendet die Roof Segment Koordinaten von Google Solar API.
"""

import requests
import json
import os
import numpy as np
from PIL import Image, ImageDraw
from io import BytesIO
from pathlib import Path
from dotenv import load_dotenv
import math

# Lade .env Datei
load_dotenv()

# Google Solar API Key
API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GOOGLE_SOLAR_API_KEY")

if not API_KEY:
    print("❌ Kein API Key gefunden!")
    exit(1)

# Output-Verzeichnis
OUTPUT_DIR = Path("data/final/dortmund/panel_visualizations")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def get_building_insights(lat: float, lon: float):
    """Holt Building Insights mit Panel-Konfiguration."""
    url = "https://solar.googleapis.com/v1/buildingInsights:findClosest"
    params = {
        "location.latitude": lat,
        "location.longitude": lon,
        "requiredQuality": "LOW",
        "key": API_KEY
    }
    response = requests.get(url, params=params, timeout=30)
    if response.status_code == 200:
        return response.json()
    return None


def get_data_layers(lat: float, lon: float, radius_meters: float = 75):
    """Holt DataLayers von Google Solar API."""
    url = "https://solar.googleapis.com/v1/dataLayers:get"
    params = {
        "location.latitude": lat,
        "location.longitude": lon,
        "radiusMeters": radius_meters,
        "view": "FULL_LAYERS",
        "requiredQuality": "LOW",
        "pixelSizeMeters": 0.25,
        "key": API_KEY
    }
    response = requests.get(url, params=params, timeout=60)
    if response.status_code == 200:
        return response.json()
    return None


def latlon_to_pixel(lat, lon, bounds, width, height):
    """Konvertiert Lat/Lon zu Pixel-Koordinaten im UTM-Bild."""
    # Bounds sind in UTM (Meter)
    # Wir müssen lat/lon erst zu UTM konvertieren
    try:
        from pyproj import Transformer
        # WGS84 zu UTM Zone 32N
        transformer = Transformer.from_crs("EPSG:4326", "EPSG:32632", always_xy=True)
        x_utm, y_utm = transformer.transform(lon, lat)
        
        # UTM zu Pixel
        x_scale = width / (bounds.right - bounds.left)
        y_scale = height / (bounds.top - bounds.bottom)
        
        px = int((x_utm - bounds.left) * x_scale)
        py = int((bounds.top - y_utm) * y_scale)  # Y ist invertiert
        
        return px, py
    except Exception as e:
        print(f"Konvertierungsfehler: {e}")
        return None, None


def create_panel_visualization_v2(lat: float, lon: float, building_id: str = "example"):
    """Erstellt eine verbesserte Panel-Visualisierung."""
    
    import rasterio
    from rasterio.io import MemoryFile
    
    print(f"\n🔆 Panel-Visualisierung V2 für {building_id}")
    print("=" * 50)
    
    # 1. Building Insights abrufen
    print("\n📊 Lade Building Insights...")
    insights = get_building_insights(lat, lon)
    
    if not insights:
        print("❌ Keine Building Insights verfügbar")
        return None
    
    solar = insights.get("solarPotential", {})
    center = insights.get("center", {})
    center_lat = center.get("latitude", lat)
    center_lon = center.get("longitude", lon)
    
    # Panel-Info
    panel_capacity = solar.get("panelCapacityWatts", 400)
    panel_height = solar.get("panelHeightMeters", 1.879)
    panel_width = solar.get("panelWidthMeters", 1.045)
    max_panels = solar.get("maxArrayPanelsCount", 0)
    
    print(f"   Gebäude-Zentrum: {center_lat}, {center_lon}")
    print(f"   Max. Panels: {max_panels}")
    print(f"   Panel-Größe: {panel_width}m x {panel_height}m")
    
    # Solar Panel Configs (enthält Panel-Positionen!)
    panel_configs = solar.get("solarPanelConfigs", [])
    
    if panel_configs:
        # Letzte (maximale) Konfiguration nehmen
        max_config = panel_configs[-1]
        panel_count = max_config.get("panelsCount", 0)
        roof_segment_summaries = max_config.get("roofSegmentSummaries", [])
        print(f"   Panel-Konfigurationen: {len(panel_configs)}")
        print(f"   Max. Konfiguration: {panel_count} Panels")
    
    # Roof Segment Stats
    roof_segments = solar.get("roofSegmentStats", [])
    print(f"   Dachsegmente: {len(roof_segments)}")
    
    # 2. DataLayers abrufen
    print("\n📥 Lade Luftbild...")
    data_layers = get_data_layers(lat, lon, radius_meters=100)
    
    if not data_layers:
        print("❌ Keine DataLayers verfügbar")
        return None
    
    rgb_url = data_layers.get("rgbUrl")
    mask_url = data_layers.get("maskUrl")
    
    if not rgb_url:
        print("❌ Kein RGB-Bild verfügbar")
        return None
    
    # RGB herunterladen
    rgb_response = requests.get(f"{rgb_url}&key={API_KEY}", timeout=60)
    if rgb_response.status_code != 200:
        print("❌ RGB-Download fehlgeschlagen")
        return None
    
    # Maske herunterladen
    mask_array = None
    if mask_url:
        mask_response = requests.get(f"{mask_url}&key={API_KEY}", timeout=60)
        if mask_response.status_code == 200:
            with MemoryFile(mask_response.content) as memfile:
                with memfile.open() as ds:
                    mask_array = ds.read(1)
    
    # 3. Bild laden und Koordinatensystem ermitteln
    with MemoryFile(rgb_response.content) as memfile:
        with memfile.open() as ds:
            # Bild-Metadaten
            width = ds.width
            height = ds.height
            bounds = ds.bounds
            transform = ds.transform
            
            print(f"   Bildgröße: {width} x {height} Pixel")
            print(f"   Bounds: {bounds}")
            
            # RGB-Bild lesen
            r = ds.read(1)
            g = ds.read(2)
            b = ds.read(3)
            rgb_array = np.stack([r, g, b], axis=-1)
    
    # 4. Konvertierung von Lat/Lon zu Pixel
    from pyproj import Transformer
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:32632", always_xy=True)
    
    def geo_to_pixel(geo_lat, geo_lon):
        """Konvertiert Geo-Koordinaten zu Pixel."""
        x_utm, y_utm = transformer.transform(geo_lon, geo_lat)
        
        # Pixel-Koordinaten berechnen
        px = int((x_utm - bounds.left) / 0.25)  # 0.25m pro Pixel
        py = int((bounds.top - y_utm) / 0.25)   # Y invertiert
        
        return px, py
    
    # 5. Panels zeichnen basierend auf Roof Segments
    print("\n🔲 Zeichne Panels auf Dachsegmente...")
    
    result_image = rgb_array.copy()
    
    # Panel-Größe in Pixeln (0.25m pro Pixel)
    pixel_size = 0.25
    panel_w_px = int(panel_width / pixel_size)
    panel_h_px = int(panel_height / pixel_size)
    gap_px = 1  # 25cm Abstand
    
    print(f"   Panel in Pixeln: {panel_w_px} x {panel_h_px}")
    
    # Panel-Farben
    panel_color = np.array([40, 80, 160], dtype=np.uint8)  # Dunkelblau
    frame_color = np.array([180, 200, 220], dtype=np.uint8)  # Silber/Grau
    
    total_panels = 0
    
    # Für jedes Dachsegment
    for seg_idx, segment in enumerate(roof_segments):
        seg_center = segment.get("center", {})
        seg_lat = seg_center.get("latitude")
        seg_lon = seg_center.get("longitude")
        
        if not seg_lat or not seg_lon:
            continue
        
        # Segment-Fläche und Ausrichtung
        seg_stats = segment.get("stats", {})
        seg_area = seg_stats.get("areaMeters2", 0)
        seg_azimuth = segment.get("azimuthDegrees", 0)
        seg_pitch = segment.get("pitchDegrees", 0)
        
        if seg_area < 20:  # Zu kleine Segmente überspringen
            continue
        
        # Segment-Zentrum zu Pixel
        cx, cy = geo_to_pixel(seg_lat, seg_lon)
        
        # Prüfe ob Pixel im Bild
        if cx < 0 or cx >= width or cy < 0 or cy >= height:
            continue
        
        # Schätze Segment-Größe in Pixeln
        seg_radius_px = int(math.sqrt(seg_area) / pixel_size / 2)
        
        # Berechne wie viele Panels in dieses Segment passen
        panels_per_row = max(1, (seg_radius_px * 2) // (panel_w_px + gap_px))
        panels_per_col = max(1, (seg_radius_px * 2) // (panel_h_px + gap_px))
        
        # Start-Position (links oben vom Segment)
        start_x = cx - (panels_per_row * (panel_w_px + gap_px)) // 2
        start_y = cy - (panels_per_col * (panel_h_px + gap_px)) // 2
        
        # Panels in diesem Segment zeichnen
        for row in range(panels_per_col):
            for col in range(panels_per_row):
                px = start_x + col * (panel_w_px + gap_px)
                py = start_y + row * (panel_h_px + gap_px)
                
                # Prüfe Bildgrenzen
                if px < 0 or py < 0 or px + panel_w_px >= width or py + panel_h_px >= height:
                    continue
                
                # Prüfe ob auf Maske (nutzbarer Bereich)
                if mask_array is not None:
                    mask_region = mask_array[py:py+panel_h_px, px:px+panel_w_px]
                    if mask_region.size == 0 or np.mean(mask_region) < 0.7:
                        continue
                
                # Prüfe Abstand zum Segment-Zentrum
                dist = math.sqrt((px + panel_w_px/2 - cx)**2 + (py + panel_h_px/2 - cy)**2)
                if dist > seg_radius_px * 1.2:
                    continue
                
                # Panel zeichnen
                for c in range(3):
                    result_image[py:py+panel_h_px, px:px+panel_w_px, c] = (
                        0.7 * panel_color[c] + 
                        0.3 * result_image[py:py+panel_h_px, px:px+panel_w_px, c]
                    ).astype(np.uint8)
                
                # Rahmen (oben, unten, links, rechts)
                result_image[py, px:px+panel_w_px, :] = frame_color
                result_image[py+panel_h_px-1, px:px+panel_w_px, :] = frame_color
                result_image[py:py+panel_h_px, px, :] = frame_color
                result_image[py:py+panel_h_px, px+panel_w_px-1, :] = frame_color
                
                # Gitterlinien (horizontal in der Mitte)
                mid_y = py + panel_h_px // 2
                result_image[mid_y, px:px+panel_w_px, :] = frame_color
                
                # Gitterlinien (vertikal)
                for vline in range(1, 4):
                    vx = px + (panel_w_px * vline) // 4
                    if vx < px + panel_w_px:
                        result_image[py:py+panel_h_px, vx, :] = frame_color
                
                total_panels += 1
    
    print(f"   ✅ {total_panels} Panels platziert")
    
    # 6. Ergebnis speichern
    result_img = Image.fromarray(result_image)
    output_file = OUTPUT_DIR / f"{building_id}_panels_v2.png"
    result_img.save(output_file, "PNG")
    print(f"\n💾 Gespeichert: {output_file}")
    
    # Original speichern
    original_img = Image.fromarray(rgb_array)
    original_file = OUTPUT_DIR / f"{building_id}_original.png"
    original_img.save(original_file, "PNG")
    
    # Vergleichsbild erstellen (nebeneinander)
    comparison = Image.new('RGB', (width * 2 + 10, height), color=(255, 255, 255))
    comparison.paste(original_img, (0, 0))
    comparison.paste(result_img, (width + 10, 0))
    
    # Text hinzufügen
    from PIL import ImageFont
    draw = ImageDraw.Draw(comparison)
    try:
        font = ImageFont.truetype("arial.ttf", 20)
    except:
        font = ImageFont.load_default()
    
    draw.text((10, 10), "Original", fill=(255, 255, 255), font=font)
    draw.text((width + 20, 10), f"Mit {total_panels} Panels ({total_panels * panel_capacity / 1000:.1f} kWp)", 
              fill=(255, 255, 255), font=font)
    
    comparison_file = OUTPUT_DIR / f"{building_id}_comparison.png"
    comparison.save(comparison_file, "PNG")
    print(f"💾 Vergleich: {comparison_file}")
    
    # Statistik
    kwp = total_panels * panel_capacity / 1000
    yearly_kwh = kwp * 950  # Schätzung: 950 kWh/kWp in Deutschland
    
    print("\n" + "=" * 50)
    print("📊 ERGEBNIS")
    print("=" * 50)
    print(f"Gebäude: {building_id}")
    print(f"Position: {lat}, {lon}")
    print(f"Platzierte Panels: {total_panels}")
    print(f"Leistung: {kwp:.1f} kWp")
    print(f"Geschätzter Jahresertrag: {yearly_kwh:,.0f} kWh")
    
    return str(comparison_file)


if __name__ == "__main__":
    # Test mit rank_002
    result = create_panel_visualization_v2(51.564617, 7.424936, "rank_002")
    
    if result:
        import subprocess
        subprocess.run(["start", result], shell=True)
