"""
Test verschiedener AI-Modelle für Dach-Analyse
Vergleicht: GPT-4o (neu), Claude 3.5 Sonnet, Gemini 2.0
"""

import json
import base64
import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv

load_dotenv()

OUTPUT_DIR = Path('data/final/dortmund/roof_analysis')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Verbesserter Prompt - präziser und strenger
ANALYSIS_PROMPT = """Du bist ein Experte für Dachanalyse und PV-Anlagen.

Analysiere dieses Luftbild eines Gebäudedaches SEHR GENAU.

WICHTIG - Suche aktiv nach diesen Hindernissen:
- Schornsteine (rechteckig oder rund, oft gemauert)
- Dachgauben (Aufbauten mit eigenen Fenstern)
- Dachfenster/Skylights (in die Dachfläche eingelassen)
- Klimaanlagen/HVAC (Kästen auf Flachdächern)
- Lüftungsrohre/-hauben
- Antennen/Satellitenschüsseln
- Bestehende Solaranlagen

Gib für JEDES gefundene Hindernis die Position als Prozent an:
- 0% = linker/oberer Rand
- 100% = rechter/unterer Rand
- Mitte des Bildes = 50%

Antworte NUR mit diesem JSON (keine Markdown-Blöcke, kein anderer Text):
{"dach_typ":"Flachdach|Satteldach|Walmdach|Pultdach|Mansarddach|Sheddach","material":"Ziegel rot|Ziegel braun|Beton|Metall|Bitumen|Schiefer|Gründach|Kies","zustand":"neu|gut|mittel|sanierungsbedürftig","hindernisse":[{"typ":"Schornstein|Gaube|Dachfenster|Klimaanlage|Lüftung|Antenne|Satellit|Solaranlage","x":50,"y":50,"breite":10,"hoehe":10,"beschreibung":"kurze Beschreibung"}],"schatten_bereiche":"keine|wenig|mittel|viel","ausrichtung":"Nord|Süd|Ost|West|Süd-West|Süd-Ost","freie_flaeche_prozent":80,"pv_eignung":"hervorragend|sehr gut|gut|mittel|schlecht","pv_kapazitaet_kw_schaetzung":100,"begruendung":"Detaillierte Begründung"}"""

# Farben
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


def test_gpt4o_latest(image_path: Path):
    """Test mit GPT-4o neueste Version"""
    from openai import OpenAI
    
    api_key = os.environ.get('OPENAI_API_KEY') or os.environ.get('OPENAI_KEY')
    client = OpenAI(api_key=api_key)
    
    with open(image_path, 'rb') as f:
        img_b64 = base64.b64encode(f.read()).decode()
    
    print("\n🔵 GPT-4o (2024-11-20) - Neueste Version...")
    
    response = client.chat.completions.create(
        model='gpt-4o-2024-11-20',  # Neueste Version
        messages=[{
            'role': 'user',
            'content': [
                {'type': 'text', 'text': ANALYSIS_PROMPT},
                {'type': 'image_url', 'image_url': {
                    'url': f'data:image/jpeg;base64,{img_b64}',
                    'detail': 'high'  # Maximale Auflösung
                }}
            ]
        }],
        max_tokens=1500,
        temperature=0.1  # Weniger kreativ, mehr präzise
    )
    
    content = response.choices[0].message.content
    tokens = response.usage.total_tokens
    
    try:
        # Bereinigen
        if "```" in content:
            content = content.split("```")[1] if "```json" not in content else content.split("```json")[1].split("```")[0]
        result = json.loads(content.strip())
        result['model'] = 'gpt-4o-2024-11-20'
        result['tokens'] = tokens
        print(f"   ✓ Hindernisse: {len(result.get('hindernisse', []))}")
        for h in result.get('hindernisse', []):
            print(f"     - {h.get('typ')}: {h.get('beschreibung', '')} @ ({h.get('x')}%, {h.get('y')}%)")
        return result
    except Exception as e:
        print(f"   ❌ Fehler: {e}")
        return {"error": str(e), "raw": content}


def test_gpt4_turbo(image_path: Path):
    """Test mit GPT-4 Turbo (sehr gute Vision)"""
    from openai import OpenAI
    
    api_key = os.environ.get('OPENAI_API_KEY') or os.environ.get('OPENAI_KEY')
    client = OpenAI(api_key=api_key)
    
    with open(image_path, 'rb') as f:
        img_b64 = base64.b64encode(f.read()).decode()
    
    print("\n🟢 GPT-4 Turbo...")
    
    response = client.chat.completions.create(
        model='gpt-4-turbo',
        messages=[{
            'role': 'user',
            'content': [
                {'type': 'text', 'text': ANALYSIS_PROMPT},
                {'type': 'image_url', 'image_url': {
                    'url': f'data:image/jpeg;base64,{img_b64}',
                    'detail': 'high'
                }}
            ]
        }],
        max_tokens=1500,
        temperature=0.1
    )
    
    content = response.choices[0].message.content
    tokens = response.usage.total_tokens
    
    try:
        if "```" in content:
            content = content.split("```")[1] if "```json" not in content else content.split("```json")[1].split("```")[0]
        result = json.loads(content.strip())
        result['model'] = 'gpt-4-turbo'
        result['tokens'] = tokens
        print(f"   ✓ Hindernisse: {len(result.get('hindernisse', []))}")
        for h in result.get('hindernisse', []):
            print(f"     - {h.get('typ')}: {h.get('beschreibung', '')} @ ({h.get('x')}%, {h.get('y')}%)")
        return result
    except Exception as e:
        print(f"   ❌ Fehler: {e}")
        return {"error": str(e), "raw": content}


def annotate_image(image_path: Path, result: dict, suffix: str):
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
        w_pct = max(h.get('breite', 10), 6)
        h_pct = max(h.get('hoehe', 10), 6)
        
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
        draw.line([cx-10, cy, cx+10, cy], fill=color, width=3)
        draw.line([cx, cy-10, cx, cy+10], fill=color, width=3)
        
        # Label
        label = h.get('typ', '?')
        draw.rectangle([x1, y1-20, x1+len(label)*9+6, y1], fill=color)
        draw.text((x1+3, y1-18), label, fill=(0,0,0), font=font)
    
    # Info-Box
    info = [
        f"Modell: {result.get('model', '?')}",
        f"Dach: {result.get('dach_typ', '?')} / {result.get('material', '?')}",
        f"Hindernisse: {len(result.get('hindernisse', []))}",
        f"PV-Eignung: {result.get('pv_eignung', '?')}",
        f"Kapazität: ~{result.get('pv_kapazitaet_kw_schaetzung', '?')} kW"
    ]
    draw.rectangle([5, 5, 280, 5 + len(info)*18 + 5], fill=(0, 0, 0))
    for i, line in enumerate(info):
        draw.text((10, 8 + i*18), line, fill=(255, 255, 255), font=font)
    
    out_path = OUTPUT_DIR / f"compare_{suffix}_{image_path.stem}.jpg"
    image.save(out_path, quality=95)
    print(f"   → Bild: {out_path.name}")
    return out_path


def main():
    print("=" * 60)
    print("MODELL-VERGLEICH: DACH-ANALYSE")
    print("=" * 60)
    
    # Test-Bild mit Hindernissen
    img_path = Path('data/final/dortmund/luftbilder/rank_002_51.564617_7.424936.jpg')
    print(f"\nTestbild: {img_path.name}")
    
    results = {}
    
    # Test GPT-4o neueste
    try:
        result = test_gpt4o_latest(img_path)
        results['gpt4o_latest'] = result
        if 'error' not in result:
            annotate_image(img_path, result, 'gpt4o_latest')
    except Exception as e:
        print(f"   ❌ GPT-4o Fehler: {e}")
    
    # Test GPT-4 Turbo
    try:
        result = test_gpt4_turbo(img_path)
        results['gpt4_turbo'] = result
        if 'error' not in result:
            annotate_image(img_path, result, 'gpt4_turbo')
    except Exception as e:
        print(f"   ❌ GPT-4 Turbo Fehler: {e}")
    
    # Ergebnisse speichern
    with open(OUTPUT_DIR / 'model_comparison.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print("\n" + "=" * 60)
    print("VERGLEICH")
    print("=" * 60)
    
    for name, r in results.items():
        if 'error' not in r:
            print(f"\n{name}:")
            print(f"  Dach: {r.get('dach_typ')} / {r.get('material')}")
            print(f"  Hindernisse: {len(r.get('hindernisse', []))}")
            print(f"  PV-Eignung: {r.get('pv_eignung')}")
            print(f"  Tokens: {r.get('tokens')}")


if __name__ == "__main__":
    main()
