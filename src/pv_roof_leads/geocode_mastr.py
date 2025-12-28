#!/usr/bin/env python3
"""
Geocoding für MaStR-Adressen ohne GPS-Koordinaten.
Verwendet Nominatim (OpenStreetMap) für kostenloses Geocoding.
"""

import pandas as pd
import time
from pathlib import Path
import requests
from typing import Optional, Tuple
import json

# Nominatim API (kostenlos, Rate Limit: 1 Request/Sekunde)
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "PV-Dach-Leads-Dortmund/1.0"

def geocode_address(street: str, plz: str, city: str = "Dortmund") -> Optional[Tuple[float, float]]:
    """
    Geocodiert eine Adresse zu GPS-Koordinaten.
    
    Args:
        street: Straße mit Hausnummer
        plz: Postleitzahl
        city: Stadt (Standard: Dortmund)
        
    Returns:
        (lat, lon) oder None bei Fehler
    """
    # Query formatieren
    query = f"{street}, {plz} {city}, Deutschland"
    
    params = {
        'q': query,
        'format': 'json',
        'limit': 1,
        'addressdetails': 1
    }
    
    headers = {
        'User-Agent': USER_AGENT
    }
    
    try:
        response = requests.get(NOMINATIM_URL, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        
        results = response.json()
        if results and len(results) > 0:
            lat = float(results[0]['lat'])
            lon = float(results[0]['lon'])
            return (lat, lon)
        else:
            return None
            
    except Exception as e:
        print(f"  ⚠️  Geocoding-Fehler für '{query}': {e}")
        return None


def geocode_mastr_data(input_csv: Path, output_csv: Path, cache_file: Optional[Path] = None) -> pd.DataFrame:
    """
    Geocodiert MaStR-Daten und speichert das Ergebnis.
    
    Args:
        input_csv: Eingabe-CSV mit MaStR-Daten
        output_csv: Ausgabe-CSV mit geocodierten Daten
        cache_file: Optional: JSON-Cache für Geocoding-Ergebnisse
        
    Returns:
        DataFrame mit geocodierten Daten
    """
    print("=" * 60)
    print("MaStR Geocoding")
    print("=" * 60)
    
    # Cache laden
    cache = {}
    if cache_file and cache_file.exists():
        with open(cache_file, 'r', encoding='utf-8') as f:
            cache = json.load(f)
        print(f"[INFO] Geocoding-Cache geladen: {len(cache)} Einträge")
    
    # MaStR-Daten laden
    print(f"\n[1/4] Lade MaStR-Daten: {input_csv.name}")
    df = pd.read_csv(input_csv, sep=';', encoding='utf-8')
    print(f"  ✓ {len(df)} Einträge geladen")
    
    # Filter für Dortmund (PLZ 44xxx)
    df = df[df['Postleitzahl'].astype(str).str.startswith('44')]
    print(f"  ✓ {len(df)} Einträge mit PLZ 44xxx")
    
    # Nur Zeilen ohne GPS-Koordinaten
    df_no_gps = df[
        (df['Breitengrad'].isna() | (df['Breitengrad'] == '')) |
        (df['Längengrad'].isna() | (df['Längengrad'] == ''))
    ].copy()
    
    df_with_gps = df[
        df['Breitengrad'].notna() & (df['Breitengrad'] != '') &
        df['Längengrad'].notna() & (df['Längengrad'] != '')
    ].copy()
    
    print(f"\n[2/4] Analyse:")
    print(f"  • Mit GPS: {len(df_with_gps)}")
    print(f"  • Ohne GPS: {len(df_no_gps)}")
    
    if len(df_no_gps) == 0:
        print("\n[INFO] Alle Einträge haben bereits GPS-Koordinaten!")
        return df
    
    # Geocoding durchführen
    print(f"\n[3/4] Geocoding für {len(df_no_gps)} Adressen:")
    print("  (Rate Limit: 1 Request/Sekunde)")
    
    geocoded = 0
    failed = 0
    skipped = 0
    
    for idx, row in df_no_gps.iterrows():
        # Adresse prüfen
        plz = str(row.get('Postleitzahl', '')).strip()
        # MaStR hat keine Straßen-Spalten, versuche über Ort
        ort = str(row.get('Ort', '')).strip()
        
        if not plz or plz == 'nan':
            skipped += 1
            continue
        
        # Nur PLZ und Ort für Geocoding (keine Straßenadressen in MaStR)
        if not ort or ort == 'nan':
            ort = "Dortmund"
        
        street = f"{plz} {ort}"  # Geocoding über PLZ + Ort
        
        # Cache-Key
        cache_key = f"{street}|{plz}"
        
        # Cache prüfen
        if cache_key in cache:
            result = cache[cache_key]
            if result:
                df.loc[idx, 'Breitengrad'] = result[0]
                df.loc[idx, 'Laengengrad'] = result[1]
                geocoded += 1
            else:
                failed += 1
            continue
        
        # Geocoding durchführen
        result = geocode_address(street, plz)
        
        # Ergebnis speichern
        cache[cache_key] = result
        
        if result:
            df.loc[idx, 'Breitengrad'] = result[0]
            df.loc[idx, 'Längengrad'] = result[1]
            geocoded += 1
            print(f"  ✓ {geocoded}/{len(df_no_gps)}: {street}, {plz} → {result[0]:.6f}, {result[1]:.6f}")
        else:
            failed += 1
            print(f"  ✗ {failed} fehlgeschlagen: {street}, {plz}")
        
        # Rate Limit respektieren (1 Request/Sekunde)
        time.sleep(1.1)
        
        # Cache regelmäßig speichern
        if (geocoded + failed) % 10 == 0 and cache_file:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache, f, ensure_ascii=False, indent=2)
    
    # Cache final speichern
    if cache_file:
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
        print(f"\n[INFO] Cache gespeichert: {cache_file}")
    
    print(f"\n[4/4] Ergebnis:")
    print(f"  ✓ Erfolgreich geocodiert: {geocoded}")
    print(f"  ✗ Fehlgeschlagen: {failed}")
    print(f"  ⊘ Übersprungen (keine Adresse): {skipped}")
    print(f"  → Gesamt mit GPS: {len(df_with_gps) + geocoded}")
    
    # Ergebnis speichern
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_csv, sep=';', index=False, encoding='utf-8')
    print(f"\n[OK] Geocodierte Daten gespeichert: {output_csv}")
    
    return df


def main():
    """Hauptfunktion für Kommandozeilen-Nutzung."""
    base_dir = Path(__file__).resolve().parents[2]
    
    # Pfade
    input_csv = base_dir / "data" / "raw" / "dortmund" / "mastr_pv.csv"
    output_csv = base_dir / "data" / "processed" / "dortmund" / "mastr_geocoded.csv"
    cache_file = base_dir / "cache" / "geocoding_cache.json"
    
    # Geocoding durchführen
    df = geocode_mastr_data(input_csv, output_csv, cache_file)
    
    # Statistik
    total = len(df)
    with_coords = df[
        df['Breitengrad'].notna() & (df['Breitengrad'] != '') &
        df['Längengrad'].notna() & (df['Längengrad'] != '')
    ]
    
    print("\n" + "=" * 60)
    print(f"[FINAL] {len(with_coords)}/{total} Einträge haben GPS-Koordinaten ({len(with_coords)/total*100:.1f}%)")
    print("=" * 60)


if __name__ == "__main__":
    main()
