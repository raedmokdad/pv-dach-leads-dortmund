"""
Dach- und Hindernis-Erkennung mit Grounding DINO

Erkennt auf Luftbildern:
- Dächer (roof)
- Schornsteine (chimney)
- Dachfenster (skylight)
- Klimaanlagen / HVAC (air conditioning)
- Gauben (dormer)
- Solarpanele (solar panel)
- Antennen (antenna)
- Dachluken (roof hatch)

Verwendet Grounding DINO für Zero-Shot Object Detection.
"""

import json
from pathlib import Path
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, asdict
from tqdm import tqdm
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Pfade
from .config import FINAL_DORTMUND, PROCESSED_DORTMUND

# Erkennung-Prompts (Englisch für bessere Modell-Performance)
DETECTION_PROMPTS = {
    "obstacles": "chimney . skylight . dormer . air conditioning unit . antenna . roof hatch . ventilation",
    "solar": "solar panel . photovoltaic panel",
    "roof": "flat roof . pitched roof . gabled roof . hip roof",
}

# Kombinierter Prompt für alle Hindernisse
FULL_DETECTION_PROMPT = (
    "chimney . skylight . dormer window . air conditioning unit . "
    "antenna . satellite dish . ventilation . roof hatch . "
    "solar panel . flat roof . pitched roof"
)

@dataclass
class DetectedObject:
    """Erkanntes Objekt auf dem Dach"""
    label: str              # z.B. "chimney", "skylight"
    confidence: float       # 0.0 - 1.0
    bbox: List[float]       # [x1, y1, x2, y2] normalisiert
    area_pct: float         # Prozent der Bildfläche
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass 
class RoofObstacleResult:
    """Ergebnis der Hindernis-Erkennung für ein Gebäude"""
    building_id: str
    image_path: str
    objects: List[DetectedObject]
    obstacle_count: int
    obstacle_types: List[str]
    has_chimney: bool
    has_skylight: bool
    has_dormer: bool
    has_hvac: bool
    has_solar: bool
    obstacle_coverage_pct: float  # Gesamtfläche der Hindernisse
    usable_roof_estimate: str     # "high", "medium", "low"
    
    def to_dict(self) -> Dict:
        result = asdict(self)
        result['objects'] = [obj.to_dict() if hasattr(obj, 'to_dict') else obj for obj in self.objects]
        return result


def check_dependencies() -> bool:
    """Prüft ob alle benötigten Pakete installiert sind"""
    missing = []
    
    try:
        import torch
    except ImportError:
        missing.append("torch (pip install torch)")
    
    try:
        from PIL import Image
    except ImportError:
        missing.append("Pillow (pip install Pillow)")
        
    try:
        import groundingdino
    except ImportError:
        missing.append("groundingdino (pip install groundingdino-py)")
        
    if missing:
        logger.error(f"Fehlende Pakete: {', '.join(missing)}")
        logger.info("\nInstallation:")
        logger.info("pip install torch torchvision")
        logger.info("pip install groundingdino-py")
        return False
    
    return True


def load_groundingdino_model():
    """Lädt das Grounding DINO Modell"""
    try:
        from groundingdino.util.inference import load_model
        import torch
        
        # Modell-Konfiguration
        # Diese werden beim ersten Aufruf heruntergeladen
        config_path = "groundingdino/config/GroundingDINO_SwinT_OGC.py"
        weights_path = "weights/groundingdino_swint_ogc.pth"
        
        # Alternativ: Hugging Face
        try:
            from huggingface_hub import hf_hub_download
            
            # Download von Hugging Face
            config_path = hf_hub_download(
                repo_id="IDEA-Research/grounding-dino-tiny",
                filename="GroundingDINO_SwinT_OGC.py"
            )
            weights_path = hf_hub_download(
                repo_id="IDEA-Research/grounding-dino-tiny", 
                filename="groundingdino_swint_ogc.pth"
            )
        except ImportError:
            logger.warning("huggingface_hub nicht installiert, versuche lokale Pfade...")
        
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Lade Grounding DINO auf {device}...")
        
        model = load_model(config_path, weights_path, device=device)
        return model, device
        
    except Exception as e:
        logger.error(f"Fehler beim Laden des Modells: {e}")
        raise


def detect_obstacles_in_image(
    model, 
    image_path: Path,
    text_prompt: str = FULL_DETECTION_PROMPT,
    box_threshold: float = 0.35,
    text_threshold: float = 0.25,
    device: str = "cpu"
) -> List[DetectedObject]:
    """
    Erkennt Hindernisse in einem Luftbild
    
    Args:
        model: Grounding DINO Modell
        image_path: Pfad zum Luftbild
        text_prompt: Text-Prompt für Erkennung (Objekte mit . getrennt)
        box_threshold: Mindest-Konfidenz für Bounding Box
        text_threshold: Mindest-Konfidenz für Text-Match
        device: "cuda" oder "cpu"
        
    Returns:
        Liste von DetectedObject
    """
    from groundingdino.util.inference import predict
    from PIL import Image
    import torch
    
    # Bild laden
    image = Image.open(image_path).convert("RGB")
    image_width, image_height = image.size
    image_area = image_width * image_height
    
    # Erkennung durchführen
    boxes, logits, phrases = predict(
        model=model,
        image=image,
        caption=text_prompt,
        box_threshold=box_threshold,
        text_threshold=text_threshold,
        device=device
    )
    
    # Ergebnisse verarbeiten
    detected_objects = []
    
    for box, confidence, label in zip(boxes, logits, phrases):
        # Box ist normalisiert (0-1), konvertiere zu Pixel für Flächenberechnung
        x1, y1, x2, y2 = box.tolist()
        
        # Berechne Fläche als Prozent des Bildes
        box_width = (x2 - x1) * image_width
        box_height = (y2 - y1) * image_height
        box_area = box_width * box_height
        area_pct = (box_area / image_area) * 100
        
        detected_objects.append(DetectedObject(
            label=label.strip().lower(),
            confidence=float(confidence),
            bbox=[x1, y1, x2, y2],
            area_pct=round(area_pct, 2)
        ))
    
    return detected_objects


def analyze_obstacles(
    objects: List[DetectedObject],
    building_id: str,
    image_path: str
) -> RoofObstacleResult:
    """
    Analysiert die erkannten Hindernisse und erstellt eine Zusammenfassung
    """
    # Kategorisiere erkannte Objekte
    labels = [obj.label for obj in objects]
    
    has_chimney = any('chimney' in l for l in labels)
    has_skylight = any('skylight' in l or 'window' in l for l in labels)
    has_dormer = any('dormer' in l for l in labels)
    has_hvac = any('air' in l or 'conditioning' in l or 'ventilation' in l for l in labels)
    has_solar = any('solar' in l or 'photovoltaic' in l or 'panel' in l for l in labels)
    
    # Berechne Gesamt-Hindernisfläche (nur nicht-Solar)
    obstacle_area = sum(
        obj.area_pct for obj in objects 
        if 'solar' not in obj.label and 'panel' not in obj.label and 'roof' not in obj.label
    )
    
    # Schätze nutzbare Dachfläche
    if obstacle_area > 20:
        usable_estimate = "low"
    elif obstacle_area > 10:
        usable_estimate = "medium"
    else:
        usable_estimate = "high"
    
    # Obstacle count (ohne Dach-Erkennung)
    obstacle_objects = [
        obj for obj in objects 
        if 'roof' not in obj.label
    ]
    
    unique_types = list(set(obj.label for obj in obstacle_objects))
    
    return RoofObstacleResult(
        building_id=building_id,
        image_path=image_path,
        objects=[obj.to_dict() for obj in objects],
        obstacle_count=len(obstacle_objects),
        obstacle_types=unique_types,
        has_chimney=has_chimney,
        has_skylight=has_skylight,
        has_dormer=has_dormer,
        has_hvac=has_hvac,
        has_solar=has_solar,
        obstacle_coverage_pct=round(obstacle_area, 2),
        usable_roof_estimate=usable_estimate
    )


def process_aerial_images(
    input_dir: Optional[Path] = None,
    output_file: Optional[Path] = None,
    limit: Optional[int] = None,
    box_threshold: float = 0.35
) -> Dict[str, RoofObstacleResult]:
    """
    Verarbeitet alle Luftbilder und erkennt Hindernisse
    
    Args:
        input_dir: Verzeichnis mit Luftbildern (default: FINAL_DORTMUND/luftbilder)
        output_file: JSON-Ausgabedatei (default: PROCESSED_DORTMUND/roof_obstacles.json)
        limit: Maximale Anzahl Bilder (für Tests)
        box_threshold: Mindest-Konfidenz für Erkennung
        
    Returns:
        Dict mit Ergebnissen pro Gebäude-ID
    """
    if not check_dependencies():
        logger.error("Abhängigkeiten nicht erfüllt. Bitte installieren Sie die benötigten Pakete.")
        return {}
    
    input_dir = input_dir or (FINAL_DORTMUND / "luftbilder")
    output_file = output_file or (PROCESSED_DORTMUND / "roof_obstacles.json")
    
    if not input_dir.exists():
        logger.error(f"Luftbild-Verzeichnis nicht gefunden: {input_dir}")
        return {}
    
    # Lade Modell
    model, device = load_groundingdino_model()
    
    # Sammle Bilder
    image_files = list(input_dir.glob("*.jpg")) + list(input_dir.glob("*.png"))
    
    if limit:
        image_files = image_files[:limit]
    
    logger.info(f"Verarbeite {len(image_files)} Luftbilder...")
    
    results = {}
    
    for image_path in tqdm(image_files, desc="Analysiere Dächer"):
        try:
            # Extrahiere Building-ID aus Dateiname
            # Format: rank_001_51.565307_7.420352.jpg
            filename = image_path.stem
            parts = filename.split('_')
            
            # ID aus Koordinaten erstellen
            if len(parts) >= 3:
                building_id = f"{parts[-2]}_{parts[-1]}"
            else:
                building_id = filename
            
            # Erkennung durchführen
            objects = detect_obstacles_in_image(
                model=model,
                image_path=image_path,
                box_threshold=box_threshold,
                device=device
            )
            
            # Analysiere Ergebnisse
            result = analyze_obstacles(
                objects=objects,
                building_id=building_id,
                image_path=str(image_path)
            )
            
            results[building_id] = result
            
        except Exception as e:
            logger.warning(f"Fehler bei {image_path.name}: {e}")
            continue
    
    # Speichere Ergebnisse
    logger.info(f"Speichere Ergebnisse in {output_file}...")
    
    output_data = {
        bid: res.to_dict() for bid, res in results.items()
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    # Statistiken
    total = len(results)
    with_chimney = sum(1 for r in results.values() if r.has_chimney)
    with_skylight = sum(1 for r in results.values() if r.has_skylight)
    with_dormer = sum(1 for r in results.values() if r.has_dormer)
    with_hvac = sum(1 for r in results.values() if r.has_hvac)
    with_solar = sum(1 for r in results.values() if r.has_solar)
    high_usable = sum(1 for r in results.values() if r.usable_roof_estimate == "high")
    
    logger.info(f"\n=== Hindernis-Erkennung abgeschlossen ===")
    logger.info(f"Analysierte Gebäude: {total}")
    logger.info(f"Mit Schornstein: {with_chimney} ({100*with_chimney/total:.1f}%)")
    logger.info(f"Mit Dachfenster: {with_skylight} ({100*with_skylight/total:.1f}%)")
    logger.info(f"Mit Gaube: {with_dormer} ({100*with_dormer/total:.1f}%)")
    logger.info(f"Mit HVAC: {with_hvac} ({100*with_hvac/total:.1f}%)")
    logger.info(f"Mit Solar (bestehend): {with_solar} ({100*with_solar/total:.1f}%)")
    logger.info(f"Hohe Nutzbarkeit: {high_usable} ({100*high_usable/total:.1f}%)")
    
    return results


def run_detection_roboflow(
    api_key: str,
    project_id: str = "roof-chimney-window-and-door",
    version: int = 1,
    input_dir: Optional[Path] = None,
    output_file: Optional[Path] = None,
    limit: Optional[int] = None
) -> Dict[str, Any]:
    """
    Alternative: Nutzt Roboflow API für Erkennung
    
    Vorteile:
    - Kein lokales GPU nötig
    - Speziell trainierte Modelle verfügbar
    
    Args:
        api_key: Roboflow API Key
        project_id: Roboflow Projekt-ID
        version: Modell-Version
    """
    try:
        from roboflow import Roboflow
    except ImportError:
        logger.error("Roboflow nicht installiert: pip install roboflow")
        return {}
    
    input_dir = input_dir or (FINAL_DORTMUND / "luftbilder")
    output_file = output_file or (PROCESSED_DORTMUND / "roof_obstacles_roboflow.json")
    
    # Initialisiere Roboflow
    rf = Roboflow(api_key=api_key)
    project = rf.workspace().project(project_id)
    model = project.version(version).model
    
    image_files = list(input_dir.glob("*.jpg"))[:limit] if limit else list(input_dir.glob("*.jpg"))
    
    results = {}
    
    for image_path in tqdm(image_files, desc="Roboflow Analyse"):
        try:
            prediction = model.predict(str(image_path), confidence=40).json()
            
            building_id = image_path.stem
            results[building_id] = {
                "image": str(image_path),
                "predictions": prediction.get("predictions", [])
            }
        except Exception as e:
            logger.warning(f"Fehler bei {image_path.name}: {e}")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    return results


# Einfache Variante ohne externe Modelle
def simple_obstacle_detection_from_google_solar(
    geojson_path: Optional[Path] = None,
    output_file: Optional[Path] = None
) -> Dict[str, Dict]:
    """
    Einfache Hindernis-Erkennung basierend auf Google Solar Daten
    
    Nutzt die Segment-Statistiken um Hindernisse zu inferieren:
    - Viele kleine Segmente → wahrscheinlich Hindernisse
    - Große Varianz in Sonnenstunden → Schattenwurf durch Hindernisse
    """
    import geopandas as gpd
    
    geojson_path = geojson_path or (PROCESSED_DORTMUND / "buildings_with_google_solar.geojson")
    output_file = output_file or (PROCESSED_DORTMUND / "obstacle_inference.json")
    
    gdf = gpd.read_file(geojson_path)
    
    results = {}
    
    for idx, row in gdf.iterrows():
        building_id = str(row.get('id', idx))
        
        # Extrahiere Google Solar Daten
        segments_count = row.get('google_solar_segments_count', 0)
        shading_factor = row.get('google_solar_shading_factor', 0)
        usable_pct = row.get('google_solar_usable_roof_pct', 100)
        
        # Inferiere Hindernisse
        obstacle_score = 0
        reasons = []
        
        # Viele Segmente = komplexes Dach mit Hindernissen
        if segments_count and segments_count > 5:
            obstacle_score += 20
            reasons.append(f"Komplexes Dach ({segments_count} Segmente)")
        
        # Hoher Schattenfaktor = Hindernisse werfen Schatten
        if shading_factor and shading_factor > 0.2:
            obstacle_score += 30
            reasons.append(f"Hohe Verschattung ({shading_factor:.0%})")
        
        # Geringe nutzbare Fläche
        if usable_pct and usable_pct < 50:
            obstacle_score += 25
            reasons.append(f"Geringe nutzbare Fläche ({usable_pct:.0f}%)")
        
        # Klassifizierung
        if obstacle_score >= 50:
            obstacle_level = "high"
        elif obstacle_score >= 25:
            obstacle_level = "medium"
        else:
            obstacle_level = "low"
        
        results[building_id] = {
            "obstacle_score": obstacle_score,
            "obstacle_level": obstacle_level,
            "reasons": reasons,
            "segments_count": segments_count,
            "shading_factor": shading_factor,
            "usable_roof_pct": usable_pct
        }
    
    # Speichern
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Ergebnisse gespeichert: {output_file}")
    
    # Statistiken
    high = sum(1 for r in results.values() if r['obstacle_level'] == 'high')
    medium = sum(1 for r in results.values() if r['obstacle_level'] == 'medium')
    low = sum(1 for r in results.values() if r['obstacle_level'] == 'low')
    total = len(results)
    
    logger.info(f"\n=== Hindernis-Inferenz (Google Solar) ===")
    logger.info(f"Analysierte Gebäude: {total}")
    logger.info(f"Hohe Hinderniswahrscheinlichkeit: {high} ({100*high/total:.1f}%)")
    logger.info(f"Mittlere Hinderniswahrscheinlichkeit: {medium} ({100*medium/total:.1f}%)")
    logger.info(f"Niedrige Hinderniswahrscheinlichkeit: {low} ({100*low/total:.1f}%)")
    
    return results


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Dach-Hindernis-Erkennung")
    parser.add_argument("--method", choices=["groundingdino", "roboflow", "simple"], 
                        default="simple", help="Erkennungsmethode")
    parser.add_argument("--limit", type=int, help="Maximale Anzahl Bilder")
    parser.add_argument("--api-key", type=str, help="Roboflow API Key")
    
    args = parser.parse_args()
    
    if args.method == "groundingdino":
        process_aerial_images(limit=args.limit)
    elif args.method == "roboflow":
        if not args.api_key:
            print("--api-key erforderlich für Roboflow")
        else:
            run_detection_roboflow(api_key=args.api_key, limit=args.limit)
    else:
        # Einfache Methode ohne KI-Modell
        simple_obstacle_detection_from_google_solar()
