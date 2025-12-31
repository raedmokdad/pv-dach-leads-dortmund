"""
Test Gemini 2.0 Flash für Dach-Analyse
Schnell, günstig und sehr gut bei Objekterkennung
"""

import json
import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

# Konfiguration
genai.configure(api_key=os.environ.get('GOOGLE_AI_API_KEY'))

OUTPUT_DIR = Path('data/final/dortmund/roof_analysis')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

COLORS = {
    "schornstein": (255, 0, 0),
    "gaube": (0, 0, 255),
    "dachfenster": (0, 255, 0),
    "klimaanlage": (255, 165, 0),
    "lüftung": (255, 192, 203),
    "antenne": (255, 255, 0),
    "satellit": (0, 255, 255),
    "solaranlage": (128, 0, 128),
    "default": (255, 255, 255)
}

ANALYSIS_PROMPT = """Du bist ein Experte für Dachanalyse aus Luftbildern.

Analysiere dieses Luftbild SEHR GENAU. Schau dir das Bild wirklich an!

WICHTIG für Positionen:
- Gib EXAKTE Positionen in Prozent an, nicht gerundete Werte!
- Schau genau hin wo jedes Objekt im Bild ist
- 0% = ganz links/oben, 100% = ganz rechts/unten
- Nutze präzise Werte wie 23%, 47%, 82% - NICHT nur 20%, 40%, 60%!

Finde diese Elemente:
1. DACHTYP: Flachdach, Satteldach, Walmdach, Pultdach?
2. MATERIAL: Ziegel, Beton, Metall, Bitumen, Kies?
3. HINDERNISSE (nur REAL sichtbare!):
   - Schornsteine
   - Dachgauben
   - Dachfenster/Skylights
   - Klimaanlagen/HVAC
   - Lüftungsrohre/-hauben
   - Antennen, Satellitenschüsseln
   - Bestehende Solaranlagen

NUR JSON ausgeben (kein Text davor oder danach):
{"dach_typ":"...","material":"...","farbe":"...","zustand":"gut|mittel|schlecht","hindernisse":[{"typ":"...","x":47,"y":23,"breite":5,"hoehe":5,"details":"..."}],"anzahl_hindernisse":3,"freie_flaeche_prozent":80,"pv_eignung":"hervorragend|sehr gut|gut|mittel|schlecht","geschaetzte_kw":100,"begruendung":"..."}

WICHTIG: Nur Hindernisse auflisten die du WIRKLICH siehst! Lieber weniger aber korrekt."""


def analyze_with_gemini(image_path: Path):
    """Analysiert Bild mit Gemini 2.0 Flash"""
    
    print(f"\n📷 Analysiere mit Gemini 2.0: {image_path.name}")
    
    # Modell laden
    model = genai.GenerativeModel('gemini-2.0-flash-exp')
    
    # Bild laden
    image = Image.open(image_path)
    
    # Analyse
    response = model.generate_content(
        [ANALYSIS_PROMPT, image],
        generation_config=genai.types.GenerationConfig(
            temperature=0.1,
            max_output_tokens=2000
        )
    )
    
    content = response.text
    
    # JSON parsen
    try:
        # Bereinigen
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
        
        result = json.loads(content.strip())
        result['model'] = 'gemini-2.0-flash-exp'
        
        print(f"   Dach: {result.get('dach_typ')} / {result.get('material')}")
        print(f"   Hindernisse: {len(result.get('hindernisse', []))}")
        for h in result.get('hindernisse', []):
            print(f"     - {h.get('typ')}: {h.get('details', '')} @ ({h.get('x')}%, {h.get('y')}%)")
        print(f"   PV-Eignung: {result.get('pv_eignung')}")
        
        return result
        
    except json.JSONDecodeError as e:
        print(f"   ⚠ JSON Fehler: {e}")
        print(f"   Raw: {content[:200]}")
        return {"error": str(e), "raw": content}


def annotate_image(image_path: Path, result: dict):
    """Zeichnet Hindernisse auf Bild"""
    
    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    width, height = image.size
    
    try:
        font = ImageFont.truetype("arial.ttf", 14)
    except:
        font = ImageFont.load_default()
    
    for h in result.get('hindernisse', []):
        typ = h.get('typ', 'Unbekannt').lower()
        x_pct = h.get('x', 50)
        y_pct = h.get('y', 50)
        w_pct = max(h.get('breite', 8), 6)
        h_pct = max(h.get('hoehe', 8), 6)
        
        x = int(x_pct / 100 * width)
        y = int(y_pct / 100 * height)
        w = max(int(w_pct / 100 * width), 50)
        h_px = max(int(h_pct / 100 * height), 50)
        
        color = COLORS.get("default")
        for key, c in COLORS.items():
            if key in typ:
                color = c
                break
        
        x1, y1 = max(5, x - w//2), max(25, y - h_px//2)
        x2, y2 = min(width-5, x + w//2), min(height-5, y + h_px//2)
        
        # Rechteck + Kreuz
        draw.rectangle([x1, y1, x2, y2], outline=color, width=4)
        cx, cy = (x1+x2)//2, (y1+y2)//2
        draw.line([cx-12, cy, cx+12, cy], fill=color, width=3)
        draw.line([cx, cy-12, cx, cy+12], fill=color, width=3)
        
        # Label
        label = h.get('typ', '?')
        draw.rectangle([x1, y1-22, x1+len(label)*9+6, y1], fill=color)
        draw.text((x1+3, y1-18), label, fill=(0,0,0), font=font)
    
    # Info-Box
    info = [
        f"🔷 GEMINI 2.0 FLASH",
        f"Dach: {result.get('dach_typ', '?')} / {result.get('material', '?')}",
        f"Hindernisse: {len(result.get('hindernisse', []))}",
        f"PV-Eignung: {result.get('pv_eignung', '?')}",
        f"Kapazität: ~{result.get('geschaetzte_kw', '?')} kW"
    ]
    draw.rectangle([5, 5, 300, 5 + len(info)*20 + 5], fill=(0, 0, 0))
    for i, line in enumerate(info):
        draw.text((10, 8 + i*20), line, fill=(255, 255, 255), font=font)
    
    out_path = OUTPUT_DIR / f"gemini_{image_path.stem}.jpg"
    image.save(out_path, quality=95)
    print(f"   ✓ Gespeichert: {out_path.name}")
    return out_path


def main():
    print("=" * 60)
    print("GEMINI 2.0 FLASH - DACH-ANALYSE")
    print("=" * 60)
    
    # Test mit 3 Bildern
    luftbilder = Path('data/final/dortmund/luftbilder')
    images = list(luftbilder.glob('*.jpg'))[:3]
    
    print(f"\nAnalysiere {len(images)} Bilder...")
    
    all_results = []
    
    for img_path in images:
        try:
            result = analyze_with_gemini(img_path)
            result['image'] = img_path.name
            all_results.append(result)
            
            if 'error' not in result:
                annotate_image(img_path, result)
                
        except Exception as e:
            print(f"   ❌ Fehler: {e}")
            all_results.append({"image": img_path.name, "error": str(e)})
    
    # Speichern
    with open(OUTPUT_DIR / 'gemini_results.json', 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    
    print("\n" + "=" * 60)
    print("ERGEBNISSE")
    print("=" * 60)
    
    for r in all_results:
        if 'error' not in r:
            print(f"\n{r.get('image')}:")
            print(f"  Dach: {r.get('dach_typ')} / {r.get('material')}")
            print(f"  Hindernisse: {len(r.get('hindernisse', []))}")
            print(f"  PV: {r.get('pv_eignung')} (~{r.get('geschaetzte_kw')} kW)")


if __name__ == "__main__":
    main()
