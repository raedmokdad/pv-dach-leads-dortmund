"""
Download aerial images for top leads from NRW WMS service
"""

import geopandas as gpd
import requests
import math
from pathlib import Path
from time import sleep
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
from .config import STAGING_DORTMUND, FINAL_DORTMUND, EXPORT_TOPK, CRS_EXPORT


def calculate_dynamic_buffer(footprint_area_m2: float, context_buffer_m: float = 40) -> float:
    """
    Berechnet dynamischen Buffer basierend auf Gebäudegröße.
    
    Idee: Buffer = Gebäude-Radius + fester Kontext-Puffer
    → Gebäude nimmt immer 40-60% des Bildes ein
    
    Args:
        footprint_area_m2: Gebäudefläche in m²
        context_buffer_m: Zusätzlicher Kontext um Gebäude (Meter)
    
    Returns:
        Buffer in Grad (WGS84)
    
    Beispiele:
        500 m² → ~55m Buffer → 0.0005°
        2000 m² → ~90m Buffer → 0.0008°
        10000 m² → ~152m Buffer → 0.0014°
    """
    # Berechne Gebäude-Radius (als wäre Gebäude kreisförmig)
    building_radius_m = math.sqrt(footprint_area_m2 / math.pi)
    
    # Gesamter Buffer = Gebäude-Radius + Kontext
    total_buffer_m = building_radius_m + context_buffer_m
    
    # Konvertiere Meter zu Grad (ungefähr: 1° ≈ 111 km)
    buffer_degrees = total_buffer_m / 111000
    
    # Sicherheitsgrenzen: Min 33m, Max 330m
    buffer_degrees = max(0.0003, min(buffer_degrees, 0.003))
    
    return buffer_degrees


def download_aerial_image(lat: float, lon: float, output_path: Path, 
                          width: int = 800, height: int = 600, 
                          buffer: float = None, footprint_area_m2: float = None) -> bool:
    """
    Download aerial image from NRW WMS service.
    
    Args:
        lat: Latitude (WGS84)
        lon: Longitude (WGS84)
        output_path: Path to save image
        width: Image width in pixels
        height: Image height in pixels
        buffer: Geographic buffer around point (degrees). If None, calculated from footprint_area_m2
        footprint_area_m2: Building footprint area in m². Used for dynamic buffer calculation
    
    Returns:
        True if successful, False otherwise
    """
    # Dynamischer Buffer basierend auf Gebäudegröße (falls nicht explizit angegeben)
    if buffer is None:
        if footprint_area_m2 is not None:
            buffer = calculate_dynamic_buffer(footprint_area_m2)
        else:
            buffer = 0.0015  # Fallback: mittlerer Wert (~165m)
    
    base_url = "https://www.wms.nrw.de/geobasis/wms_nw_dop"
    
    # Calculate bounding box (EPSG:4326)
    # WICHTIG: WMS 1.3.0 mit EPSG:4326 erwartet lat,lon Reihenfolge!
    bbox = f"{lat-buffer},{lon-buffer},{lat+buffer},{lon+buffer}"
    
    params = {
        'SERVICE': 'WMS',
        'VERSION': '1.3.0',
        'REQUEST': 'GetMap',
        'LAYERS': 'nw_dop_rgb',
        'STYLES': '',
        'CRS': 'EPSG:4326',
        'BBOX': bbox,
        'WIDTH': str(width),
        'HEIGHT': str(height),
        'FORMAT': 'image/jpeg'
    }
    
    try:
        response = requests.get(base_url, params=params, timeout=30)
        
        if response.status_code == 200:
            # Check if response is actually an image
            content_type = response.headers.get('Content-Type', '')
            if 'image' in content_type:
                with open(output_path, 'wb') as f:
                    f.write(response.content)
                return True
            else:
                return False
        else:
            return False
            
    except Exception as e:
        return False


def download_single_building(row_data: dict, output_dir: Path) -> tuple:
    """
    Download aerial image for a single building (thread-safe).
    
    Args:
        row_data: Dictionary mit Gebäudedaten (lat, lon, name, etc.)
        output_dir: Ausgabe-Verzeichnis
    
    Returns:
        Tuple (success: bool, filename: str)
    """
    # Create filename
    rank = row_data.get('rank', 0)
    name = row_data.get('name', 'Unbekannt')
    lat = row_data['lat']
    lon = row_data['lon']
    
    if name and name != 'Unbekannt':
        # Clean filename
        name_clean = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_'))[:30]
        filename = f"rank_{rank:03d}_{name_clean}_{lat:.6f}_{lon:.6f}.jpg"
    else:
        filename = f"rank_{rank:03d}_{lat:.6f}_{lon:.6f}.jpg"
    
    output_path = output_dir / filename
    
    # Get building area for dynamic buffer
    footprint_area = row_data.get('footprint_area_m2', None)
    
    # Download mit dynamischem Buffer
    success = download_aerial_image(lat, lon, output_path, footprint_area_m2=footprint_area)
    
    # Rate limiting (pro Thread)
    sleep(0.05)  # Kleine Pause pro Request
    
    return (success, filename)


def main():
    """
    Download aerial images for top K leads mit Threading.
    """
    print("\n" + "=" * 60)
    print("Luftbilder Download (Multi-Threaded)")
    print("=" * 60)
    
    # Load scored buildings
    scored_file = STAGING_DORTMUND / "scored_buildings.geojson"
    print(f"\nLade Gebäude: {scored_file}")
    
    if not scored_file.exists():
        raise FileNotFoundError(
            f"Gescorte Gebäude nicht gefunden: {scored_file}\n"
            f"Bitte erst Task 5.2 ausführen: python -m pv_roof_leads.score_leads"
        )
    
    buildings = gpd.read_file(scored_file)
    print(f"[OK] {len(buildings)} Gebäude geladen")
    
    # Take all buildings (not just top K)
    top_leads = buildings.copy()
    print(f"[OK] Alle {len(top_leads)} Leads ausgewählt")
    
    # Extract coordinates (berechne Centroid VORHER in projiziertem CRS)
    centroid_geom = top_leads.geometry.centroid
    
    # Transform to WGS84
    if top_leads.crs != CRS_EXPORT:
        print(f"   Transformiere von {top_leads.crs} → {CRS_EXPORT}")
        top_leads = top_leads.to_crs(CRS_EXPORT)
        centroid_geom = centroid_geom.to_crs(CRS_EXPORT)
    
    top_leads['lon'] = centroid_geom.x
    top_leads['lat'] = centroid_geom.y
    
    # Create output directory
    output_dir = FINAL_DORTMUND / "luftbilder"
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"\nSpeichere Bilder in: {output_dir}")
    
    # Download images
    print(f"\n   Lade {len(top_leads)} Luftbilder herunter (max 15 parallel)...")
    print("   (Dies dauert ca. 3-5 Minuten...)\n")
    
    success_count = 0
    failed_count = 0
    
    # Prepare data for threading
    download_tasks = []
    for idx, row in top_leads.iterrows():
        rank = idx + 1 if isinstance(idx, int) else len(download_tasks) + 1
        row_dict = row.to_dict()
        row_dict['rank'] = rank
        download_tasks.append(row_dict)
    
    # ThreadPoolExecutor für parallele Downloads
    max_workers = 15  # 15 parallele Downloads
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit alle Tasks
        future_to_data = {
            executor.submit(download_single_building, task, output_dir): task 
            for task in download_tasks
        }
        
        # Progress bar
        with tqdm(total=len(download_tasks), desc="Download") as pbar:
            for future in as_completed(future_to_data):
                success, filename = future.result()
                if success:
                    success_count += 1
                else:
                    failed_count += 1
                pbar.update(1)
    
    # Summary
    print("\n" + "=" * 60)
    print("Download abgeschlossen!")
    print("=" * 60)
    print(f"\nErgebnis:")
    print(f"   [OK] Erfolgreich: {success_count}")
    print(f"   [FEHLER] Fehlgeschlagen: {failed_count}")
    print(f"   Verzeichnis: {output_dir}")
    print(f"\nOeffne Verzeichnis: explorer {output_dir}")


if __name__ == '__main__':
    main()
