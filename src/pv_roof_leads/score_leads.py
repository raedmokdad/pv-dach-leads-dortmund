"""
Task 5.2: Lead-Scoring-System
Bewertet Zielgebäude nach Potential (0-100 Punkte)
"""

import geopandas as gpd
import pandas as pd
import math 
from pathlib import Path
from .config import (
    STAGING_DORTMUND,
    FINAL_DORTMUND,
    LANDUSE_INCLUDE,
    POI_NURSING_HOME,
    POI_EDUCATION,
    POI_SPORTS,
    POI_RETAIL,
    POI_HOSPITALITY,
    POI_PUBLIC,
    POI_LOGISTICS, 
    ZONE_SCORES,
    PRIORITY_THRESHOLDS
)

def calculate_roof_score(area_m2: float, max_points: float = 60.0) -> float:
    """
    Berechnet Dachflächen-Score (0-60 Punkte).
    
    Formel: score = min(60, (fläche / 10000) × 60)
    
    Beispiele:
    - 500 m²    → 3 Punkte
    - 2.000 m²  → 12 Punkte
    - 5.000 m²  → 30 Punkte
    - 10.000 m² → 60 Punkte (Maximum)
    - 20.000 m² → 60 Punkte (gedeckelt)
    """
    if area_m2 is None or not isinstance(area_m2, (int, float)) or math.isnan(area_m2):
        return 0.0
    reference_area = 10000.0  # 10.000 m² = 100% (60 Punkte)
    score = (area_m2 / reference_area) * max_points
    return min(score, max_points)


def calculate_zone_score(landuse: str, amenity: str, max_points: float = 40.0) -> float:
    """
    Berechnet Zonen-/Nutzungs-Score (0-40 Punkte).
    
    Priorität:
    - industrial / nursing_home: 40 Punkte (höchste Priorität)
    - commercial: 30 Punkte
    - education / sports: 25 Punkte
    - retail / hospitality: 20 Punkte
    - public / logistics: 15 Punkte
    - sonstige: 10 Punkte
    """
     # Prüfe zuerst landuse (Gewerbegebiete)
    if pd.notna(landuse) and landuse in ZONE_SCORES:
        return float(ZONE_SCORES[landuse])
    
    # Dann prüfe amenity (POI-Typen)
    if pd.notna(amenity) and amenity in ZONE_SCORES:
        return float(ZONE_SCORES[amenity])
    
    # Fallback für unbekannte Typen
    return float(ZONE_SCORES['default'])

def assign_priority(total_score: float) -> str:
    """
    Weist Prioritätskategorie basierend auf Score zu.
    
    A-Leads: Score ≥ 75 (Top-Priorität)
    B-Leads: Score 55-74 (Mittel)
    C-Leads: Score < 55 (Niedrig)
    """
    if total_score >= PRIORITY_THRESHOLDS['A']:
        return 'A'
    elif total_score >= PRIORITY_THRESHOLDS['B']:
        return 'B'
    else:
        return 'C'
    
    
# ...existing code...

def apply_scoring(buildings: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Wendet Scoring auf alle Gebäude an.
    
    Fügt hinzu:
    - roof_score (0-60)
    - zone_score (0-40)
    - total_score (0-100)
    - priority ('A', 'B', 'C')
    """
    print("\n" + "=" * 60)
    print("🎯 Berechne Scores für alle Gebäude")
    print("=" * 60)
    
    # Berechne Dachflächen-Score
    buildings['roof_score'] = buildings['footprint_area_m2'].apply(calculate_roof_score)
    
    # Berechne Zonen-Score
    buildings['zone_score'] = buildings.apply(
        lambda row: calculate_zone_score(row['landuse'], row['amenity']), 
        axis=1
    )
    
    # Berechne Gesamt-Score
    buildings['total_score'] = buildings['roof_score'] + buildings['zone_score']
    
    # Weise Priorität zu
    buildings['priority'] = buildings['total_score'].apply(assign_priority)
    
    print(f"✅ Scoring abgeschlossen für {len(buildings)} Gebäude")
    
    return buildings


def print_statistics(buildings: gpd.GeoDataFrame):
    """
    Gibt detaillierte Statistiken aus.
    """
    print("\n" + "=" * 60)
    print("📊 Scoring-Statistiken")
    print("=" * 60)
    
    # Score-Verteilung
    print(f"\n📈 Score-Verteilung:")
    print(f"   Durchschnitt: {buildings['total_score'].mean():.1f} Punkte")
    print(f"   Median:       {buildings['total_score'].median():.1f} Punkte")
    print(f"   Min:          {buildings['total_score'].min():.1f} Punkte")
    print(f"   Max:          {buildings['total_score'].max():.1f} Punkte")
    
    # Prioritäts-Verteilung
    print(f"\n🏆 Prioritäts-Verteilung:")
    for priority in ['A', 'B', 'C']:
        subset = buildings[buildings['priority'] == priority]
        count = len(subset)
        avg_area = subset['footprint_area_m2'].mean()
        avg_score = subset['total_score'].mean()
        
        print(f"   {priority}-Leads: {count:>4} Gebäude "
              f"(Ø {avg_area:>6.0f} m², Ø Score {avg_score:>4.1f})")
    
    # Top 10 Leads
    print(f"\n💎 Top 10 Leads:")
    top10 = buildings.nlargest(10, 'total_score')
    for idx, (i, row) in enumerate(top10.iterrows(), 1):
        name = row.get('name', 'Unbekannt')
        if pd.isna(name):
            name = 'Unbekannt'
        area = row['footprint_area_m2']
        score = row['total_score']
        landuse = row.get('landuse', '-')
        amenity = row.get('amenity', '-')
        
        print(f"   {idx:>2}. {name[:30]:30} | {area:>6.0f} m² | "
              f"Score: {score:>5.1f} | {landuse}/{amenity}")


def main():
    """
    Hauptfunktion: Lädt Daten, berechnet Scores, speichert Ergebnis.
    """
    print("\n" + "=" * 60)
    print("📊 Task 5.2: Lead Scoring")
    print("=" * 60)
    
    # Lade Zielgebäude (aus Task 5.1)
    target_file = STAGING_DORTMUND / "target_buildings.geojson"
    print(f"\n📂 Lade Zielgebäude: {target_file}")
    
    if not target_file.exists():
        raise FileNotFoundError(
            f"Zielgebäude nicht gefunden: {target_file}\n"
            f"Bitte erst Task 5.1 ausführen: python -m pv_roof_leads.filter_target"
        )
    
    buildings = gpd.read_file(target_file)
    print(f"✓ {len(buildings)} Gebäude geladen")
    
    # Wende Scoring an
    buildings = apply_scoring(buildings)
    
    # Sortiere nach Score (absteigend)
    buildings = buildings.sort_values('total_score', ascending=False).reset_index(drop=True)
    
    # Statistiken ausgeben
    print_statistics(buildings)
    
    # Speichere gescorte Gebäude
    output_file = STAGING_DORTMUND / "scored_buildings.geojson"
    buildings.to_file(output_file, driver='GeoJSON')
    print(f"\n✅ Gescorte Gebäude gespeichert: {output_file}")
    
    print("\n" + "=" * 60)
    print("✅ Task 5.2 abgeschlossen!")
    print("=" * 60)


if __name__ == '__main__':
    main()