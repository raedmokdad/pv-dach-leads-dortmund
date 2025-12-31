"""
Vollständige Dach-Analyse aller Luftbilder mit Gemini 2.0 Flash
Mit Resume-Funktion und Integration in Gebäude-Daten
"""

import json
import os
import time
from pathlib import Path
from datetime import datetime
from PIL import Image
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

# Konfiguration
genai.configure(api_key=os.environ.get('GOOGLE_AI_API_KEY'))

LUFTBILDER_DIR = Path('data/final/dortmund/luftbilder')
OUTPUT_DIR = Path('data/final/dortmund/roof_analysis')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

RESULTS_FILE = OUTPUT_DIR / 'all_roofs_analysis.json'
PROGRESS_FILE = OUTPUT_DIR / 'analysis_progress.json'

ANALYSIS_PROMPT = """Du bist ein Experte für Dachanalyse aus Luftbildern.

Analysiere dieses Luftbild SEHR GENAU. Schau dir das Bild wirklich an!

Finde diese Elemente:
1. DACHTYP: Flachdach, Satteldach, Walmdach, Pultdach, Sheddach, Mansarddach?
2. MATERIAL: Ziegel rot, Ziegel braun, Beton, Metall, Bitumen, Kies, Schiefer, Gründach?
3. FARBE: rot, grau, schwarz, braun, grün, weiß?
4. ZUSTAND: neu, gut, mittel, sanierungsbedürftig?
5. HINDERNISSE (nur REAL sichtbare!):
   - Schornsteine
   - Dachgauben  
   - Dachfenster/Skylights
   - Klimaanlagen/HVAC
   - Lüftungsrohre/-hauben
   - Antennen, Satellitenschüsseln
   - Bestehende Solaranlagen

NUR JSON ausgeben (kein Text davor oder danach):
{"dach_typ":"...","material":"...","farbe":"...","zustand":"...","hindernisse_anzahl":3,"hindernisse_typen":["Lüftung","Schornstein"],"hat_solaranlage":false,"freie_flaeche_prozent":80,"pv_eignung":"hervorragend|sehr gut|gut|mittel|schlecht","geschaetzte_kw":100,"begruendung":"..."}"""


def load_progress():
    """Lädt Fortschritt für Resume"""
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, 'r') as f:
            return json.load(f)
    return {"processed": [], "failed": [], "last_index": 0}


def save_progress(progress):
    """Speichert Fortschritt"""
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f)


def load_results():
    """Lädt bisherige Ergebnisse"""
    if RESULTS_FILE.exists():
        with open(RESULTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_results(results):
    """Speichert Ergebnisse"""
    with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)


def analyze_image(model, image_path: Path) -> dict:
    """Analysiert ein einzelnes Bild"""
    
    image = Image.open(image_path)
    
    response = model.generate_content(
        [ANALYSIS_PROMPT, image],
        generation_config=genai.types.GenerationConfig(
            temperature=0.1,
            max_output_tokens=500
        )
    )
    
    content = response.text.strip()
    
    # JSON parsen
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0]
    elif "```" in content:
        content = content.split("```")[1].split("```")[0]
    
    result = json.loads(content.strip())
    return result


def main():
    print("=" * 70)
    print("GEMINI 2.0 - VOLLSTÄNDIGE DACH-ANALYSE")
    print("=" * 70)
    
    # Modell laden
    model = genai.GenerativeModel('gemini-2.0-flash-exp')
    
    # Alle Bilder finden
    all_images = sorted(LUFTBILDER_DIR.glob('*.jpg'))
    total = len(all_images)
    print(f"\nGefunden: {total} Bilder")
    
    # Fortschritt laden
    progress = load_progress()
    results = load_results()
    
    already_done = len(progress["processed"])
    if already_done > 0:
        print(f"Bereits analysiert: {already_done} (Resume-Modus)")
    
    # Statistiken
    start_time = time.time()
    success_count = already_done
    error_count = len(progress["failed"])
    
    print(f"\nStarte Analyse...")
    print(f"Geschätzte Kosten: ~${total * 0.001:.2f}")
    print(f"Geschätzte Zeit: ~{total * 2 / 60:.0f} Minuten")
    print("-" * 70)
    
    for i, img_path in enumerate(all_images):
        # Skip bereits verarbeitete
        if img_path.name in progress["processed"]:
            continue
        
        # Fortschritt anzeigen
        elapsed = time.time() - start_time
        if success_count > already_done:
            per_image = elapsed / (success_count - already_done)
            remaining = (total - i) * per_image
            eta_min = remaining / 60
        else:
            eta_min = 0
        
        print(f"[{i+1}/{total}] {img_path.name[:50]}... ", end="", flush=True)
        
        try:
            result = analyze_image(model, img_path)
            result['image'] = img_path.name
            result['analyzed_at'] = datetime.now().isoformat()
            
            # Gebäude-ID aus Dateinamen extrahieren (falls vorhanden)
            # Format: rank_XXX_lat_lon.jpg
            parts = img_path.stem.split('_')
            if len(parts) >= 3:
                try:
                    result['lat'] = float(parts[-2])
                    result['lon'] = float(parts[-1])
                except:
                    pass
            
            results[img_path.name] = result
            progress["processed"].append(img_path.name)
            success_count += 1
            
            print(f"✓ {result.get('dach_typ', '?')} / {result.get('material', '?')} / {result.get('pv_eignung', '?')}")
            
        except Exception as e:
            error_msg = str(e)[:50]
            print(f"❌ {error_msg}")
            progress["failed"].append({"image": img_path.name, "error": str(e)})
            error_count += 1
            
            # Bei Rate-Limit warten
            if "429" in str(e) or "quota" in str(e).lower():
                print("   ⏳ Rate-Limit erreicht, warte 60 Sekunden...")
                time.sleep(60)
        
        # Regelmäßig speichern (alle 10 Bilder)
        if (i + 1) % 10 == 0:
            save_progress(progress)
            save_results(results)
        
        # Kurze Pause um Rate-Limits zu vermeiden
        time.sleep(0.5)
    
    # Final speichern
    save_progress(progress)
    save_results(results)
    
    # Zusammenfassung
    elapsed_total = time.time() - start_time
    
    print("\n" + "=" * 70)
    print("ANALYSE ABGESCHLOSSEN")
    print("=" * 70)
    print(f"Erfolgreich: {success_count}/{total}")
    print(f"Fehler: {error_count}")
    print(f"Zeit: {elapsed_total/60:.1f} Minuten")
    print(f"Kosten: ~${success_count * 0.001:.2f}")
    print(f"\nErgebnisse: {RESULTS_FILE}")
    
    # Statistiken ausgeben
    if results:
        dach_typen = {}
        materialien = {}
        eignungen = {}
        mit_solar = 0
        
        for r in results.values():
            dt = r.get('dach_typ', 'Unbekannt')
            dach_typen[dt] = dach_typen.get(dt, 0) + 1
            
            mat = r.get('material', 'Unbekannt')
            materialien[mat] = materialien.get(mat, 0) + 1
            
            eig = r.get('pv_eignung', 'Unbekannt')
            eignungen[eig] = eignungen.get(eig, 0) + 1
            
            if r.get('hat_solaranlage'):
                mit_solar += 1
        
        print("\n📊 STATISTIKEN:")
        print(f"\nDachtypen: {dict(sorted(dach_typen.items(), key=lambda x: -x[1]))}")
        print(f"\nMaterialien: {dict(sorted(materialien.items(), key=lambda x: -x[1]))}")
        print(f"\nPV-Eignung: {dict(sorted(eignungen.items(), key=lambda x: -x[1]))}")
        print(f"\nMit bestehender Solaranlage: {mit_solar}")


if __name__ == "__main__":
    main()
