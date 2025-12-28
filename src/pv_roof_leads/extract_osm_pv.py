"""
Extract PV installations from OpenStreetMap using OSMnx
"""

import osmnx as ox
import geopandas as gpd
import pandas as pd
from pathlib import Path
import logging
from .config import RAW_DORTMUND, DORTMUND_BBOX, CRS_INTERNAL

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def extract_osm_pv_installations():
    """
    Extract PV installations from OpenStreetMap.
    
    Searches for:
    - generator:source=solar
    - plant:source=solar  
    - power=generator with solar tags
    """
    logger.info("\n" + "=" * 60)
    logger.info("OSM PV-Anlagen Extraktion")
    logger.info("=" * 60)
    
    # Dortmund bounding box
    north, south, east, west = DORTMUND_BBOX
    
    # Query OSM for solar installations
    logger.info(f"\nSuche OSM-Daten in Bbox: {north}, {south}, {east}, {west}")
    
    # Query 1: Nodes with solar generator tags
    logger.info("\n1. Suche Nodes mit 'generator:source=solar'...")
    try:
        tags_generator = {
            'generator:source': 'solar',
        }
        solar_nodes = ox.features_from_bbox(
            bbox=(north, south, east, west),
            tags=tags_generator
        )
        logger.info(f"   Gefunden: {len(solar_nodes)} solar generator nodes")
    except Exception as e:
        logger.warning(f"   Keine solar generator nodes gefunden: {e}")
        solar_nodes = gpd.GeoDataFrame()
    
    # Query 2: Power=generator with solar
    logger.info("\n2. Suche 'power=generator'...")
    try:
        tags_power = {
            'power': 'generator',
        }
        power_generators = ox.features_from_bbox(
            bbox=(north, south, east, west),
            tags=tags_power
        )
        # Filter for solar only
        if 'generator:source' in power_generators.columns:
            power_generators = power_generators[
                power_generators['generator:source'] == 'solar'
            ]
        logger.info(f"   Gefunden: {len(power_generators)} power=generator (solar)")
    except Exception as e:
        logger.warning(f"   Keine power generators gefunden: {e}")
        power_generators = gpd.GeoDataFrame()
    
    # Query 3: Plant:source=solar
    logger.info("\n3. Suche 'plant:source=solar'...")
    try:
        tags_plant = {
            'plant:source': 'solar',
        }
        solar_plants = ox.features_from_bbox(
            bbox=(north, south, east, west),
            tags=tags_plant
        )
        logger.info(f"   Gefunden: {len(solar_plants)} solar plants")
    except Exception as e:
        logger.warning(f"   Keine solar plants gefunden: {e}")
        solar_plants = gpd.GeoDataFrame()
    
    # Combine all results
    all_solar = []
    
    if not solar_nodes.empty:
        all_solar.append(solar_nodes)
    if not power_generators.empty:
        all_solar.append(power_generators)
    if not solar_plants.empty:
        all_solar.append(solar_plants)
    
    if not all_solar:
        logger.warning("\n⚠️  Keine PV-Anlagen in OSM gefunden!")
        return gpd.GeoDataFrame()
    
    # Merge and deduplicate
    combined = pd.concat(all_solar, ignore_index=True)
    
    # Remove duplicates based on OSM ID
    if 'osmid' in combined.columns:
        combined = combined.drop_duplicates(subset=['osmid'])
    
    logger.info(f"\n✓ Total (nach Deduplizierung): {len(combined)} PV-Anlagen")
    
    # Convert to point geometries (centroids)
    combined['geometry'] = combined['geometry'].centroid
    
    # Convert to internal CRS
    if combined.crs != CRS_INTERNAL:
        logger.info(f"   Transformiere von {combined.crs} → {CRS_INTERNAL}")
        combined = combined.to_crs(CRS_INTERNAL)
    
    # Extract relevant fields
    pv_data = gpd.GeoDataFrame(
        geometry=combined.geometry,
        crs=CRS_INTERNAL
    )
    
    # Add capacity if available
    capacity_fields = ['generator:output:electricity', 'capacity', 'power_output']
    for field in capacity_fields:
        if field in combined.columns:
            pv_data['capacity_kwp'] = pd.to_numeric(
                combined[field].str.extract(r'(\d+\.?\d*)')[0],
                errors='coerce'
            )
            break
    
    if 'capacity_kwp' not in pv_data.columns:
        pv_data['capacity_kwp'] = None
    
    # Add source
    pv_data['data_source'] = 'OSM'
    
    # Add OSM ID
    if 'osmid' in combined.columns:
        pv_data['osm_id'] = combined['osmid']
    
    # Add name if available
    if 'name' in combined.columns:
        pv_data['name'] = combined['name']
    
    # Add operator if available
    if 'operator' in combined.columns:
        pv_data['operator'] = combined['operator']
    
    # Save to file
    output_file = RAW_DORTMUND / "osm_pv_installations.geojson"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    pv_data.to_file(output_file, driver='GeoJSON')
    logger.info(f"\n✓ Gespeichert: {output_file}")
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("Zusammenfassung")
    logger.info("=" * 60)
    logger.info(f"OSM PV-Anlagen gesamt: {len(pv_data)}")
    logger.info(f"Mit Kapazität: {pv_data['capacity_kwp'].notna().sum()}")
    if pv_data['capacity_kwp'].notna().any():
        logger.info(f"Durchschnittliche Kapazität: {pv_data['capacity_kwp'].mean():.1f} kWp")
    
    return pv_data


def main():
    """Main function"""
    extract_osm_pv_installations()


if __name__ == '__main__':
    main()
