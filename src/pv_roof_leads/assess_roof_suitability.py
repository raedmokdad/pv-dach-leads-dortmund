"""
Erweiterte Dach-Eignungsbewertung für PV-Anlagen

Bewertet Dächer basierend auf:
- Ausrichtung (Azimut)
- Neigung (Pitch)
- Verschattung (Shading)
- Nutzbare Fläche
- Dachzustand (optional)
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional


def score_azimuth(azimuth: float) -> float:
    """
    Bewertet Ausrichtung (0-100 Punkte).
    
    Optimal: Süd (150-210°) = 100 Punkte
    Sehr gut: Südost/Südwest (120-150° oder 210-240°) = 90 Punkte
    Gut: Ost/West (90-120° oder 240-270°) = 75 Punkte
    Akzeptabel: 60-90° oder 270-300° = 60 Punkte
    Suboptimal: 30-60° oder 300-330° = 40 Punkte
    Schlecht: Nord (0-30° oder 330-360°) = 20 Punkte
    
    Args:
        azimuth: Azimut in Grad (0°=Nord, 90°=Ost, 180°=Süd, 270°=West)
    
    Returns:
        Score 0-100
    """
    if pd.isna(azimuth) or azimuth is None:
        return 50.0  # Neutral wenn unbekannt
    
    # Normalisiere auf 0-360
    azimuth = azimuth % 360
    
    # Optimal: 150-210° (Süd ±30°)
    if 150 <= azimuth <= 210:
        return 100.0
    # Sehr gut: 120-150° oder 210-240° (Südost/Südwest)
    elif 120 <= azimuth < 150 or 210 < azimuth <= 240:
        return 90.0
    # Gut: 90-120° oder 240-270° (Ost/West)
    elif 90 <= azimuth < 120 or 240 < azimuth <= 270:
        return 75.0
    # Akzeptabel: 60-90° oder 270-300°
    elif 60 <= azimuth < 90 or 270 < azimuth <= 300:
        return 60.0
    # Suboptimal: 30-60° oder 300-330°
    elif 30 <= azimuth < 60 or 300 < azimuth <= 330:
        return 40.0
    # Schlecht: Nord (0-30° oder 330-360°)
    else:
        return 20.0


def score_pitch(pitch: float) -> float:
    """
    Bewertet Dachneigung (0-100 Punkte).
    
    Optimal: 25-40° für Deutschland = 100 Punkte
    Sehr gut: 20-25° oder 40-45° = 90 Punkte
    Gut: 15-20° oder 45-50° = 80 Punkte
    Akzeptabel: 10-15° oder 50-55° = 65 Punkte
    Suboptimal: 5-10° oder 55-60° = 50 Punkte
    Schlecht: <5° (Flachdach) oder >60° = 30 Punkte
    
    Args:
        pitch: Neigungswinkel in Grad (0°=flach, 90°=senkrecht)
    
    Returns:
        Score 0-100
    """
    if pd.isna(pitch) or pitch is None:
        return 70.0  # Neutral wenn unbekannt
    
    # Optimal: 25-40° für Deutschland (51° Breitengrad)
    if 25 <= pitch <= 40:
        return 100.0
    # Sehr gut: 20-25° oder 40-45°
    elif 20 <= pitch < 25 or 40 < pitch <= 45:
        return 90.0
    # Gut: 15-20° oder 45-50°
    elif 15 <= pitch < 20 or 45 < pitch <= 50:
        return 80.0
    # Akzeptabel: 10-15° oder 50-55°
    elif 10 <= pitch < 15 or 50 < pitch <= 55:
        return 65.0
    # Suboptimal: 5-10° oder 55-60°
    elif 5 <= pitch < 10 or 55 < pitch <= 60:
        return 50.0
    # Schlecht: <5° (Flachdach) oder >60° (sehr steil)
    else:
        return 30.0


def score_shading(sunshine_hours_per_year: float, 
                  max_sunshine_hours: float = 2000.0) -> float:
    """
    Bewertet Verschattung basierend auf Sonnenstunden.
    
    Keine/minimale Verschattung: >1800h = 100 Punkte
    Geringe Verschattung: >1600h = 85 Punkte
    Moderate Verschattung: >1400h = 70 Punkte
    Stärkere Verschattung: >1200h = 55 Punkte
    Starke Verschattung: >1000h = 40 Punkte
    Sehr starke Verschattung: <1000h = 20 Punkte
    
    Args:
        sunshine_hours_per_year: Tatsächliche Sonnenstunden/Jahr
        max_sunshine_hours: Theoretisches Maximum (ca. 2000h für Deutschland)
    
    Returns:
        Score 0-100
    """
    if pd.isna(sunshine_hours_per_year) or sunshine_hours_per_year is None:
        return 70.0  # Neutral wenn unbekannt
    
    if sunshine_hours_per_year <= 0:
        return 0.0
    
    # Keine/minimale Verschattung: >90% des Maximums
    if sunshine_hours_per_year >= max_sunshine_hours * 0.9:  # >1800h
        return 100.0
    # Geringe Verschattung: >80%
    elif sunshine_hours_per_year >= max_sunshine_hours * 0.8:  # >1600h
        return 85.0
    # Moderate Verschattung: >70%
    elif sunshine_hours_per_year >= max_sunshine_hours * 0.7:  # >1400h
        return 70.0
    # Stärkere Verschattung: >60%
    elif sunshine_hours_per_year >= max_sunshine_hours * 0.6:  # >1200h
        return 55.0
    # Starke Verschattung: >50%
    elif sunshine_hours_per_year >= max_sunshine_hours * 0.5:  # >1000h
        return 40.0
    # Sehr starke Verschattung: <50%
    else:
        return 20.0


def score_usable_area(usable_area_m2: float, 
                     total_roof_area_m2: float) -> float:
    """
    Bewertet nutzbare Dachfläche.
    
    Optimal: >80% nutzbar = 100 Punkte
    Sehr gut: 70-80% = 90 Punkte
    Gut: 60-70% = 80 Punkte
    Akzeptabel: 50-60% = 65 Punkte
    Suboptimal: 40-50% = 50 Punkte
    Schlecht: <40% = 30 Punkte
    
    Args:
        usable_area_m2: PV-nutzbare Fläche (nach Hindernissen)
        total_roof_area_m2: Gesamte Dachfläche
    
    Returns:
        Score 0-100
    """
    if (pd.isna(usable_area_m2) or pd.isna(total_roof_area_m2) or 
        total_roof_area_m2 == 0 or usable_area_m2 is None):
        return 70.0  # Neutral wenn unbekannt
    
    # Verhältnis nutzbar/gesamt
    ratio = usable_area_m2 / total_roof_area_m2
    
    # Optimal: >80% nutzbar
    if ratio >= 0.8:
        return 100.0
    # Sehr gut: 70-80%
    elif ratio >= 0.7:
        return 90.0
    # Gut: 60-70%
    elif ratio >= 0.6:
        return 80.0
    # Akzeptabel: 50-60%
    elif ratio >= 0.5:
        return 65.0
    # Suboptimal: 40-50%
    elif ratio >= 0.4:
        return 50.0
    # Schlecht: <40%
    else:
        return 30.0


def score_roof_condition(baujahr: Optional[int] = None) -> float:
    """
    Bewertet Dachzustand basierend auf Baujahr (Heuristik).
    
    Optimal: <10 Jahre alt = 100 Punkte
    Sehr gut: 10-20 Jahre = 90 Punkte
    Gut: 20-30 Jahre = 80 Punkte
    Akzeptabel: 30-40 Jahre = 65 Punkte
    Suboptimal: 40-50 Jahre = 50 Punkte
    Schlecht: >50 Jahre = 35 Punkte
    
    Args:
        baujahr: Baujahr des Gebäudes
    
    Returns:
        Score 0-100
    """
    if baujahr is None or pd.isna(baujahr):
        return 70.0  # Neutral wenn unbekannt
    
    current_year = 2025
    age = current_year - int(baujahr)
    
    if age < 0:  # Zukunftsdaten (unwahrscheinlich)
        return 70.0
    
    # Optimal: <10 Jahre alt
    if age <= 10:
        return 100.0
    # Sehr gut: 10-20 Jahre
    elif age <= 20:
        return 90.0
    # Gut: 20-30 Jahre
    elif age <= 30:
        return 80.0
    # Akzeptabel: 30-40 Jahre
    elif age <= 40:
        return 65.0
    # Suboptimal: 40-50 Jahre
    elif age <= 50:
        return 50.0
    # Schlecht: >50 Jahre
    else:
        return 35.0


def calculate_solar_suitability_score(solar_data: Dict) -> Dict:
    """
    Berechnet Eignungs-Score basierend auf allen Kriterien.
    
    Gewichtung:
    - Ausrichtung: 30%
    - Neigung: 20%
    - Verschattung: 25%
    - Nutzbare Fläche: 15%
    - Dachzustand: 10%
    
    Args:
        solar_data: Dict mit Solar-Daten (aus Google Solar API oder ähnlich)
    
    Returns:
        Dict mit einzelnen Scores, Gewichtungen und Gesamt-Score
    """
    scores = {}
    
    # 1. Ausrichtung (30% Gewichtung)
    azimuth = solar_data.get('solar_best_azimuth', 
                            solar_data.get('solar_avg_azimuth', 0))
    scores['azimuth_score'] = score_azimuth(azimuth)
    scores['azimuth_weight'] = 0.30
    
    # 2. Neigung (20% Gewichtung)
    pitch = solar_data.get('solar_best_pitch', 
                          solar_data.get('solar_avg_pitch', 0))
    scores['pitch_score'] = score_pitch(pitch)
    scores['pitch_weight'] = 0.20
    
    # 3. Verschattung (25% Gewichtung)
    sunshine_hours = solar_data.get('solar_sunshine_hours_year', 0)
    scores['shading_score'] = score_shading(sunshine_hours)
    scores['shading_weight'] = 0.25
    
    # 4. Nutzbare Fläche (15% Gewichtung)
    usable_area = solar_data.get('solar_max_array_m2', 0)
    total_area = solar_data.get('solar_roof_area_m2', 
                               solar_data.get('footprint_area_m2', 0))
    scores['area_score'] = score_usable_area(usable_area, total_area)
    scores['area_weight'] = 0.15
    
    # 5. Dachzustand (10% Gewichtung) - falls verfügbar
    baujahr = solar_data.get('baujahr', None)
    scores['condition_score'] = score_roof_condition(baujahr)
    scores['condition_weight'] = 0.10
    
    # Gesamt-Score (gewichteter Durchschnitt)
    total_score = (
        scores['azimuth_score'] * scores['azimuth_weight'] +
        scores['pitch_score'] * scores['pitch_weight'] +
        scores['shading_score'] * scores['shading_weight'] +
        scores['area_score'] * scores['area_weight'] +
        scores['condition_score'] * scores['condition_weight']
    )
    
    scores['total_suitability_score'] = round(total_score, 1)
    
    # Eignungsklasse
    if total_score >= 80:
        scores['suitability_class'] = 'A'  # Sehr gut geeignet
    elif total_score >= 65:
        scores['suitability_class'] = 'B'  # Gut geeignet
    elif total_score >= 50:
        scores['suitability_class'] = 'C'  # Akzeptabel
    else:
        scores['suitability_class'] = 'D'  # Suboptimal
    
    return scores


def assess_buildings_suitability(buildings_df: pd.DataFrame) -> pd.DataFrame:
    """
    Bewertet Eignung für alle Gebäude im DataFrame.
    
    Erwartet Spalten:
    - solar_best_azimuth (oder solar_avg_azimuth)
    - solar_best_pitch (oder solar_avg_pitch)
    - solar_sunshine_hours_year
    - solar_max_array_m2
    - solar_roof_area_m2 (oder footprint_area_m2)
    - baujahr (optional)
    
    Args:
        buildings_df: DataFrame mit Gebäuden und Solar-Daten
    
    Returns:
        DataFrame mit zusätzlichen Eignungs-Scores
    """
    suitability_scores = []
    
    for idx, row in buildings_df.iterrows():
        solar_data = {
            'solar_best_azimuth': row.get('solar_best_azimuth', row.get('solar_avg_azimuth', 0)),
            'solar_best_pitch': row.get('solar_best_pitch', row.get('solar_avg_pitch', 0)),
            'solar_avg_azimuth': row.get('solar_avg_azimuth', 0),
            'solar_avg_pitch': row.get('solar_avg_pitch', 0),
            'solar_sunshine_hours_year': row.get('solar_sunshine_hours_year', 0),
            'solar_max_array_m2': row.get('solar_max_array_m2', 0),
            'solar_roof_area_m2': row.get('solar_roof_area_m2', row.get('footprint_area_m2', 0)),
            'baujahr': row.get('baujahr', None)
        }
        
        scores = calculate_solar_suitability_score(solar_data)
        suitability_scores.append(scores)
    
    # Konvertiere zu DataFrame
    suitability_df = pd.DataFrame(suitability_scores)
    
    # Merge zurück
    result = pd.concat([buildings_df.reset_index(drop=True), 
                       suitability_df.reset_index(drop=True)], axis=1)
    
    return result


if __name__ == '__main__':
    # Test
    test_data = {
        'solar_best_azimuth': 180,  # Süd
        'solar_best_pitch': 30,  # Optimal
        'solar_sunshine_hours_year': 1800,  # Geringe Verschattung
        'solar_max_array_m2': 800,  # Nutzbare Fläche
        'solar_roof_area_m2': 1000,  # Gesamtfläche
        'baujahr': 2010
    }
    
    scores = calculate_solar_suitability_score(test_data)
    print("Test-Ergebnis:")
    for key, value in scores.items():
        print(f"  {key}: {value}")



