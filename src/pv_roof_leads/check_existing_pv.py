"""
Erkennung bestehender PV-Anlagen auf Dächern

Kombiniert MaStR und OpenStreetMap Daten für maximale Abdeckung.
"""

import logging
import geopandas as gpd
import pandas as pd
from pathlib import Path
from typing import Optional
from datetime import datetime

from .config import (
    CRS_INTERNAL,
    CRS_EXPORT,
    PV_DETECTION_BUFFER_M,
    MASTR_CSV_PATH,
    DORTMUND_BBOX,
    DORTMUND_PLZ_PREFIXES
)
from .paths import RAW_DORTMUND, PROCESSED_DORTMUND

logger = logging.getLogger(__name__)


def load_mastr_pv_installations(mastr_csv_path: Optional[Path] = None) -> gpd.GeoDataFrame:
    """
    Lädt PV-Anlagen aus MaStR CSV-Datei.
    
    Args:
        mastr_csv_path: Pfad zur MaStR CSV-Datei. Falls None, wird MASTR_CSV_PATH aus config verwendet.
    
    Returns:
        GeoDataFrame mit PV-Anlagen (Koordinaten, Leistung, etc.)
    """
    if mastr_csv_path is None:
        mastr_csv_path = MASTR_CSV_PATH if 'MASTR_CSV_PATH' in globals() else RAW_DORTMUND / "mastr_pv.csv"
    
    if not mastr_csv_path.exists():
        logger.warning(f"MaStR-Datei nicht gefunden: {mastr_csv_path}")
        return gpd.GeoDataFrame()
    
    logger.info(f"Lade MaStR-Daten: {mastr_csv_path}")
    
    try:
        # CSV laden (Semikolon-getrennt, UTF-8)
        df = pd.read_csv(mastr_csv_path, sep=';', encoding='utf-8', low_memory=False)
        
        logger.info(f"{len(df)} Einträge geladen")
        
        # Filtere nur PV-Anlagen (Solare Strahlungsenergie)
        if 'Energieträger' in df.columns:
            pv_df = df[df['Energieträger'] == 'Solare Strahlungsenergie'].copy()
            logger.info(f"{len(pv_df)} PV-Anlagen gefunden")
        else:
            pv_df = df.copy()
        
        # Filtere auf Dortmund (PLZ-basiert)
        if 'Postleitzahl' in pv_df.columns:
            plz_str = pv_df['Postleitzahl'].astype(str).str[:2]
            pv_df = pv_df[plz_str.isin(DORTMUND_PLZ_PREFIXES)].copy()
            logger.info(f"{len(pv_df)} PV-Anlagen in Dortmund-Bereich (PLZ)")
        
        # Erstelle GeoDataFrame mit Koordinaten
        if 'Längengrad' in pv_df.columns and 'Breitengrad' in pv_df.columns:
            from shapely.geometry import Point
            
            # Entferne ungültige Koordinaten
            pv_df = pv_df[
                (pv_df['Längengrad'].notna()) & 
                (pv_df['Breitengrad'].notna()) &
                (pv_df['Längengrad'] != 0) &
                (pv_df['Breitengrad'] != 0)
            ].copy()
            
            # Validiere Koordinaten für Dortmund Bounding Box
            lon_min, lat_min, lon_max, lat_max = DORTMUND_BBOX
            lon_buffer = (lon_max - lon_min) * 0.1
            lat_buffer = (lat_max - lat_min) * 0.1
            
            valid_coords = (
                (pv_df['Breitengrad'] >= lat_min - lat_buffer) & 
                (pv_df['Breitengrad'] <= lat_max + lat_buffer) &
                (pv_df['Längengrad'] >= lon_min - lon_buffer) & 
                (pv_df['Längengrad'] <= lon_max + lon_buffer)
            )
            pv_df = pv_df[valid_coords].copy()
            
            geometry = [
                Point(lon, lat) 
                for lon, lat in zip(pv_df['Längengrad'], pv_df['Breitengrad'])
            ]
            
            gdf = gpd.GeoDataFrame(pv_df, geometry=geometry, crs=CRS_EXPORT)
            gdf = gdf.to_crs(CRS_INTERNAL)
            
            logger.info(f"✓ {len(gdf)} MaStR PV-Anlagen mit gültigen Koordinaten")
            return gdf
        else:
            logger.warning("Keine Koordinaten-Spalten gefunden")
            return gpd.GeoDataFrame()
            
    except Exception as e:
        logger.error(f"Fehler beim Laden der MaStR-Daten: {e}")
        return gpd.GeoDataFrame()


def load_osm_pv_installations() -> gpd.GeoDataFrame:
    """
    Lädt PV-Anlagen aus OSM-Daten (extrahiert mit extract_osm_pv.py).
    
    Returns:
        GeoDataFrame mit OSM PV-Anlagen
    """
    osm_path = RAW_DORTMUND / "osm_pv_installations.geojson"
    
    if not osm_path.exists():
        logger.warning(f"OSM PV-Datei nicht gefunden: {osm_path}")
        logger.info("Führe 'python -m pv_roof_leads.extract_osm_pv' aus, um OSM-Daten zu extrahieren")
        return gpd.GeoDataFrame()
    
    try:
        gdf = gpd.read_file(osm_path)
        logger.info(f"✓ {len(gdf)} OSM PV-Anlagen geladen")
        
        if gdf.crs != CRS_INTERNAL:
            gdf = gdf.to_crs(CRS_INTERNAL)
        
        gdf['data_source'] = 'OSM'
        
        return gdf
        
    except Exception as e:
        logger.error(f"Fehler beim Laden der OSM-Daten: {e}")
        return gpd.GeoDataFrame()


def combine_pv_sources(mastr_gdf: gpd.GeoDataFrame, osm_gdf: gpd.GeoDataFrame, 
                       deduplicate_distance: float = 10.0) -> gpd.GeoDataFrame:
    """
    Kombiniert MaStR und OSM PV-Anlagen, entfernt Duplikate basierend auf räumlicher Nähe.
    
    Args:
        mastr_gdf: MaStR PV-Anlagen
        osm_gdf: OSM PV-Anlagen
        deduplicate_distance: Distanz in Metern für Duplikaterkennung (Standard: 10m)
    
    Returns:
        Kombiniertes GeoDataFrame mit allen PV-Anlagen
    """
    if len(mastr_gdf) == 0 and len(osm_gdf) == 0:
        logger.warning("Keine PV-Anlagen in beiden Datenquellen gefunden")
        return gpd.GeoDataFrame()
    
    if len(mastr_gdf) == 0:
        logger.info("Nur OSM-Daten vorhanden")
        return osm_gdf
    
    if len(osm_gdf) == 0:
        logger.info("Nur MaStR-Daten vorhanden")
        mastr_gdf['data_source'] = 'MaStR'
        return mastr_gdf
    
    # Markiere MaStR-Daten
    mastr_gdf = mastr_gdf.copy()
    mastr_gdf['data_source'] = 'MaStR'
    
    # Deduplizierung: Finde OSM-Anlagen, die nahe an MaStR-Anlagen liegen
    osm_to_keep = []
    osm_duplicates = 0
    
    for idx, osm_row in osm_gdf.iterrows():
        distances = mastr_gdf.geometry.distance(osm_row.geometry)
        min_distance = distances.min()
        
        if min_distance > deduplicate_distance:
            osm_to_keep.append(idx)
        else:
            osm_duplicates += 1
    
    osm_unique = osm_gdf.loc[osm_to_keep].copy()
    
    logger.info(f"Deduplizierung: {osm_duplicates} OSM-Anlagen als Duplikate von MaStR identifiziert (< {deduplicate_distance}m)")
    logger.info(f"Kombiniere {len(mastr_gdf)} MaStR + {len(osm_unique)} OSM = {len(mastr_gdf) + len(osm_unique)} PV-Anlagen")
    
    # Standardisiere Spaltennamen
    if 'Nettonennleistung' in mastr_gdf.columns:
        mastr_gdf['capacity_kwp'] = mastr_gdf['Nettonennleistung']
    if 'capacity' in osm_unique.columns:
        osm_unique['capacity_kwp'] = osm_unique['capacity']
    
    # Baujahr standardisieren
    if 'Inbetriebnahmedatum' in mastr_gdf.columns:
        mastr_gdf['installation_year'] = pd.to_datetime(
            mastr_gdf['Inbetriebnahmedatum'], 
            errors='coerce'
        ).dt.year
    
    # Kombiniere DataFrames
    combined = pd.concat([mastr_gdf, osm_unique], ignore_index=True)
    combined_gdf = gpd.GeoDataFrame(combined, geometry='geometry', crs=mastr_gdf.crs)
    
    return combined_gdf


def check_buildings_for_existing_pv(
    buildings_gdf: gpd.GeoDataFrame,
    buffer_distance: float = PV_DETECTION_BUFFER_M
) -> gpd.GeoDataFrame:
    """
    Überprüft Gebäude auf existierende PV-Anlagen durch Kombinieren von MaStR und OSM Daten.
    
    Args:
        buildings_gdf: GeoDataFrame mit Gebäuden
        buffer_distance: Buffer-Distanz in Metern für Matching
    
    Returns:
        GeoDataFrame mit PV-Informationen
    """
    logger.info("="*80)
    logger.info("PRÜFE BESTEHENDE PV-ANLAGEN (MaStR + OSM kombiniert)")
    logger.info("="*80)
    
    # 1. Lade beide Datenquellen
    mastr_gdf = load_mastr_pv_installations()
    osm_gdf = load_osm_pv_installations()
    
    # 2. Kombiniere und dedupliziere
    pv_installations = combine_pv_sources(mastr_gdf, osm_gdf)
    
    if len(pv_installations) == 0:
        logger.warning("Keine PV-Anlagen gefunden - alle Gebäude ohne PV markiert")
        buildings_gdf['has_existing_pv'] = False
        buildings_gdf['pv_installations_count'] = 0
        buildings_gdf['pv_total_capacity_kwp'] = 0.0
        buildings_gdf['pv_data_sources'] = ''
        return buildings_gdf
    
    # 3. Sicherstellen dass beide in gleichem CRS sind
    if buildings_gdf.crs != CRS_INTERNAL:
        buildings_gdf = buildings_gdf.to_crs(CRS_INTERNAL)
    
    logger.info(f"Gebäude: {len(buildings_gdf)}")
    logger.info(f"PV-Anlagen (kombiniert): {len(pv_installations)}")
    logger.info(f"Buffer: {buffer_distance}m")
    
    # 4. Spatial Join mit Buffer
    logger.info("Spatial Join: Gebäude ↔ PV-Anlagen mit Buffer...")
    
    pv_buffered = pv_installations.copy()
    pv_buffered['geometry'] = pv_installations.geometry.buffer(buffer_distance)
    
    # Berechne Alter für jede Anlage
    current_year = datetime.now().year
    if 'Inbetriebnahmedatum' in pv_buffered.columns:
        pv_buffered['installation_year'] = pd.to_datetime(
            pv_buffered['Inbetriebnahmedatum'], errors='coerce'
        ).dt.year
        pv_buffered['installation_age'] = current_year - pv_buffered['installation_year']
        
        # EEG-Auslauf (20 Jahre Förderung)
        pv_buffered['eeg_expiry_year'] = pv_buffered['installation_year'] + 20
        pv_buffered['eeg_expiring_soon'] = pv_buffered['eeg_expiry_year'] <= current_year + 2
    
    # Wähle Spalten für Join
    join_cols = ['geometry', 'data_source']
    if 'capacity_kwp' in pv_buffered.columns:
        join_cols.append('capacity_kwp')
    if 'installation_year' in pv_buffered.columns:
        join_cols.extend(['installation_year', 'installation_age', 'eeg_expiring_soon'])
    
    # Spatial Join
    joined = gpd.sjoin(
        buildings_gdf,
        pv_buffered[join_cols],
        how='left',
        predicate='intersects'
    )
    
    # Aggregiere Statistiken
    agg_dict = {'index_right': 'count'}
    
    if 'capacity_kwp' in joined.columns:
        agg_dict['capacity_kwp'] = 'sum'
    if 'installation_year' in joined.columns:
        agg_dict['installation_year'] = ['min', 'max']
        agg_dict['installation_age'] = ['min', 'max', 'mean']
    if 'eeg_expiring_soon' in joined.columns:
        agg_dict['eeg_expiring_soon'] = 'any'
    
    agg_stats = joined.groupby(joined.index).agg(agg_dict)
    
    # Flache Spalten erstellen
    buildings_gdf['pv_installations_count'] = agg_stats[('index_right', 'count')].fillna(0).astype(int)
    
    if 'capacity_kwp' in joined.columns:
        buildings_gdf['pv_total_capacity_kwp'] = agg_stats[('capacity_kwp', 'sum')].fillna(0.0)
    else:
        buildings_gdf['pv_total_capacity_kwp'] = 0.0
    
    if 'installation_year' in joined.columns:
        buildings_gdf['pv_oldest_installation_year'] = agg_stats[('installation_year', 'min')].fillna(0).astype(int)
        buildings_gdf['pv_newest_installation_year'] = agg_stats[('installation_year', 'max')].fillna(0).astype(int)
        buildings_gdf['pv_min_age_years'] = agg_stats[('installation_age', 'min')].fillna(0).astype(int)
        buildings_gdf['pv_max_age_years'] = agg_stats[('installation_age', 'max')].fillna(0).astype(int)
        buildings_gdf['pv_avg_age_years'] = agg_stats[('installation_age', 'mean')].fillna(0.0).round(1)
    else:
        buildings_gdf['pv_oldest_installation_year'] = 0
        buildings_gdf['pv_newest_installation_year'] = 0
        buildings_gdf['pv_min_age_years'] = 0
        buildings_gdf['pv_max_age_years'] = 0
        buildings_gdf['pv_avg_age_years'] = 0.0
    
    if 'eeg_expiring_soon' in joined.columns:
        buildings_gdf['pv_eeg_expiring_soon'] = agg_stats[('eeg_expiring_soon', 'any')].fillna(False)
    else:
        buildings_gdf['pv_eeg_expiring_soon'] = False
    
    # Datenquellen separat aggregieren (Lambda funktioniert nicht in multi-index)
    if 'data_source' in joined.columns:
        data_sources_agg = joined.groupby(joined.index)['data_source'].apply(
            lambda x: ', '.join(sorted(set(x.dropna())))
        )
        buildings_gdf['pv_data_sources'] = data_sources_agg.fillna('')
    else:
        buildings_gdf['pv_data_sources'] = ''
    
    # Markiere Gebäude mit PV
    buildings_gdf['has_existing_pv'] = buildings_gdf['pv_installations_count'] > 0
    
    # 5. Statistik
    buildings_with_pv = buildings_gdf['has_existing_pv'].sum()
    logger.info("="*80)
    logger.info("Prüfung abgeschlossen:")
    logger.info(f"Gebäude mit PV-Anlagen: {buildings_with_pv} ({buildings_with_pv/len(buildings_gdf)*100:.1f}%)")
    logger.info(f"Gebäude ohne PV-Anlagen: {len(buildings_gdf) - buildings_with_pv}")
    
    if buildings_with_pv > 0:
        pv_buildings = buildings_gdf[buildings_gdf['has_existing_pv']]
        avg_capacity = pv_buildings['pv_total_capacity_kwp'].mean()
        logger.info(f"Ø installierte Leistung: {avg_capacity:.1f} kWp")
        
        if 'pv_avg_age_years' in buildings_gdf.columns:
            avg_age = pv_buildings[pv_buildings['pv_avg_age_years'] > 0]['pv_avg_age_years'].mean()
            logger.info(f"Ø Anlagenalter: {avg_age:.1f} Jahre")
            
            old_installations = (pv_buildings['pv_max_age_years'] >= 15).sum()
            logger.info(f"Gebäude mit Anlagen ≥15 Jahre: {old_installations} (Modernisierungspotential)")
            
        if 'pv_eeg_expiring_soon' in buildings_gdf.columns:
            eeg_expiring = pv_buildings['pv_eeg_expiring_soon'].sum()
            if eeg_expiring > 0:
                logger.info(f"Gebäude mit auslaufendem EEG: {eeg_expiring} (Beratungsbedarf!)")
        
        # Datenquellen-Statistik
        mastr_only = (pv_buildings['pv_data_sources'] == 'MaStR').sum()
        osm_only = (pv_buildings['pv_data_sources'] == 'OSM').sum()
        both = (pv_buildings['pv_data_sources'] == 'MaStR, OSM').sum()
        logger.info(f"Datenquellen: {mastr_only} nur MaStR, {osm_only} nur OSM, {both} beide")
    
    logger.info("="*80)
    
    return buildings_gdf


def filter_buildings_without_pv(buildings: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Filtert Gebäude heraus, die bereits PV-Anlagen haben."""
    if 'has_existing_pv' not in buildings.columns:
        logger.warning("Spalte 'has_existing_pv' nicht gefunden")
        return buildings
    
    before = len(buildings)
    filtered = buildings[~buildings['has_existing_pv']].copy()
    after = len(filtered)
    
    logger.info(f"Filterung: {before} → {after} Gebäude ({before - after} mit PV entfernt)")
    
    return filtered


def main():
    """Hauptfunktion: Lädt MaStR und OSM Daten und prüft Gebäude."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger.info("=" * 80)
    logger.info("🔍 PV-Anlagen-Erkennung (MaStR + OSM)")
    logger.info("=" * 80)
    
    # Lade verarbeitete Gebäude
    buildings_path = PROCESSED_DORTMUND / "buildings_processed.geojson"
    if not buildings_path.exists():
        logger.error(f"Datei nicht gefunden: {buildings_path}")
        logger.info("Bitte erst ausführen: python -m pv_roof_leads.process_data")
        return
    
    logger.info(f"Lade Gebäude: {buildings_path}")
    buildings = gpd.read_file(buildings_path)
    logger.info(f"✓ {len(buildings)} Gebäude geladen")
    
    # Prüfe Gebäude (lädt automatisch beide Datenquellen)
    buildings = check_buildings_for_existing_pv(buildings)
    
    # Speichere vollständige Version (mit PV-Info)
    output_path_full = PROCESSED_DORTMUND / "buildings_processed_with_pv_info.geojson"
    buildings.to_file(output_path_full, driver='GeoJSON')
    logger.info(f"✓ Vollständige Version gespeichert: {output_path_full}")
    
    # Filtere Gebäude ohne PV
    buildings_filtered = filter_buildings_without_pv(buildings)
    
    # Speichere gefilterte Version
    output_path = PROCESSED_DORTMUND / "buildings_processed_no_pv.geojson"
    buildings_filtered.to_file(output_path, driver='GeoJSON')
    logger.info(f"✓ Gefilterte Version gespeichert: {output_path}")
    logger.info(f"{len(buildings_filtered)} Gebäude ohne bestehende PV-Anlagen")


if __name__ == '__main__':
    main()



