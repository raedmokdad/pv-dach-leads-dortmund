"""
Test-Script für Google Solar API - Ein Beispielgebäude
Zeigt die automatische Hinderniserkennung und Panel-Platzierung
"""

import requests
import json
import os
from dotenv import load_dotenv

# Lade .env Datei
load_dotenv()

# Google Solar API Key
API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GOOGLE_SOLAR_API_KEY")

if not API_KEY:
    print("❌ Kein API Key gefunden!")
    print("   Bitte setzen Sie GOOGLE_API_KEY in der .env Datei")
    print("   Oder als Umgebungsvariable")
    exit(1)

# Beispiel-Koordinaten: Ein Gebäude in Dortmund
# Sie können diese durch beliebige Koordinaten ersetzen
EXAMPLE_LAT = 51.5136  # Dortmund Zentrum
EXAMPLE_LON = 7.4653

def get_building_insights(lat: float, lon: float):
    """Holt Gebäude-Insights von Google Solar API."""
    
    url = "https://solar.googleapis.com/v1/buildingInsights:findClosest"
    
    params = {
        "location.latitude": lat,
        "location.longitude": lon,
        "requiredQuality": "LOW",  # Akzeptiert auch niedrigere Qualität
        "key": API_KEY
    }
    
    print(f"\n🔍 Frage Google Solar API ab...")
    print(f"   Koordinaten: {lat}, {lon}")
    
    response = requests.get(url, params=params, timeout=30)
    
    if response.status_code == 200:
        return response.json()
    elif response.status_code == 404:
        print(f"❌ Keine Solar-Daten für diese Position verfügbar")
        return None
    else:
        print(f"❌ API-Fehler {response.status_code}: {response.text}")
        return None


def display_results(data: dict):
    """Zeigt die Ergebnisse übersichtlich an."""
    
    if not data:
        return
    
    print("\n" + "="*60)
    print("📊 GOOGLE SOLAR API ERGEBNIS")
    print("="*60)
    
    # Gebäude-Infos
    center = data.get("center", {})
    print(f"\n📍 Gebäude-Zentrum: {center.get('latitude', 'N/A')}, {center.get('longitude', 'N/A')}")
    
    # Luftbild-Qualität
    imagery_quality = data.get("imageryQuality", "UNKNOWN")
    imagery_date = data.get("imageryDate", {})
    date_str = f"{imagery_date.get('year', '?')}-{imagery_date.get('month', '?')}-{imagery_date.get('day', '?')}"
    print(f"📷 Luftbild-Qualität: {imagery_quality} (Datum: {date_str})")
    
    # Solar-Potenzial
    solar = data.get("solarPotential", {})
    
    if not solar:
        print("❌ Keine Solar-Potenzial Daten verfügbar")
        return
    
    print("\n" + "-"*60)
    print("☀️  SOLAR-POTENZIAL")
    print("-"*60)
    
    # Maximale Sonnenstunden
    max_sun = solar.get("maxSunshineHoursPerYear", 0)
    print(f"🌞 Max. Sonnenstunden/Jahr: {max_sun:.0f} h")
    
    # Panel-Kapazität
    panel_capacity = solar.get("panelCapacityWatts", 400)
    panel_height = solar.get("panelHeightMeters", 1.65)
    panel_width = solar.get("panelWidthMeters", 0.99)
    panel_area = panel_height * panel_width
    print(f"🔲 Panel-Spezifikation: {panel_capacity}W ({panel_height}m x {panel_width}m = {panel_area:.2f}m²)")
    
    # Maximale Panel-Anzahl (mit Hinderniserkennung!)
    max_panels = solar.get("maxArrayPanelsCount", 0)
    max_array_area = solar.get("maxArrayAreaMeters2", 0)
    print(f"\n🔢 Maximale Panel-Anzahl: {max_panels} Stück")
    print(f"📐 Maximale Array-Fläche: {max_array_area:.1f} m²")
    
    # Berechnung der nutzbaren Fläche
    roof_stats = solar.get("wholeRoofStats", {})
    total_roof_area = roof_stats.get("areaMeters2", 0)
    
    if total_roof_area > 0:
        usable_percentage = (max_array_area / total_roof_area) * 100
        print(f"🏠 Gesamte Dachfläche: {total_roof_area:.1f} m²")
        print(f"✅ Nutzbare Fläche: {usable_percentage:.1f}% (Rest = Hindernisse)")
    
    # CO2-Einsparung
    carbon_offset = solar.get("carbonOffsetFactorKgPerMwh", 0)
    print(f"\n🌱 CO2-Offset-Faktor: {carbon_offset:.1f} kg/MWh")
    
    # Dach-Segmente (zeigt verschiedene Dachbereiche)
    roof_segments = solar.get("roofSegmentStats", [])
    
    if roof_segments:
        print("\n" + "-"*60)
        print("🏗️  DACH-SEGMENTE (Automatisch erkannt)")
        print("-"*60)
        
        for i, segment in enumerate(roof_segments, 1):
            azimuth = segment.get("azimuthDegrees", 0)
            pitch = segment.get("pitchDegrees", 0)
            area = segment.get("stats", {}).get("areaMeters2", 0)
            sunshine = segment.get("stats", {}).get("sunshineQuantiles", [0]*12)
            
            # Ausrichtung berechnen
            if 337.5 <= azimuth or azimuth < 22.5:
                orientation = "Nord"
            elif 22.5 <= azimuth < 67.5:
                orientation = "Nord-Ost"
            elif 67.5 <= azimuth < 112.5:
                orientation = "Ost"
            elif 112.5 <= azimuth < 157.5:
                orientation = "Süd-Ost"
            elif 157.5 <= azimuth < 202.5:
                orientation = "Süd"
            elif 202.5 <= azimuth < 247.5:
                orientation = "Süd-West"
            elif 247.5 <= azimuth < 292.5:
                orientation = "West"
            else:
                orientation = "Nord-West"
            
            # Sonnenstunden (Median der Quantile)
            median_sunshine = sunshine[5] if len(sunshine) > 5 else 0
            
            print(f"\n  Segment {i}:")
            print(f"    📐 Fläche: {area:.1f} m²")
            print(f"    🧭 Ausrichtung: {orientation} ({azimuth:.1f}°)")
            print(f"    📈 Neigung: {pitch:.1f}°")
            print(f"    ☀️  Sonnenstunden (Median): {median_sunshine:.0f} h/Jahr")
    
    # Panel-Konfigurationen (verschiedene Anlagengrößen)
    configs = solar.get("solarPanelConfigs", [])
    
    if configs:
        print("\n" + "-"*60)
        print("⚡ PANEL-KONFIGURATIONEN (Optimiert)")
        print("-"*60)
        print("   Google berechnet verschiedene Anlagengrößen mit optimalem Layout:")
        print()
        
        # Zeige erste 5 Konfigurationen
        for i, config in enumerate(configs[:5], 1):
            panels_count = config.get("panelsCount", 0)
            yearly_energy = config.get("yearlyEnergyDcKwh", 0)
            kwp = (panels_count * panel_capacity) / 1000
            
            print(f"  {i}. {panels_count:3d} Panels = {kwp:6.1f} kWp → {yearly_energy:,.0f} kWh/Jahr")
        
        if len(configs) > 5:
            max_config = configs[-1]
            panels_count = max_config.get("panelsCount", 0)
            yearly_energy = max_config.get("yearlyEnergyDcKwh", 0)
            kwp = (panels_count * panel_capacity) / 1000
            print(f"  ...")
            print(f"  Max. {panels_count:3d} Panels = {kwp:6.1f} kWp → {yearly_energy:,.0f} kWh/Jahr")
    
    print("\n" + "="*60)
    print("✅ Die Panel-Anzahl berücksichtigt automatisch:")
    print("   - Hindernisse (Kamine, Dachfenster, etc.)")
    print("   - Verschattung durch Umgebung")
    print("   - Optimale Abstände zwischen Panels")
    print("   - Dachränder und Sicherheitsabstände")
    print("="*60)
    
    # Speichere als JSON
    output_file = "google_solar_example_result.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\n💾 Vollständige Daten gespeichert in: {output_file}")


if __name__ == "__main__":
    print("🔆 Google Solar API Test")
    print("=" * 40)
    
    # Sie können hier andere Koordinaten eingeben
    lat = EXAMPLE_LAT
    lon = EXAMPLE_LON
    
    # Optionale Eingabe
    try:
        user_input = input(f"\nKoordinaten eingeben (Enter für Standard {lat}, {lon}): ").strip()
        if user_input:
            parts = user_input.replace(",", " ").split()
            if len(parts) == 2:
                lat = float(parts[0])
                lon = float(parts[1])
    except:
        pass
    
    # API abfragen
    data = get_building_insights(lat, lon)
    
    # Ergebnisse anzeigen
    display_results(data)
