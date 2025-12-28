"""
Google Solar API Integration für detaillierte Dach-Analyse.

Diese API liefert:
- Exakte Dach-Segmente mit individueller Neigung & Azimuth
- Verschattungs-Analyse (stündliche Sonneneinstrahlung)
- Nutzbare Dachfläche pro Segment
- Optimale Panel-Platzierung
- Monatliche & jährliche Energieproduktion

Kosten: $0.006 pro Gebäude
Dokumentation: https://developers.google.com/maps/documentation/solar
"""

import requests
import logging
from pathlib import Path
import json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
import time
import os
from dotenv import load_dotenv

# Lade .env Datei
load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class RoofSegment:
    """Repräsentiert ein einzelnes Dach-Segment."""
    center_lat: float
    center_lon: float
    azimuth_degrees: float  # 0=Nord, 90=Ost, 180=Süd, 270=West
    pitch_degrees: float  # Neigung
    area_m2: float
    yearly_energy_kwh: float
    panels_count: int
    
    @property
    def orientation_name(self) -> str:
        """Konvertiert Azimuth in lesbaren Namen."""
        if 337.5 <= self.azimuth_degrees or self.azimuth_degrees < 22.5:
            return "Nord"
        elif 22.5 <= self.azimuth_degrees < 67.5:
            return "Nord-Ost"
        elif 67.5 <= self.azimuth_degrees < 112.5:
            return "Ost"
        elif 112.5 <= self.azimuth_degrees < 157.5:
            return "Süd-Ost"
        elif 157.5 <= self.azimuth_degrees < 202.5:
            return "Süd"
        elif 202.5 <= self.azimuth_degrees < 247.5:
            return "Süd-West"
        elif 247.5 <= self.azimuth_degrees < 292.5:
            return "West"
        else:
            return "Nord-West"


@dataclass
class SolarPotential:
    """Detaillierte Solar-Potenzial Daten von Google Solar API."""
    building_id: str
    max_array_panels_count: int
    max_array_area_m2: float
    max_sunshine_hours_per_year: float
    carbon_offset_kg_per_year: float
    
    # Beste Konfiguration
    whole_roof_stats: Dict[str, float]  # yearly_energy_kwh, cost_usd, etc.
    
    # Dach-Segmente
    roof_segments: List[RoofSegment]
    
    # Verschattung
    max_array_efficiency: float
    
    # API Metadaten
    image_date: str  # Datum der Luftaufnahme
    data_quality: str  # "HIGH", "MEDIUM", "LOW"
    

class GoogleSolarAPI:
    """Client für Google Solar API."""
    
    BASE_URL = "https://solar.googleapis.com/v1"
    
    def __init__(self, api_key: str, cache_dir: str = "cache/google_solar"):
        """
        Initialisiert den Google Solar API Client.
        
        Args:
            api_key: Google Cloud API Key mit Solar API aktiviert
            cache_dir: Verzeichnis für Cache-Dateien
        """
        self.api_key = api_key
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Rate Limiting: 600 requests/minute = 10 requests/second
        self.min_request_interval = 0.1  # 100ms zwischen Requests
        self.last_request_time = 0
    
    def _get_cache_path(self, building_id: str) -> Path:
        """Erstellt Cache-Pfad für ein Gebäude."""
        return self.cache_dir / f"{building_id}.json"
    
    def _wait_for_rate_limit(self):
        """Wartet, um Rate Limit einzuhalten."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)
        self.last_request_time = time.time()
    
    def get_building_insights(self, lat: float, lon: float, building_id: str) -> Optional[Dict[str, Any]]:
        """
        Holt Gebäude-Insights von Google Solar API.
        
        Args:
            lat: Breitengrad (WGS84)
            lon: Längengrad (WGS84)
            building_id: Eindeutige Gebäude-ID für Caching
            
        Returns:
            API-Response als Dictionary oder None bei Fehler
        """
        # Cache prüfen
        cache_path = self._get_cache_path(building_id)
        if cache_path.exists():
            logger.debug(f"Lade Google Solar Daten aus Cache: {building_id}")
            with open(cache_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        # API-Aufruf
        self._wait_for_rate_limit()
        
        url = f"{self.BASE_URL}/buildingInsights:findClosest"
        params = {
            "location.latitude": lat,
            "location.longitude": lon,
            "requiredQuality": "LOW",  # Akzeptiere auch niedrigere Qualität
            "key": self.api_key
        }
        
        try:
            response = requests.get(url, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                
                # In Cache speichern
                with open(cache_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                
                logger.info(f"Google Solar Daten abgerufen: {building_id}")
                return data
            
            elif response.status_code == 404:
                logger.warning(f"Keine Solar-Daten verfügbar für: {building_id} ({lat}, {lon})")
                return None
            
            else:
                logger.error(f"Google Solar API Fehler {response.status_code}: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Fehler beim API-Aufruf für {building_id}: {str(e)}")
            return None
    
    def parse_solar_potential(self, data: Dict[str, Any], building_id: str) -> Optional[SolarPotential]:
        """
        Parst API-Response und extrahiert Solar-Potenzial.
        
        Args:
            data: API-Response Dictionary
            building_id: Gebäude-ID
            
        Returns:
            SolarPotential Objekt oder None
        """
        try:
            solar_potential = data.get("solarPotential", {})
            
            # Dach-Segmente extrahieren
            roof_segments = []
            for segment_data in solar_potential.get("roofSegmentStats", []):
                segment = RoofSegment(
                    center_lat=segment_data.get("center", {}).get("latitude", 0),
                    center_lon=segment_data.get("center", {}).get("longitude", 0),
                    azimuth_degrees=segment_data.get("azimuthDegrees", 0),
                    pitch_degrees=segment_data.get("pitchDegrees", 0),
                    area_m2=segment_data.get("stats", {}).get("areaMeters2", 0),
                    yearly_energy_kwh=segment_data.get("stats", {}).get("sunshineQuantiles", [0])[5] if segment_data.get("stats", {}).get("sunshineQuantiles") else 0,
                    panels_count=segment_data.get("panelsCount", 0)
                )
                roof_segments.append(segment)
            
            # Beste Konfiguration (ganzes Dach)
            max_array_config = solar_potential.get("maxArrayPanelsCount", 0)
            
            # Finde die Config mit maximaler Panel-Anzahl
            whole_roof_stats = {}
            for config in solar_potential.get("solarPanelConfigs", []):
                if config.get("panelsCount") == max_array_config:
                    whole_roof_stats = {
                        "panels_count": config.get("panelsCount", 0),
                        "yearly_energy_kwh": config.get("yearlyEnergyDcKwh", 0),
                        "roof_area_m2": config.get("roofSegmentSummaries", [{}])[0].get("pitchedAreaMeters2", 0) if config.get("roofSegmentSummaries") else 0,
                    }
                    break
            
            potential = SolarPotential(
                building_id=building_id,
                max_array_panels_count=solar_potential.get("maxArrayPanelsCount", 0),
                max_array_area_m2=solar_potential.get("maxArrayAreaMeters2", 0),
                max_sunshine_hours_per_year=solar_potential.get("maxSunshineHoursPerYear", 0),
                carbon_offset_kg_per_year=solar_potential.get("carbonOffsetFactorKgPerMwh", 0) * (whole_roof_stats.get("yearly_energy_kwh", 0) / 1000),
                whole_roof_stats=whole_roof_stats,
                roof_segments=roof_segments,
                max_array_efficiency=solar_potential.get("panelCapacityWatts", 400) / 1000,  # kW
                image_date=data.get("imageryDate", {}).get("year", "unknown"),
                data_quality=data.get("imageryQuality", "UNKNOWN")
            )
            
            return potential
            
        except Exception as e:
            logger.error(f"Fehler beim Parsen der Solar-Daten für {building_id}: {str(e)}")
            return None
    
    def enrich_building_with_solar_data(self, building: Dict[str, Any]) -> Dict[str, Any]:
        """
        Reichert ein Gebäude mit Google Solar API Daten an.
        
        Args:
            building: Building Feature Dictionary mit geometry
            
        Returns:
            Angereichertes Building Dictionary mit google_solar_* Feldern
        """
        # Extrahiere Koordinaten - nutze Centroid der Geometrie
        import shapely.geometry
        from pyproj import Transformer
        
        building_id = str(building.get("properties", {}).get("id", "unknown"))
        
        try:
            # Erstelle Shapely-Geometrie und berechne Centroid
            geom = building.get("geometry", {})
            shape = shapely.geometry.shape(geom)
            centroid = shape.centroid
            
            # Transformiere von UTM (EPSG:25832) zu WGS84 (EPSG:4326)
            # UTM coordinates -> lat/lon
            transformer = Transformer.from_crs("EPSG:25832", "EPSG:4326", always_xy=True)
            lon, lat = transformer.transform(centroid.x, centroid.y)
            
            # Validiere Koordinaten (Deutschland: ~47-55°N, 5-15°E)
            if not (5 <= lon <= 15 and 47 <= lat <= 55):
                logger.warning(f"Ungültige Koordinaten für Gebäude {building_id}: ({lat}, {lon})")
                building["properties"]["google_solar_available"] = False
                building["properties"]["google_solar_error"] = "invalid_coordinates"
                return building
                
        except Exception as e:
            logger.error(f"Fehler bei Koordinaten-Extraktion für {building_id}: {str(e)}")
            building["properties"]["google_solar_available"] = False
            building["properties"]["google_solar_error"] = f"geometry_error: {str(e)}"
            return building
        
        # API-Aufruf
        data = self.get_building_insights(lat, lon, building_id)
        
        if not data:
            # Keine Daten verfügbar
            building["properties"]["google_solar_available"] = False
            return building
        
        # Parsen
        potential = self.parse_solar_potential(data, building_id)
        
        if not potential:
            building["properties"]["google_solar_available"] = False
            return building
        
        # Daten hinzufügen
        props = building["properties"]
        props["google_solar_available"] = True
        props["google_solar_panels_max"] = potential.max_array_panels_count
        props["google_solar_area_m2"] = potential.max_array_area_m2
        props["google_solar_yearly_kwh"] = potential.whole_roof_stats.get("yearly_energy_kwh", 0)
        props["google_solar_sunshine_hours"] = potential.max_sunshine_hours_per_year
        props["google_solar_co2_offset_kg"] = potential.carbon_offset_kg_per_year
        props["google_solar_segments_count"] = len(potential.roof_segments)
        props["google_solar_image_date"] = potential.image_date
        props["google_solar_data_quality"] = potential.data_quality
        
        # Bestes Segment (höchste Energie)
        if potential.roof_segments:
            best_segment = max(potential.roof_segments, key=lambda s: s.yearly_energy_kwh)
            props["google_solar_best_azimuth"] = best_segment.azimuth_degrees
            props["google_solar_best_pitch"] = best_segment.pitch_degrees
            props["google_solar_best_orientation"] = best_segment.orientation_name
        
        return building


def test_api():
    """Testet die Google Solar API mit einem Beispiel-Gebäude in Dortmund."""
    import os
    
    # API Key aus Umgebungsvariable ODER direkt hier eingeben:
    api_key = os.environ.get("GOOGLE_SOLAR_API_KEY") 
    if not api_key:
        print("❌ FEHLER: GOOGLE_SOLAR_API_KEY Umgebungsvariable nicht gesetzt!")
        print("\nSo bekommst du einen API Key:")
        print("1. Gehe zu: https://console.cloud.google.com/")
        print("2. Erstelle ein neues Projekt oder wähle ein bestehendes")
        print("3. Aktiviere 'Solar API' unter APIs & Services")
        print("4. Erstelle einen API Key unter 'Credentials'")
        print("5. Setze Umgebungsvariable: $env:GOOGLE_SOLAR_API_KEY='your-key-here'")
        return
    
    client = GoogleSolarAPI(api_key)
    
    # Beispiel: Dortmund Rathaus
    lat, lon = 51.5136, 7.4653
    building_id = "test_rathaus_dortmund"
    
    print("=" * 80)
    print("GOOGLE SOLAR API TEST")
    print("=" * 80)
    print(f"Koordinaten: {lat}, {lon}")
    print(f"Building ID: {building_id}")
    print()
    
    # API-Aufruf
    print("📡 Rufe Google Solar API auf...")
    data = client.get_building_insights(lat, lon, building_id)
    
    if not data:
        print("❌ Keine Daten verfügbar")
        return
    
    print("✅ Daten erfolgreich abgerufen!")
    print()
    
    # Parsen
    potential = client.parse_solar_potential(data, building_id)
    
    if not potential:
        print("❌ Fehler beim Parsen")
        return
    
    # Ausgabe
    print("=" * 80)
    print("SOLAR-POTENZIAL")
    print("=" * 80)
    print(f"Max. Panels: {potential.max_array_panels_count}")
    print(f"Dachfläche: {potential.max_array_area_m2:.1f} m²")
    print(f"Jahresertrag: {potential.whole_roof_stats.get('yearly_energy_kwh', 0):,.0f} kWh")
    print(f"Sonnenstunden/Jahr: {potential.max_sunshine_hours_per_year:.0f} h")
    print(f"CO₂-Einsparung: {potential.carbon_offset_kg_per_year:.0f} kg/Jahr")
    print(f"Dach-Segmente: {len(potential.roof_segments)}")
    print(f"Luftbild vom: {potential.image_date}")
    print(f"Datenqualität: {potential.data_quality}")
    print()
    
    # Dach-Segmente
    if potential.roof_segments:
        print("=" * 80)
        print("DACH-SEGMENTE")
        print("=" * 80)
        for i, segment in enumerate(potential.roof_segments, 1):
            print(f"\nSegment {i}:")
            print(f"  Fläche: {segment.area_m2:.1f} m²")
            print(f"  Neigung: {segment.pitch_degrees:.1f}°")
            print(f"  Orientierung: {segment.orientation_name} ({segment.azimuth_degrees:.0f}°)")
            print(f"  Panels: {segment.panels_count}")
            print(f"  Jahresertrag: {segment.yearly_energy_kwh:,.0f} kWh")
    
    print()
    print("=" * 80)
    print("✓ TEST ERFOLGREICH!")
    print("=" * 80)


if __name__ == "__main__":
    test_api()
