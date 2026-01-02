"""
PV Dach Leads Pipeline - Master-Script für alle Städte

Dieses Script führt alle Schritte der Pipeline aus:
1. ALKIS normalisieren (normalize_alkis.py)
2. Solar-Daten abrufen (enrich_with_google_solar.py)
3. Alle Daten zusammenführen MIT VALIDIERUNG (merge_all_data.py)
4. Report erstellen (create_complete_report.py)

Verwendung:
    python run_pipeline.py --city dortmund --steps all
    python run_pipeline.py --city bonn --steps 1,2,3,4
    python run_pipeline.py --city dortmund --steps merge,report
"""
import argparse
import subprocess
import sys
from pathlib import Path
from datetime import datetime


STEPS = {
    'normalize': {
        'name': 'ALKIS Normalisieren',
        'module': 'pv_roof_leads.normalize_alkis',
        'description': 'Normalisiert ALKIS-Daten zu buildings_processed.geojson'
    },
    'solar': {
        'name': 'Google Solar API',
        'module': 'pv_roof_leads.enrich_with_google_solar',
        'description': 'Ruft Solar-Daten für jedes Gebäude ab'
    },
    'merge': {
        'name': 'Daten Zusammenführen',
        'module': 'pv_roof_leads.merge_all_data',
        'description': 'Führt alle Daten mit Validierung zusammen'
    },
    'report': {
        'name': 'Report Erstellen',
        'module': 'pv_roof_leads.create_complete_report',
        'description': 'Erstellt interaktiven HTML-Report'
    }
}


def print_banner(city: str):
    """Zeigt Banner mit Pipeline-Info"""
    print("\n" + "=" * 70)
    print("  🏠 PV DACH LEADS PIPELINE")
    print("=" * 70)
    print(f"  📍 Stadt: {city.upper()}")
    print(f"  📅 Start: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)


def run_step(step_id: str, city: str, extra_args: list = None) -> bool:
    """
    Führt einen Pipeline-Schritt aus.
    
    Returns:
        True wenn erfolgreich, False bei Fehler
    """
    step = STEPS.get(step_id)
    if not step:
        print(f"❌ Unbekannter Schritt: {step_id}")
        return False
    
    print(f"\n{'─' * 70}")
    print(f"▶ STEP: {step['name']}")
    print(f"  {step['description']}")
    print(f"{'─' * 70}")
    
    cmd = [sys.executable, '-m', step['module'], '--city', city]
    if extra_args:
        cmd.extend(extra_args)
    
    try:
        result = subprocess.run(cmd, check=True)
        print(f"✅ {step['name']} - Abgeschlossen")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {step['name']} - Fehler: {e}")
        return False
    except Exception as e:
        print(f"❌ {step['name']} - Unerwarteter Fehler: {e}")
        return False


def parse_steps(steps_arg: str) -> list:
    """Parst Schritt-Argument"""
    if steps_arg == 'all':
        return ['normalize', 'solar', 'merge', 'report']
    
    # Numerisch (1,2,3)
    step_order = ['normalize', 'solar', 'merge', 'report']
    if steps_arg.replace(',', '').isdigit():
        indices = [int(x) - 1 for x in steps_arg.split(',')]
        return [step_order[i] for i in indices if 0 <= i < len(step_order)]
    
    # Namen (merge,report)
    return [s.strip() for s in steps_arg.split(',')]


def main():
    parser = argparse.ArgumentParser(
        description='PV Dach Leads Pipeline',
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        '--city', 
        required=True,
        help='Stadt (z.B. dortmund, bonn, essen)'
    )
    parser.add_argument(
        '--steps',
        default='all',
        help='''Welche Schritte ausführen:
  all        - Alle Schritte (Standard)
  1,2,3,4    - Schritte per Nummer
  merge,report - Schritte per Name
        
Verfügbare Schritte:
  1. normalize - ALKIS normalisieren
  2. solar     - Google Solar API
  3. merge     - Daten zusammenführen
  4. report    - HTML Report'''
    )
    parser.add_argument(
        '--skip-errors',
        action='store_true',
        help='Bei Fehler mit nächstem Schritt fortfahren'
    )
    
    args = parser.parse_args()
    
    print_banner(args.city)
    
    steps = parse_steps(args.steps)
    print(f"\n📋 Geplante Schritte: {', '.join(steps)}")
    
    # Prüfe ob Daten-Ordner existiert
    city_path = Path(f"data/raw/{args.city}")
    if not city_path.exists() and 'normalize' in steps:
        print(f"\n⚠️ WARNUNG: Kein Rohdaten-Ordner gefunden: {city_path}")
        print("   Stelle sicher, dass die ALKIS/OSM-Daten dort liegen.")
    
    # Führe Schritte aus
    success = True
    completed = []
    failed = []
    
    for step_id in steps:
        if run_step(step_id, args.city):
            completed.append(step_id)
        else:
            failed.append(step_id)
            success = False
            if not args.skip_errors:
                print(f"\n⛔ Pipeline gestoppt wegen Fehler in '{step_id}'")
                print("   Verwende --skip-errors um fortzufahren")
                break
    
    # Zusammenfassung
    print("\n" + "=" * 70)
    print("  📊 ZUSAMMENFASSUNG")
    print("=" * 70)
    print(f"  ✅ Erfolgreich: {', '.join(completed) if completed else 'keine'}")
    if failed:
        print(f"  ❌ Fehlgeschlagen: {', '.join(failed)}")
    print(f"  📅 Ende: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
