"""
Vollständige Dach-Analyse mit GPT-4 Vision
Erkennt: Hindernisse, Dachart, Material, PV-Eignung

Benötigt: OpenAI API Key (https://platform.openai.com/api-keys)
"""

import json
import base64
import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# Konfiguration
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENAI_KEY", "")
LUFTBILDER_DIR = Path("data/final/dortmund/luftbilder")
OUTPUT_DIR = Path("data/final/dortmund/roof_analysis")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Analyse-Prompt für GPT-4 Vision
ANALYSIS_PROMPT = """Analysiere dieses Luftbild eines Daches für eine PV-Anlagen-Installation.

Antworte NUR im folgenden JSON-Format (keine anderen Texte):

{
  "dach_typ": "Flachdach | Satteldach | Walmdach | Pultdach | Mansarddach | Unbekannt",
  "dach_material": "Ziegel | Beton | Metall | Bitumen | Schiefer | Gründach | Unbekannt",
  "dach_farbe": "rot | grau | schwarz | braun | grün | andere",
  "dach_zustand": "gut | mittel | schlecht | unklar",
  "hindernisse": [
    {"typ": "Schornstein | Gaube | Dachfenster | Antenne | Klimaanlage | Lüftung | Solaranlage | Andere", "anzahl": 1}
  ],
  "hindernisse_beschreibung": "Kurze Beschreibung der sichtbaren Hindernisse",
  "freie_dachflaeche_prozent": 80,
  "pv_eignung": "sehr gut | gut | mittel | schlecht",
  "pv_eignung_begruendung": "Kurze Begründung",
  "besonderheiten": "Weitere relevante Beobachtungen"
}"""


def encode_image(image_path: Path) -> str:
    """Bild als base64 encodieren"""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def analyze_roof(client: OpenAI, image_path: Path) -> dict:
    """Analysiert ein Dachbild mit GPT-4 Vision"""
    
    base64_image = encode_image(image_path)
    
    # Dateiendung für MIME-Type
    suffix = image_path.suffix.lower()
    mime_type = "image/jpeg" if suffix in [".jpg", ".jpeg"] else "image/png"
    
    response = client.chat.completions.create(
        model="gpt-4o",  # oder "gpt-4-vision-preview"
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": ANALYSIS_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{base64_image}",
                            "detail": "high"
                        }
                    }
                ]
            }
        ],
        max_tokens=1000
    )
    
    # JSON aus Antwort extrahieren
    content = response.choices[0].message.content
    
    # Versuche JSON zu parsen
    try:
        # Falls in Markdown-Block
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
        
        return json.loads(content.strip())
    except json.JSONDecodeError:
        return {"raw_response": content, "parse_error": True}


def main():
    print("=" * 60)
    print("DACH-ANALYSE MIT GPT-4 VISION")
    print("=" * 60)
    
    if not OPENAI_API_KEY:
        print("\n❌ Kein OPENAI_API_KEY in .env gefunden!")
        print("\nSo bekommst du einen API Key:")
        print("1. Gehe zu: https://platform.openai.com/api-keys")
        print("2. Erstelle neuen API Key")
        print("3. Füge zu .env hinzu: OPENAI_API_KEY=sk-...")
        print("\nKosten: ca. $0.01-0.03 pro Bild (gpt-4o)")
        return
    
    # OpenAI Client
    client = OpenAI(api_key=OPENAI_API_KEY)
    
    # Bilder finden
    images = list(LUFTBILDER_DIR.glob("*.jpg"))[:5]  # Nur 5 für Test
    
    if not images:
        print(f"Keine Bilder in {LUFTBILDER_DIR}")
        return
    
    print(f"\nAnalysiere {len(images)} Bilder...")
    print("(Kosten: ca. $0.01-0.03 pro Bild)\n")
    
    all_results = []
    
    for i, img_path in enumerate(images, 1):
        print(f"[{i}/{len(images)}] {img_path.name}")
        
        try:
            result = analyze_roof(client, img_path)
            result["image"] = img_path.name
            
            if "parse_error" not in result:
                print(f"  ✓ Dach: {result.get('dach_typ', '?')} ({result.get('dach_material', '?')})")
                print(f"  ✓ Hindernisse: {len(result.get('hindernisse', []))}")
                print(f"  ✓ PV-Eignung: {result.get('pv_eignung', '?')}")
            else:
                print(f"  ⚠ JSON Parse-Fehler")
            
            all_results.append(result)
            
        except Exception as e:
            print(f"  ❌ Fehler: {e}")
            all_results.append({"image": img_path.name, "error": str(e)})
    
    # Ergebnisse speichern
    output_file = OUTPUT_DIR / "roof_analysis_gpt4.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    
    print("\n" + "=" * 60)
    print("ZUSAMMENFASSUNG")
    print("=" * 60)
    
    successful = [r for r in all_results if "error" not in r and "parse_error" not in r]
    
    if successful:
        # Statistiken
        dach_typen = {}
        materialien = {}
        eignungen = {}
        
        for r in successful:
            dt = r.get("dach_typ", "Unbekannt")
            dach_typen[dt] = dach_typen.get(dt, 0) + 1
            
            mat = r.get("dach_material", "Unbekannt")
            materialien[mat] = materialien.get(mat, 0) + 1
            
            eig = r.get("pv_eignung", "Unbekannt")
            eignungen[eig] = eignungen.get(eig, 0) + 1
        
        print(f"\nDachtypen: {dach_typen}")
        print(f"Materialien: {materialien}")
        print(f"PV-Eignung: {eignungen}")
    
    print(f"\nErgebnisse: {output_file}")


if __name__ == "__main__":
    main()
