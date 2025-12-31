"""
Integration der Gemini Dach-Analyse in den HTML-Report
Fügt Dachtyp, Material, Hindernisse und PV-Eignung hinzu
"""

import json
import pandas as pd
from pathlib import Path
from datetime import datetime

# Pfade
ROOF_ANALYSIS_FILE = Path('data/final/dortmund/roof_analysis/all_roofs_analysis.json')
IMAGES_DIR = Path('data/final/dortmund/luftbilder')
ANNOTATED_DIR = Path('data/final/dortmund/roof_analysis/annotated')
OUTPUT_DIR = Path('data/final/dortmund')


def load_roof_analysis():
    """Lädt die Dach-Analyse Ergebnisse"""
    if not ROOF_ANALYSIS_FILE.exists():
        print(f"❌ Datei nicht gefunden: {ROOF_ANALYSIS_FILE}")
        return {}
    
    with open(ROOF_ANALYSIS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def match_analysis_to_image(image_name: str, analysis_data: dict) -> dict:
    """Findet passende Analyse für ein Bild"""
    # Direkte Suche
    if image_name in analysis_data:
        return analysis_data[image_name]
    
    # Suche nach Koordinaten im Dateinamen
    for key, data in analysis_data.items():
        if image_name in key or key in image_name:
            return data
    
    return None


def create_html_report_with_roof_analysis():
    """Erstellt HTML-Report mit Dach-Analyse Daten"""
    
    print("=" * 60)
    print("HTML-REPORT MIT DACH-ANALYSE")
    print("=" * 60)
    
    # Lade Dach-Analyse
    roof_data = load_roof_analysis()
    print(f"✓ {len(roof_data)} Dach-Analysen geladen")
    
    # Finde alle Bilder
    images = sorted(IMAGES_DIR.glob('*.jpg'))
    print(f"✓ {len(images)} Luftbilder gefunden")
    
    # CSS Styles
    css = """
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'Segoe UI', Tahoma, sans-serif;
            background: #f0f2f5;
            color: #333;
            line-height: 1.6;
        }
        
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px 20px;
            text-align: center;
        }
        
        .header h1 { font-size: 2.2em; margin-bottom: 10px; }
        .header p { font-size: 1.1em; opacity: 0.9; }
        
        .stats {
            display: flex;
            justify-content: center;
            gap: 30px;
            margin: 25px 0;
            flex-wrap: wrap;
        }
        
        .stat-box {
            background: rgba(255,255,255,0.2);
            padding: 15px 30px;
            border-radius: 10px;
            text-align: center;
        }
        
        .stat-box .number { font-size: 2em; font-weight: bold; }
        .stat-box .label { font-size: 0.9em; opacity: 0.9; }
        
        .container { max-width: 1400px; margin: 0 auto; padding: 30px 20px; }
        
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
            gap: 25px;
        }
        
        .card {
            background: white;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            transition: transform 0.2s, box-shadow 0.2s;
        }
        
        .card:hover {
            transform: translateY(-3px);
            box-shadow: 0 8px 20px rgba(0,0,0,0.15);
        }
        
        .card-image {
            width: 100%;
            height: 250px;
            object-fit: cover;
        }
        
        .card-content { padding: 20px; }
        
        .card-title {
            font-size: 1.2em;
            font-weight: 600;
            margin-bottom: 15px;
            color: #333;
        }
        
        .card-rank {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 3px 10px;
            border-radius: 15px;
            font-size: 0.85em;
            margin-right: 10px;
        }
        
        .info-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }
        
        .info-item {
            background: #f8f9fa;
            padding: 10px;
            border-radius: 8px;
        }
        
        .info-label {
            font-size: 0.75em;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .info-value {
            font-size: 1em;
            font-weight: 600;
            color: #333;
        }
        
        .pv-eignung {
            display: inline-block;
            padding: 5px 12px;
            border-radius: 20px;
            font-weight: 600;
            font-size: 0.9em;
        }
        
        .pv-hervorragend { background: #d4edda; color: #155724; }
        .pv-sehr-gut { background: #cce5ff; color: #004085; }
        .pv-gut { background: #fff3cd; color: #856404; }
        .pv-mittel { background: #ffeeba; color: #856404; }
        .pv-schlecht { background: #f8d7da; color: #721c24; }
        
        .hindernisse {
            margin-top: 10px;
            padding: 10px;
            background: #fff3cd;
            border-radius: 8px;
            font-size: 0.9em;
        }
        
        .hindernisse-none {
            background: #d4edda;
        }
        
        .footer {
            text-align: center;
            padding: 30px;
            color: #666;
            font-size: 0.9em;
        }
        
        .no-analysis {
            color: #999;
            font-style: italic;
        }
    </style>
    """
    
    # Statistiken berechnen
    stats = {
        'total': len(images),
        'analyzed': len(roof_data),
        'dach_typen': {},
        'materialien': {},
        'eignungen': {}
    }
    
    for data in roof_data.values():
        dt = data.get('dach_typ', 'Unbekannt')
        stats['dach_typen'][dt] = stats['dach_typen'].get(dt, 0) + 1
        
        mat = data.get('material', 'Unbekannt')
        stats['materialien'][mat] = stats['materialien'].get(mat, 0) + 1
        
        eig = data.get('pv_eignung', 'Unbekannt')
        stats['eignungen'][eig] = stats['eignungen'].get(eig, 0) + 1
    
    # HTML generieren
    html_parts = [
        "<!DOCTYPE html>",
        "<html lang='de'>",
        "<head>",
        "<meta charset='UTF-8'>",
        "<meta name='viewport' content='width=device-width, initial-scale=1.0'>",
        "<title>PV-Dach-Analyse Report - Dortmund</title>",
        css,
        "</head>",
        "<body>",
        
        # Header
        "<div class='header'>",
        "<h1>🏠 PV-Dach-Analyse Report</h1>",
        f"<p>Dortmund - Analysiert mit Gemini 2.0 | {datetime.now().strftime('%d.%m.%Y')}</p>",
        "<div class='stats'>",
        f"<div class='stat-box'><div class='number'>{stats['analyzed']}</div><div class='label'>Analysiert</div></div>",
        f"<div class='stat-box'><div class='number'>{stats['eignungen'].get('hervorragend', 0)}</div><div class='label'>Hervorragend</div></div>",
        f"<div class='stat-box'><div class='number'>{stats['eignungen'].get('sehr gut', 0)}</div><div class='label'>Sehr gut</div></div>",
        f"<div class='stat-box'><div class='number'>{stats['eignungen'].get('gut', 0)}</div><div class='label'>Gut</div></div>",
        "</div>",
        "</div>",
        
        "<div class='container'>",
        "<div class='grid'>"
    ]
    
    # Cards für jedes analysierte Bild
    for img_path in images:
        analysis = match_analysis_to_image(img_path.name, roof_data)
        
        if not analysis:
            continue  # Nur analysierte Bilder zeigen
        
        # Rang aus Dateiname
        parts = img_path.stem.split('_')
        rank = parts[1] if len(parts) > 1 else '?'
        
        # PV-Eignung Klasse
        eignung = analysis.get('pv_eignung', 'unbekannt')
        eignung_class = f"pv-{eignung.replace(' ', '-').lower()}"
        
        # Hindernisse
        hindernisse_anzahl = analysis.get('hindernisse_anzahl', 0)
        hindernisse_typen = analysis.get('hindernisse_typen', [])
        
        # Annotiertes Bild verwenden wenn vorhanden
        annotated_name = f"annotated_{img_path.name}"
        annotated_path = ANNOTATED_DIR / annotated_name
        
        if annotated_path.exists():
            img_src = f"roof_analysis/annotated/{annotated_name}"
        else:
            img_src = f"luftbilder/{img_path.name}"
        
        card_html = f"""
        <div class='card'>
            <img class='card-image' src='{img_src}' alt='Dach {rank}' loading='lazy'>
            <div class='card-content'>
                <div class='card-title'>
                    <span class='card-rank'>#{rank}</span>
                    {analysis.get('dach_typ', 'Unbekannt')}
                </div>
                
                <div class='info-grid'>
                    <div class='info-item'>
                        <div class='info-label'>Material</div>
                        <div class='info-value'>{analysis.get('material', '-')}</div>
                    </div>
                    <div class='info-item'>
                        <div class='info-label'>Farbe</div>
                        <div class='info-value'>{analysis.get('farbe', '-')}</div>
                    </div>
                    <div class='info-item'>
                        <div class='info-label'>Zustand</div>
                        <div class='info-value'>{analysis.get('zustand', '-')}</div>
                    </div>
                    <div class='info-item'>
                        <div class='info-label'>Freie Fläche</div>
                        <div class='info-value'>{analysis.get('freie_flaeche_prozent', '-')}%</div>
                    </div>
                    <div class='info-item'>
                        <div class='info-label'>Geschätzte Leistung</div>
                        <div class='info-value'>{analysis.get('geschaetzte_kw', '-')} kW</div>
                    </div>
                    <div class='info-item'>
                        <div class='info-label'>PV-Eignung</div>
                        <div class='info-value'><span class='pv-eignung {eignung_class}'>{eignung}</span></div>
                    </div>
                </div>
                
                <div class='hindernisse {"hindernisse-none" if hindernisse_anzahl == 0 else ""}'>
                    <strong>Hindernisse:</strong> {hindernisse_anzahl} 
                    {f"({', '.join(hindernisse_typen)})" if hindernisse_typen else "(keine)"}
                </div>
                
                <div style='margin-top: 10px; font-size: 0.85em; color: #666;'>
                    {analysis.get('begruendung', '')}
                </div>
            </div>
        </div>
        """
        html_parts.append(card_html)
    
    # Footer
    html_parts.extend([
        "</div>",  # grid
        "</div>",  # container
        "<div class='footer'>",
        f"<p>Generiert am {datetime.now().strftime('%d.%m.%Y %H:%M')} | Gemini 2.0 Flash Analyse</p>",
        "</div>",
        "</body>",
        "</html>"
    ])
    
    # Speichern
    output_file = OUTPUT_DIR / 'dach_analyse_report.html'
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(html_parts))
    
    print(f"\n✓ Report gespeichert: {output_file}")
    print(f"\n📊 Statistiken:")
    print(f"   Dachtypen: {stats['dach_typen']}")
    print(f"   Materialien: {stats['materialien']}")
    print(f"   PV-Eignung: {stats['eignungen']}")
    
    return output_file


if __name__ == "__main__":
    output = create_html_report_with_roof_analysis()
    print(f"\n🌐 Öffne Report: {output}")
