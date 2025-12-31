"""
PV-Panel Visualisierung auf Luftbild
Verwendet Google Solar API DataLayers für:
- Hochauflösendes Luftbild
- Dachmaske (nutzbare Flächen)
- Sonneneinstrahlung (Flux)

Die Panels werden korrekt auf dem Dach positioniert.
"""

import requests
import json
import os
import numpy as np
from PIL import Image
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


def get_data_layers(lat: float, lon: float, radius_meters: float = 50):
    """
    Holt DataLayers von Google Solar API.
    Enthält: Luftbild, Dachmaske, Sonneneinstrahlung, Höhendaten.
    """
    url = "https://solar.googleapis.com/v1/dataLayers:get"
    
    params = {
        "location.latitude": lat,
        "location.longitude": lon,
        "radiusMeters": radius_meters,
        "view": "FULL_LAYERS",  # Alle Layer
        "requiredQuality": "LOW",
        "pixelSizeMeters": 0.25,  # Höchste Auflösung: 25cm/Pixel
        "key": API_KEY
    }
    
    print(f"\n🔍 Lade DataLayers für {lat}, {lon}...")
    
    response = requests.get(url, params=params, timeout=60)
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"❌ API-Fehler {response.status_code}: {response.text}")
        return None


def download_geotiff(url: str, api_key: str) -> bytes:
    """Lädt ein GeoTIFF von der URL herunter."""
    full_url = f"{url}&key={api_key}"
    response = requests.get(full_url, timeout=60)
    if response.status_code == 200:
        return response.content
    return None


def geotiff_to_image(geotiff_bytes: bytes) -> np.ndarray:
    """Konvertiert GeoTIFF-Bytes zu einem NumPy-Array."""
    try:
        # Versuche mit rasterio (besser für GeoTIFF)
        import rasterio
        from rasterio.io import MemoryFile
        
        with MemoryFile(geotiff_bytes) as memfile:
            with memfile.open() as dataset:
                # Lese alle Bänder
                if dataset.count >= 3:
                    # RGB
                    r = dataset.read(1)
                    g = dataset.read(2)
                    b = dataset.read(3)
                    return np.stack([r, g, b], axis=-1)
                else:
                    # Einzelnes Band (Maske, Flux, etc.)
                    return dataset.read(1)
    except ImportError:
        # Fallback: PIL (funktioniert nicht für alle GeoTIFFs)
        try:
            img = Image.open(BytesIO(geotiff_bytes))
            return np.array(img)
        except:
            return None


def create_panel_visualization(lat: float, lon: float, building_id: str = "example"):
    """
    Erstellt eine Visualisierung mit PV-Panels auf dem Dach.
    """
    
    # 1. Building Insights abrufen (für Panel-Konfiguration)
    print("\n📊 Lade Building Insights...")
    insights_url = "https://solar.googleapis.com/v1/buildingInsights:findClosest"
    insights_params = {
        "location.latitude": lat,
        "location.longitude": lon,
        "requiredQuality": "LOW",
        "key": API_KEY
    }
    
    insights_response = requests.get(insights_url, params=insights_params, timeout=30)
    if insights_response.status_code != 200:
        print(f"❌ Keine Building Insights verfügbar")
        return None
    
    insights = insights_response.json()
    solar_potential = insights.get("solarPotential", {})
    
    # Panel-Info
    panel_capacity = solar_potential.get("panelCapacityWatts", 400)
    panel_height = solar_potential.get("panelHeightMeters", 1.65)
    panel_width = solar_potential.get("panelWidthMeters", 0.99)
    max_panels = solar_potential.get("maxArrayPanelsCount", 0)
    
    print(f"   Max. Panels: {max_panels}")
    print(f"   Panel-Größe: {panel_width}m x {panel_height}m")
    
    # Roof Segments
    roof_segments = solar_potential.get("roofSegmentStats", [])
    print(f"   Dachsegmente: {len(roof_segments)}")
    
    # 2. DataLayers abrufen
    data_layers = get_data_layers(lat, lon, radius_meters=75)
    
    if not data_layers:
        print("❌ Keine DataLayers verfügbar")
        return None
    
    # Verfügbare Layer ausgeben
    print("\n📦 Verfügbare DataLayers:")
    for key in data_layers.keys():
        if key != "imageryDate":
            print(f"   - {key}")
    
    # 3. RGB-Luftbild herunterladen
    rgb_url = data_layers.get("rgbUrl")
    mask_url = data_layers.get("maskUrl")
    flux_url = data_layers.get("annualFluxUrl")
    
    if not rgb_url:
        print("❌ Kein RGB-Bild verfügbar")
        return None
    
    print("\n📥 Lade Bilder...")
    
    # RGB-Bild
    print("   - RGB Luftbild...")
    rgb_bytes = download_geotiff(rgb_url, API_KEY)
    if not rgb_bytes:
        print("❌ RGB-Download fehlgeschlagen")
        return None
    
    # Speichere RGB als Datei zur Prüfung
    rgb_file = OUTPUT_DIR / f"{building_id}_rgb.tif"
    with open(rgb_file, 'wb') as f:
        f.write(rgb_bytes)
    print(f"   ✅ RGB gespeichert: {rgb_file}")
    
    # Maske herunterladen
    mask_array = None
    if mask_url:
        print("   - Dachmaske...")
        mask_bytes = download_geotiff(mask_url, API_KEY)
        if mask_bytes:
            mask_file = OUTPUT_DIR / f"{building_id}_mask.tif"
            with open(mask_file, 'wb') as f:
                f.write(mask_bytes)
            print(f"   ✅ Maske gespeichert: {mask_file}")
    
    # Flux herunterladen
    if flux_url:
        print("   - Sonneneinstrahlung (Flux)...")
        flux_bytes = download_geotiff(flux_url, API_KEY)
        if flux_bytes:
            flux_file = OUTPUT_DIR / f"{building_id}_flux.tif"
            with open(flux_file, 'wb') as f:
                f.write(flux_bytes)
            print(f"   ✅ Flux gespeichert: {flux_file}")
    
    # 4. Versuche die Bilder zu verarbeiten
    print("\n🎨 Verarbeite Bilder...")
    
    try:
        import rasterio
        from rasterio.io import MemoryFile
        
        # RGB-Bild laden
        with MemoryFile(rgb_bytes) as memfile:
            with memfile.open() as rgb_dataset:
                # Bild-Metadaten
                print(f"   Bildgröße: {rgb_dataset.width} x {rgb_dataset.height} Pixel")
                print(f"   CRS: {rgb_dataset.crs}")
                print(f"   Bounds: {rgb_dataset.bounds}")
                
                # RGB-Bänder lesen
                r = rgb_dataset.read(1)
                g = rgb_dataset.read(2)
                b = rgb_dataset.read(3)
                rgb_array = np.stack([r, g, b], axis=-1)
                
                # Transformation für Geo-Koordinaten zu Pixel
                transform = rgb_dataset.transform
        
        # Maske laden falls vorhanden
        if mask_bytes:
            with MemoryFile(mask_bytes) as memfile:
                with memfile.open() as mask_dataset:
                    mask_array = mask_dataset.read(1)
                    print(f"   Maske-Werte: min={mask_array.min()}, max={mask_array.max()}")
        
        # 5. Panel-Positionen berechnen und zeichnen
        print("\n🔲 Zeichne Panels auf Dach...")
        
        # Kopie des RGB-Bildes für Overlay
        result_image = rgb_array.copy()
        
        # Panel-Farbe (semi-transparent blau)
        panel_color = np.array([30, 80, 180], dtype=np.uint8)  # Dunkelblau
        
        # Wenn wir eine Maske haben, zeichne Panels auf maskierte Bereiche
        if mask_array is not None:
            # Maske: Werte > 0 sind nutzbare Dachflächen
            usable_mask = mask_array > 0
            
            # Pixel-Größe in Metern
            pixel_size_m = 0.25  # 25cm pro Pixel (wie angefordert)
            
            # Panel-Größe in Pixeln
            panel_width_px = int(panel_width / pixel_size_m)
            panel_height_px = int(panel_height / pixel_size_m)
            
            print(f"   Panel in Pixeln: {panel_width_px} x {panel_height_px}")
            
            # Abstand zwischen Panels (für Wartung)
            gap_px = int(0.1 / pixel_size_m)  # 10cm Abstand
            
            # Finde zusammenhängende Dachbereiche
            from scipy import ndimage
            labeled_mask, num_features = ndimage.label(usable_mask)
            
            print(f"   Gefundene Dachbereiche: {num_features}")
            
            panels_placed = 0
            max_panels_to_place = min(max_panels, 500)  # Limit für Performance
            
            # Für jeden Dachbereich
            for region_id in range(1, num_features + 1):
                if panels_placed >= max_panels_to_place:
                    break
                
                # Bereich extrahieren
                region_mask = labeled_mask == region_id
                region_pixels = np.sum(region_mask)
                
                # Nur größere Bereiche
                min_pixels = panel_width_px * panel_height_px * 2
                if region_pixels < min_pixels:
                    continue
                
                # Bounding Box des Bereichs
                rows = np.any(region_mask, axis=1)
                cols = np.any(region_mask, axis=0)
                y_min, y_max = np.where(rows)[0][[0, -1]]
                x_min, x_max = np.where(cols)[0][[0, -1]]
                
                # Panels im Bereich platzieren (Raster)
                y = y_min + gap_px
                while y + panel_height_px < y_max and panels_placed < max_panels_to_place:
                    x = x_min + gap_px
                    while x + panel_width_px < x_max and panels_placed < max_panels_to_place:
                        # Prüfe ob alle Pixel des Panels auf nutzbarer Fläche sind
                        panel_area = region_mask[y:y+panel_height_px, x:x+panel_width_px]
                        
                        if panel_area.shape[0] == panel_height_px and panel_area.shape[1] == panel_width_px:
                            coverage = np.mean(panel_area)
                            
                            if coverage > 0.9:  # 90% der Panel-Fläche muss nutzbar sein
                                # Panel zeichnen
                                for c in range(3):
                                    # Semi-transparent: 60% Panel, 40% Original
                                    result_image[y:y+panel_height_px, x:x+panel_width_px, c] = (
                                        0.6 * panel_color[c] + 
                                        0.4 * result_image[y:y+panel_height_px, x:x+panel_width_px, c]
                                    ).astype(np.uint8)
                                
                                # Rahmen zeichnen (1 Pixel)
                                result_image[y, x:x+panel_width_px, :] = [200, 200, 200]  # Oben
                                result_image[y+panel_height_px-1, x:x+panel_width_px, :] = [200, 200, 200]  # Unten
                                result_image[y:y+panel_height_px, x, :] = [200, 200, 200]  # Links
                                result_image[y:y+panel_height_px, x+panel_width_px-1, :] = [200, 200, 200]  # Rechts
                                
                                panels_placed += 1
                        
                        x += panel_width_px + gap_px
                    y += panel_height_px + gap_px
            
            print(f"   ✅ {panels_placed} Panels platziert")
        
        # 6. Ergebnis speichern
        result_img = Image.fromarray(result_image)
        
        # Als PNG speichern
        output_file = OUTPUT_DIR / f"{building_id}_panels.png"
        result_img.save(output_file, "PNG")
        print(f"\n💾 Visualisierung gespeichert: {output_file}")
        
        # Auch ohne Panels speichern (zum Vergleich)
        original_img = Image.fromarray(rgb_array)
        original_file = OUTPUT_DIR / f"{building_id}_original.png"
        original_img.save(original_file, "PNG")
        print(f"💾 Original gespeichert: {original_file}")
        
        # Statistik
        print("\n" + "="*50)
        print("📊 ERGEBNIS")
        print("="*50)
        print(f"Gebäude-Position: {lat}, {lon}")
        print(f"Platzierte Panels: {panels_placed}")
        print(f"Leistung: {panels_placed * panel_capacity / 1000:.1f} kWp")
        print(f"Bilder: {OUTPUT_DIR}")
        
        return str(output_file)
        
    except ImportError as e:
        print(f"\n⚠️  Für die Bildverarbeitung wird 'rasterio' benötigt.")
        print("   Installation: pip install rasterio scipy")
        print(f"\n   Die GeoTIFF-Dateien wurden gespeichert in: {OUTPUT_DIR}")
        print("   Sie können diese mit QGIS oder ähnlichen Tools öffnen.")
        return None
    except Exception as e:
        print(f"❌ Fehler bei der Bildverarbeitung: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    print("🔆 PV-Panel Visualisierung")
    print("=" * 50)
    
    # Beispiel-Koordinaten
    # Dortmund Zentrum (großes Gebäude)
    lat = 51.5136
    lon = 7.4653
    
    # Optional: Andere Koordinaten eingeben
    try:
        user_input = input(f"\nKoordinaten eingeben (Enter für Standard {lat}, {lon}): ").strip()
        if user_input:
            parts = user_input.replace(",", " ").split()
            if len(parts) == 2:
                lat = float(parts[0])
                lon = float(parts[1])
    except:
        pass
    
    # Visualisierung erstellen
    result = create_panel_visualization(lat, lon, f"building_{lat}_{lon}")
    
    if result:
        print(f"\n✅ Fertig! Öffne: {result}")
