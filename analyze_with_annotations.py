"""
Dach-Analyse mit GPT-4o + Visuelle Markierungen
GPT-4o gibt Koordinaten zurück, Python zeichnet sie ein
"""

import json
import base64
import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

api_key = os.environ.get('OPENAI_API_KEY') or os.environ.get('OPENAI_KEY')
client = OpenAI(api_key=api_key)

OUTPUT_DIR = Path('data/final/dortmund/roof_analysis')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Farben für verschiedene Hindernistypen
COLORS = {
    "schornstein": (255, 0, 0),      # Rot
    "gaube": (0, 0, 255),            # Blau
    "dachfenster": (0, 255, 0),      # Grün
    "antenne": (255, 165, 0),        # Orange
    "klimaanlage": (128, 0, 128),    # Lila
    "lüftung": (255, 192, 203),      # Rosa
    "solaranlage": (255, 255, 0),    # Gelb
    "default": (255, 255, 255)       # Weiß
}

ANALYSIS_PROMPT = """Analysiere dieses Dach-Luftbild für PV-Installation.

WICHTIG: Gib für jedes Hindernis die ungefähre Position als Prozent der Bildbreite/Höhe an.
Das Bild ist 100% x 100%. Position (0,0) ist oben-links, (100,100) ist unten-rechts.

Antworte NUR als JSON (kein Markdown, keine Erklärung):
{
  "dach_typ": "Flachdach | Satteldach | Walmdach | Pultdach | Mansarddach",
  "material": "Ziegel | Beton | Metall | Bitumen | Schiefer | Gründach",
  "material_farbe": "rot | grau | schwarz | braun | grün",
  "zustand": "gut | mittel | schlecht",
  "hindernisse": [
    {
      "typ": "Schornstein | Gaube | Dachfenster | Antenne | Klimaanlage | Lüftung | Solaranlage",
      "position_x_prozent": 50,
      "position_y_prozent": 30,
      "breite_prozent": 10,
      "hoehe_prozent": 10
    }
  ],
  "freie_flaeche_prozent": 80,
  "pv_eignung": "sehr gut | gut | mittel | schlecht",
  "begruendung": "Kurze Begründung für die PV-Eignung"
}"""


def analyze_and_annotate(image_path: Path) -> dict:
    """Analysiert Bild mit GPT-4o und zeichnet Markierungen"""
    
    print(f"\n📷 Analysiere: {image_path.name}")
    
    # Bild laden
    image = Image.open(image_path).convert("RGB")
    width, height = image.size
    
    # Bild als base64
    with open(image_path, 'rb') as f:
        img_b64 = base64.b64encode(f.read()).decode()
    
    # GPT-4o API Call
    response = client.chat.completions.create(
        model='gpt-4o',
        messages=[{
            'role': 'user',
            'content': [
                {'type': 'text', 'text': ANALYSIS_PROMPT},
                {'type': 'image_url', 'image_url': {'url': f'data:image/jpeg;base64,{img_b64}', 'detail': 'high'}}
            ]
        }],
        max_tokens=1000
    )
    
    content = response.choices[0].message.content
    tokens = response.usage.total_tokens
    
    # JSON parsen
    try:
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
        
        result = json.loads(content.strip())
    except json.JSONDecodeError as e:
        print(f"  ⚠ JSON Parse-Fehler: {e}")
        return {"error": str(e), "raw": content}
    
    # Ergebnis ausgeben
    print(f"  Dach: {result.get('dach_typ', '?')} ({result.get('material', '?')})")
    print(f"  Hindernisse: {len(result.get('hindernisse', []))}")
    print(f"  PV-Eignung: {result.get('pv_eignung', '?')}")
    print(f"  Tokens: {tokens} (~${tokens * 0.000005:.4f})")
    
    # Annotiertes Bild erstellen
    annotated = image.copy()
    draw = ImageDraw.Draw(annotated)
    
    try:
        font = ImageFont.truetype("arial.ttf", 16)
        font_small = ImageFont.truetype("arial.ttf", 12)
    except:
        font = ImageFont.load_default()
        font_small = font
    
    # Hindernisse einzeichnen
    for h in result.get('hindernisse', []):
        typ = h.get('typ', 'Unbekannt').lower()
        x_pct = h.get('position_x_prozent', 50)
        y_pct = h.get('position_y_prozent', 50)
        w_pct = max(h.get('breite_prozent', 10), 8)  # Minimum 8%
        h_pct = max(h.get('hoehe_prozent', 10), 8)   # Minimum 8%
        
        # Prozent zu Pixel
        x = int(x_pct / 100 * width)
        y = int(y_pct / 100 * height)
        w = int(w_pct / 100 * width)
        h_px = int(h_pct / 100 * height)
        
        # Mindestgröße sicherstellen
        w = max(w, 40)
        h_px = max(h_px, 40)
        
        # Farbe wählen
        color = COLORS.get("default")
        for key, c in COLORS.items():
            if key in typ:
                color = c
                break
        
        # Rechteck zeichnen (dicker)
        x1, y1 = x - w//2, y - h_px//2
        x2, y2 = x + w//2, y + h_px//2
        
        # Sicherstellen dass Box im Bild ist
        x1 = max(5, x1)
        y1 = max(25, y1)  # Platz für Label lassen
        x2 = min(width - 5, x2)
        y2 = min(height - 5, y2)
        
        draw.rectangle([x1, y1, x2, y2], outline=color, width=4)
        
        # Kreis in der Mitte für bessere Sichtbarkeit
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        r = 8
        draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill=color)
        
        # Label mit Hintergrund
        label = h.get('typ', 'Hindernis')
        label_width = len(label) * 9 + 8
        draw.rectangle([x1, y1-22, x1+label_width, y1-2], fill=color)
        draw.text((x1+4, y1-20), label, fill=(0, 0, 0), font=font_small)
    
    # Info-Box oben links
    info_lines = [
        f"Dach: {result.get('dach_typ', '?')}",
        f"Material: {result.get('material', '?')}",
        f"PV-Eignung: {result.get('pv_eignung', '?')}",
        f"Freie Fläche: {result.get('freie_flaeche_prozent', '?')}%"
    ]
    
    # Hintergrund für Info-Box
    box_height = len(info_lines) * 20 + 10
    draw.rectangle([5, 5, 220, box_height], fill=(0, 0, 0, 180))
    
    for i, line in enumerate(info_lines):
        draw.text((10, 10 + i*20), line, fill=(255, 255, 255), font=font_small)
    
    # Speichern
    output_path = OUTPUT_DIR / f"annotated_{image_path.stem}.jpg"
    annotated.save(output_path, quality=95)
    print(f"  ✓ Gespeichert: {output_path.name}")
    
    result['image'] = image_path.name
    result['tokens'] = tokens
    
    return result


def main():
    print("=" * 60)
    print("DACH-ANALYSE MIT GPT-4o + VISUELLE MARKIERUNGEN")
    print("=" * 60)
    
    # Test mit ersten 3 Bildern
    luftbilder = Path('data/final/dortmund/luftbilder')
    images = list(luftbilder.glob('*.jpg'))[:3]
    
    print(f"\nAnalysiere {len(images)} Testbilder...")
    
    all_results = []
    total_tokens = 0
    
    for img_path in images:
        result = analyze_and_annotate(img_path)
        all_results.append(result)
        total_tokens += result.get('tokens', 0)
    
    # Ergebnisse speichern
    results_file = OUTPUT_DIR / "analysis_with_coordinates.json"
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    
    print("\n" + "=" * 60)
    print("ZUSAMMENFASSUNG")
    print("=" * 60)
    print(f"Bilder analysiert: {len(all_results)}")
    print(f"Tokens gesamt: {total_tokens}")
    print(f"Kosten gesamt: ~${total_tokens * 0.000005:.4f}")
    print(f"\nErgebnisse: {results_file}")
    print(f"Annotierte Bilder: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
