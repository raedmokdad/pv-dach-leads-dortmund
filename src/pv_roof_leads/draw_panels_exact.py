"""
Zeichnet PV-Panels auf Luftbilder mit EXAKTEM Matching.
Verwendet die ID aus dem GeoJSON um die richtige Cache-Datei zu finden.
"""
import json
import math
from pathlib import Path
from PIL import Image, ImageDraw
import geopandas as gpd
from concurrent.futures import ThreadPoolExecutor, as_completed

# Pfade
GEOJSON_FILE = Path('data/processed/dortmund/buildings_with_google_solar.geojson')
CACHE_DIR = Path('data/processed/dortmund/google_solar_cache')
IMAGES_DIR = Path('data/final/dortmund/luftbilder')
OUTPUT_DIR = Path('data/final/dortmund/luftbilder_mit_panels')


def lat_lon_to_pixel(panel_lat, panel_lon, center_lat, center_lon, img_width, img_height):
    """Rechnet Lat/Lon zu Pixel-Koordinaten um."""
    meters_per_lat = 111320
    meters_per_lon = 111320 * math.cos(math.radians(center_lat))
    
    dlat_meters = (panel_lat - center_lat) * meters_per_lat
    dlon_meters = (panel_lon - center_lon) * meters_per_lon
    
    pixel_size = 0.5  # 0.5m pro Pixel bei Zoom 20
    dx_pixels = dlon_meters / pixel_size
    dy_pixels = -dlat_meters / pixel_size
    
    x = img_width / 2 + dx_pixels
    y = img_height / 2 + dy_pixels
    
    return int(x), int(y)


def draw_panels_on_image(img_path, panels, center_lat, center_lon, output_path):
    """Zeichnet Panels auf ein Bild."""
    try:
        img = Image.open(img_path)
        draw = ImageDraw.Draw(img, 'RGBA')
        img_width, img_height = img.size
        
        panel_count = 0
        for panel in panels:
            panel_center = panel.get('center', {})
            panel_lat = panel_center.get('latitude', 0)
            panel_lon = panel_center.get('longitude', 0)
            
            if panel_lat == 0 or panel_lon == 0:
                continue
            
            x, y = lat_lon_to_pixel(panel_lat, panel_lon, center_lat, center_lon, img_width, img_height)
            
            # Nur zeichnen wenn im Bild
            if 0 <= x < img_width and 0 <= y < img_height:
                # Panel als kleines Rechteck (3x2 Pixel)
                draw.rectangle([x-1, y-1, x+1, y], fill=(25, 55, 110, 240))
                panel_count += 1
        
        if panel_count > 0:
            img.save(output_path, 'JPEG', quality=85)
            return panel_count
        
        return 0
    except Exception as e:
        print(f"Fehler bei {img_path.name}: {e}")
        return 0


def main():
    print("=" * 60)
    print("PV-PANELS AUF BILDER ZEICHNEN (EXAKTES MATCHING)")
    print("=" * 60)
    
    # Lade GeoJSON
    print("\n1. Lade GeoJSON...")
    gdf = gpd.read_file(GEOJSON_FILE)
    print(f"   {len(gdf)} Gebäude geladen")
    
    # Erstelle Output-Ordner
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Erstelle Lookup: Koordinaten -> (ID, Bild-Pfad)
    print("\n2. Erstelle Koordinaten-Lookup...")
    coord_to_data = {}
    for idx, row in gdf.iterrows():
        building_id = int(row['id'])
        lat = row.geometry.centroid.y
        lon = row.geometry.centroid.x
        
        # Bildname basiert auf Koordinaten
        # Format: building_X_LAT_LON.jpg - finde das passende Bild
        key = f"{lat:.6f}_{lon:.6f}"
        coord_to_data[key] = {
            'id': building_id,
            'lat': lat,
            'lon': lon
        }
    
    # Finde alle Bilder
    print("\n3. Finde Bilder...")
    images = list(IMAGES_DIR.glob('*.jpg'))
    print(f"   {len(images)} Bilder gefunden")
    
    # Verarbeite Bilder
    print("\n4. Zeichne Panels...")
    processed = 0
    total_panels = 0
    errors = 0
    
    for i, img_path in enumerate(images):
        # Extrahiere Koordinaten aus Bildname
        parts = img_path.stem.split('_')
        if len(parts) < 4:
            continue
        
        try:
            img_lat = float(parts[2])
            img_lon = float(parts[3])
        except ValueError:
            continue
        
        # Finde passendes Gebäude
        key = f"{img_lat:.6f}_{img_lon:.6f}"
        
        # Exaktes Matching
        data = coord_to_data.get(key)
        
        # Falls nicht gefunden, suche mit kleiner Toleranz
        if not data:
            for coord_key, coord_data in coord_to_data.items():
                c_lat, c_lon = map(float, coord_key.split('_'))
                if abs(c_lat - img_lat) < 0.00001 and abs(c_lon - img_lon) < 0.00001:
                    data = coord_data
                    break
        
        if not data:
            continue
        
        # Lade Cache-Datei
        cache_file = CACHE_DIR / f"{data['id']}.json"
        if not cache_file.exists():
            continue
        
        with open(cache_file, 'r') as f:
            cache_data = json.load(f)
        
        panels = cache_data.get('solarPotential', {}).get('solarPanels', [])
        if not panels:
            continue
        
        # Zeichne Panels
        output_path = OUTPUT_DIR / img_path.name
        panel_count = draw_panels_on_image(
            img_path, panels, 
            data['lat'], data['lon'], 
            output_path
        )
        
        if panel_count > 0:
            processed += 1
            total_panels += panel_count
        
        if (i + 1) % 500 == 0:
            print(f"   Fortschritt: {i+1}/{len(images)} ({processed} mit Panels)")
    
    print("\n" + "=" * 60)
    print("FERTIG!")
    print("=" * 60)
    print(f"   Bilder verarbeitet: {processed}")
    print(f"   Panels gezeichnet:  {total_panels:,}")
    print(f"   Ausgabe: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
