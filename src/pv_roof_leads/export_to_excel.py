"""
Excel-Export für PV-Lead-Listen

Exportiert Gebäude mit allen Informationen (inkl. PV-Status) nach Excel.
"""

import logging
import geopandas as gpd
import pandas as pd
from pathlib import Path
from typing import Optional

from .config import CRS_EXPORT
from .paths import PROCESSED_DORTMUND, EXPORTS_DORTMUND

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def export_buildings_to_excel(
    input_geojson: Path,
    output_excel: Path,
    min_area_m2: float = 500.0,
    include_geometry: bool = False
) -> bool:
    """
    Exportiert Gebäude nach Excel mit Filterung.
    
    Args:
        input_geojson: Pfad zum GeoJSON mit Gebäuden
        output_excel: Pfad für Excel-Output
        min_area_m2: Minimale Dachfläche in m²
        include_geometry: Geometrie-Spalte behalten (WKT-Format)
    
    Returns:
        True wenn erfolgreich
    """
    logger.info("=" * 70)
    logger.info("EXCEL-EXPORT")
    logger.info("=" * 70)
    
    if not input_geojson.exists():
        logger.error(f"Eingabedatei nicht gefunden: {input_geojson}")
        return False
    
    logger.info(f"Lade Gebäude: {input_geojson.name}")
    gdf = gpd.read_file(input_geojson)
    logger.info(f"✓ {len(gdf)} Gebäude geladen")
    
    # Filtere nach Mindestfläche
    if 'footprint_area_m2' in gdf.columns:
        area_col = 'footprint_area_m2'
    elif 'solar_roof_area_m2' in gdf.columns:
        area_col = 'solar_roof_area_m2'
    else:
        logger.warning("Keine Flächenspalte gefunden - exportiere alle Gebäude")
        area_col = None
    
    if area_col:
        before = len(gdf)
        gdf = gdf[gdf[area_col] >= min_area_m2].copy()
        logger.info(f"Gefiltert: {len(gdf)} Gebäude mit ≥{min_area_m2} m² ({area_col})")
        logger.info(f"Entfernt: {before - len(gdf)} Gebäude")
    
    if len(gdf) == 0:
        logger.warning("Keine Gebäude nach Filterung übrig!")
        return False
    
    # Konvertiere zu DataFrame (ohne Geometrie für Excel)
    df = pd.DataFrame(gdf.drop(columns='geometry'))
    
    # Optional: Geometrie als WKT-Text hinzufügen
    if include_geometry:
        df['geometry_wkt'] = gdf.geometry.to_wkt()
    
    # Sortiere Spalten: Wichtigste zuerst
    priority_cols = [
        'name', 'addr:street', 'addr:housenumber', 'addr:postcode', 'addr:city',
        'building', 'footprint_area_m2', 'solar_roof_area_m2',
        'has_existing_pv', 'pv_installations_count', 'pv_total_capacity_kwp',
        'pv_oldest_installation_year', 'pv_newest_installation_year',
        'pv_min_age_years', 'pv_max_age_years', 'pv_avg_age_years',
        'pv_eeg_expiring_soon',
        'landuse', 'eigentuemer', 'baujahr'
    ]
    
    # Erstelle sortierte Spaltenliste
    existing_priority = [col for col in priority_cols if col in df.columns]
    other_cols = [col for col in df.columns if col not in existing_priority]
    sorted_cols = existing_priority + other_cols
    df = df[sorted_cols]
    
    # Erstelle Excel mit mehreren Sheets
    output_excel.parent.mkdir(parents=True, exist_ok=True)
    
    with pd.ExcelWriter(output_excel, engine='openpyxl') as writer:
        # Sheet 1: Alle gefilterten Gebäude
        df.to_excel(writer, sheet_name='Alle Gebäude', index=False)
        logger.info(f"✓ Sheet 'Alle Gebäude': {len(df)} Einträge")
        
        # Sheet 2: Gebäude OHNE PV (Neuanlagen-Leads)
        if 'has_existing_pv' in df.columns:
            no_pv = df[df['has_existing_pv'] == False].copy()
            no_pv.to_excel(writer, sheet_name='Ohne PV (Neuanlagen)', index=False)
            logger.info(f"✓ Sheet 'Ohne PV (Neuanlagen)': {len(no_pv)} Einträge")
        
        # Sheet 3: Gebäude MIT ALTER PV (≥15 Jahre, Modernisierung)
        if 'pv_max_age_years' in df.columns:
            old_pv = df[df['pv_max_age_years'] >= 15].copy()
            if len(old_pv) > 0:
                old_pv.to_excel(writer, sheet_name='Alte PV (Modernisierung)', index=False)
                logger.info(f"✓ Sheet 'Alte PV (Modernisierung)': {len(old_pv)} Einträge")
        
        # Sheet 4: Gebäude mit auslaufendem EEG
        if 'pv_eeg_expiring_soon' in df.columns:
            eeg_expiring = df[df['pv_eeg_expiring_soon'] == True].copy()
            if len(eeg_expiring) > 0:
                eeg_expiring.to_excel(writer, sheet_name='EEG läuft aus', index=False)
                logger.info(f"✓ Sheet 'EEG läuft aus': {len(eeg_expiring)} Einträge")
        
        # Sheet 5: Zusammenfassung/Statistik
        create_summary_sheet(df, writer)
    
    logger.info("=" * 70)
    logger.info(f"✓ Excel-Datei erstellt: {output_excel}")
    logger.info("=" * 70)
    
    return True


def create_summary_sheet(df: pd.DataFrame, writer: pd.ExcelWriter) -> None:
    """Erstellt Zusammenfassungs-Sheet mit Statistiken."""
    
    summary_data = {
        'Kategorie': [],
        'Anzahl': [],
        'Prozent': []
    }
    
    total = len(df)
    
    # Basis-Statistiken
    summary_data['Kategorie'].append('Gesamt Gebäude')
    summary_data['Anzahl'].append(total)
    summary_data['Prozent'].append('100.0%')
    
    if 'has_existing_pv' in df.columns:
        with_pv = df['has_existing_pv'].sum()
        without_pv = total - with_pv
        
        summary_data['Kategorie'].append('Mit PV-Anlagen')
        summary_data['Anzahl'].append(with_pv)
        summary_data['Prozent'].append(f"{with_pv/total*100:.1f}%")
        
        summary_data['Kategorie'].append('Ohne PV-Anlagen')
        summary_data['Anzahl'].append(without_pv)
        summary_data['Prozent'].append(f"{without_pv/total*100:.1f}%")
    
    if 'pv_max_age_years' in df.columns:
        old_pv = (df['pv_max_age_years'] >= 15).sum()
        summary_data['Kategorie'].append('Mit alter PV (≥15 Jahre)')
        summary_data['Anzahl'].append(old_pv)
        summary_data['Prozent'].append(f"{old_pv/total*100:.1f}%")
    
    if 'pv_eeg_expiring_soon' in df.columns:
        eeg_expiring = df['pv_eeg_expiring_soon'].sum()
        summary_data['Kategorie'].append('EEG läuft bald aus')
        summary_data['Anzahl'].append(eeg_expiring)
        summary_data['Prozent'].append(f"{eeg_expiring/total*100:.1f}%")
    
    # Flächen-Statistiken
    if 'footprint_area_m2' in df.columns:
        summary_data['Kategorie'].append('')
        summary_data['Anzahl'].append('')
        summary_data['Prozent'].append('')
        
        summary_data['Kategorie'].append('Ø Gebäudefläche (m²)')
        summary_data['Anzahl'].append(f"{df['footprint_area_m2'].mean():.1f}")
        summary_data['Prozent'].append('')
        
        summary_data['Kategorie'].append('Gesamt Gebäudefläche (m²)')
        summary_data['Anzahl'].append(f"{df['footprint_area_m2'].sum():.0f}")
        summary_data['Prozent'].append('')
    
    # PV-Kapazität
    if 'pv_total_capacity_kwp' in df.columns:
        pv_buildings = df[df['has_existing_pv'] == True]
        if len(pv_buildings) > 0:
            summary_data['Kategorie'].append('')
            summary_data['Anzahl'].append('')
            summary_data['Prozent'].append('')
            
            summary_data['Kategorie'].append('Ø PV-Leistung (kWp)')
            summary_data['Anzahl'].append(f"{pv_buildings['pv_total_capacity_kwp'].mean():.1f}")
            summary_data['Prozent'].append('')
            
            summary_data['Kategorie'].append('Gesamt PV-Leistung (kWp)')
            summary_data['Anzahl'].append(f"{pv_buildings['pv_total_capacity_kwp'].sum():.1f}")
            summary_data['Prozent'].append('')
    
    summary_df = pd.DataFrame(summary_data)
    summary_df.to_excel(writer, sheet_name='Zusammenfassung', index=False)
    logger.info(f"✓ Sheet 'Zusammenfassung': Statistiken erstellt")


def main():
    """Hauptfunktion für Excel-Export."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Exportiere Gebäude-Daten nach Excel"
    )
    parser.add_argument(
        '--input',
        type=str,
        default=str(PROCESSED_DORTMUND / "buildings_processed_with_pv_info.geojson"),
        help='Pfad zum Input-GeoJSON'
    )
    parser.add_argument(
        '--output',
        type=str,
        default=str(EXPORTS_DORTMUND / "pv_leads_dortmund.xlsx"),
        help='Pfad für Excel-Output'
    )
    parser.add_argument(
        '--min-area',
        type=float,
        default=500.0,
        help='Minimale Gebäudefläche in m² (Standard: 500)'
    )
    parser.add_argument(
        '--with-geometry',
        action='store_true',
        help='Geometrie als WKT-Text in Excel einschließen'
    )
    
    args = parser.parse_args()
    
    success = export_buildings_to_excel(
        Path(args.input),
        Path(args.output),
        min_area_m2=args.min_area,
        include_geometry=args.with_geometry
    )
    
    if success:
        logger.info("\n✅ Export abgeschlossen!")
        logger.info(f"Excel-Datei: {args.output}")
    else:
        logger.error("❌ Export fehlgeschlagen!")


if __name__ == '__main__':
    main()
