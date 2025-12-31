"""
Parallele Dach-Analyse aller Luftbilder mit Gemini 2.0 Flash
Nutzt mehrere Threads für schnellere Verarbeitung
"""

import json
import os
import time
from pathlib import Path
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv
import google.generativeai as genai
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

load_dotenv()

# Konfiguration
genai.configure(api_key=os.environ.get('GOOGLE_AI_API_KEY'))

LUFTBILDER_DIR = Path('data/final/dortmund/luftbilder')
OUTPUT_DIR = Path('data/final/dortmund/roof_analysis')
ANNOTATED_DIR = OUTPUT_DIR / 'annotated'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
ANNOTATED_DIR.mkdir(parents=True, exist_ok=True)

RESULTS_FILE = OUTPUT_DIR / 'all_roofs_analysis.json'
PROGRESS_FILE = OUTPUT_DIR / 'analysis_progress.json'

# Parallele Worker (reduziert wegen Rate-Limits)
MAX_WORKERS = 1

# Thread-sichere Counter
lock = threading.Lock()
stats = {"success": 0, "error": 0, "processed": 0}

ANALYSIS_PROMPT = """Analysiere dieses Dach-Luftbild für PV-Installation.

NUR JSON ausgeben:
{"dach_typ":"Flachdach|Satteldach|Walmdach|Pultdach|Sheddach","material":"Ziegel|Beton|Metall|Bitumen|Kies|Schiefer","farbe":"rot|grau|schwarz|braun","zustand":"gut|mittel|schlecht","hindernisse_anzahl":0,"hindernisse_typen":[],"hat_solaranlage":false,"freie_flaeche_prozent":80,"pv_eignung":"hervorragend|sehr gut|gut|mittel|schlecht","geschaetzte_kw":100,"begruendung":"kurz"}"""


def load_progress():
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, 'r') as f:
            return set(json.load(f).get("processed", []))
    return set()


def load_results():
    if RESULTS_FILE.exists():
        with open(RESULTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_results(results):
    with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)


def save_progress(processed_set):
    with open(PROGRESS_FILE, 'w') as f:
        json.dump({"processed": list(processed_set)}, f)


def analyze_single_image(args):
    """Analysiert ein einzelnes Bild (für Thread) mit Retry bei 429"""
    img_path, model = args
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            image = Image.open(img_path)
            
            response = model.generate_content(
                [ANALYSIS_PROMPT, image],
                generation_config=genai.types.GenerationConfig(
                    temperature=0.1,
                    max_output_tokens=400
                )
            )
            
            content = response.text.strip()
            
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            result = json.loads(content.strip())
            result['image'] = img_path.name
            
            # Koordinaten aus Dateiname
            parts = img_path.stem.split('_')
            if len(parts) >= 3:
                try:
                    result['lat'] = float(parts[-2])
                    result['lon'] = float(parts[-1])
                except:
                    pass
            
            with lock:
                stats["success"] += 1
                stats["processed"] += 1
            
            return img_path.name, result, None
            
        except Exception as e:
            error_str = str(e)
            if "429" in error_str and attempt < max_retries - 1:
                # Rate limit - warte und versuche erneut
                time.sleep(30)
                continue
            
            with lock:
                stats["error"] += 1
                stats["processed"] += 1
            return img_path.name, None, error_str


def create_annotated_image(img_path: Path, result: dict):
    """Erstellt annotiertes Bild mit Info-Box"""
    image = Image.open(img_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    width, height = image.size
    
    try:
        font = ImageFont.truetype("arial.ttf", 14)
        font_small = ImageFont.truetype("arial.ttf", 12)
    except:
        font = ImageFont.load_default()
        font_small = font
    
    # Info-Box Daten
    dach_typ = result.get('dach_typ', '?')
    material = result.get('material', '?')
    farbe = result.get('farbe', '?')
    zustand = result.get('zustand', '?')
    hindernisse = result.get('hindernisse_anzahl', 0)
    pv_eignung = result.get('pv_eignung', '?')
    freie_flaeche = result.get('freie_flaeche_prozent', '?')
    kw = result.get('geschaetzte_kw', '?')
    
    # Eignung-Farbe
    eignung_colors = {
        'hervorragend': (40, 167, 69),   # Grün
        'sehr gut': (23, 162, 184),       # Blau
        'gut': (255, 193, 7),             # Gelb
        'mittel': (255, 133, 27),         # Orange
        'schlecht': (220, 53, 69)         # Rot
    }
    eignung_color = eignung_colors.get(pv_eignung, (128, 128, 128))
    
    # Info-Box zeichnen (oben links)
    box_lines = [
        f"🏠 {dach_typ}",
        f"📦 {material} ({farbe})",
        f"🔧 Zustand: {zustand}",
        f"🚧 Hindernisse: {hindernisse}",
        f"📐 Freie Fläche: {freie_flaeche}%",
        f"⚡ ~{kw} kW",
    ]
    
    line_height = 22
    box_width = 220
    box_height = len(box_lines) * line_height + 40
    
    # Halbtransparenter Hintergrund
    overlay = Image.new('RGBA', image.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.rectangle([10, 10, 10 + box_width, 10 + box_height], fill=(0, 0, 0, 180))
    
    # Eignung-Banner
    overlay_draw.rectangle([10, 10, 10 + box_width, 40], fill=eignung_color + (220,))
    
    image = Image.alpha_composite(image.convert('RGBA'), overlay).convert('RGB')
    draw = ImageDraw.Draw(image)
    
    # Eignung-Text
    draw.text((20, 16), f"PV: {pv_eignung.upper()}", fill=(255, 255, 255), font=font)
    
    # Info-Zeilen
    y = 48
    for line in box_lines:
        draw.text((18, y), line, fill=(255, 255, 255), font=font_small)
        y += line_height
    
    # Speichern
    annotated_path = ANNOTATED_DIR / f"annotated_{img_path.name}"
    image.save(annotated_path, quality=92)


def main():
    print("=" * 70)
    print("GEMINI 2.0 - PARALLELE DACH-ANALYSE")
    print(f"Workers: {MAX_WORKERS}")
    print("=" * 70)
    
    # Modell laden
    model = genai.GenerativeModel('gemini-2.0-flash-exp')
    
    # Alle Bilder finden
    all_images = sorted(LUFTBILDER_DIR.glob('*.jpg'))  # ALLE Bilder
    total = len(all_images)
    print(f"\nGefunden: {total} Bilder (erste 10)")
    
    # Bereits verarbeitete überspringen
    processed = load_progress()
    results = load_results()
    
    to_process = [img for img in all_images if img.name not in processed]
    
    if len(processed) > 0:
        print(f"Bereits analysiert: {len(processed)} (Resume-Modus)")
    
    print(f"Zu verarbeiten: {len(to_process)}")
    print(f"Geschätzte Zeit: ~{len(to_process) / MAX_WORKERS * 2 / 60:.1f} Minuten")
    print("-" * 70)
    
    if not to_process:
        print("Alle Bilder bereits analysiert!")
        return
    
    start_time = time.time()
    
    # Parallel verarbeiten
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Tasks erstellen
        futures = {
            executor.submit(analyze_single_image, (img, model)): img 
            for img in to_process
        }
        
        # Ergebnisse sammeln
        for future in as_completed(futures):
            img_name, result, error = future.result()
            
            if result:
                results[img_name] = result
                processed.add(img_name)
                status = f"✓ {result.get('dach_typ', '?')[:10]} / {result.get('pv_eignung', '?')}"
            else:
                status = f"❌ {error[:30]}"
            
            # Fortschritt anzeigen
            elapsed = time.time() - start_time
            rate = stats["processed"] / elapsed if elapsed > 0 else 0
            remaining = (len(to_process) - stats["processed"]) / rate / 60 if rate > 0 else 0
            
            print(f"[{stats['processed']}/{len(to_process)}] {img_name[:40]}... {status} (ETA: {remaining:.1f}min)")
            
            # Regelmäßig speichern
            if stats["processed"] % 50 == 0:
                save_results(results)
                save_progress(processed)
            
            # Pause um Rate-Limits zu vermeiden (Free Tier: 15 RPM)
            time.sleep(5)
    
    # Final speichern
    save_results(results)
    save_progress(processed)
    
    elapsed_total = time.time() - start_time
    
    print("\n" + "=" * 70)
    print("ANALYSE ABGESCHLOSSEN")
    print("=" * 70)
    print(f"Erfolgreich: {stats['success']}")
    print(f"Fehler: {stats['error']}")
    print(f"Zeit: {elapsed_total/60:.1f} Minuten")
    print(f"Geschwindigkeit: {stats['processed']/elapsed_total:.1f} Bilder/Sekunde")
    print(f"Kosten: ~${len(results) * 0.001:.2f}")
    print(f"\nErgebnisse: {RESULTS_FILE}")
    
    # Statistiken
    if results:
        dach_typen = {}
        materialien = {}
        eignungen = {}
        
        for r in results.values():
            dt = r.get('dach_typ', 'Unbekannt')
            dach_typen[dt] = dach_typen.get(dt, 0) + 1
            
            mat = r.get('material', 'Unbekannt')
            materialien[mat] = materialien.get(mat, 0) + 1
            
            eig = r.get('pv_eignung', 'Unbekannt')
            eignungen[eig] = eignungen.get(eig, 0) + 1
        
        print("\n📊 STATISTIKEN:")
        print(f"Dachtypen: {dict(sorted(dach_typen.items(), key=lambda x: -x[1]))}")
        print(f"Materialien: {dict(sorted(materialien.items(), key=lambda x: -x[1]))}")
        print(f"PV-Eignung: {dict(sorted(eignungen.items(), key=lambda x: -x[1]))}")


if __name__ == "__main__":
    main()
