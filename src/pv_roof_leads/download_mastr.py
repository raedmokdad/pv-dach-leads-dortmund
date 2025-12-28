"""
MaStR-Daten Download und Vorbereitung für Dortmund

Dieses Skript hilft beim Herunterladen und Filtern der Marktstammdatenregister (MaStR) Daten.
Die MaStR-Daten liegen als XML vor und werden nach Dortmund gefiltert und als CSV gespeichert.
"""

import logging
import pandas as pd
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional, List, Dict

from .config import DORTMUND_PLZ_PREFIXES, DORTMUND_BBOX, MASTR_CSV_PATH
from .paths import RAW_DORTMUND

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def parse_mastr_xml_to_csv(
    xml_or_zip_path: Path,
    output_csv: Path,
    filter_dortmund: bool = True
) -> bool:
    """
    Parst MaStR XML-Datei und extrahiert Solar-Anlagen für Dortmund.
    
    Args:
        xml_or_zip_path: Pfad zur XML-Datei oder ZIP mit XML
        output_csv: Pfad für CSV-Output
        filter_dortmund: Nur Dortmund-Anlagen (PLZ 44xxx)
    
    Returns:
        True wenn erfolgreich
    """
    logger.info("=" * 70)
    logger.info("MASTR XML VERARBEITUNG")
    logger.info("=" * 70)
    
    # Prüfe ob ZIP oder XML
    xml_path = xml_or_zip_path
    temp_extracted = None
    
    if xml_or_zip_path.suffix == '.zip':
        logger.info(f"Extrahiere XML aus ZIP: {xml_or_zip_path.name}")
        xml_path = extract_xml_from_zip(xml_or_zip_path)
        temp_extracted = xml_path
    
    if not xml_path.exists():
        logger.error(f"XML-Datei nicht gefunden: {xml_path}")
        return False
    
    logger.info(f"Parse XML: {xml_path.name}")
    logger.info("Dies kann 5-10 Minuten dauern bei großen Dateien...")
    
    # Parse XML iterativ (Memory-effizient)
    solar_units = []
    count = 0
    
    try:
        # Iteriere durch XML ohne alles in Memory zu laden
        context = ET.iterparse(xml_path, events=('start', 'end'))
        context = iter(context)
        
        current_unit = {}
        in_solar_unit = False
        
        for event, elem in context:
            if event == 'start':
                # Prüfe ob Solar-Einheit
                if elem.tag.endswith('EinheitSolar'):
                    in_solar_unit = True
                    current_unit = {}
                    
            elif event == 'end':
                if in_solar_unit:
                    # Extrahiere relevante Felder
                    tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
                    
                    # Grunddaten
                    if tag in ['EinheitMastrNummer', 'Registrierungsdatum', 
                               'Inbetriebnahmedatum', 'Bruttoleistung', 
                               'Nettonennleistung', 'Postleitzahl', 'Ort',
                               'Laengengrad', 'Breitengrad', 'Energietraeger',
                               # Technische Details
                               'Einspeisungsart', 'AnlageIstImKombibetrieb',
                               'Leistungsbegrenzung', 'ArtDerFlaeche',
                               # Wirtschaftliche Daten
                               'AnlageMitEegFoerderung', 'EegInbetriebnahmedatum',
                               'VerknuepfteEinheit',
                               # Status
                               'Betriebsstatus', 'Stilllegungsdatum',
                               'GeplantesInbetriebnahmedatum']:
                        current_unit[tag] = elem.text
                    
                    # Ende der Solar-Einheit
                    if elem.tag.endswith('EinheitSolar'):
                        in_solar_unit = False
                        
                        # Prüfe ob Dortmund
                        if filter_dortmund:
                            plz = current_unit.get('Postleitzahl', '')
                            if plz and str(plz)[:2] in DORTMUND_PLZ_PREFIXES:
                                solar_units.append(current_unit.copy())
                                count += 1
                                if count % 100 == 0:
                                    logger.info(f"Gefunden: {count} Solar-Anlagen in Dortmund")
                        else:
                            solar_units.append(current_unit.copy())
                            count += 1
                        
                # Speicher freigeben
                elem.clear()
        
        logger.info(f"✓ Insgesamt {len(solar_units)} Solar-Anlagen extrahiert")
        
        if len(solar_units) == 0:
            logger.warning("Keine Solar-Anlagen gefunden!")
            return False
        
        # Konvertiere zu DataFrame
        df = pd.DataFrame(solar_units)
        
        # Umbenennen für Kompatibilität mit check_existing_pv.py
        # Priorisiere Bruttoleistung, falls nicht vorhanden nutze Nettonennleistung
        if 'Bruttoleistung' in df.columns:
            df['InstallierteLeistung'] = df['Bruttoleistung']
        elif 'Nettonennleistung' in df.columns:
            df['InstallierteLeistung'] = df['Nettonennleistung']
        
        column_mapping = {
            'EinheitMastrNummer': 'EinheitMastrNummer',
            'Laengengrad': 'Längengrad',
            'Breitengrad': 'Breitengrad',
            'Postleitzahl': 'Postleitzahl',
            'Ort': 'Ort',
            'Registrierungsdatum': 'Registrierungsdatum',
            'Inbetriebnahmedatum': 'Inbetriebnahmedatum',
            'EegInbetriebnahmedatum': 'EEG_Inbetriebnahmedatum',
            'Einspeisungsart': 'Einspeisungsart',
            'AnlageIstImKombibetrieb': 'Kombibetrieb',
            'Leistungsbegrenzung': 'Leistungsbegrenzung',
            'ArtDerFlaeche': 'Anlagenart',
            'AnlageMitEegFoerderung': 'EEG_Foerderung',
            'Betriebsstatus': 'Betriebsstatus',
            'Stilllegungsdatum': 'Stilllegungsdatum',
            'GeplantesInbetriebnahmedatum': 'Geplantes_Inbetriebnahmedatum'
        }
        
        df = df.rename(columns={k: v for k, v in column_mapping.items() if k in df.columns})
        
        # Energieträger hinzufügen
        df['Energieträger'] = 'Solare Strahlungsenergie'
        
        # Koordinaten und numerische Werte bereinigen
        if 'Längengrad' in df.columns:
            df['Längengrad'] = pd.to_numeric(df['Längengrad'], errors='coerce')
        if 'Breitengrad' in df.columns:
            df['Breitengrad'] = pd.to_numeric(df['Breitengrad'], errors='coerce')
        if 'InstallierteLeistung' in df.columns:
            df['InstallierteLeistung'] = pd.to_numeric(df['InstallierteLeistung'], errors='coerce')
        
        # Datums-Felder konvertieren
        date_columns = ['Inbetriebnahmedatum', 'EEG_Inbetriebnahmedatum', 'Registrierungsdatum', 
                        'Stilllegungsdatum', 'Geplantes_Inbetriebnahmedatum']
        for col in date_columns:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
        
        # Statistik
        valid_coords = df[df['Längengrad'].notna() & df['Breitengrad'].notna()]
        logger.info(f"✓ {len(valid_coords)} Anlagen mit Koordinaten")
        
        if 'InstallierteLeistung' in df.columns:
            total_kwp = df['InstallierteLeistung'].sum()
            logger.info(f"✓ Gesamtleistung: {total_kwp:.1f} kWp")
        
        if 'Inbetriebnahmedatum' in df.columns:
            valid_dates = df['Inbetriebnahmedatum'].notna()
            if valid_dates.sum() > 0:
                oldest = df.loc[valid_dates, 'Inbetriebnahmedatum'].min()
                newest = df.loc[valid_dates, 'Inbetriebnahmedatum'].max()
                logger.info(f"✓ Inbetriebnahme: {oldest.year} bis {newest.year}")
        
        # Speichere CSV
        output_csv.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_csv, sep=';', encoding='utf-8', index=False)
        logger.info(f"✓ CSV gespeichert: {output_csv}")
        
        # Cleanup
        if temp_extracted:
            temp_extracted.unlink()
            logger.info("✓ Temporäre Dateien gelöscht")
        
        return True
        
    except Exception as e:
        logger.error(f"Fehler beim Parsen der XML: {e}")
        import traceback
        traceback.print_exc()
        return False


def extract_xml_from_zip(zip_path: Path) -> Path:
    """
    Extrahiert XML aus MaStR-ZIP.
    
    Args:
        zip_path: Pfad zur ZIP-Datei
    
    Returns:
        Pfad zur extrahierten XML
    """
    logger.info("Suche XML in ZIP...")
    
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        # Liste alle Dateien
        xml_files = [f for f in zip_ref.namelist() if f.endswith('.xml')]
        
        if not xml_files:
            raise FileNotFoundError("Keine XML-Datei in ZIP gefunden!")
        
        # Nimm die größte XML (ist meist die Haupt-Datei)
        xml_file = max(xml_files, key=lambda f: zip_ref.getinfo(f).file_size)
        logger.info(f"Gefunden: {xml_file} ({zip_ref.getinfo(xml_file).file_size / 1024 / 1024:.1f} MB)")
        
        # Extrahiere
        extract_path = RAW_DORTMUND / "mastr_temp.xml"
        with zip_ref.open(xml_file) as source, open(extract_path, 'wb') as target:
            logger.info("Extrahiere XML...")
            chunk_size = 1024 * 1024  # 1 MB chunks
            while True:
                chunk = source.read(chunk_size)
                if not chunk:
                    break
                target.write(chunk)
        
        logger.info(f"✓ Extrahiert nach: {extract_path}")
        return extract_path


def print_manual_download_instructions() -> None:
    """Zeigt Anleitung für manuellen Download."""
    print("\n" + "=" * 70)
    print("📋 DOWNLOAD-ANLEITUNG")
    print("=" * 70)
    print("\n1. Besuche:")
    print("   https://www.marktstammdatenregister.de/MaStR/Datendownload")
    print("\n2. Lade herunter:")
    print("   'Gesamtdatenauszug vom Vortag' (neuestes Datum)")
    print("   Format: Gesamtdatenexport_YYYYMMDD_XX.X.zip (~2-3 GB)")
    print("\n3. Speichere die ZIP-Datei irgendwo (z.B. Downloads)")
    print("\n4. Führe dann aus:")
    print("   python -m pv_roof_leads.download_mastr --process <pfad-zur-zip>")
    print("\n   Beispiel:")
    print("   python -m pv_roof_leads.download_mastr --process")
    print("     \"C:\\Users\\<Name>\\Downloads\\Gesamtdatenexport_20251228_25.2.zip\"")
    print("\n" + "=" * 70)


def download_mastr_solar_data(output_path: Optional[Path] = None) -> bool:
    """
    Zeigt Anleitung für manuellen Download (automatischer Download nicht verfügbar).
    """
    logger.info("Automatischer Download ist nicht verfügbar.")
    logger.info("Die MaStR-Daten müssen manuell heruntergeladen werden.")
    print_manual_download_instructions()
    return False


def main():
    """Hauptfunktion für Download und Filterung."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="MaStR-Daten verarbeiten und für Dortmund filtern"
    )
    parser.add_argument(
        '--process',
        type=str,
        help='Pfad zu heruntergeladener MaStR-ZIP oder XML zum Verarbeiten'
    )
    parser.add_argument(
        '--output',
        type=str,
        default=str(MASTR_CSV_PATH),
        help='Ausgabepfad für gefilterte CSV'
    )
    parser.add_argument(
        '--no-filter',
        action='store_true',
        help='NICHT nach Dortmund filtern (alle Anlagen behalten)'
    )
    
    args = parser.parse_args()
    
    if args.process:
        # Verarbeite vorhandene XML/ZIP
        input_path = Path(args.process)
        output_path = Path(args.output)
        
        if not input_path.exists():
            logger.error(f"Datei nicht gefunden: {input_path}")
            return
        
        logger.info(f"Verarbeite MaStR-Daten: {input_path.name}")
        success = parse_mastr_xml_to_csv(
            input_path,
            output_path,
            filter_dortmund=not args.no_filter
        )
        
        if success:
            logger.info("=" * 70)
            logger.info("✓ ERFOLGREICH!")
            logger.info("=" * 70)
            logger.info(f"Die gefilterten Daten wurden gespeichert:")
            logger.info(f"  {output_path}")
            logger.info("\nJetzt kannst du ausführen:")
            logger.info("  python -m pv_roof_leads.check_existing_pv")
        else:
            logger.error("Verarbeitung fehlgeschlagen!")
    else:
        # Zeige Anleitung
        print_manual_download_instructions()


if __name__ == '__main__':
    main()
