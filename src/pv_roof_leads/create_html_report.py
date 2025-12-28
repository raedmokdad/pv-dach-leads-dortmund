"""
Erstellt HTML-Report mit Leads-Daten und Luftbildern
"""

import pandas as pd
from pathlib import Path
from .config import FINAL_DORTMUND, EXPORT_TOPK


def create_lead_card(row, image_path: Path, rank: int) -> str:
    """
    Erstellt HTML-Card für einen Lead.
    """
    # Prüfe ob Bild existiert
    img_exists = image_path.exists() if image_path else False
    img_src = f"luftbilder/{image_path.name}" if img_exists else ""
    
    # Prioritätsfarben
    priority_colors = {
        'A': '#FF0000',
        'B': '#FFA500', 
        'C': '#90EE90'
    }
    color = priority_colors.get(row.get('Priorität', 'C'), '#808080')
    
    return f"""
    <div class="lead-card" id="lead-{rank}">
        <div class="lead-header" style="background: {color};">
            <h3>#{rank} - {row['Name']}</h3>
            <span class="priority-badge">Priorität {row['Priorität']}</span>
        </div>
        <div class="lead-content">
            <div class="lead-image">
                {f'<img src="{img_src}" alt="Luftbild {rank}">' if img_exists else '<div class="no-image">Kein Bild verfügbar</div>'}
            </div>
            <div class="lead-info">
                <table>
                    <tr>
                        <th>Adresse:</th>
                        <td>{row['Adresse']}</td>
                    </tr>
                    <tr>
                        <th>Kontakt:</th>
                        <td>{row['Kontakt']}</td>
                    </tr>
                    <tr>
                        <th>Gebäudetyp:</th>
                        <td>{row['Gebäudetyp']}</td>
                    </tr>
                    <tr>
                        <th>Landuse:</th>
                        <td>{row['Landuse']}</td>
                    </tr>
                    <tr>
                        <th>Amenity:</th>
                        <td>{row['Amenity']}</td>
                    </tr>
                    <tr>
                        <th>Dachfläche:</th>
                        <td><strong>{row['Dachfläche_m2']:,} m²</strong></td>
                    </tr>
                    <tr>
                        <th>Score Gesamt:</th>
                        <td><strong>{row['Score_Gesamt']}</strong></td>
                    </tr>
                    <tr>
                        <th>Score Fläche:</th>
                        <td>{row['Score_Fläche']}</td>
                    </tr>
                    <tr>
                        <th>Score Zone:</th>
                        <td>{row['Score_Zone']}</td>
                    </tr>
                    <tr>
                        <th>Koordinaten:</th>
                        <td>{row['Latitude']:.6f}, {row['Longitude']:.6f}</td>
                    </tr>
                    <tr>
                        <th>Karten:</th>
                        <td>
                            <a href="https://www.google.com/maps?q={row['Latitude']},{row['Longitude']}" target="_blank" style="margin-right: 15px;">🗺️ Google Maps</a>
                            <a href="https://www.tim-online.nrw.de/tim-online2/?center={row['Longitude']},{row['Latitude']}&scale=500" target="_blank">🗺️ TIM-online NRW</a>
                        </td>
                    </tr>
                </table>
            </div>
        </div>
    </div>
    """


def create_html_report(excel_file: Path, images_dir: Path, output_file: Path):
    """
    Erstellt vollständigen HTML-Report.
    """
    print(f"\n📄 Erstelle HTML-Report...")
    
    # Lade Excel-Daten
    df = pd.read_excel(excel_file)
    print(f"   ✓ {len(df)} Leads geladen")
    
    # CSS Styles
    css = """
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #f5f5f5;
            color: #333;
            line-height: 1.6;
        }
        
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px 20px;
            text-align: center;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
        }
        
        .header p {
            font-size: 1.2em;
            opacity: 0.9;
        }
        
        .stats {
            display: flex;
            justify-content: center;
            gap: 40px;
            margin: 30px 0;
            flex-wrap: wrap;
        }
        
        .stat-box {
            background: rgba(255,255,255,0.2);
            padding: 20px 40px;
            border-radius: 10px;
            text-align: center;
        }
        
        .stat-box .number {
            font-size: 2em;
            font-weight: bold;
        }
        
        .stat-box .label {
            font-size: 0.9em;
            opacity: 0.9;
        }
        
        .container {
            max-width: 1400px;
            margin: 40px auto;
            padding: 0 20px;
        }
        
        .filters {
            background: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 30px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        .filter-buttons {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }
        
        .filter-btn {
            padding: 10px 20px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 1em;
            transition: all 0.3s;
        }
        
        .filter-btn.active {
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
            transform: translateY(-2px);
        }
        
        .filter-btn.priority-a {
            background: #FF0000;
            color: white;
        }
        
        .filter-btn.priority-b {
            background: #FFA500;
            color: white;
        }
        
        .filter-btn.priority-c {
            background: #90EE90;
            color: #333;
        }
        
        .filter-btn.all {
            background: #667eea;
            color: white;
        }
        
        .lead-card {
            background: white;
            border-radius: 10px;
            margin-bottom: 30px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            overflow: hidden;
            transition: transform 0.3s, box-shadow 0.3s;
        }
        
        .lead-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 8px 16px rgba(0,0,0,0.2);
        }
        
        .lead-header {
            padding: 20px;
            color: white;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .lead-header h3 {
            font-size: 1.5em;
        }
        
        .priority-badge {
            background: rgba(255,255,255,0.3);
            padding: 8px 16px;
            border-radius: 20px;
            font-weight: bold;
        }
        
        .lead-content {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
            padding: 30px;
        }
        
        @media (max-width: 968px) {
            .lead-content {
                grid-template-columns: 1fr;
            }
        }
        
        .lead-image img {
            width: 100%;
            height: auto;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        
        .no-image {
            width: 100%;
            height: 400px;
            background: #f0f0f0;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 8px;
            color: #999;
            font-style: italic;
        }
        
        .lead-info table {
            width: 100%;
            border-collapse: collapse;
        }
        
        .lead-info th {
            text-align: left;
            padding: 12px 0;
            border-bottom: 1px solid #eee;
            color: #666;
            font-weight: 600;
            width: 40%;
        }
        
        .lead-info td {
            padding: 12px 0;
            border-bottom: 1px solid #eee;
        }
        
        .lead-info a {
            color: #667eea;
            text-decoration: none;
        }
        
        .lead-info a:hover {
            text-decoration: underline;
        }
        
        .back-to-top {
            position: fixed;
            bottom: 30px;
            right: 30px;
            background: #667eea;
            color: white;
            width: 50px;
            height: 50px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
            transition: all 0.3s;
            text-decoration: none;
            font-size: 1.5em;
        }
        
        .back-to-top:hover {
            background: #764ba2;
            transform: translateY(-5px);
        }
        
        .footer {
            background: #333;
            color: white;
            padding: 30px 20px;
            text-align: center;
            margin-top: 60px;
        }
    </style>
    """
    
    # JavaScript für Filter
    js = """
    <script>
        function filterLeads(priority) {
            const cards = document.querySelectorAll('.lead-card');
            const buttons = document.querySelectorAll('.filter-btn');
            
            // Update button states
            buttons.forEach(btn => btn.classList.remove('active'));
            event.target.classList.add('active');
            
            // Filter cards
            cards.forEach(card => {
                if (priority === 'all') {
                    card.style.display = 'block';
                } else {
                    const header = card.querySelector('.lead-header h3').textContent;
                    const cardPriority = card.querySelector('.priority-badge').textContent.split(' ')[1];
                    
                    if (cardPriority === priority) {
                        card.style.display = 'block';
                    } else {
                        card.style.display = 'none';
                    }
                }
            });
        }
        
        // Smooth scroll to top
        document.addEventListener('DOMContentLoaded', function() {
            const backToTop = document.querySelector('.back-to-top');
            
            window.addEventListener('scroll', function() {
                if (window.pageYOffset > 300) {
                    backToTop.style.display = 'flex';
                } else {
                    backToTop.style.display = 'none';
                }
            });
        });
    </script>
    """
    
    # HTML Start
    html_parts = [
        "<!DOCTYPE html>",
        "<html lang='de'>",
        "<head>",
        "<meta charset='UTF-8'>",
        "<meta name='viewport' content='width=device-width, initial-scale=1.0'>",
        "<title>PV-Dach-Leads Dortmund - Top 500</title>",
        css,
        js,
        "</head>",
        "<body>",
        
        # Header
        "<div class='header'>",
        "<h1>🏢 PV-Dach-Leads Dortmund</h1>",
        f"<p>Top {EXPORT_TOPK} potenzielle Solaranlagen-Dächer</p>",
        "<div class='stats'>",
        f"<div class='stat-box'><div class='number'>{(df['Priorität'] == 'A').sum()}</div><div class='label'>A-Leads</div></div>",
        f"<div class='stat-box'><div class='number'>{(df['Priorität'] == 'B').sum()}</div><div class='label'>B-Leads</div></div>",
        f"<div class='stat-box'><div class='number'>{(df['Priorität'] == 'C').sum()}</div><div class='label'>C-Leads</div></div>",
        f"<div class='stat-box'><div class='number'>{df['Dachfläche_m2'].sum():,.0f} m²</div><div class='label'>Gesamtfläche</div></div>",
        "</div>",
        "</div>",
        
        # Container
        "<div class='container'>",
        
        # Filter
        "<div class='filters'>",
        "<h3>🔍 Filtern nach Priorität:</h3>",
        "<div class='filter-buttons'>",
        "<button class='filter-btn all active' onclick='filterLeads(\"all\")'>Alle anzeigen</button>",
        "<button class='filter-btn priority-a' onclick='filterLeads(\"A\")'>Priorität A</button>",
        "<button class='filter-btn priority-b' onclick='filterLeads(\"B\")'>Priorität B</button>",
        "<button class='filter-btn priority-c' onclick='filterLeads(\"C\")'>Priorität C</button>",
        "</div>",
        "</div>",
        
        # Leads
        "<div class='leads-container'>"
    ]
    
    # Generiere Cards für alle Leads
    print(f"   Generiere Lead-Cards...")
    for idx, row in df.iterrows():
        rank = row['Rang']
        
        # Finde zugehöriges Bild
        image_files = list(images_dir.glob(f"rank_{rank:03d}_*.jpg"))
        image_path = image_files[0] if image_files else None
        
        card_html = create_lead_card(row, image_path, rank)
        html_parts.append(card_html)
    
    # HTML Ende
    html_parts.extend([
        "</div>",  # leads-container
        "</div>",  # container
        
        # Back to top button
        "<a href='#' class='back-to-top'>↑</a>",
        
        # Footer
        "<div class='footer'>",
        "<p>PV-Dach-Leads Dortmund | Generiert am 25. Dezember 2025</p>",
        "<p>Datenquellen: ALKIS Dortmund, OpenStreetMap, NRW Luftbilder</p>",
        "</div>",
        
        "</body>",
        "</html>"
    ])
    
    # Schreibe HTML
    html_content = "\n".join(html_parts)
    output_file.write_text(html_content, encoding='utf-8')
    
    print(f"✅ HTML-Report erstellt: {output_file}")
    print(f"   📊 {len(df)} Leads")
    print(f"   🛰️  {len(list(images_dir.glob('*.jpg')))} Luftbilder")
    

def main():
    """
    Hauptfunktion: Erstellt HTML-Report aus Excel + Luftbildern.
    """
    print("\n" + "=" * 60)
    print("📄 HTML-Report Erstellung")
    print("=" * 60)
    
    # Dateien
    excel_file = FINAL_DORTMUND / f"dortmund_top{EXPORT_TOPK}_leads.xlsx"
    images_dir = FINAL_DORTMUND / "luftbilder"
    output_file = FINAL_DORTMUND / f"dortmund_leads_report_top{EXPORT_TOPK}.html"
    
    # Prüfe ob Dateien existieren
    if not excel_file.exists():
        raise FileNotFoundError(
            f"Excel-Datei nicht gefunden: {excel_file}\n"
            f"Bitte erst Export ausführen: python -m pv_roof_leads.export_leads"
        )
    
    if not images_dir.exists() or len(list(images_dir.glob('*.jpg'))) == 0:
        print("⚠️  Warnung: Keine Luftbilder gefunden!")
        print(f"   Verzeichnis: {images_dir}")
        print("   Report wird ohne Bilder erstellt.")
    
    # Erstelle Report
    create_html_report(excel_file, images_dir, output_file)
    
    print("\n" + "=" * 60)
    print("✅ HTML-Report fertig!")
    print("=" * 60)
    print(f"\n📁 Output: {output_file.name}")
    print(f"\n💡 Öffne im Browser: start {output_file}")


if __name__ == '__main__':
    main()
