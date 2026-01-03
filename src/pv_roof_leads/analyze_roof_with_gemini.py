"""
Dachanalyse mit Gemini Vision API

Erkennt aus Luftbildern:
- Dachmaterial (Ziegel, Beton, Metall/Blech, Bitumen, etc.)
- Dachzustand (Gut, Mittel, Schlecht)
- Hindernisse mit Bounding Boxes (Schornsteine, Dachfenster, Lüftungen, Gauben)

Kosten: ~$0.0003 pro Bild (Gemini 2.0 Flash)
"""

import json
import base64
import time
from pathlib import Path
from typing import Optional
import os

import geopandas as gpd
from dotenv import load_dotenv
from tqdm import tqdm

try:
    from google import genai
    from google.genai import types
except ImportError:
    print("❌ Google GenAI nicht installiert!")
    print("   Installiere mit: pip install google-genai")
    raise

from pv_roof_leads.paths import FINAL_DORTMUND

# Lade Umgebungsvariablen
load_dotenv()

# Konfiguration
IMAGES_DIR = FINAL_DORTMUND / "luftbilder"
OUTPUT_FILE = FINAL_DORTMUND / "all_buildings_with_solar.geojson"
RESULTS_FILE = FINAL_DORTMUND / "gemini_roof_analysis.json"

# Gemini Modell
MODEL_NAME = "gemini-2.0-flash"

# Rate Limiting (60 Requests/Minute für kostenlose API)
REQUESTS_PER_MINUTE = 55
DELAY_BETWEEN_REQUESTS = 60 / REQUESTS_PER_MINUTE  # ~1.1 Sekunden


def get_gemini_client():
    """Erstellt Gemini Client mit API Key aus .env"""
    # Versuche beide möglichen Key-Namen
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_AI_API_KEY")
    if not api_key:
        raise ValueError(
            "Kein Gemini API Key gefunden!\n"
            "Bitte in .env Datei eintragen als:\n"
            "GEMINI_API_KEY=dein_api_key\n"
            "oder GOOGLE_AI_API_KEY=dein_api_key\n\n"
            "API Key hier erstellen: https://aistudio.google.com/apikey"
        )
    return genai.Client(api_key=api_key)


def create_analysis_prompt():
    """Prompt für Dachanalyse mit strukturierter JSON-Ausgabe"""
    return """Analysiere dieses Luftbild eines Gebäudedachs für eine PV-Anlagen-Installation.

Gib die Ergebnisse als JSON zurück mit folgendem Format:
{
  "roof_material": "Ziegel" | "Beton" | "Metall" | "Bitumen" | "Schiefer" | "Gründach" | "Unbekannt",
  "roof_material_confidence": 0.0-1.0,
  "roof_condition": "Gut" | "Mittel" | "Schlecht" | "Unbekannt",
  "roof_condition_notes": "Kurze Begründung",
  "roof_color": "Rot" | "Grau" | "Braun" | "Schwarz" | "Grün" | "Weiß" | "Gemischt",
  "has_existing_pv": true | false,
  "obstacles": [
    {
      "type": "Schornstein" | "Dachfenster" | "Lüftung" | "Gaube" | "Antenne" | "Klimaanlage" | "Sonstiges",
      "box_2d": [ymin, xmin, ymax, xmax],
      "confidence": 0.0-1.0
    }
  ],
  "obstacle_count": Anzahl der Hindernisse,
  "usable_roof_percentage": 0-100,
  "installation_complexity": "Einfach" | "Mittel" | "Komplex",
  "notes": "Zusätzliche Beobachtungen"
}

Die box_2d Koordinaten sollten auf 0-1000 normalisiert sein (0=links/oben, 1000=rechts/unten).
Wenn keine Hindernisse erkannt werden, gib eine leere Liste zurück.
Antworte NUR mit dem JSON, ohne zusätzlichen Text."""


def analyze_single_image(client, image_path: Path) -> Optional[dict]:
    """
    Analysiert ein einzelnes Dachbild mit Gemini.
    
    Returns:
        dict mit Analyseergebnissen oder None bei Fehler
    """
    try:
        # Bild laden
        with open(image_path, 'rb') as f:
            image_bytes = f.read()
        
        # Request an Gemini
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[
                types.Part.from_bytes(
                    data=image_bytes,
                    mime_type='image/jpeg',
                ),
                create_analysis_prompt()
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1,  # Niedrig für konsistente Ergebnisse
            )
        )
        
        # JSON parsen
        result_text = response.text.strip()
        
        # Falls Markdown-Fencing vorhanden
        if result_text.startswith("```"):
            lines = result_text.split('\n')
            result_text = '\n'.join(lines[1:-1])
        
        result = json.loads(result_text)
        result['analysis_success'] = True
        return result
        
    except json.JSONDecodeError as e:
        return {
            'analysis_success': False,
            'error': f'JSON Parse Error: {str(e)}',
            'raw_response': response.text if 'response' in dir() else None
        }
    except Exception as e:
        return {
            'analysis_success': False,
            'error': str(e)
        }


def load_existing_results() -> dict:
    """Lädt bereits analysierte Ergebnisse für Resume-Funktionalität"""
    if RESULTS_FILE.exists():
        with open(RESULTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_results(results: dict):
    """Speichert Ergebnisse (nach jedem Batch für Sicherheit)"""
    with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)


def run_analysis(limit: Optional[int] = None, skip_existing: bool = True):
    """
    Führt Gemini-Analyse für alle Dachbilder durch.
    
    Args:
        limit: Maximale Anzahl zu analysierender Bilder (None = alle)
        skip_existing: Bereits analysierte Bilder überspringen
    """
    print("=" * 60)
    print("🔍 GEMINI DACHANALYSE")
    print("=" * 60)
    
    # Gemini Client erstellen
    print("\n⏳ Verbinde mit Gemini API...")
    client = get_gemini_client()
    print("✓ Gemini Client bereit")
    
    # Bilder laden
    image_files = list(IMAGES_DIR.glob("building_*.jpg"))
    print(f"✓ {len(image_files)} Bilder gefunden in {IMAGES_DIR}")
    
    # Bereits analysierte laden
    existing_results = load_existing_results() if skip_existing else {}
    print(f"✓ {len(existing_results)} bereits analysierte Bilder")
    
    # Zu analysierende Bilder filtern
    to_analyze = []
    for img_path in image_files:
        if img_path.name not in existing_results:
            to_analyze.append(img_path)
    
    if limit:
        to_analyze = to_analyze[:limit]
    
    print(f"\n📊 Zu analysieren: {len(to_analyze)} Bilder")
    
    if not to_analyze:
        print("✓ Alle Bilder bereits analysiert!")
        return existing_results
    
    # Kostenabschätzung
    estimated_cost = len(to_analyze) * 0.0003  # ~$0.0003 pro Bild
    print(f"💰 Geschätzte Kosten: ${estimated_cost:.2f}")
    print(f"⏱️  Geschätzte Zeit: {len(to_analyze) * DELAY_BETWEEN_REQUESTS / 60:.1f} Minuten")
    
    input("\nDrücke Enter um zu starten (Ctrl+C zum Abbrechen)...")
    
    # Analyse durchführen
    results = existing_results.copy()
    success_count = 0
    error_count = 0
    
    print("\n" + "=" * 60)
    
    for i, img_path in enumerate(tqdm(to_analyze, desc="Analysiere Dächer")):
        try:
            result = analyze_single_image(client, img_path)
            
            if result and result.get('analysis_success'):
                success_count += 1
            else:
                error_count += 1
            
            results[img_path.name] = result
            
            # Speichern alle 50 Bilder
            if (i + 1) % 50 == 0:
                save_results(results)
                tqdm.write(f"  💾 Zwischengespeichert ({i + 1}/{len(to_analyze)})")
            
            # Rate Limiting
            time.sleep(DELAY_BETWEEN_REQUESTS)
            
        except KeyboardInterrupt:
            print("\n\n⚠️  Abgebrochen! Speichere bisherige Ergebnisse...")
            save_results(results)
            print(f"✓ {len(results)} Ergebnisse gespeichert")
            raise
    
    # Finale Speicherung
    save_results(results)
    
    print("\n" + "=" * 60)
    print("✅ ANALYSE ABGESCHLOSSEN")
    print("=" * 60)
    print(f"✓ Erfolgreich: {success_count}")
    print(f"✗ Fehler: {error_count}")
    print(f"📁 Ergebnisse: {RESULTS_FILE}")
    
    return results


def merge_results_to_geojson():
    """
    Fügt Gemini-Analyseergebnisse zur GeoJSON hinzu.
    """
    print("\n📊 Merge Ergebnisse in GeoJSON...")
    
    # Lade GeoJSON
    gdf = gpd.read_file(OUTPUT_FILE)
    print(f"✓ {len(gdf)} Gebäude in GeoJSON")
    
    # Lade Gemini Ergebnisse
    if not RESULTS_FILE.exists():
        print("❌ Keine Gemini-Ergebnisse gefunden!")
        return
    
    with open(RESULTS_FILE, 'r', encoding='utf-8') as f:
        gemini_results = json.load(f)
    print(f"✓ {len(gemini_results)} Gemini-Ergebnisse")
    
    # Neue Spalten initialisieren
    new_columns = [
        'gemini_roof_material',
        'gemini_roof_condition', 
        'gemini_roof_color',
        'gemini_has_pv',
        'gemini_obstacle_count',
        'gemini_obstacles',
        'gemini_usable_percentage',
        'gemini_complexity',
        'gemini_notes',
        'gemini_analysis_success'
    ]
    
    for col in new_columns:
        gdf[col] = None
    
    # Ergebnisse zuordnen
    matched = 0
    for idx, row in gdf.iterrows():
        image_name = row.get('solar_rgb_image')
        if image_name and image_name in gemini_results:
            result = gemini_results[image_name]
            
            gdf.at[idx, 'gemini_roof_material'] = result.get('roof_material')
            gdf.at[idx, 'gemini_roof_condition'] = result.get('roof_condition')
            gdf.at[idx, 'gemini_roof_color'] = result.get('roof_color')
            gdf.at[idx, 'gemini_has_pv'] = result.get('has_existing_pv')
            gdf.at[idx, 'gemini_obstacle_count'] = result.get('obstacle_count', 0)
            gdf.at[idx, 'gemini_obstacles'] = result.get('obstacles', [])
            gdf.at[idx, 'gemini_usable_percentage'] = result.get('usable_roof_percentage')
            gdf.at[idx, 'gemini_complexity'] = result.get('installation_complexity')
            gdf.at[idx, 'gemini_notes'] = result.get('notes')
            gdf.at[idx, 'gemini_analysis_success'] = result.get('analysis_success', False)
            matched += 1
    
    print(f"✓ {matched} Gebäude mit Gemini-Daten angereichert")
    
    # Speichern
    gdf.to_file(OUTPUT_FILE, driver='GeoJSON')
    print(f"✓ GeoJSON aktualisiert: {OUTPUT_FILE}")
    
    # Statistiken
    print("\n📊 STATISTIKEN:")
    if matched > 0:
        materials = gdf['gemini_roof_material'].value_counts()
        print("\nDachmaterial:")
        for mat, count in materials.items():
            if mat:
                print(f"  {mat}: {count}")
        
        conditions = gdf['gemini_roof_condition'].value_counts()
        print("\nDachzustand:")
        for cond, count in conditions.items():
            if cond:
                print(f"  {cond}: {count}")


def test_single_image(image_name: str = None):
    """
    Testet die Analyse mit einem einzelnen Bild.
    """
    print("🧪 TEST: Einzelbild-Analyse")
    print("=" * 60)
    
    client = get_gemini_client()
    
    # Erstes Bild nehmen wenn nicht angegeben
    if image_name:
        image_path = IMAGES_DIR / image_name
    else:
        images = list(IMAGES_DIR.glob("building_*.jpg"))
        if not images:
            print("❌ Keine Bilder gefunden!")
            return
        image_path = images[0]
    
    print(f"📷 Analysiere: {image_path.name}")
    
    result = analyze_single_image(client, image_path)
    
    print("\n📊 ERGEBNIS:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    return result


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "test":
            # Test mit einem Bild
            test_single_image()
        elif sys.argv[1] == "merge":
            # Ergebnisse in GeoJSON mergen
            merge_results_to_geojson()
        elif sys.argv[1].isdigit():
            # Analyse mit Limit
            run_analysis(limit=int(sys.argv[1]))
        else:
            print("Verwendung:")
            print("  python analyze_roof_with_gemini.py          # Alle Bilder analysieren")
            print("  python analyze_roof_with_gemini.py test     # Test mit einem Bild")
            print("  python analyze_roof_with_gemini.py 100      # Nur 100 Bilder")
            print("  python analyze_roof_with_gemini.py merge    # Ergebnisse in GeoJSON")
    else:
        # Vollständige Analyse
        run_analysis()
        merge_results_to_geojson()
