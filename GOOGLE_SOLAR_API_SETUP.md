"""
Setup-Anleitung für Google Solar API
====================================

Die Google Solar API liefert detaillierte Dach-Analysen für präzise PV-Potenzial-Berechnungen.

KOSTEN
------
- $0.006 pro Gebäude
- Für 200 Top-Leads: 200 × $0.006 = $1.20
- Für 4.906 Gebäude: 4.906 × $0.006 = $29.44

VORTEILE
--------
✅ Exakte Dach-Segmente mit individueller Neigung & Azimuth
✅ Verschattungs-Analyse (stündliche Sonneneinstrahlung)
✅ Nutzbare Dachfläche pro Segment (nicht nur Grundfläche!)
✅ Optimale Panel-Platzierung
✅ Monatliche & jährliche Energieproduktion
✅ Datenqualität & Luftbild-Datum


SCHRITT 1: Google Cloud Projekt erstellen
------------------------------------------
1. Gehe zu: https://console.cloud.google.com/
2. Klicke oben auf "Select a project" → "New Project"
3. Projektname: "PV-Leads-Dortmund"
4. Klicke "Create"


SCHRITT 2: Solar API aktivieren
--------------------------------
1. Im Google Cloud Console: https://console.cloud.google.com/apis/library
2. Suche nach "Solar API"
3. Klicke auf "Solar API"
4. Klicke "Enable"
5. Warte ~2 Minuten bis API aktiviert ist


SCHRITT 3: API Key erstellen
-----------------------------
1. Gehe zu: https://console.cloud.google.com/apis/credentials
2. Klicke "+ CREATE CREDENTIALS" → "API key"
3. Kopiere den API Key (sieht aus wie: AIzaSyD...)
4. Klicke "EDIT API KEY" (optional):
   - Unter "API restrictions": Wähle "Restrict key"
   - Wähle nur "Solar API"
   - Klicke "Save"


SCHRITT 4: Billing aktivieren (WICHTIG!)
-----------------------------------------
Die Solar API erfordert ein Billing-Konto, auch wenn du im Free Tier bleibst.

1. Gehe zu: https://console.cloud.google.com/billing
2. Klicke "Link a billing account"
3. Erstelle ein neues Billing-Konto oder verknüpfe ein bestehendes
4. Kreditkarte hinzufügen (wird nur bei Überschreitung des Free Tier belastet)

GOOGLE CLOUD FREE TIER:
- $200 Guthaben für die ersten 90 Tage
- Die ersten $200 sind kostenlos!
- Für 4.906 Gebäude ($29.44) bist du weit unter dem Free Tier


SCHRITT 5: API Key in Umgebung setzen
--------------------------------------
Setze den API Key als Umgebungsvariable (PowerShell):

    $env:GOOGLE_SOLAR_API_KEY = "AIzaSyD..."

Oder dauerhaft in Windows:
1. Suche "Umgebungsvariablen bearbeiten"
2. "Umgebungsvariablen..." Button
3. Unter "Benutzervariablen": "Neu..."
4. Variable: GOOGLE_SOLAR_API_KEY
5. Wert: dein API Key


SCHRITT 6: API testen
----------------------
Teste die Integration:

    python src/pv_roof_leads/google_solar_api.py

Wenn alles funktioniert, siehst du Solar-Daten für das Dortmunder Rathaus.


SCHRITT 7: Top-Leads anreichern
--------------------------------
Nachdem die PVGIS-Berechnung fertig ist, können wir die Top 200 Leads mit
Google Solar Daten anreichern:

    python enrich_top_leads_with_google_solar.py


HÄUFIGE FEHLER
--------------
❌ "GOOGLE_SOLAR_API_KEY nicht gesetzt"
   → Umgebungsvariable setzen (siehe Schritt 5)

❌ "API Key not valid"
   → API Key nochmal prüfen, keine Leerzeichen kopiert?

❌ "Solar API has not been enabled"
   → API aktivieren (Schritt 2), 2 Minuten warten

❌ "PROJECT_BILLING_NOT_ENABLED"
   → Billing aktivieren (Schritt 4)

❌ "404 Not Found" bei manchen Gebäuden
   → Normal! Nicht alle Gebäude haben Google Solar Daten
   → Für Deutschland ist die Abdeckung ~60-80%


NÄCHSTE SCHRITTE
----------------
1. Warte bis PVGIS-Berechnung fertig ist
2. Filtere Top 200 Leads nach ROI
3. Reichere diese 200 mit Google Solar API an
4. Vergleiche PVGIS vs Google Solar Daten
5. Nutze präzisere Google-Daten für finales Angebot


FRAGEN?
-------
Die API-Dokumentation findest du hier:
https://developers.google.com/maps/documentation/solar
"""

print(__doc__)
