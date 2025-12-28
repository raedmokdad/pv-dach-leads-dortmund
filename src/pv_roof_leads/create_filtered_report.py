"""
Generate interactive HTML report for all buildings with filters.
Inline HTML generation (no external templates) for reliability.
"""

import geopandas as gpd
import pandas as pd
from pathlib import Path
from datetime import datetime
import json
from .config import PROCESSED_DORTMUND, FINAL_DORTMUND, CRS_EXPORT, PROJECT_ROOT


def create_filtered_report():
    """
    Create interactive HTML report with filters for area and PV status.
    """
    print("\n" + "=" * 60)
    print("HTML Report Generator (mit Filtern)")
    print("=" * 60)
    
    # Load buildings
    google_solar_file = PROCESSED_DORTMUND / "buildings_with_google_solar.geojson"
    buildings_file = PROCESSED_DORTMUND / "buildings_processed_with_pv_info.geojson"
    
    if google_solar_file.exists():
        print(f"\nLade Gebäude mit Google Solar Daten: {google_solar_file}")
        buildings = gpd.read_file(google_solar_file)
        print(f"[OK] {len(buildings)} Gebäude mit Google Solar API geladen")
    else:
        print(f"\nLade Gebäude: {buildings_file}")
        if not buildings_file.exists():
            raise FileNotFoundError(f"Gebäudedaten nicht gefunden: {buildings_file}")
        buildings = gpd.read_file(buildings_file)
        print(f"[OK] {len(buildings)} Gebäude geladen")
    
    # Transform to WGS84 for coordinates
    if buildings.crs != CRS_EXPORT:
        buildings = buildings.to_crs(CRS_EXPORT)
    
    # Extract coordinates from geometry
    buildings['lon'] = buildings.geometry.apply(lambda g: g.centroid.x)
    buildings['lat'] = buildings.geometry.apply(lambda g: g.centroid.y)
    
    # Build address string
    def build_address(row):
        parts = []
        if pd.notna(row.get('addr:street')):
            street = str(row.get('addr:street', ''))
            housenumber = str(row.get('addr:housenumber', ''))
            if housenumber and housenumber != 'nan':
                parts.append(f"{street} {housenumber}")
            else:
                parts.append(street)
        
        postcode = str(row.get('addr:postcode', ''))
        city = str(row.get('addr:city', ''))
        if postcode and postcode != 'nan' and city and city != 'nan':
            parts.append(f"{postcode} {city}")
        elif city and city != 'nan':
            parts.append(city)
        
        return ', '.join(parts) if parts else '-'
    
    buildings['address'] = buildings.apply(build_address, axis=1)
    
    # Prepare data
    buildings['has_pv'] = buildings['has_existing_pv'].fillna(False)
    buildings['pv_status'] = buildings['has_pv'].apply(lambda x: 'Ja' if x else 'Nein')
    buildings['pv_count'] = buildings['pv_installations_count'].fillna(0).astype(int)
    buildings['footprint_area_m2'] = buildings['footprint_area_m2'].fillna(0)
    buildings['name'] = buildings['name'].fillna('Unbekannt')
    
    # Load Google Solar detailed data (prefer extended data)
    extended_file = FINAL_DORTMUND / "roof_segments_extended.json"
    preprocessed_file = PROCESSED_DORTMUND / "roof_segments_summary.json"
    google_solar_details = {}
    
    if extended_file.exists():
        print(f"\nLade erweiterte Dach-Segment-Daten...")
        with open(extended_file, 'r', encoding='utf-8') as f:
            google_solar_details = json.load(f)
        print(f"[OK] {len(google_solar_details)} Gebäude mit erweiterten Dach-Segmenten geladen")
    elif preprocessed_file.exists():
        print(f"\nLade vorverarbeitete Dach-Segment-Daten...")
        with open(preprocessed_file, 'r', encoding='utf-8') as f:
            google_solar_details = json.load(f)
        print(f"[OK] {len(google_solar_details)} Gebäude mit Dach-Segmenten geladen")
    
    # Add building_id column if not exists
    if 'id' in buildings.columns:
        buildings['building_id'] = buildings['id'].astype(str)
    
    # Calculate statistics
    total_buildings = len(buildings)
    with_pv = int(buildings['has_pv'].sum())
    without_pv = total_buildings - with_pv
    avg_area = buildings['footprint_area_m2'].mean()
    min_area = buildings['footprint_area_m2'].min()
    max_area = buildings['footprint_area_m2'].max()
    
    # Count buildings with age information
    buildings_with_age = len(buildings[buildings['pv_min_age_years'] > 0]) if 'pv_min_age_years' in buildings.columns else 0
    
    # Load aerial images mapping
    luftbilder_dir = FINAL_DORTMUND / "luftbilder"
    luftbilder_map = {}
    if luftbilder_dir.exists():
        print(f"\nLade Luftbilder...")
        for bild in luftbilder_dir.glob('*.jpg'):
            parts = bild.stem.split('_')
            try:
                lat = round(float(parts[-2]), 5)
                lon = round(float(parts[-1]), 5)
                luftbilder_map[(lat, lon)] = bild.name
            except:
                pass
        print(f"[OK] {len(luftbilder_map)} Luftbilder gefunden")
    
    print(f"\nStatistiken:")
    print(f"  Gesamt: {total_buildings:,}")
    print(f"  Mit PV: {with_pv:,} ({with_pv/total_buildings*100:.1f}%)")
    print(f"  Ohne PV: {without_pv:,} ({without_pv/total_buildings*100:.1f}%)")
    print(f"  Durchschnittliche Fläche: {avg_area:.0f} m²")
    
    # Generate HTML
    output_file = FINAL_DORTMUND / "buildings_report_filtered.html"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"\nGeneriere HTML Report: {output_file}")
    
    # Prepare buildings data for JSON
    buildings_data = prepare_buildings_data(buildings, google_solar_details, luftbilder_map)
    buildings_json = json.dumps(buildings_data, ensure_ascii=False)
    
    # Generate HTML content
    html_content = generate_html(
        buildings_json=buildings_json,
        total_buildings=total_buildings,
        with_pv=with_pv,
        without_pv=without_pv,
        avg_area=avg_area,
        min_area=min_area,
        max_area=max_area,
        buildings_with_age=buildings_with_age
    )
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"[OK] HTML Report erstellt: {output_file}")
    print(f"[OK] Dateigröße: {output_file.stat().st_size / 1024 / 1024:.1f} MB")
    print("=" * 60)
    
    return output_file


def prepare_buildings_data(buildings_gdf, google_solar_details, luftbilder_map):
    """Convert GeoDataFrame to JSON-serializable format."""
    buildings_data = []
    
    def safe_val(val, default=''):
        if pd.isna(val) or str(val) == 'nan':
            return default
        return val
    
    for idx, row in buildings_gdf.iterrows():
        building_id = str(safe_val(row.get('id'), ''))
        
        # Get roof segment info
        has_segments = building_id in google_solar_details
        segment_info = google_solar_details.get(building_id, {})
        
        # Find matching aerial image
        lat = float(row['lat'])
        lon = float(row['lon'])
        lat_key = round(lat, 5)
        lon_key = round(lon, 5)
        image_file = luftbilder_map.get((lat_key, lon_key), '')
        
        building_data = {
            'id': building_id,
            'name': str(safe_val(row.get('name'), 'Unbekannt')),
            'address': str(safe_val(row.get('address'), '-')),
            'area': float(safe_val(row.get('footprint_area_m2'), 0)),
            'has_pv': bool(row.get('has_pv', False)),
            'pv_status': str(row.get('pv_status', 'Nein')),
            'pv_count': int(safe_val(row.get('pv_installations_count'), 0)),
            'pv_min_age': int(safe_val(row.get('pv_min_age_years'), 0)),
            'pv_max_age': int(safe_val(row.get('pv_max_age_years'), 0)),
            'lat': float(row['lat']),
            'lon': float(row['lon']),
            # Google Solar data
            'google_solar_available': str(safe_val(row.get('google_solar_available'), 'False')) == 'True',
            'google_solar_panels_max': int(safe_val(row.get('google_solar_panels_max'), 0)),
            'google_solar_area_m2': float(safe_val(row.get('google_solar_area_m2'), 0)),
            'google_solar_yearly_kwh': float(safe_val(row.get('google_solar_yearly_kwh'), 0)),
            'google_solar_best_orientation': str(safe_val(row.get('google_solar_best_orientation'), '')),
            'google_solar_best_azimuth': float(safe_val(row.get('google_solar_best_azimuth'), 0)),
            'google_solar_best_pitch': float(safe_val(row.get('google_solar_best_pitch'), 0)),
            'google_solar_sunshine_hours': float(safe_val(row.get('google_solar_sunshine_hours'), 0)),
            'google_solar_co2_offset_kg': float(safe_val(row.get('google_solar_co2_offset_kg'), 0)),
            # Roof segments (extended)
            'has_roof_segments': has_segments,
            'segment_count': len(segment_info.get('segments', [])),
            'main_roof_pitch': segment_info.get('main_pitch', 0),
            'main_roof_azimuth': segment_info.get('main_azimuth', 0),
            'main_roof_area': segment_info.get('main_area', 0),
            'segments': segment_info.get('segments', []),
            'imagery_quality': segment_info.get('imageryQuality', ''),
            'usable_roof_pct': segment_info.get('usable_pct', 0),
            'total_panels': segment_info.get('total_panels', 0),
            'configs': segment_info.get('configs', []),
            'image': image_file,
        }
        buildings_data.append(building_data)
    
    return buildings_data


def generate_html(buildings_json, total_buildings, with_pv, without_pv, avg_area, min_area, max_area, buildings_with_age):
    """Generate complete HTML with inline CSS and JavaScript."""
    
    current_date = datetime.now().strftime("%d.%m.%Y %H:%M")
    
    return f'''<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PV-Dach Gebäude Report - Dortmund</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: #f8f9fa;
            border-radius: 15px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}
        .header h1 {{ font-size: 2em; margin-bottom: 5px; }}
        .header p {{ opacity: 0.9; }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 15px;
            padding: 20px;
            background: white;
        }}
        .stat-card {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
        }}
        .stat-card h3 {{ color: #667eea; font-size: 1.8em; }}
        .stat-card p {{ color: #666; font-size: 0.9em; }}
        .filters {{
            padding: 20px;
            background: white;
            border-top: 1px solid #eee;
        }}
        .filters h2 {{ margin-bottom: 15px; color: #333; }}
        .filter-group {{
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
            margin-bottom: 15px;
        }}
        .filter-item {{ display: flex; flex-direction: column; gap: 5px; }}
        .filter-item label {{ font-weight: 500; color: #555; font-size: 0.9em; }}
        .filter-item input[type="number"] {{
            padding: 8px 12px;
            border: 1px solid #ddd;
            border-radius: 6px;
            width: 120px;
        }}
        .pv-filter {{ display: flex; gap: 10px; }}
        .pv-filter label {{ display: flex; align-items: center; gap: 5px; cursor: pointer; }}
        button {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 6px;
            cursor: pointer;
            font-weight: 500;
            margin-right: 10px;
        }}
        button:hover {{ opacity: 0.9; }}
        .results-info {{
            padding: 15px 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }}
        .buildings-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
            gap: 20px;
            padding: 20px;
            max-height: 70vh;
            overflow-y: auto;
        }}
        .building-card {{
            background: white;
            border-radius: 12px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.08);
            overflow: hidden;
            border: 1px solid #e2e8f0;
        }}
        .building-card.has-pv {{ border-left: 4px solid #10b981; }}
        .building-image {{
            width: 100%;
            height: 180px;
            object-fit: cover;
            background: #e2e8f0;
        }}
        .building-image-placeholder {{
            width: 100%;
            height: 120px;
            background: linear-gradient(135deg, #e2e8f0 0%, #cbd5e1 100%);
            display: flex;
            align-items: center;
            justify-content: center;
            color: #94a3b8;
            font-size: 2em;
        }}
        .building-header {{
            padding: 15px;
            border-bottom: 1px solid #eee;
        }}
        .pv-age {{
            margin-top: 5px;
            font-size: 0.85em;
            color: #666;
        }}
        .building-name {{ font-weight: 600; font-size: 1.1em; color: #333; }}
        .building-address {{ color: #666; font-size: 0.9em; margin-top: 3px; }}
        .building-details {{ padding: 15px; }}
        .detail-row {{
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid #f0f0f0;
        }}
        .detail-row:last-child {{ border-bottom: none; }}
        .detail-label {{ color: #888; }}
        .detail-value {{ font-weight: 500; }}
        .section-title {{
            font-weight: 600;
            color: #667eea;
            margin-top: 15px;
            margin-bottom: 10px;
            padding-top: 10px;
            border-top: 1px solid #eee;
        }}
        .pv-badge {{
            display: inline-block;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 0.85em;
            font-weight: 500;
        }}
        .pv-yes {{ background: #dcfce7; color: #166534; }}
        .pv-no {{ background: #fef3c7; color: #92400e; }}
        .map-links {{ margin-top: 10px; }}
        .map-links a {{
            display: inline-block;
            margin-right: 10px;
            color: #667eea;
            text-decoration: none;
            font-size: 0.9em;
        }}
        .map-links a:hover {{ text-decoration: underline; }}
        .footer {{
            padding: 20px;
            text-align: center;
            background: #333;
            color: white;
        }}
        .load-more {{
            text-align: center;
            padding: 20px;
        }}
        .no-results {{
            padding: 40px;
            text-align: center;
            color: #666;
        }}
        .segments-toggle {{
            background: #f0f4ff;
            border: 1px solid #667eea;
            color: #667eea;
            padding: 6px 12px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 0.85em;
            margin-top: 8px;
        }}
        .segments-toggle:hover {{ background: #e0e7ff; }}
        .segments-list {{
            display: none;
            margin-top: 10px;
            background: #f8fafc;
            border-radius: 8px;
            padding: 10px;
            border: 1px solid #e2e8f0;
        }}
        .segments-list.show {{ display: block; }}
        .segment-item {{
            display: flex;
            justify-content: space-between;
            padding: 6px 8px;
            background: white;
            margin-bottom: 5px;
            border-radius: 4px;
            border-left: 3px solid #667eea;
            font-size: 0.85em;
        }}
        .segment-item:last-child {{ margin-bottom: 0; }}
        .segment-info {{ display: flex; gap: 15px; }}
        .segment-label {{ color: #888; }}
        .quality-badge {{
            display: inline-block;
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 0.75em;
            font-weight: 500;
        }}
        .quality-HIGH {{ background: #dcfce7; color: #166534; }}
        .quality-MEDIUM {{ background: #fef3c7; color: #92400e; }}
        .quality-LOW {{ background: #fee2e2; color: #991b1b; }}
        .shading-bar {{
            width: 80px;
            height: 8px;
            background: #e5e7eb;
            border-radius: 4px;
            overflow: hidden;
            display: inline-block;
            vertical-align: middle;
            margin-left: 5px;
        }}
        .shading-fill {{
            height: 100%;
            border-radius: 4px;
        }}
        .shading-good {{ background: linear-gradient(90deg, #22c55e, #16a34a); }}
        .shading-medium {{ background: linear-gradient(90deg, #eab308, #ca8a04); }}
        .shading-poor {{ background: linear-gradient(90deg, #ef4444, #dc2626); }}
        .configs-list {{
            margin-top: 10px;
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }}
        .config-item {{
            background: #f0f9ff;
            border: 1px solid #0ea5e9;
            border-radius: 6px;
            padding: 6px 10px;
            font-size: 0.8em;
        }}
        .config-item strong {{ color: #0369a1; }}
        .segment-extended {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 5px;
            margin-top: 5px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>PV-Dach Gebäude Report</h1>
            <p>Dortmund - Erstellt am {current_date}</p>
        </div>
        
        <div class="stats">
            <div class="stat-card">
                <h3>{total_buildings:,}</h3>
                <p>Gebäude gesamt</p>
            </div>
            <div class="stat-card">
                <h3>{without_pv:,}</h3>
                <p>Ohne PV-Anlage</p>
            </div>
            <div class="stat-card">
                <h3>{with_pv:,}</h3>
                <p>Mit PV-Anlage</p>
            </div>
            <div class="stat-card">
                <h3>{buildings_with_age}</h3>
                <p>Mit Altersangabe</p>
            </div>
            <div class="stat-card">
                <h3>{avg_area:,.0f} m²</h3>
                <p>Durchschn. Fläche</p>
            </div>
        </div>
        
        <div class="filters">
            <h2>Filter</h2>
            <div class="filter-group">
                <div class="filter-item">
                    <label>Fläche von (m²):</label>
                    <input type="number" id="minArea" value="{min_area:.0f}" min="0" step="50">
                </div>
                <div class="filter-item">
                    <label>Fläche bis (m²):</label>
                    <input type="number" id="maxArea" value="{max_area:.0f}" min="0" step="50">
                </div>
                <div class="filter-item">
                    <label>Min. Jahresertrag (kWh):</label>
                    <input type="number" id="minYield" value="0" min="0" step="1000">
                </div>
                <div class="filter-item">
                    <label>Min. Panels:</label>
                    <input type="number" id="minPanels" value="0" min="0" step="10">
                </div>
                <div class="filter-item">
                    <label>PV-Anlage:</label>
                    <div class="pv-filter">
                        <label><input type="checkbox" id="filterPvYes" checked> Ja</label>
                        <label><input type="checkbox" id="filterPvNo" checked> Nein</label>
                    </div>
                </div>
            </div>
            <button onclick="applyFilters()">Filter anwenden</button>
            <button onclick="resetFilters()">Filter zurücksetzen</button>
        </div>
        
        <div class="results-info">
            Zeige <strong id="resultCount">{total_buildings:,}</strong> von <strong>{total_buildings:,}</strong> Gebäuden
        </div>
        
        <div class="buildings-grid" id="buildingsGrid"></div>
        
        <div class="load-more" id="loadMoreContainer">
            <button onclick="loadMore()">▼ Mehr laden</button>
            <div id="loadingInfo" style="margin-top: 10px; color: #666;"></div>
        </div>
        
        <div id="noResults" class="no-results" style="display: none;">
            Keine Gebäude gefunden, die den Filterkriterien entsprechen.
        </div>
        
        <div class="footer">
            <p>© 2025 PV-Dach Leads Dortmund | Raed Mokdad</p>
        </div>
    </div>
    
    <script>
        // Data
        const allBuildings = {buildings_json};
        
        // State
        let filteredBuildings = allBuildings;
        let currentPage = 0;
        const ITEMS_PER_PAGE = 50;
        
        // Initialize
        document.addEventListener('DOMContentLoaded', function() {{
            console.log('Loaded', allBuildings.length, 'buildings');
            renderBuildings(filteredBuildings.slice(0, ITEMS_PER_PAGE));
            updateLoadMore();
        }});
        
        function applyFilters() {{
            const minArea = parseFloat(document.getElementById('minArea').value) || 0;
            const maxArea = parseFloat(document.getElementById('maxArea').value) || Infinity;
            const minYield = parseFloat(document.getElementById('minYield').value) || 0;
            const minPanels = parseFloat(document.getElementById('minPanels').value) || 0;
            const showPvYes = document.getElementById('filterPvYes').checked;
            const showPvNo = document.getElementById('filterPvNo').checked;
            
            filteredBuildings = allBuildings.filter(b => {{
                const areaOk = b.area >= minArea && b.area <= maxArea;
                const yieldOk = (b.google_solar_yearly_kwh || 0) >= minYield;
                const panelsOk = (b.google_solar_panels_max || 0) >= minPanels;
                const pvOk = (b.has_pv && showPvYes) || (!b.has_pv && showPvNo);
                return areaOk && yieldOk && panelsOk && pvOk;
            }});
            
            currentPage = 0;
            renderBuildings(filteredBuildings.slice(0, ITEMS_PER_PAGE));
            document.getElementById('resultCount').textContent = filteredBuildings.length.toLocaleString('de-DE');
            updateLoadMore();
        }}
        
        function resetFilters() {{
            document.getElementById('minArea').value = {min_area:.0f};
            document.getElementById('maxArea').value = {max_area:.0f};
            document.getElementById('minYield').value = 0;
            document.getElementById('minPanels').value = 0;
            document.getElementById('filterPvYes').checked = true;
            document.getElementById('filterPvNo').checked = true;
            applyFilters();
        }}
        
        function loadMore() {{
            currentPage++;
            const start = currentPage * ITEMS_PER_PAGE;
            const end = start + ITEMS_PER_PAGE;
            const newBuildings = filteredBuildings.slice(start, end);
            
            const grid = document.getElementById('buildingsGrid');
            newBuildings.forEach(b => {{
                grid.insertAdjacentHTML('beforeend', createCard(b));
            }});
            updateLoadMore();
        }}
        
        function updateLoadMore() {{
            const shown = Math.min((currentPage + 1) * ITEMS_PER_PAGE, filteredBuildings.length);
            const container = document.getElementById('loadMoreContainer');
            const info = document.getElementById('loadingInfo');
            
            if (shown >= filteredBuildings.length) {{
                container.style.display = 'none';
            }} else {{
                container.style.display = 'block';
                info.textContent = shown + ' von ' + filteredBuildings.length + ' angezeigt';
            }}
            
            document.getElementById('noResults').style.display = 
                filteredBuildings.length === 0 ? 'block' : 'none';
        }}
        
        function renderBuildings(buildings) {{
            const grid = document.getElementById('buildingsGrid');
            grid.innerHTML = buildings.map(b => createCard(b)).join('');
        }}
        
        function createCard(b) {{
            const pvClass = b.has_pv ? 'has-pv' : '';
            const pvBadge = b.has_pv 
                ? '<span class="pv-badge pv-yes">✓ PV vorhanden</span>'
                : '<span class="pv-badge pv-no">Keine PV</span>';
            
            // PV-Alter anzeigen
            let pvAgeInfo = '';
            if (b.has_pv && (b.pv_min_age > 0 || b.pv_max_age > 0)) {{
                if (b.pv_min_age === b.pv_max_age && b.pv_min_age > 0) {{
                    pvAgeInfo = `<div class="pv-age">Alter: ca. ${{b.pv_min_age}} Jahre</div>`;
                }} else if (b.pv_min_age > 0 && b.pv_max_age > 0) {{
                    pvAgeInfo = `<div class="pv-age">Alter: ${{b.pv_min_age}}-${{b.pv_max_age}} Jahre</div>`;
                }} else if (b.pv_min_age > 0) {{
                    pvAgeInfo = `<div class="pv-age">Alter: mind. ${{b.pv_min_age}} Jahre</div>`;
                }}
            }}
            
            // Bild oder Platzhalter
            const imageHtml = b.image 
                ? `<img class="building-image" src="luftbilder/${{b.image}}" alt="Luftbild" loading="lazy" onerror="this.outerHTML='<div class=building-image-placeholder>🏢</div>'">`
                : `<div class="building-image-placeholder">🏢</div>`;
            
            let solarInfo = '';
            if (b.google_solar_available) {{
                // Berechne Leistung in kWp (ca. 400W pro Panel)
                const kwp = (b.google_solar_panels_max * 0.4).toFixed(1);
                // CO2 in Tonnen
                const co2Tons = (b.google_solar_co2_offset_kg / 1000).toFixed(1);
                
                solarInfo = `
                    <div class="section-title">☀️ Solar-Potenzial</div>
                    <div class="detail-row">
                        <span class="detail-label">Dachneigung</span>
                        <span class="detail-value">${{b.google_solar_best_pitch.toFixed(0)}}° (${{getRoofType(b.google_solar_best_pitch)}})</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Ausrichtung</span>
                        <span class="detail-value">${{b.google_solar_best_azimuth.toFixed(0)}}° (${{b.google_solar_best_orientation || getDirection(b.google_solar_best_azimuth)}})</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Nutzbare Fläche</span>
                        <span class="detail-value">${{b.google_solar_area_m2.toFixed(1)}} m²</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Max. Panels</span>
                        <span class="detail-value">${{b.google_solar_panels_max}} (≈ ${{kwp}} kWp)</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Sonnenstunden/Jahr</span>
                        <span class="detail-value">${{Math.round(b.google_solar_sunshine_hours).toLocaleString('de-DE')}} h</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Jahresertrag</span>
                        <span class="detail-value">${{Math.round(b.google_solar_yearly_kwh).toLocaleString('de-DE')}} kWh</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">CO₂-Einsparung</span>
                        <span class="detail-value">${{co2Tons}} t/Jahr</span>
                    </div>
                `;
            }}
            
            let roofInfo = '';
            if (b.has_roof_segments && b.segments && b.segments.length > 0) {{
                const qualityClass = b.imagery_quality ? 'quality-' + b.imagery_quality : '';
                const qualityBadge = b.imagery_quality ? `<span class="quality-badge ${{qualityClass}}">${{b.imagery_quality}}</span>` : '';
                
                // Erweiterte Segment-Liste mit Verschattung und Sonnenstunden
                let segmentsList = '';
                if (b.segments && b.segments.length > 0) {{
                    segmentsList = b.segments.map((seg, idx) => {{
                        const shading = seg.shading || 0;
                        const shadingPct = Math.round(shading * 100);
                        const shadingClass = shading >= 0.9 ? 'shading-good' : (shading >= 0.7 ? 'shading-medium' : 'shading-poor');
                        const panels = seg.panels || 0;
                        const yearlyKwh = seg.yearly_kwh || 0;
                        const orientation = seg.orientation || getDirection(seg.azimuth);
                        
                        return `
                            <div class="segment-item" style="flex-direction: column; align-items: flex-start;">
                                <div style="display: flex; justify-content: space-between; width: 100%; margin-bottom: 5px;">
                                    <strong>Segment ${{idx + 1}}: ${{orientation}}</strong>
                                    <span>${{seg.area_m2 || seg.area}} m²</span>
                                </div>
                                <div class="segment-extended">
                                    <span><span class="segment-label">Neigung:</span> ${{seg.pitch}}°</span>
                                    <span><span class="segment-label">Azimut:</span> ${{seg.azimuth}}°</span>
                                    <span><span class="segment-label">Panels:</span> ${{panels}}</span>
                                    <span><span class="segment-label">Ertrag:</span> ${{Math.round(yearlyKwh).toLocaleString('de-DE')}} kWh</span>
                                    <span>
                                        <span class="segment-label">Besonnung:</span> ${{shadingPct}}%
                                        <div class="shading-bar"><div class="shading-fill ${{shadingClass}}" style="width: ${{shadingPct}}%"></div></div>
                                    </span>
                                    ${{seg.sunshine_min ? `<span><span class="segment-label">☀️ Min/Max:</span> ${{Math.round(seg.sunshine_min)}}-${{Math.round(seg.sunshine_max)}} h</span>` : ''}}
                                </div>
                            </div>
                        `;
                    }}).join('');
                }}
                
                // Panel-Konfigurationen anzeigen
                let configsHtml = '';
                if (b.configs && b.configs.length > 0) {{
                    const configItems = b.configs.slice(0, 5).map(c => `
                        <div class="config-item">
                            <strong>${{c.panels_count}} Panels</strong> → ${{Math.round(c.yearly_energy_kwh).toLocaleString('de-DE')}} kWh/Jahr
                        </div>
                    `).join('');
                    configsHtml = `
                        <div class="section-title">⚡ Anlagen-Konfigurationen</div>
                        <div class="configs-list">${{configItems}}</div>
                    `;
                }}
                
                roofInfo = `
                    <div class="section-title">🏠 Dach-Analyse ${{qualityBadge}}</div>
                    ${{b.usable_roof_pct ? `
                    <div class="detail-row">
                        <span class="detail-label">Nutzbare Dachfläche</span>
                        <span class="detail-value">${{b.usable_roof_pct.toFixed(1)}}%</span>
                    </div>` : ''}}
                    <div class="detail-row">
                        <span class="detail-label">Dachsegmente</span>
                        <span class="detail-value">${{b.segment_count}}</span>
                    </div>
                    ${{b.total_panels ? `
                    <div class="detail-row">
                        <span class="detail-label">Max. Panels (alle Segmente)</span>
                        <span class="detail-value">${{b.total_panels}} (≈ ${{(b.total_panels * 0.4).toFixed(1)}} kWp)</span>
                    </div>` : ''}}
                    ${{b.segments && b.segments.length > 0 ? `
                        <button class="segments-toggle" onclick="toggleSegments(this)">📊 Alle ${{b.segment_count}} Segmente anzeigen</button>
                        <div class="segments-list">${{segmentsList}}</div>
                    ` : ''}}
                    ${{configsHtml}}
                `;
            }} else if (b.has_roof_segments && b.main_roof_pitch > 0) {{
                // Fallback für alte Daten ohne erweiterte Segmente
                const qualityClass = b.imagery_quality ? 'quality-' + b.imagery_quality : '';
                const qualityBadge = b.imagery_quality ? `<span class="quality-badge ${{qualityClass}}">${{b.imagery_quality}}</span>` : '';
                
                roofInfo = `
                    <div class="section-title">Dach-Info ${{qualityBadge}}</div>
                    <div class="detail-row">
                        <span class="detail-label">Dachneigung</span>
                        <span class="detail-value">${{b.main_roof_pitch}}° (${{getRoofType(b.main_roof_pitch)}})</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Ausrichtung</span>
                        <span class="detail-value">${{b.main_roof_azimuth}}° (${{getDirection(b.main_roof_azimuth)}})</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Hauptdach</span>
                        <span class="detail-value">${{b.main_roof_area}} m²</span>
                    </div>
                `;
            }}
            
            return `
                <div class="building-card ${{pvClass}}">
                    ${{imageHtml}}
                    <div class="building-header">
                        <div class="building-name">${{escapeHtml(b.name)}}</div>
                        <div class="building-address">${{escapeHtml(b.address)}}</div>
                    </div>
                    <div class="building-details">
                        <div class="detail-row">
                            <span class="detail-label">Fläche</span>
                            <span class="detail-value">${{Math.round(b.area).toLocaleString('de-DE')}} m²</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">PV-Status</span>
                            ${{pvBadge}}
                        </div>
                        ${{pvAgeInfo}}
                        ${{solarInfo}}
                        ${{roofInfo}}
                        <div class="map-links">
                            <a href="https://www.google.com/maps?q=${{b.lat}},${{b.lon}}" target="_blank">📍 Google Maps</a>
                            <a href="https://www.tim-online.nrw.de/tim-online2/?center=${{b.lon}},${{b.lat}}&scale=500" target="_blank">🗺️ TIM-online</a>
                        </div>
                    </div>
                </div>
            `;
        }}
        
        function escapeHtml(text) {{
            if (!text) return '';
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }}
        
        function getRoofType(pitch) {{
            if (pitch < 10) return 'Flachdach';
            if (pitch < 25) return 'Flach geneigt';
            if (pitch < 40) return 'Optimal';
            return 'Steil';
        }}
        
        function getDirection(azimuth) {{
            if (azimuth >= 337.5 || azimuth < 22.5) return 'N';
            if (azimuth < 67.5) return 'NO';
            if (azimuth < 112.5) return 'O';
            if (azimuth < 157.5) return 'SO';
            if (azimuth < 202.5) return 'S';
            if (azimuth < 247.5) return 'SW';
            if (azimuth < 292.5) return 'W';
            return 'NW';
        }}
        
        function toggleSegments(btn) {{
            const list = btn.nextElementSibling;
            const isVisible = list.classList.contains('show');
            list.classList.toggle('show');
            btn.textContent = isVisible ? 'Alle ' + list.children.length + ' Segmente anzeigen' : 'Segmente ausblenden';
        }}
    </script>
</body>
</html>'''


def main():
    """Main function"""
    create_filtered_report()


if __name__ == '__main__':
    main()
