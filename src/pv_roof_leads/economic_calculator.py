"""
Wirtschaftlichkeitsrechner für PV-Anlagen mit echten Datenquellen.

Datenquellen:
- PVGIS API (EU Joint Research Centre): Präzise Solarertragsdaten
- Bundesnetzagentur: Aktuelle EEG-Vergütungssätze
- Fraunhofer ISE: Reale Investitionskosten aus Studien
"""

import logging
from pathlib import Path
from typing import Dict, Optional, Tuple
import requests
import time
import json
import geopandas as gpd
import pandas as pd
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EconomicCalculator:
    """Berechnet Wirtschaftlichkeit von PV-Anlagen mit echten Datenquellen."""
    
    # Aktuelle Marktdaten (Stand Dezember 2024)
    # Quelle: Fraunhofer ISE "Aktuelle Fakten zur Photovoltaik in Deutschland"
    INVESTMENT_COSTS = {
        'small': 1600,      # < 10 kWp (Einfamilienhaus): 1.600 €/kWp
        'medium': 1400,     # 10-40 kWp (Mehrfamilienhaus): 1.400 €/kWp
        'large': 1200,      # > 40 kWp (Gewerbe): 1.200 €/kWp
    }
    
    # Aktuelle EEG-Vergütung 2024/2025 (Bundesnetzagentur)
    # https://www.bundesnetzagentur.de/DE/Fachthemen/ElektrizitaetundGas/ErneuerbareEnergien/start.html
    EEG_TARIFF = {
        'small': 0.0825,    # < 10 kWp: 8,25 ct/kWh
        'medium': 0.0715,   # 10-40 kWp: 7,15 ct/kWh
        'large': 0.0575,    # 40-100 kWp: 5,75 ct/kWh
    }
    
    # Aktuelle Strompreise (Verivox Durchschnitt Dezember 2024)
    ELECTRICITY_PRICE = 0.32  # 32 ct/kWh Haushalt
    ELECTRICITY_PRICE_COMMERCIAL = 0.25  # 25 ct/kWh Gewerbe
    
    # Technische Parameter (konservativ)
    USABLE_ROOF_FACTOR = 0.65  # 65% der Dachfläche nutzbar
    KWP_PER_SQM = 0.17  # 170 Wp/m² (moderne Module ~330Wp, 1,95m²)
    PERFORMANCE_RATIO = 0.80  # 80% Performance Ratio (konservativ)
    MAINTENANCE_COST_PERCENT = 0.015  # 1,5% der Investition/Jahr
    DEGRADATION_RATE = 0.005  # 0,5% Leistungsverlust/Jahr
    SELF_CONSUMPTION_RESIDENTIAL = 0.35  # 35% Eigenverbrauch Wohngebäude
    SELF_CONSUMPTION_COMMERCIAL = 0.60  # 60% Eigenverbrauch Gewerbe
    LIFESPAN_YEARS = 25
    
    def __init__(self, cache_dir: Path = None):
        """
        Initialisiert den Wirtschaftlichkeitsrechner.
        
        Args:
            cache_dir: Verzeichnis für API-Cache (optional)
        """
        self.cache_dir = cache_dir or Path("cache/pvgis")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.pvgis_base_url = "https://re.jrc.ec.europa.eu/api/v5_2"
        
    def get_solar_radiation(self, lat: float, lon: float, 
                           slope: int = 30, azimuth: int = 0) -> Optional[Dict]:
        """
        Holt präzise Solarertragsdaten von PVGIS API.
        
        Args:
            lat: Breitengrad
            lon: Längengrad
            slope: Dachneigung in Grad (0=flach, 30=Standard, 90=Fassade)
            azimuth: Ausrichtung (0=Süd, -90=Ost, 90=West, 180=Nord)
            
        Returns:
            Dict mit Ertragsdaten oder None bei Fehler
        """
        # Cache-Key generieren
        cache_key = f"{lat:.4f}_{lon:.4f}_{slope}_{azimuth}"
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        # Aus Cache laden wenn vorhanden
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Cache-Fehler für {cache_key}: {e}")
        
        # Von PVGIS API abrufen
        try:
            # PVGIS PVcalc Tool API
            # https://joint-research-centre.ec.europa.eu/pvgis-photovoltaic-geographical-information-system/getting-started-pvgis/api-non-interactive-service_en
            params = {
                'lat': lat,
                'lon': lon,
                'peakpower': 1,  # 1 kWp für Normierung
                'loss': 20,  # 20% Systemverluste (1 - Performance Ratio)
                'angle': slope,  # Dachneigung
                'aspect': azimuth,  # Ausrichtung
                'pvtechchoice': 'crystSi',  # Kristallines Silizium (Standard)
                'mountingplace': 'building',  # Auf Gebäude montiert
                'outputformat': 'json'
            }
            
            response = requests.get(
                f"{self.pvgis_base_url}/PVcalc",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Relevante Daten extrahieren
            if 'outputs' in data and 'totals' in data['outputs']:
                result = {
                    'yearly_kwh_per_kwp': data['outputs']['totals']['fixed']['E_y'],  # kWh/Jahr pro kWp
                    'yearly_irradiation': data['outputs']['totals']['fixed']['H(i)_y'],  # kWh/m²/Jahr
                    'optimal_slope': data['inputs']['mounting_system'].get('fixed', {}).get('slope', slope),
                    'optimal_azimuth': data['inputs']['mounting_system'].get('fixed', {}).get('azimuth', azimuth),
                    'location': data['inputs']['location'],
                    'retrieved_at': datetime.now().isoformat()
                }
                
                # In Cache speichern
                try:
                    with open(cache_file, 'w', encoding='utf-8') as f:
                        json.dump(result, f, indent=2)
                except Exception as e:
                    logger.warning(f"Cache-Speichern fehlgeschlagen für {cache_key}: {e}")
                
                logger.info(f"PVGIS Daten abgerufen: {result['yearly_kwh_per_kwp']:.1f} kWh/kWp/Jahr")
                return result
            else:
                logger.error(f"Unerwartete PVGIS Antwort: {data}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"PVGIS API Fehler für ({lat}, {lon}): {e}")
            return None
        except Exception as e:
            logger.error(f"Fehler beim Verarbeiten der PVGIS Daten: {e}")
            return None
    
    def calculate_system_size(self, roof_area_m2: float, 
                             building_type: str = 'residential') -> Dict:
        """
        Berechnet die mögliche Anlagengröße basierend auf Dachfläche.
        
        Args:
            roof_area_m2: Dachfläche in m²
            building_type: 'residential', 'commercial', 'industrial'
            
        Returns:
            Dict mit Anlagengröße und technischen Details
        """
        usable_area = roof_area_m2 * self.USABLE_ROOF_FACTOR
        kwp_peak = usable_area * self.KWP_PER_SQM
        
        # Größenkategorie bestimmen
        if kwp_peak < 10:
            size_category = 'small'
        elif kwp_peak < 40:
            size_category = 'medium'
        else:
            size_category = 'large'
        
        return {
            'roof_area_m2': roof_area_m2,
            'usable_area_m2': usable_area,
            'kwp_peak': kwp_peak,
            'size_category': size_category,
            'module_area_m2': kwp_peak / self.KWP_PER_SQM,
            'estimated_modules': int(kwp_peak / 0.33)  # Bei 330W Modulen
        }
    
    def calculate_economics(self, lat: float, lon: float, roof_area_m2: float,
                           building_type: str = 'residential',
                           roof_slope: int = 30, roof_azimuth: int = 0) -> Dict:
        """
        Berechnet vollständige Wirtschaftlichkeit einer PV-Anlage.
        
        Args:
            lat: Breitengrad
            lon: Längengrad
            roof_area_m2: Dachfläche in m²
            building_type: 'residential', 'commercial', 'industrial'
            roof_slope: Dachneigung (0-90 Grad)
            roof_azimuth: Ausrichtung (0=Süd, -90=Ost, 90=West)
            
        Returns:
            Dict mit allen wirtschaftlichen Kennzahlen
        """
        # 1. Anlagengröße berechnen
        system = self.calculate_system_size(roof_area_m2, building_type)
        
        # 2. Solarertrag von PVGIS abrufen
        solar_data = self.get_solar_radiation(lat, lon, roof_slope, roof_azimuth)
        
        if not solar_data:
            logger.warning(f"Keine PVGIS Daten verfügbar für ({lat}, {lon}), verwende Fallback")
            # Fallback für Dortmund-Region: 950 kWh/kWp/Jahr
            yearly_kwh_per_kwp = 950
        else:
            yearly_kwh_per_kwp = solar_data['yearly_kwh_per_kwp']
        
        # 3. Jahresertrag berechnen
        yearly_production_kwh = system['kwp_peak'] * yearly_kwh_per_kwp
        
        # 4. Investitionskosten
        investment_cost_per_kwp = self.INVESTMENT_COSTS[system['size_category']]
        total_investment = system['kwp_peak'] * investment_cost_per_kwp
        
        # 5. Eigenverbrauch und Einspeisung
        if building_type in ['commercial', 'industrial']:
            self_consumption_rate = self.SELF_CONSUMPTION_COMMERCIAL
            electricity_price = self.ELECTRICITY_PRICE_COMMERCIAL
        else:
            self_consumption_rate = self.SELF_CONSUMPTION_RESIDENTIAL
            electricity_price = self.ELECTRICITY_PRICE
        
        self_consumption_kwh = yearly_production_kwh * self_consumption_rate
        grid_feed_in_kwh = yearly_production_kwh * (1 - self_consumption_rate)
        
        # 6. Erlöse
        eeg_tariff = self.EEG_TARIFF[system['size_category']]
        
        savings_self_consumption = self_consumption_kwh * electricity_price
        revenue_feed_in = grid_feed_in_kwh * eeg_tariff
        total_annual_revenue = savings_self_consumption + revenue_feed_in
        
        # 7. Betriebskosten
        annual_maintenance = total_investment * self.MAINTENANCE_COST_PERCENT
        annual_net_revenue = total_annual_revenue - annual_maintenance
        
        # 8. Amortisation (einfach, ohne Degradation)
        payback_period_years = total_investment / annual_net_revenue if annual_net_revenue > 0 else 999
        
        # 9. 25-Jahres-ROI (mit Degradation)
        cumulative_revenue = 0
        for year in range(1, self.LIFESPAN_YEARS + 1):
            degradation_factor = (1 - self.DEGRADATION_RATE) ** (year - 1)
            year_production = yearly_production_kwh * degradation_factor
            year_self_consumption = year_production * self_consumption_rate
            year_feed_in = year_production * (1 - self_consumption_rate)
            year_revenue = (year_self_consumption * electricity_price + 
                          year_feed_in * eeg_tariff - 
                          annual_maintenance)
            cumulative_revenue += year_revenue
        
        roi_25_years = cumulative_revenue - total_investment
        roi_25_years_percent = (roi_25_years / total_investment * 100) if total_investment > 0 else 0
        
        return {
            # Systemdaten
            'kwp_peak': round(system['kwp_peak'], 2),
            'usable_roof_area_m2': round(system['usable_area_m2'], 1),
            'estimated_modules': system['estimated_modules'],
            'size_category': system['size_category'],
            
            # Ertragsdaten
            'yearly_kwh_per_kwp': round(yearly_kwh_per_kwp, 1),
            'yearly_production_kwh': round(yearly_production_kwh, 0),
            'self_consumption_kwh': round(self_consumption_kwh, 0),
            'grid_feed_in_kwh': round(grid_feed_in_kwh, 0),
            'self_consumption_rate': round(self_consumption_rate * 100, 1),
            
            # Kosten
            'investment_cost_per_kwp': investment_cost_per_kwp,
            'total_investment_eur': round(total_investment, 0),
            'annual_maintenance_eur': round(annual_maintenance, 0),
            
            # Erlöse
            'electricity_price_eur_kwh': electricity_price,
            'eeg_tariff_eur_kwh': eeg_tariff,
            'annual_savings_self_consumption_eur': round(savings_self_consumption, 0),
            'annual_revenue_feed_in_eur': round(revenue_feed_in, 0),
            'annual_total_revenue_eur': round(total_annual_revenue, 0),
            'annual_net_revenue_eur': round(annual_net_revenue, 0),
            
            # ROI
            'payback_period_years': round(payback_period_years, 1),
            'roi_25_years_eur': round(roi_25_years, 0),
            'roi_25_years_percent': round(roi_25_years_percent, 1),
            
            # Metadaten
            'building_type': building_type,
            'calculation_date': datetime.now().isoformat(),
            'data_source_solar': 'PVGIS' if solar_data else 'Fallback',
            'data_source_prices': 'Fraunhofer ISE 2024, Bundesnetzagentur 2024'
        }


def enrich_buildings_with_economics(
    input_geojson: Path,
    output_geojson: Path,
    max_buildings: Optional[int] = None,
    max_workers: int = 10  # Parallel workers
) -> None:
    """
    Reichert GeoJSON-Datei mit Wirtschaftlichkeitsdaten an.
    
    Args:
        input_geojson: Pfad zur Eingabe-GeoJSON
        output_geojson: Pfad zur Ausgabe-GeoJSON
        max_buildings: Maximale Anzahl zu verarbeitender Gebäude (für Tests)
        max_workers: Anzahl paralleler Threads (Standard: 10)
    """
    logger.info(f"Lade Gebäudedaten von {input_geojson}")
    buildings = gpd.read_file(input_geojson)
    
    if max_buildings:
        buildings = buildings.head(max_buildings)
        logger.info(f"Limitiere auf {max_buildings} Gebäude für Test")
    
    logger.info(f"Verarbeite {len(buildings)} Gebäude")
    
    calculator = EconomicCalculator()
    
    # Nur Gebäude ohne existierende PV-Anlage berechnen
    buildings_to_calculate = buildings[buildings['has_existing_pv'] == False].copy()
    logger.info(f"Davon {len(buildings_to_calculate)} ohne bestehende PV-Anlage")
    logger.info(f"Verwende {max_workers} parallele Worker für schnellere Berechnung")
    
    # Neue Spalten initialisieren
    economic_columns = [
        'pv_kwp_potential', 'pv_yearly_kwh', 'pv_investment_eur',
        'pv_annual_revenue_eur', 'pv_payback_years', 'pv_roi_25y_eur',
        'pv_roi_25y_percent', 'pv_data_source'
    ]
    
    for col in economic_columns:
        if col not in buildings.columns:
            buildings[col] = None
    
    # Rate Limiting für PVGIS API (max 30 requests/minute = 0.5/second)
    # Mit 10 Workers: theoretisch 5 requests/second, aber wir throttlen auf 0.5/second
    rate_limiter = threading.Semaphore(1)  # Nur 1 Request gleichzeitig für PVGIS
    min_request_interval = 2.0  # Sekunden zwischen Requests
    last_request_time = {'time': time.time() - min_request_interval}
    lock = threading.Lock()
    
    def calculate_building(row_data):
        """Berechnet Wirtschaftlichkeit für ein Gebäude (Thread-safe)."""
        idx, row = row_data
        
        try:
            # Koordinaten-Transformation (UTM zu WGS84)
            centroid = row.geometry.centroid
            from pyproj import Transformer
            transformer = Transformer.from_crs("EPSG:25832", "EPSG:4326", always_xy=True)
            lon, lat = transformer.transform(centroid.x, centroid.y)
            
            # Dachfläche
            roof_area = row.get('footprint_area_m2', 0)
            if roof_area <= 0 or pd.isna(roof_area):
                return idx, None, f"keine Dachfläche"
            
            # Gebäudetyp ableiten
            building_tag = row.get('building', '')
            if building_tag in ['commercial', 'industrial', 'warehouse', 'retail']:
                building_type = 'commercial'
            else:
                building_type = 'residential'
            
            # Dachneigung schätzen
            roof_shape = row.get('roof:shape', '')
            if roof_shape == 'flat':
                roof_slope = 5
            elif roof_shape in ['gabled', 'hipped', 'pyramidal']:
                roof_slope = 35
            else:
                roof_slope = 30
            
            # Rate Limiting für PVGIS API
            with lock:
                elapsed = time.time() - last_request_time['time']
                if elapsed < min_request_interval:
                    time.sleep(min_request_interval - elapsed)
                last_request_time['time'] = time.time()
            
            # Wirtschaftlichkeit berechnen
            economics = calculator.calculate_economics(
                lat=lat,
                lon=lon,
                roof_area_m2=roof_area,
                building_type=building_type,
                roof_slope=roof_slope,
                roof_azimuth=0
            )
            
            return idx, economics, None
            
        except Exception as e:
            return idx, None, str(e)
    
    # Parallel verarbeiten
    results = {}
    errors = []
    completed = 0
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Alle Tasks starten
        future_to_idx = {
            executor.submit(calculate_building, (idx, row)): idx 
            for idx, row in buildings_to_calculate.iterrows()
        }
        
        # Ergebnisse sammeln
        for future in as_completed(future_to_idx):
            idx, economics, error = future.result()
            completed += 1
            
            if error:
                errors.append((idx, error))
            elif economics:
                results[idx] = economics
                
                # Daten in DataFrame schreiben
                buildings.at[idx, 'pv_kwp_potential'] = economics['kwp_peak']
                buildings.at[idx, 'pv_yearly_kwh'] = economics['yearly_production_kwh']
                buildings.at[idx, 'pv_investment_eur'] = economics['total_investment_eur']
                buildings.at[idx, 'pv_annual_revenue_eur'] = economics['annual_net_revenue_eur']
                buildings.at[idx, 'pv_payback_years'] = economics['payback_period_years']
                buildings.at[idx, 'pv_roi_25y_eur'] = economics['roi_25_years_eur']
                buildings.at[idx, 'pv_roi_25y_percent'] = economics['roi_25_years_percent']
                buildings.at[idx, 'pv_data_source'] = economics['data_source_solar']
            
            # Fortschritt
            if completed % 50 == 0:
                success_rate = len(results) / completed * 100 if completed > 0 else 0
                logger.info(f"Fortschritt: {completed}/{len(buildings_to_calculate)} Gebäude "
                          f"({success_rate:.1f}% erfolgreich)")
    
    # Zusammenfassung
    logger.info(f"\n{'='*60}")
    logger.info(f"Berechnung abgeschlossen:")
    logger.info(f"  Gesamt: {len(buildings_to_calculate)} Gebäude")
    logger.info(f"  Erfolgreich: {len(results)}")
    logger.info(f"  Fehler: {len(errors)}")
    if errors and len(errors) <= 10:
        logger.info(f"\nErste Fehler:")
        for idx, error in errors[:10]:
            logger.info(f"  Gebäude {idx}: {error}")
    logger.info(f"{'='*60}\n")
    
    # Speichern
    logger.info(f"Speichere angereicherte Daten nach {output_geojson}")
    output_geojson.parent.mkdir(parents=True, exist_ok=True)
    buildings.to_file(output_geojson, driver='GeoJSON')
    logger.info("Fertig!")


if __name__ == "__main__":
    """Test mit einem Beispiel-Gebäude"""
    
    # Beispiel: Gebäude in Dortmund
    calc = EconomicCalculator()
    
    # Test PVGIS API
    logger.info("=== Test: PVGIS API Abfrage ===")
    solar_data = calc.get_solar_radiation(
        lat=51.5136, 
        lon=7.4653,  # Dortmund Zentrum
        slope=30,    # 30° Dachneigung
        azimuth=0    # Süd-Ausrichtung
    )
    
    if solar_data:
        logger.info(f"✓ PVGIS Ertrag: {solar_data['yearly_kwh_per_kwp']:.1f} kWh/kWp/Jahr")
        logger.info(f"✓ Einstrahlung: {solar_data['yearly_irradiation']:.1f} kWh/m²/Jahr")
    
    # Test Wirtschaftlichkeitsrechnung
    logger.info("\n=== Test: Wirtschaftlichkeitsrechnung ===")
    economics = calc.calculate_economics(
        lat=51.5136,
        lon=7.4653,
        roof_area_m2=150,  # 150m² Dachfläche (z.B. Einfamilienhaus)
        building_type='residential',
        roof_slope=35,
        roof_azimuth=0
    )
    
    logger.info(f"\n📊 Ergebnis für 150m² Wohngebäude:")
    logger.info(f"  Anlagengröße: {economics['kwp_peak']} kWp")
    logger.info(f"  Jahresertrag: {economics['yearly_production_kwh']:,.0f} kWh")
    logger.info(f"  Investition: {economics['total_investment_eur']:,.0f} €")
    logger.info(f"  Jährliche Ersparnis: {economics['annual_net_revenue_eur']:,.0f} €")
    logger.info(f"  Amortisation: {economics['payback_period_years']:.1f} Jahre")
    logger.info(f"  ROI (25 Jahre): {economics['roi_25_years_eur']:,.0f} € ({economics['roi_25_years_percent']:.1f}%)")
