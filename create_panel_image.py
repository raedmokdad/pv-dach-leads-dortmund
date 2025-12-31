"""
PV-Panel Visualisierung - Finale Version
Verwendet exakte Google Panel-Koordinaten und gleiche Bounds für RGB/Maske.
"""

import requests
import json
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
from dotenv import load_dotenv
import rasterio
from rasterio.io import MemoryFile
from pyproj import Transformer

load_dotenv()
API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GOOGLE_SOLAR_API_KEY")

OUTPUT_DIR = Path("data/final/dortmund/panel_visualizations")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def create_panel_visualization(lat: float, lon: float, building_id: str = "building"):
    """Erstellt Panel-Visualisierung mit exakten Google-Koordinaten."""
    
    print(f"\n🔆 Panel-Visualisierung für {building_id}")
    print("=" * 50)
    
    # 1. Building Insights abrufen
    print("\n📊 Lade Building Insights...")
    resp = requests.get(
        "https://solar.googleapis.com/v1/buildingInsights:findClosest",
        params={
            "location.latitude": lat,
            "location.longitude": lon,
            "requiredQuality": "LOW",
            "key": API_KEY
        },
        timeout=30
    )
    
    if resp.status_code != 200:
        print(f"❌ API-Fehler: {resp.status_code}")
        return None
    
    data = resp.json()
    solar = data.get("solarPotential", {})
    
    # Panel-Spezifikationen
    panel_height = solar.get("panelHeightMeters", 1.879)
    panel_width = solar.get("panelWidthMeters", 1.045)
    panel_capacity = solar.get("panelCapacityWatts", 400)
    
    # Exakte Panel-Positionen
    panels = solar.get("solarPanels", [])
    
    if not panels:
        print("❌ Keine Panel-Positionen verfügbar")
        return None
    
    print(f"   Panels verfügbar: {len(panels)}")
    print(f"   Panel-Größe: {panel_width}m x {panel_height}m")
    
    # 2. Berechne Zentrum aller Panels für Bildanfrage
    panel_lats = [p["center"]["latitude"] for p in panels]
    panel_lons = [p["center"]["longitude"] for p in panels]
    center_lat = (min(panel_lats) + max(panel_lats)) / 2
    center_lon = (min(panel_lons) + max(panel_lons)) / 2
    
    # Berechne Radius
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:32632", always_xy=True)
    min_x, min_y = transformer.transform(min(panel_lons), min(panel_lats))
    max_x, max_y = transformer.transform(max(panel_lons), max(panel_lats))
    
    extent = max(max_x - min_x, max_y - min_y)
    radius = extent / 2 + 20  # 20m Puffer
    
    print(f"   Panel-Ausdehnung: {max_x - min_x:.0f}m x {max_y - min_y:.0f}m")
    
    # 3. DataLayers laden (RGB und Maske)
    print("\n📥 Lade Luftbild...")
    
    layers_resp = requests.get(
        "https://solar.googleapis.com/v1/dataLayers:get",
        params={
            "location.latitude": center_lat,
            "location.longitude": center_lon,
            "radiusMeters": min(radius, 175),
            "view": "FULL_LAYERS",
            "requiredQuality": "LOW",
            "pixelSizeMeters": 0.25,
            "key": API_KEY
        },
        timeout=60
    )
    
    if layers_resp.status_code != 200:
        print(f"❌ DataLayers-Fehler: {layers_resp.status_code}")
        return None
    
    layers = layers_resp.json()
    rgb_url = layers.get("rgbUrl")
    
    if not rgb_url:
        print("❌ Kein RGB verfügbar")
        return None
    
    # RGB laden
    rgb_resp = requests.get(f"{rgb_url}&key={API_KEY}", timeout=60)
    
    with MemoryFile(rgb_resp.content) as memfile:
        with memfile.open() as ds:
            bounds = ds.bounds
            width, height = ds.width, ds.height
            pixel_size = (bounds.right - bounds.left) / width
            
            r = ds.read(1)
            g = ds.read(2)
            b = ds.read(3)
            rgb = np.stack([r, g, b], axis=-1)
    
    print(f"   Bildgröße: {width}x{height} Pixel")
    print(f"   Auflösung: {pixel_size:.2f} m/Pixel")
    
    # 4. Panels zeichnen
    print("\n🔲 Zeichne Panels...")
    
    result = rgb.copy()
    
    # Panel-Größe in Pixeln
    pw = int(panel_width / pixel_size)
    ph = int(panel_height / pixel_size)
    
    print(f"   Panel in Pixeln: {pw}x{ph}")
    
    # Farben für realistische PV-Module
    panel_dark = np.array([25, 35, 60], dtype=np.float32)   # Dunkles Blau (Zellen)
    panel_mid = np.array([35, 55, 90], dtype=np.float32)    # Mittleres Blau
    frame_color = np.array([180, 185, 190], dtype=np.uint8)  # Aluminium-Rahmen
    
    panels_drawn = 0
    
    for panel in panels:
        center = panel.get("center", {})
        plat = center.get("latitude")
        plon = center.get("longitude")
        orientation = panel.get("orientation", "LANDSCAPE")
        
        if not plat or not plon:
            continue
        
        # Zu Pixel konvertieren
        px_utm, py_utm = transformer.transform(plon, plat)
        cx = int((px_utm - bounds.left) / pixel_size)
        cy = int((bounds.top - py_utm) / pixel_size)
        
        # Panel-Größe basierend auf Orientierung
        if orientation == "PORTRAIT":
            w, h = ph, pw
        else:
            w, h = pw, ph
        
        # Eckpunkte
        x1 = cx - w // 2
        y1 = cy - h // 2
        x2 = x1 + w
        y2 = y1 + h
        
        # Bildgrenzen
        if x1 < 1 or y1 < 1 or x2 >= width - 1 or y2 >= height - 1:
            continue
        
        # Panel-Fläche zeichnen (dunkelblau, semi-transparent)
        alpha = 0.85
        for c in range(3):
            result[y1:y2, x1:x2, c] = (
                alpha * panel_dark[c] + 
                (1 - alpha) * result[y1:y2, x1:x2, c]
            ).astype(np.uint8)
        
        # Rahmen (2 Pixel dick)
        result[y1:y1+2, x1:x2, :] = frame_color
        result[y2-2:y2, x1:x2, :] = frame_color
        result[y1:y2, x1:x1+2, :] = frame_color
        result[y1:y2, x2-2:x2, :] = frame_color
        
        # Zellen-Raster
        cell_color = np.array([20, 30, 50], dtype=np.uint8)
        
        # Horizontale Linien
        for i in range(1, 6):
            ly = y1 + (h * i) // 6
            if y1 < ly < y2:
                result[ly, x1+2:x2-2, :] = cell_color
        
        # Vertikale Linien
        for i in range(1, 10):
            lx = x1 + (w * i) // 10
            if x1 < lx < x2:
                result[y1+2:y2-2, lx, :] = cell_color
        
        panels_drawn += 1
    
    print(f"   ✅ {panels_drawn} Panels gezeichnet")
    
    # 5. Speichern
    result_img = Image.fromarray(result)
    original_img = Image.fromarray(rgb)
    
    # Einzelbilder
    result_file = OUTPUT_DIR / f"{building_id}_with_panels.png"
    original_file = OUTPUT_DIR / f"{building_id}_original.png"
    result_img.save(result_file, "PNG")
    original_img.save(original_file, "PNG")
    
    # Vergleichsbild
    comparison = Image.new('RGB', (width * 2 + 20, height + 60), color=(30, 30, 30))
    comparison.paste(original_img, (0, 30))
    comparison.paste(result_img, (width + 20, 30))
    
    draw = ImageDraw.Draw(comparison)
    try:
        font = ImageFont.truetype("arial.ttf", 20)
    except:
        font = ImageFont.load_default()
    
    kwp = panels_drawn * panel_capacity / 1000
    yearly_kwh = sum(p.get("yearlyEnergyDcKwh", 0) for p in panels)
    
    draw.text((10, 5), "Original", fill=(255, 255, 255), font=font)
    draw.text((width + 30, 5), f"Mit PV-Anlage: {panels_drawn} Module = {kwp:.0f} kWp", 
              fill=(255, 255, 255), font=font)
    
    # Legende unten
    draw.text((10, height + 35), 
              f"Jahresertrag: {yearly_kwh:,.0f} kWh | CO2-Einsparung: ~{yearly_kwh * 0.4:,.0f} kg/Jahr",
              fill=(200, 200, 200), font=font)
    
    comparison_file = OUTPUT_DIR / f"{building_id}_vergleich.png"
    comparison.save(comparison_file, "PNG")
    
    print(f"\n💾 Gespeichert:")
    print(f"   - {result_file}")
    print(f"   - {comparison_file}")
    
    # Statistik
    print("\n" + "=" * 50)
    print("📊 ERGEBNIS")
    print("=" * 50)
    print(f"Gebäude: {building_id}")
    print(f"Module: {panels_drawn}")
    print(f"Leistung: {kwp:.1f} kWp")
    print(f"Jahresertrag: {yearly_kwh:,.0f} kWh")
    
    return str(comparison_file)


if __name__ == "__main__":
    import subprocess
    
    result = create_panel_visualization(
        lat=51.564617,
        lon=7.424936,
        building_id="rank_002"
    )
    
    if result:
        subprocess.run(["start", result], shell=True)
