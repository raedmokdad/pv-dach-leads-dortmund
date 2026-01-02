"""
Erstellt einen umfassenden HTML-Report mit allen Daten:
- ALKIS: Adresse, Funktion, Fläche
- Google Solar API: Panels, Sonnenstunden, Dachsegmente
- Gemini: Dachmaterial, Zustand, Hindernisse
- PV-Status: Bestehende Anlagen

Verwendung:
    python -m pv_roof_leads.create_complete_report --city dortmund
"""

import argparse
import json
from pathlib import Path
from datetime import datetime
import geopandas as gpd

from pv_roof_leads.paths import FINAL_DORTMUND, PROCESSED_DORTMUND


def get_paths(city: str = "dortmund"):
    """Gibt die Pfade für die angegebene Stadt zurück"""
    base = Path("data")
    return {
        'geojson': base / "processed" / city / "buildings_complete.geojson",
        'gemini': base / "final" / city / "gemini_roof_analysis.json",
        'images': base / "final" / city / "luftbilder",
        'output': base / "final" / city / "complete_buildings_report.html"
    }

# Fallback für direkten Import (Rückwärtskompatibilität)
GEOJSON_FILE = PROCESSED_DORTMUND / "buildings_complete.geojson"
GEMINI_RESULTS = FINAL_DORTMUND / "gemini_roof_analysis.json"
IMAGES_DIR = FINAL_DORTMUND / "luftbilder"
OUTPUT_FILE = FINAL_DORTMUND / "complete_buildings_report.html"


def load_data(city: str = "dortmund"):
    """Lädt alle Datenquellen"""
    print("📂 Lade Daten...")
    
    paths = get_paths(city)
    
    # GeoJSON mit Solar-Daten
    geojson_path = paths['geojson']
    if not geojson_path.exists():
        # Fallback für alte Struktur
        geojson_path = PROCESSED_DORTMUND / "buildings_complete_v2.geojson"
    
    gdf = gpd.read_file(geojson_path)
    print(f"  ✓ {len(gdf)} Gebäude aus {geojson_path.name}")
    
    # Gemini Ergebnisse
    gemini_data = {}
    gemini_path = paths['gemini']
    if gemini_path.exists():
        with open(gemini_path, 'r', encoding='utf-8') as f:
            gemini_data = json.load(f)
        print(f"  ✓ {len(gemini_data)} Gemini-Analysen")
    
    return gdf, gemini_data, paths


def get_material_color(material):
    """Farbe für Dachmaterial"""
    colors = {
        'Ziegel': '#dc2626',
        'Beton': '#6b7280',
        'Metall': '#3b82f6',
        'Bitumen': '#1f2937',
        'Schiefer': '#4b5563',
        'Gründach': '#22c55e',
        'Unbekannt': '#9ca3af'
    }
    return colors.get(material, '#9ca3af')


def get_condition_badge(condition):
    """Badge für Dachzustand"""
    badges = {
        'Gut': ('✓ Gut', '#dcfce7', '#166534'),
        'Mittel': ('◐ Mittel', '#fef3c7', '#92400e'),
        'Schlecht': ('✗ Schlecht', '#fee2e2', '#991b1b'),
        'Unbekannt': ('? Unbekannt', '#f3f4f6', '#6b7280')
    }
    text, bg, color = badges.get(condition, badges['Unbekannt'])
    return f'<span style="background:{bg};color:{color};padding:2px 8px;border-radius:4px;font-size:0.85em;">{text}</span>'


def format_obstacles(obstacles):
    """Formatiert Hindernisse als HTML - gruppiert nach Typ"""
    if not obstacles:
        return '<span style="color:#9ca3af;">Keine erkannt</span>'
    
    # Zähle Hindernisse nach Typ
    from collections import Counter
    type_counts = Counter()
    for obs in obstacles:
        obs_type = obs.get('type', 'Unbekannt')
        type_counts[obs_type] += 1
    
    # Formatiere als "5× Lüftung, 3× Fenster"
    items = []
    for obs_type, count in type_counts.most_common():
        if count > 1:
            label = f'{count}× {obs_type}'
        else:
            label = obs_type
        items.append(f'<span style="background:#fef3c7;color:#92400e;padding:2px 6px;border-radius:3px;font-size:0.8em;margin-right:4px;">{label}</span>')
    
    return ' '.join(items)


def generate_html(gdf, gemini_data):
    """Generiert den HTML-Report"""
    print("\n🔨 Generiere HTML-Report...")
    
    # Statistiken berechnen
    total = len(gdf)
    
    # Flexibel: Prüfe welche Spalten vorhanden sind
    if 'solar_api_success' in gdf.columns:
        with_solar = len(gdf[gdf['solar_api_success'] == True])
    elif 'solar_max_array_panels_count' in gdf.columns:
        with_solar = len(gdf[gdf['solar_max_array_panels_count'] > 0])
    elif 'google_solar_available' in gdf.columns:
        with_solar = len(gdf[gdf['google_solar_available'] == True])
    else:
        with_solar = len(gdf[gdf['google_solar_panels_max'] > 0])
    
    # Gemini-Daten sind jetzt direkt in der GeoJSON
    if 'roof_material' in gdf.columns:
        with_gemini = len(gdf[gdf['roof_material'].notna() & (gdf['roof_material'] != 'Unbekannt')])
    else:
        with_gemini = len(gemini_data)
    
    # PV aus MaStR-Daten oder Gemini-Erkennung
    if 'has_existing_pv' in gdf.columns:
        with_pv_mastr = len(gdf[gdf['has_existing_pv'] == True])
    else:
        with_pv_mastr = 0
    
    # PV aus Gemini-Erkennung (direkt aus GeoJSON oder separate Datei)
    if 'has_existing_pv' in gdf.columns:
        with_pv_gemini = len(gdf[gdf['has_existing_pv'] == True])
    else:
        with_pv_gemini = sum(1 for d in gemini_data.values() if d.get('has_pv', False))
    with_pv = max(with_pv_mastr, with_pv_gemini)  # Nehme das Maximum
    
    # Material-Statistiken (direkt aus GeoJSON oder separate Datei)
    material_stats = {}
    condition_stats = {}
    if 'roof_material' in gdf.columns:
        # Daten direkt aus GeoJSON
        for _, row in gdf.iterrows():
            mat = row.get('roof_material', 'Unbekannt') or 'Unbekannt'
            cond = row.get('roof_condition', 'Unbekannt') or 'Unbekannt'
            if mat and mat != 'Unbekannt':
                material_stats[mat] = material_stats.get(mat, 0) + 1
            if cond and cond != 'Unbekannt':
                condition_stats[cond] = condition_stats.get(cond, 0) + 1
    else:
        # Fallback auf separate Datei
        for img_name, data in gemini_data.items():
            if data.get('analysis_success'):
                mat = data.get('roof_material', 'Unbekannt')
                cond = data.get('roof_condition', 'Unbekannt')
                material_stats[mat] = material_stats.get(mat, 0) + 1
                condition_stats[cond] = condition_stats.get(cond, 0) + 1
    
    # HTML Header
    html = f'''<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Kompletter PV-Dach Report - Dortmund</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1e3a5f 0%, #0d1b2a 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{
            max-width: 1600px;
            margin: 0 auto;
            background: #f8f9fa;
            border-radius: 15px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.3);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #1e3a5f 0%, #0d1b2a 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}
        .header h1 {{ font-size: 2.2em; margin-bottom: 5px; }}
        .header p {{ opacity: 0.8; }}
        
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            padding: 20px;
            background: white;
        }}
        .stat-card {{
            background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
            padding: 20px;
            border-radius: 10px;
            text-align: center;
            border: 1px solid #e2e8f0;
        }}
        .stat-card h3 {{ color: #1e3a5f; font-size: 1.8em; }}
        .stat-card p {{ color: #64748b; font-size: 0.85em; }}
        
        .material-stats {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            padding: 15px 20px;
            background: #f1f5f9;
            border-top: 1px solid #e2e8f0;
        }}
        .material-badge {{
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 0.85em;
            font-weight: 500;
            color: white;
        }}
        
        .filters {{
            padding: 20px;
            background: white;
            border-top: 1px solid #e2e8f0;
        }}
        .filter-row {{
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
            align-items: center;
        }}
        .filter-item label {{ font-weight: 500; color: #374151; margin-right: 5px; }}
        .filter-item select, .filter-item input {{
            padding: 8px 12px;
            border: 1px solid #d1d5db;
            border-radius: 6px;
            font-size: 0.9em;
        }}
        button {{
            background: linear-gradient(135deg, #1e3a5f 0%, #0d1b2a 100%);
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 6px;
            cursor: pointer;
            font-weight: 500;
        }}
        button:hover {{ opacity: 0.9; }}
        
        .results-info {{
            padding: 12px 20px;
            background: #1e3a5f;
            color: white;
            font-size: 0.95em;
        }}
        
        .buildings-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 20px;
            padding: 20px;
            max-height: 75vh;
            overflow-y: auto;
        }}
        
        @media (max-width: 1200px) {{
            .buildings-grid {{ grid-template-columns: 1fr; }}
        }}
        
        .building-card {{
            background: white;
            border-radius: 12px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.08);
            overflow: hidden;
            border: 1px solid #e2e8f0;
            display: grid;
            grid-template-columns: 280px 1fr;
        }}
        .building-card.has-pv {{ border-left: 5px solid #22c55e; }}
        
        .building-image-section {{
            position: relative;
        }}
        .building-image {{
            width: 100%;
            height: 100%;
            min-height: 300px;
            object-fit: cover;
            background: #e2e8f0;
        }}
        .material-overlay {{
            position: absolute;
            top: 10px;
            left: 10px;
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 0.8em;
            font-weight: 600;
            color: white;
        }}
        .pv-overlay {{
            position: absolute;
            top: 10px;
            right: 10px;
            background: #22c55e;
            color: white;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.75em;
            font-weight: 600;
        }}
        
        .building-info {{
            padding: 15px;
            display: flex;
            flex-direction: column;
        }}
        .building-header {{
            border-bottom: 1px solid #e2e8f0;
            padding-bottom: 10px;
            margin-bottom: 10px;
        }}
        .building-name {{
            font-weight: 600;
            font-size: 1.1em;
            color: #1e293b;
        }}
        .building-address {{
            color: #64748b;
            font-size: 0.9em;
            margin-top: 3px;
        }}
        
        .info-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
            font-size: 0.85em;
        }}
        .info-item {{
            display: flex;
            justify-content: space-between;
            padding: 6px 0;
            border-bottom: 1px solid #f1f5f9;
        }}
        .info-label {{ color: #64748b; }}
        .info-value {{ font-weight: 500; color: #1e293b; text-align: right; }}
        
        .section-title {{
            font-weight: 600;
            color: #1e3a5f;
            font-size: 0.9em;
            margin-top: 12px;
            margin-bottom: 8px;
            padding-top: 8px;
            border-top: 1px solid #e2e8f0;
        }}
        
        .obstacles-row {{
            margin-top: 8px;
        }}
        
        .map-links {{
            margin-top: auto;
            padding-top: 10px;
            border-top: 1px solid #e2e8f0;
        }}
        .map-links a {{
            color: #1e3a5f;
            text-decoration: none;
            font-size: 0.85em;
            margin-right: 15px;
        }}
        .map-links a:hover {{ text-decoration: underline; }}
        
        .footer {{
            padding: 20px;
            text-align: center;
            background: #1e293b;
            color: #94a3b8;
            font-size: 0.9em;
        }}
        
        .no-image {{
            width: 100%;
            height: 100%;
            min-height: 300px;
            background: linear-gradient(135deg, #e2e8f0 0%, #cbd5e1 100%);
            display: flex;
            align-items: center;
            justify-content: center;
            color: #94a3b8;
            font-size: 3em;
        }}
        
        .load-more-container {{
            text-align: center;
            padding: 30px;
            background: #f8fafc;
        }}
        .load-more-btn {{
            background: linear-gradient(135deg, #1e3a5f 0%, #0d1b2a 100%);
            color: white;
            border: none;
            padding: 15px 40px;
            font-size: 1.1em;
            border-radius: 8px;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        .load-more-btn:hover {{
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(0,0,0,0.3);
        }}
        .load-more-btn:disabled {{
            background: #94a3b8;
            cursor: not-allowed;
            transform: none;
            box-shadow: none;
        }}
        .load-progress {{
            margin-top: 10px;
            color: #64748b;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🏢 Kompletter PV-Dach Report</h1>
            <p>Dortmund</p>
        </div>
        
        <div class="stats">
            <div class="stat-card">
                <h3>{total:,}</h3>
                <p>Gebäude gesamt</p>
            </div>
            <div class="stat-card">
                <h3>{with_solar:,}</h3>
                <p>Mit Solar-Daten</p>
            </div>
            <div class="stat-card">
                <h3>{with_gemini:,}</h3>
                <p>Mit KI-Analyse</p>
            </div>
            <div class="stat-card">
                <h3>{with_pv:,}</h3>
                <p>Mit bestehender PV</p>
            </div>
            <div class="stat-card">
                <h3>{condition_stats.get('Gut', 0):,}</h3>
                <p>Dach "Gut"</p>
            </div>
            <div class="stat-card">
                <h3>{sum(1 for d in gemini_data.values() if d.get('obstacle_count', 0) > 0):,}</h3>
                <p>Mit Hindernissen</p>
            </div>
        </div>
        
        <div class="material-stats">
            <span style="color:#374151;font-weight:500;margin-right:10px;">Dachmaterial:</span>
'''
    
    # Material-Badges
    for mat, count in sorted(material_stats.items(), key=lambda x: -x[1]):
        color = get_material_color(mat)
        html += f'<span class="material-badge" style="background:{color};">{mat}: {count}</span>\n'
    
    html += '''
        </div>
        
        <div class="filters">
            <div class="filter-row">
                <div class="filter-item">
                    <label>Ausrichtung:</label>
                    <select id="filterAusrichtung">
                        <option value="">Alle</option>
                        <option value="sued">Süd (optimal)</option>
                        <option value="ost-west">Ost/West (gut)</option>
                        <option value="nord">Nord (schlecht)</option>
                    </select>
                </div>
                <div class="filter-item">
                    <label>Dachneigung:</label>
                    <select id="filterDachform">
                        <option value="">Alle</option>
                        <option value="Flachdach">Flachdach (0-10°)</option>
                        <option value="Flach geneigt">Flach geneigt (10-25°)</option>
                        <option value="Steildach">Steildach (25-45°)</option>
                        <option value="Sehr steil">Sehr steil (>45°)</option>
                    </select>
                </div>
                <div class="filter-item">
                    <label>Zustand:</label>
                    <select id="filterCondition">
                        <option value="">Alle</option>
                        <option value="Gut">Gut</option>
                        <option value="Mittel">Mittel</option>
                        <option value="Schlecht">Schlecht</option>
                    </select>
                </div>
                <div class="filter-item">
                    <label>PV vorhanden:</label>
                    <select id="filterPV">
                        <option value="">Alle</option>
                        <option value="no">Ohne PV ⭐</option>
                        <option value="yes">Mit PV</option>
                    </select>
                </div>
            </div>
            <div class="filter-row" style="margin-top:10px;">
                <div class="filter-item">
                    <label>Min. Panels:</label>
                    <input type="number" id="minPanels" value="0" min="0" style="width:80px;">
                </div>
                <div class="filter-item">
                    <label>Min. kWh/Jahr:</label>
                    <input type="number" id="minKwh" value="0" min="0" style="width:100px;">
                </div>
                <div class="filter-item">
                    <label>Max. Hindernisse:</label>
                    <input type="number" id="maxObstacles" value="" min="0" style="width:80px;" placeholder="∞">
                </div>
                <div class="filter-item">
                    <label>Material:</label>
                    <select id="filterMaterial">
                        <option value="">Alle</option>
                        <option value="Ziegel">Ziegel</option>
                        <option value="Beton">Beton</option>
                        <option value="Metall">Metall</option>
                        <option value="Bitumen">Bitumen</option>
                        <option value="Schiefer">Schiefer</option>
                        <option value="Gründach">Gründach</option>
                    </select>
                </div>
                <button onclick="applyFilters()">🔍 Filter anwenden</button>
                <button onclick="resetFilters()" style="background:#64748b;">↺ Zurücksetzen</button>
            </div>
        </div>
        
        <div class="results-info" id="resultsInfo">
            Lade Gebäude...
        </div>
        
        <div class="buildings-grid" id="buildingsGrid">
        </div>
        
        <div class="load-more-container" id="loadMoreContainer">
            <button class="load-more-btn" id="loadMoreBtn" onclick="loadMore()">
                Weitere 50 Gebäude laden
            </button>
            <div class="load-progress" id="loadProgress"></div>
        </div>
'''
    
    # Gebäude-Karten generieren
    buildings_data = []
    import math
    
    def safe_float(val, default=0):
        """Konvertiert NaN zu default"""
        if val is None:
            return default
        try:
            if math.isnan(val):
                return default
        except (TypeError, ValueError):
            pass
        return val
    
    def safe_int(val, default=0):
        """Konvertiert zu int, NaN zu default"""
        val = safe_float(val, default)
        try:
            return int(val)
        except (TypeError, ValueError):
            return default
    
    # Erstelle Bild-Lookup basierend auf Koordinaten mit Toleranz-Matching
    import os
    image_coords = []  # Liste von (lat, lon, filename)
    if IMAGES_DIR.exists():
        for img_file in IMAGES_DIR.glob("*.jpg"):
            # Extrahiere Koordinaten aus Bildname: building_X_LAT_LON.jpg
            parts = img_file.stem.split('_')
            if len(parts) >= 4:
                try:
                    lat = float(parts[2])
                    lon = float(parts[3])
                    image_coords.append((lat, lon, img_file.name))
                except:
                    pass
    
    def find_nearest_image(lat, lon, tolerance=0.0002):
        """Finde nächstes Bild innerhalb Toleranz (~20m)"""
        for img_lat, img_lon, img_name in image_coords:
            if abs(lat - img_lat) < tolerance and abs(lon - img_lon) < tolerance:
                return img_name
        return ''
    
    for idx, row in gdf.iterrows():
        # Bild über solar_rgb_image oder Koordinaten finden
        image_name = row.get('solar_rgb_image', '')
        if not image_name:
            # Versuche über Koordinaten zu finden (mit Toleranz-Matching)
            lat = row.geometry.centroid.y
            lon = row.geometry.centroid.x
            image_name = find_nearest_image(lat, lon)
        
        gemini = gemini_data.get(image_name, {}) if image_name else {}
        
        # Daten extrahieren
        address = row.get('lagebeztxt', row.get('name', 'Unbekannte Adresse'))
        funktion = row.get('funktion', row.get('building', 'Unbekannt'))
        area = safe_float(row.get('area_m2', row.get('footprint_area_m2', 0)))
        
        # Solar API Daten - flexibel für beide Dateiformate
        max_panels = safe_int(row.get('solar_max_array_panels_count', row.get('google_solar_panels_max', 0)))
        sunshine_hours = safe_float(row.get('solar_max_sunshine_hours_per_year', row.get('google_solar_sunshine_hours', 0)))
        panel_area = safe_float(row.get('solar_max_array_area_m2', row.get('google_solar_area_m2', 0)))
        co2_offset = safe_float(row.get('solar_carbon_offset_kg_per_mwh', row.get('google_solar_co2_offset_kg', 0)))
        
        # Neue Felder: Pitch, Azimuth, Flächen
        pitch = safe_float(row.get('google_solar_best_pitch', 0))
        azimuth = safe_float(row.get('google_solar_best_azimuth', 0))
        total_roof_area = safe_float(row.get('google_solar_total_roof_area_m2', 0))
        usable_roof_area = total_roof_area * safe_float(row.get('google_solar_usable_roof_pct', 0)) / 100
        
        # Dachform aus Neigung ableiten
        def get_dachform(pitch_deg):
            if pitch_deg < 10:
                return 'Flachdach'
            elif pitch_deg < 25:
                return 'Flach geneigt'
            elif pitch_deg < 45:
                return 'Steildach'
            else:
                return 'Sehr steil'
        
        dachform = get_dachform(pitch)
        
        # Ausrichtung als Text
        def azimuth_to_direction(az):
            if az == 0:
                return '-'
            directions = [
                (0, 'Nord'), (45, 'Nord-Ost'), (90, 'Ost'), (135, 'Süd-Ost'),
                (180, 'Süd'), (225, 'Süd-West'), (270, 'West'), (315, 'Nord-West'), (360, 'Nord')
            ]
            for deg, name in reversed(directions):
                if az >= deg - 22.5:
                    return name
            return 'Nord'
        
        ausrichtung = azimuth_to_direction(azimuth)
        
        # PV Status - Gemini erkennt PV auf Luftbildern, has_existing_pv aus MaStR
        # Jetzt sind Gemini-Daten direkt in row oder in gemini dict
        gemini_has_pv = gemini.get('has_pv', row.get('has_existing_pv', False))
        mastr_has_pv = row.get('has_existing_pv', False)
        has_pv = gemini_has_pv or mastr_has_pv
        
        # Gemini Daten - zuerst aus row, dann aus gemini dict
        roof_material = row.get('roof_material') or gemini.get('roof_material', 'Unbekannt') or 'Unbekannt'
        roof_condition = row.get('roof_condition') or gemini.get('roof_condition', 'Unbekannt') or 'Unbekannt'
        roof_color = row.get('roof_color') or gemini.get('roof_color', '-') or '-'
        obstacle_count = row.get('obstacle_count') if 'obstacle_count' in row.index else gemini.get('obstacle_count', 0)
        obstacles = row.get('obstacles') if 'obstacles' in row.index and row.get('obstacles') else gemini.get('obstacles', [])
        usable_pct = row.get('usable_roof_percentage') if 'usable_roof_percentage' in row.index else gemini.get('usable_roof_percentage', '-')
        complexity = row.get('installation_complexity') if 'installation_complexity' in row.index else gemini.get('installation_complexity', '-')
        notes = gemini.get('notes', '')
        
        # Koordinaten - aus Geometry extrahieren falls nicht vorhanden
        if 'lat' in row.index and row.get('lat'):
            lat = row.get('lat', 0)
            lon = row.get('lon', 0)
        else:
            lat = row.geometry.centroid.y
            lon = row.geometry.centroid.x
        
        # Bild-Pfad - solar_rgb_image enthält bereits den vollen Pfad (luftbilder/...)
        if image_name and image_name.startswith('luftbilder/'):
            img_path = image_name
        elif image_name:
            img_path = f"luftbilder/{image_name}"
        else:
            img_path = ""
        
        # Material-Farbe
        mat_color = get_material_color(roof_material)
        
        # Geschätzte jährliche Produktion (400W Panels, Sonnenstunden)
        est_kwh = safe_int(max_panels * 0.4 * sunshine_hours) if max_panels and sunshine_hours else 0
        
        buildings_data.append({
            'address': address,
            'funktion': funktion,
            'area': area,
            'max_panels': max_panels,
            'sunshine_hours': sunshine_hours,
            'has_pv': has_pv,
            'roof_material': roof_material,
            'roof_condition': roof_condition,
            'obstacle_count': obstacle_count,
            'lat': lat,
            'lon': lon,
            'img_path': img_path,
            'mat_color': mat_color,
            'roof_color': roof_color,
            'usable_pct': usable_pct,
            'complexity': complexity,
            'obstacles': obstacles,
            'notes': notes,
            'est_kwh': est_kwh,
            'co2_offset': co2_offset,
            'panel_area': panel_area,
            'pitch': pitch,
            'azimuth': azimuth,
            'dachform': dachform,
            'ausrichtung': ausrichtung,
            'total_roof_area': total_roof_area,
            'usable_roof_area': usable_roof_area
        })
    
    # Nach Panels sortieren (höchste zuerst)
    buildings_data.sort(key=lambda x: -(x['max_panels'] or 0))
    
    # Obstacles zu Text konvertieren für JSON
    def format_obstacles_text(obstacles):
        if not obstacles:
            return "Keine erkannt"
        from collections import Counter
        type_counts = Counter(obs.get('type', 'Unbekannt') for obs in obstacles)
        parts = []
        for obs_type, count in type_counts.most_common():
            if count > 1:
                parts.append(f'{count}× {obs_type}')
            else:
                parts.append(obs_type)
        return ', '.join(parts)
    
    # JSON für JavaScript erstellen (nur notwendige Felder für kompaktere Größe)
    buildings_json = []
    for b in buildings_data:
        buildings_json.append({
            'a': b['address'],  # address
            'f': b['funktion'],  # funktion
            'ar': round(b['area']),  # area
            'p': b['max_panels'],  # panels
            'sh': round(b['sunshine_hours']),  # sunshine hours
            'pv': b['has_pv'],  # has_pv
            'm': b['roof_material'],  # material
            'c': b['roof_condition'],  # condition
            'oc': b['obstacle_count'],  # obstacle_count
            'o': format_obstacles_text(b['obstacles']),  # obstacles text
            'lt': round(b['lat'], 6),  # lat
            'ln': round(b['lon'], 6),  # lon
            'i': b['img_path'],  # image
            'mc': b['mat_color'],  # material color
            'rc': b['roof_color'],  # roof color
            'u': b['usable_pct'],  # usable %
            'x': b['complexity'],  # complexity
            'e': b['est_kwh'],  # estimated kWh
            'co': round(b['co2_offset']),  # co2 offset
            'pa': round(b['panel_area']),  # panel area
            'pt': round(b['pitch'], 1),  # pitch (Dachneigung)
            'az': round(b['azimuth'], 1),  # azimuth
            'df': b['dachform'],  # Dachform
            'au': b['ausrichtung'],  # Ausrichtung (Text)
            'tra': round(b['total_roof_area']),  # total roof area
            'ura': round(b['usable_roof_area'])  # usable roof area
        })
    
    # JSON als JavaScript-Variable einfügen
    import json as json_module
    html += f'''
        <div class="footer">
            <p>PV-Dach Lead-Generierung | Datenquellen: ALKIS, Google Solar API, Gemini Vision AI | © Raed Mokdad</p>
        </div>
    </div>
    
    <script>
        // Gebäude-Daten
        const allBuildings = {json_module.dumps(buildings_json, ensure_ascii=False)};
        
        let displayedCount = 0;
        let filteredBuildings = [...allBuildings];
        const BATCH_SIZE = 50;
        
        function getConditionBadge(condition) {{
            const badges = {{
                'Gut': ['✓ Gut', '#dcfce7', '#166534'],
                'Mittel': ['◐ Mittel', '#fef3c7', '#92400e'],
                'Schlecht': ['✗ Schlecht', '#fee2e2', '#991b1b'],
                'Unbekannt': ['? Unbekannt', '#f3f4f6', '#6b7280']
            }};
            const [text, bg, color] = badges[condition] || badges['Unbekannt'];
            return `<span style="background:${{bg}};color:${{color}};padding:2px 8px;border-radius:4px;font-size:0.85em;">${{text}}</span>`;
        }}
        
        function createBuildingCard(b) {{
            const pvClass = b.pv ? 'has-pv' : '';
            const pvBadge = b.pv ? '<div class="pv-overlay">✓ PV vorhanden</div>' : '';
            const imgHtml = b.i ? `<img class="building-image" src="${{b.i}}" alt="Dachbild" loading="lazy">` : '<div class="no-image">🏢</div>';
            const conditionHtml = getConditionBadge(b.c);
            
            return `
                <div class="building-card ${{pvClass}}" 
                     data-material="${{b.m}}" 
                     data-condition="${{b.c}}"
                     data-panels="${{b.p}}"
                     data-pv="${{b.pv}}">
                    <div class="building-image-section">
                        ${{imgHtml}}
                        <div class="material-overlay" style="background:${{b.mc}};">${{b.m}}</div>
                        ${{pvBadge}}
                    </div>
                    <div class="building-info">
                        <div class="building-header">
                            <div class="building-name">${{b.a}}</div>
                            <div class="building-address">${{b.f}}</div>
                        </div>
                        
                        <div class="info-grid">
                            <div class="info-item">
                                <span class="info-label">Fläche</span>
                                <span class="info-value">${{b.ar.toLocaleString('de-DE')}} m²</span>
                            </div>
                            <div class="info-item">
                                <span class="info-label">Max. Panels</span>
                                <span class="info-value">${{b.p.toLocaleString('de-DE')}}</span>
                            </div>
                            <div class="info-item">
                                <span class="info-label">Sonnenstunden</span>
                                <span class="info-value">${{b.sh}} h/Jahr</span>
                            </div>
                            <div class="info-item">
                                <span class="info-label">Panel-Fläche</span>
                                <span class="info-value">${{b.pa.toLocaleString('de-DE')}} m²</span>
                            </div>
                        </div>
                        
                        <div class="section-title">🏠 Dachdetails (Google Solar)</div>
                        <div class="info-grid">
                            <div class="info-item">
                                <span class="info-label">Dachform</span>
                                <span class="info-value">${{b.df}}</span>
                            </div>
                            <div class="info-item">
                                <span class="info-label">Neigung</span>
                                <span class="info-value">${{b.pt}}°</span>
                            </div>
                            <div class="info-item">
                                <span class="info-label">Ausrichtung</span>
                                <span class="info-value">${{b.au}}</span>
                            </div>
                            <div class="info-item">
                                <span class="info-label">Azimuth</span>
                                <span class="info-value">${{b.az}}°</span>
                            </div>
                            <div class="info-item">
                                <span class="info-label">Gesamtfläche</span>
                                <span class="info-value">${{b.tra.toLocaleString('de-DE')}} m²</span>
                            </div>
                            <div class="info-item">
                                <span class="info-label">Nutzbare Fläche</span>
                                <span class="info-value">${{b.ura.toLocaleString('de-DE')}} m²</span>
                            </div>
                        </div>
                        
                        <div class="section-title">🔍 KI-Analyse (Gemini)</div>
                        <div class="info-grid">
                            <div class="info-item">
                                <span class="info-label">Dachfarbe</span>
                                <span class="info-value">${{b.rc}}</span>
                            </div>
                            <div class="info-item">
                                <span class="info-label">Zustand</span>
                                <span class="info-value">${{conditionHtml}}</span>
                            </div>
                            <div class="info-item">
                                <span class="info-label">Nutzbar</span>
                                <span class="info-value">${{b.u}}%</span>
                            </div>
                            <div class="info-item">
                                <span class="info-label">Komplexität</span>
                                <span class="info-value">${{b.x}}</span>
                            </div>
                        </div>
                        
                        <div class="obstacles-row">
                            <span class="info-label">Hindernisse (${{b.oc}}):</span> 
                            <span style="background:#fef3c7;color:#92400e;padding:2px 6px;border-radius:3px;font-size:0.8em;">${{b.o}}</span>
                        </div>
                        
                        <div class="section-title">⚡ Geschätzte Produktion</div>
                        <div class="info-grid">
                            <div class="info-item">
                                <span class="info-label">Jahresertrag</span>
                                <span class="info-value" style="color:#22c55e;font-weight:600;">${{b.e.toLocaleString('de-DE')}} kWh</span>
                            </div>
                            <div class="info-item">
                                <span class="info-label">CO₂-Offset</span>
                                <span class="info-value">${{b.co}} kg/MWh</span>
                            </div>
                        </div>
                        
                        <div class="map-links">
                            <a href="https://www.google.com/maps?q=${{b.lt}},${{b.ln}}" target="_blank">📍 Google Maps</a>
                            <a href="https://www.openstreetmap.org/?mlat=${{b.lt}}&mlon=${{b.ln}}&zoom=18" target="_blank">🗺️ OpenStreetMap</a>
                        </div>
                    </div>
                </div>`;
        }}
        
        function renderBuildings(buildings, append = false) {{
            const grid = document.getElementById('buildingsGrid');
            if (!append) {{
                grid.innerHTML = '';
                displayedCount = 0;
            }}
            
            const endIdx = Math.min(displayedCount + BATCH_SIZE, buildings.length);
            for (let i = displayedCount; i < endIdx; i++) {{
                grid.insertAdjacentHTML('beforeend', createBuildingCard(buildings[i]));
            }}
            displayedCount = endIdx;
            
            updateUI();
        }}
        
        function updateUI() {{
            document.getElementById('resultsInfo').textContent = 
                `Zeige ${{displayedCount}} von ${{filteredBuildings.length}} Gebäuden`;
            
            const loadMoreBtn = document.getElementById('loadMoreBtn');
            const loadProgress = document.getElementById('loadProgress');
            
            if (displayedCount >= filteredBuildings.length) {{
                loadMoreBtn.disabled = true;
                loadMoreBtn.textContent = 'Alle Gebäude geladen';
                loadProgress.textContent = '';
            }} else {{
                loadMoreBtn.disabled = false;
                loadMoreBtn.textContent = `Weitere ${{Math.min(BATCH_SIZE, filteredBuildings.length - displayedCount)}} Gebäude laden`;
                loadProgress.textContent = `${{filteredBuildings.length - displayedCount}} weitere verfügbar`;
            }}
        }}
        
        function loadMore() {{
            renderBuildings(filteredBuildings, true);
        }}
        
        function applyFilters() {{
            const material = document.getElementById('filterMaterial').value;
            const condition = document.getElementById('filterCondition').value;
            const minPanels = parseInt(document.getElementById('minPanels').value) || 0;
            const minKwh = parseInt(document.getElementById('minKwh').value) || 0;
            const maxObstacles = document.getElementById('maxObstacles').value;
            const pvFilter = document.getElementById('filterPV').value;
            const ausrichtung = document.getElementById('filterAusrichtung').value;
            const dachform = document.getElementById('filterDachform').value;
            
            filteredBuildings = allBuildings.filter(b => {{
                if (material && b.m !== material) return false;
                if (condition && b.c !== condition) return false;
                if (b.p < minPanels) return false;
                if (b.e < minKwh) return false;
                if (maxObstacles !== '' && b.oc > parseInt(maxObstacles)) return false;
                if (pvFilter === 'yes' && !b.pv) return false;
                if (pvFilter === 'no' && b.pv) return false;
                if (dachform && b.df !== dachform) return false;
                
                // Ausrichtungs-Filter
                if (ausrichtung) {{
                    const az = b.au; // Ausrichtung als Text
                    if (ausrichtung === 'sued') {{
                        if (!az.includes('Süd') && az !== 'Süd') return false;
                    }} else if (ausrichtung === 'ost-west') {{
                        if (!az.includes('Ost') && !az.includes('West')) return false;
                    }} else if (ausrichtung === 'nord') {{
                        if (az !== 'Nord' && !az.includes('Nord-')) return false;
                    }}
                }}
                
                return true;
            }});
            
            renderBuildings(filteredBuildings, false);
        }}
        
        function resetFilters() {{
            document.getElementById('filterMaterial').value = '';
            document.getElementById('filterCondition').value = '';
            document.getElementById('minPanels').value = '0';
            document.getElementById('minKwh').value = '0';
            document.getElementById('maxObstacles').value = '';
            document.getElementById('filterPV').value = '';
            document.getElementById('filterAusrichtung').value = '';
            document.getElementById('filterDachform').value = '';
            filteredBuildings = [...allBuildings];
            renderBuildings(filteredBuildings, false);
        }}
        
        // Initial load
        renderBuildings(allBuildings, false);
    </script>
</body>
</html>
'''
    
    return html


def main():
    parser = argparse.ArgumentParser(description='Erstellt HTML-Report')
    parser.add_argument('--city', default='dortmund', help='Stadt (default: dortmund)')
    args = parser.parse_args()
    
    print("=" * 60)
    print(f"📊 KOMPLETTER PV-DACH REPORT GENERATOR - {args.city.upper()}")
    print("=" * 60)
    
    gdf, gemini_data, paths = load_data(args.city)
    html = generate_html(gdf, gemini_data)
    
    output_file = paths['output']
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"\n💾 Speichere Report...")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"✅ Report erstellt: {output_file}")
    print(f"   Größe: {output_file.stat().st_size / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    main()
