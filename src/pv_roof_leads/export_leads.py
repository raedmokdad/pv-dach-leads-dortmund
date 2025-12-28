"""
Task 5.3: Export & Visualisierung
Exportiert Top-Leads als Excel und erstellt interaktive Karte
"""

import geopandas as gpd
import pandas as pd
import folium
from pathlib import Path
from .config import (
    STAGING_DORTMUND,
    FINAL_DORTMUND,
    EXPORT_TOPK,
    CRS_EXPORT
)


def prepare_excel_export(buildings: gpd.GeoDataFrame, top_k: int = 1000) -> pd.DataFrame:
    """
    Bereitet Top-K Gebäude für Excel-Export vor.
    
    Spalten:
    - Rang, Name, Adresse, Kontakt, Fläche, Score, Priorität, Koordinaten
    """
    print(f"\n📊 Bereite Top {top_k} Leads für Export vor...")
    
    # Nimm Top K nach Score
    top_leads = buildings.head(top_k).copy()
    
    # Transformiere zu WGS84 für Koordinaten
    if top_leads.crs != CRS_EXPORT:
        top_leads = top_leads.to_crs(CRS_EXPORT)
    
    # Extrahiere Koordinaten (Zentroid)
    top_leads['lon'] = top_leads.geometry.centroid.x
    top_leads['lat'] = top_leads.geometry.centroid.y
    
    # Extrahiere Adressinformationen aus OSM-Daten
    def extract_address(row):
        """Erstellt Adress-String aus OSM addr:* Feldern"""
        parts = []
        
        # Straße und Hausnummer
        street = row.get('addr:street', '')
        housenumber = row.get('addr:housenumber', '')
        if pd.notna(street) and street:
            addr_line = str(street)
            if pd.notna(housenumber) and housenumber:
                addr_line += f" {housenumber}"
            parts.append(addr_line)
        
        # PLZ und Stadt
        postcode = row.get('addr:postcode', '')
        city = row.get('addr:city', '')
        if pd.notna(postcode) and postcode:
            city_line = str(postcode)
            if pd.notna(city) and city:
                city_line += f" {city}"
            elif city == '' or pd.isna(city):
                city_line += " Dortmund"  # Fallback
            parts.append(city_line)
        elif pd.notna(city) and city:
            parts.append(str(city))
        
        return ', '.join(parts) if parts else '-'
    
    def extract_contact(row):
        """Extrahiert Kontaktinformationen (Telefon, Website, Email)"""
        contacts = []
        
        # Telefon
        phone = row.get('phone', row.get('contact:phone', ''))
        if pd.notna(phone) and phone:
            contacts.append(f"Tel: {phone}")
        
        # Website
        website = row.get('website', row.get('contact:website', ''))
        if pd.notna(website) and website:
            contacts.append(f"Web: {website}")
        
        # Email
        email = row.get('email', row.get('contact:email', ''))
        if pd.notna(email) and email:
            contacts.append(f"Email: {email}")
        
        return ' | '.join(contacts) if contacts else '-'
    
    # Erstelle Export-DataFrame mit Adressen und Kontakten
    export_df = pd.DataFrame({
        'Rang': range(1, len(top_leads) + 1),
        'Name': top_leads['name'].fillna('Unbekannt'),
        'Adresse': top_leads.apply(extract_address, axis=1),
        'Kontakt': top_leads.apply(extract_contact, axis=1),
        'Gebäudetyp': top_leads['building'].fillna('-'),
        'Landuse': top_leads['landuse'].fillna('-'),
        'Amenity': top_leads['amenity'].fillna('-'),
        'Dachfläche_m2': top_leads['footprint_area_m2'].round(0).astype(int),
        'Score_Gesamt': top_leads['total_score'].round(1),
        'Score_Fläche': top_leads['roof_score'].round(1),
        'Score_Zone': top_leads['zone_score'].round(1),
        'Priorität': top_leads['priority'],
        'Longitude': top_leads['lon'].round(6),
        'Latitude': top_leads['lat'].round(6),
        'OSM_ID': top_leads['id'],
    })
    
    # Statistiken über verfügbare Kontaktdaten
    has_address = (export_df['Adresse'] != '-').sum()
    has_contact = (export_df['Kontakt'] != '-').sum()
    
    print(f"✓ {len(export_df)} Leads vorbereitet")
    print(f"   {has_address} mit Adresse, {has_contact} mit Kontaktdaten")
    return export_df


def create_interactive_map(buildings: gpd.GeoDataFrame, top_k: int = 200) -> folium.Map:
    """
    Erstellt interaktive Folium-Karte mit Top-K Leads.
    
    Features:
    - Marker nach Priorität eingefärbt (A=rot, B=orange, C=gelb)
    - Popup mit Details
    - Heatmap-Layer
    """
    print(f"\n🗺️  Erstelle interaktive Karte...")
    
    # Top K Leads
    top_leads = buildings.head(top_k).copy()
    
    # WICHTIG: Transformiere zu WGS84 BEVOR Centroid berechnet wird
    if top_leads.crs != CRS_EXPORT:
        print(f"   Transformiere von {top_leads.crs} → {CRS_EXPORT}")
        top_leads = top_leads.to_crs(CRS_EXPORT)
    
    # Jetzt erst Centroids berechnen (in WGS84)
    centroids = top_leads.geometry.centroid
    
    # Karten-Zentrum (Dortmund)
    center_lat = centroids.y.mean()
    center_lon = centroids.x.mean()
    
    print(f"   Karten-Zentrum: Lat={center_lat:.6f}, Lon={center_lon:.6f}")
    print(f"   Zoom-Level: 12")
    
    # Erstelle einfache Karte (wie funktionierende Test-Karte)
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=12,
        tiles='OpenStreetMap'
    )
    
    # Farben nach Priorität
    priority_colors = {
        'A': 'red',
        'B': 'orange',
        'C': 'lightgreen'
    }
    
    # Füge Marker hinzu
    marker_count = 0
    for idx, row in top_leads.iterrows():
        # Koordinaten vom Centroid
        centroid = row.geometry.centroid
        lat, lon = centroid.y, centroid.x
        
        # Debug: Erste 3 Marker ausgeben
        if marker_count < 3:
            print(f"   Marker {marker_count+1}: Lat={lat:.6f}, Lon={lon:.6f}")
        
        marker_count += 1
        
        # Einfaches Popup (wie in funktionierender Test-Karte)
        name = row.get('name', 'Unbekannt')
        if pd.isna(name):
            name = 'Unbekannt'
        
        # Google Maps und TIM-online Links
        google_maps_url = f"https://www.google.com/maps?q={lat},{lon}"
        # TIM-online verwendet center=lon,lat (!) und scale statt zoom
        tim_online_url = f"https://www.tim-online.nrw.de/tim-online2/?center={lon},{lat}&scale=500"
        
        popup_text = f"""
        <b>{name}</b><br>
        Score: {row['total_score']:.1f}<br>
        Fläche: {row['footprint_area_m2']:.0f} m²<br>
        Priorität: {row['priority']}<br>
        Zone: {row.get('landuse', '-')}<br>
        <hr style="margin: 5px 0;">
        <a href="{google_maps_url}" target="_blank">📍 Google Maps</a><br>
        <a href="{tim_online_url}" target="_blank">🗺️ TIM-online NRW</a>
        """
        
        # Marker hinzufügen (genau wie Test-Karte)
        folium.Marker(
            location=[lat, lon],
            popup=popup_text,
            icon=folium.Icon(color=priority_colors.get(row['priority'], 'gray'), icon='info-sign')
        ).add_to(m)
    
    print(f"✓ Karte mit {marker_count} Markern erstellt")
    return m


def create_polygon_map(buildings: gpd.GeoDataFrame, top_k: int = 200) -> folium.Map:
    """
    Erstellt interaktive Karte mit Dach-Polygonen (statt Marker).
    
    Features:
    - Dächer als farbige Polygone sichtbar
    - Farbe nach Priorität (A=rot, B=orange, C=grün)
    - Popup mit Details
    - Legende
    """
    print(f"\n🗺️  Erstelle Polygon-Karte...")
    
    # Top K Leads
    top_leads = buildings.head(top_k).copy()
    
    # Transformiere zu WGS84
    if top_leads.crs != CRS_EXPORT:
        print(f"   Transformiere von {top_leads.crs} → {CRS_EXPORT}")
        top_leads = top_leads.to_crs(CRS_EXPORT)
    
    # Karten-Zentrum
    center_lat = top_leads.geometry.centroid.y.mean()
    center_lon = top_leads.geometry.centroid.x.mean()
    
    print(f"   Karten-Zentrum: Lat={center_lat:.6f}, Lon={center_lon:.6f}")
    
    # Erstelle Karte
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=13,
        tiles='OpenStreetMap'
    )
    
    # Farben nach Priorität (Hex-Codes für GeoJson)
    priority_colors = {
        'A': '#FF0000',  # Rot
        'B': '#FFA500',  # Orange
        'C': '#90EE90'   # Hellgrün
    }
    
    # Füge Gebäude als Polygone hinzu
    polygon_count = 0
    for idx, row in top_leads.iterrows():
        polygon_count += 1
        
        # Farbe nach Priorität
        color = priority_colors.get(row['priority'], '#808080')
        
        # Popup-Info
        name = row.get('name', 'Unbekannt')
        if pd.isna(name):
            name = 'Unbekannt'
        
        # Koordinaten für Links
        centroid = row.geometry.centroid
        lat, lon = centroid.y, centroid.x
        google_maps_url = f"https://www.google.com/maps?q={lat},{lon}"
        # TIM-online verwendet center=lon,lat (!) und scale statt zoom
        tim_online_url = f"https://www.tim-online.nrw.de/tim-online2/?center={lon},{lat}&scale=500"
        
        popup_html = f"""
        <div style="font-family: Arial; min-width: 250px;">
            <h4 style="margin: 0 0 10px 0; color: {color};">
                {name}
            </h4>
            <table style="width: 100%; font-size: 13px;">
                <tr style="background: #f0f0f0;">
                    <td><b>Score:</b></td>
                    <td>{row['total_score']:.1f} Punkte</td>
                </tr>
                <tr>
                    <td><b>Priorität:</b></td>
                    <td style="color: {color}; font-weight: bold;">{row['priority']}</td>
                </tr>
                <tr style="background: #f0f0f0;">
                    <td><b>Dachfläche:</b></td>
                    <td>{row['footprint_area_m2']:.0f} m²</td>
                </tr>
                <tr>
                    <td><b>Zone:</b></td>
                    <td>{row.get('landuse', '-')}</td>
                </tr>
                <tr style="background: #f0f0f0;">
                    <td><b>Typ:</b></td>
                    <td>{row.get('amenity', '-')}</td>
                </tr>
            </table>
            <hr style="margin: 10px 0;">
            <div style="text-align: center;">
                <a href="{google_maps_url}" target="_blank" style="display: inline-block; margin: 5px; padding: 8px 12px; background: #4285F4; color: white; text-decoration: none; border-radius: 4px; font-size: 12px;">📍 Google Maps</a>
                <a href="{tim_online_url}" target="_blank" style="display: inline-block; margin: 5px; padding: 8px 12px; background: #00853F; color: white; text-decoration: none; border-radius: 4px; font-size: 12px;">🗺️ TIM-online</a>
            </div>
        </div>
        """
        
        # GeoJson für Polygon
        folium.GeoJson(
            row.geometry,
            style_function=lambda x, col=color: {
                'fillColor': col,
                'color': col,
                'weight': 2,
                'fillOpacity': 0.5
            },
            popup=folium.Popup(popup_html, max_width=300)
        ).add_to(m)
    
    # Legende hinzufügen
    legend_html = '''
    <div style="position: fixed; 
                bottom: 50px; left: 50px; 
                width: 200px; 
                background-color: white; 
                border: 2px solid grey; 
                z-index: 9999; 
                font-size: 14px; 
                padding: 15px;
                border-radius: 5px;">
        <h4 style="margin: 0 0 10px 0;">Priorität</h4>
        <div style="margin: 8px 0;">
            <span style="background: #FF0000; padding: 5px 10px; color: white; font-weight: bold;">A</span>
            <span style="margin-left: 10px;">Score ≥ 75</span>
        </div>
        <div style="margin: 8px 0;">
            <span style="background: #FFA500; padding: 5px 10px; color: white; font-weight: bold;">B</span>
            <span style="margin-left: 10px;">Score 55-74</span>
        </div>
        <div style="margin: 8px 0;">
            <span style="background: #90EE90; padding: 5px 10px; color: white; font-weight: bold;">C</span>
            <span style="margin-left: 10px;">Score &lt; 55</span>
        </div>
        <hr style="margin: 10px 0;">
        <small><b>Tipp:</b> Klick auf Dächer für Details</small>
    </div>
    '''
    m.get_root().html.add_child(folium.Element(legend_html))
    
    print(f"✓ Polygon-Karte mit {polygon_count} Dächern erstellt")
    return m


def main():
    """
    Hauptfunktion: Lädt gescorte Gebäude, exportiert Top-K als Excel + Karte.
    """
    print("\n" + "=" * 60)
    print("📊 Task 5.3: Export & Visualisierung")
    print("=" * 60)
    
    # Lade gescorte Gebäude (aus Task 5.2)
    scored_file = STAGING_DORTMUND / "scored_buildings.geojson"
    print(f"\n📂 Lade gescorte Gebäude: {scored_file}")
    
    if not scored_file.exists():
        raise FileNotFoundError(
            f"Gescorte Gebäude nicht gefunden: {scored_file}\n"
            f"Bitte erst Task 5.2 ausführen: python -m pv_roof_leads.score_leads"
        )
    
    buildings = gpd.read_file(scored_file)
    print(f"✓ {len(buildings)} Gebäude geladen")
    
    # Erstelle FINAL_DORTMUND Verzeichnis falls nicht vorhanden
    FINAL_DORTMUND.mkdir(parents=True, exist_ok=True)
    
    # 1. Excel-Export
    print("\n" + "=" * 60)
    print("📊 Excel-Export")
    print("=" * 60)
    
    export_df = prepare_excel_export(buildings, EXPORT_TOPK)
    excel_file = FINAL_DORTMUND / f"dortmund_top{EXPORT_TOPK}_leads.xlsx"
    
    try:
        export_df.to_excel(excel_file, index=False, sheet_name='PV-Leads')
        print(f"✅ Excel exportiert: {excel_file}")
    except PermissionError:
        print(f"⚠️  Excel-Datei ist geöffnet - überspringe Excel-Export")
        print(f"   Bitte schließe: {excel_file}")
    
    # Statistiken
    print(f"\n📈 Export-Statistik:")
    for priority in ['A', 'B', 'C']:
        count = (export_df['Priorität'] == priority).sum()
        avg_area = export_df[export_df['Priorität'] == priority]['Dachfläche_m2'].mean()
        print(f"   {priority}-Leads: {count:>3} Gebäude (Ø {avg_area:>7.0f} m²)")
    
    # 2. Interaktive Karte mit Markern
    print("\n" + "=" * 60)
    print("🗺️  Interaktive Karte (Marker)")
    print("=" * 60)
    
    map_obj = create_interactive_map(buildings, EXPORT_TOPK)
    map_file = FINAL_DORTMUND / f"dortmund_leads_map_top{EXPORT_TOPK}.html"
    map_obj.save(str(map_file))
    print(f"✅ Marker-Karte gespeichert: {map_file}")
    
    # 3. Interaktive Karte mit Dach-Polygonen
    print("\n" + "=" * 60)
    print("🏘️  Dach-Polygon-Karte")
    print("=" * 60)
    
    polygon_map = create_polygon_map(buildings, EXPORT_TOPK)
    polygon_file = FINAL_DORTMUND / "dortmund_roofs_map.html"
    polygon_map.save(str(polygon_file))
    print(f"✅ Polygon-Karte gespeichert: {polygon_file}")
    
    print("\n" + "=" * 60)
    print("✅ Task 5.3 abgeschlossen!")
    print("=" * 60)
    print(f"\n📁 Finale Outputs:")
    print(f"   • Excel: {excel_file.name}")
    print(f"   • Marker-Karte: {map_file.name}")
    print(f"   • Polygon-Karte: {polygon_file.name}")
    print(f"\n💡 Öffne die HTML-Karten im Browser, um die Leads zu visualisieren!")


if __name__ == '__main__':
    main()
