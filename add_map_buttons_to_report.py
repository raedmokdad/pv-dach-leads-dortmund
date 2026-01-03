#!/usr/bin/env python3
import re

# Read the report file
report_path = r"C:\Users\r.mokdad\OneDrive\Raed\Firma\PV\pv-dach-leads-dortmund\data\final\dortmund\dortmund_leads_report_top500.html"

with open(report_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Pattern to find coordinates and add button
# Find pattern: Koordinaten:</th>\n<td>LAT, LON</td> followed by Karten section
pattern = r'(<tr>\s*<th>Koordinaten:</th>\s*<td>([\d.]+),\s*([\d.]+)</td>\s*</tr>\s*<tr>\s*<th>Karten:</th>\s*<td>.*?)(</td>\s*</tr>)'

def add_button(match):
    before = match.group(1)
    lat = match.group(2)
    lon = match.group(3)
    after = match.group(4)
    
    # Check if button already exists
    if '📍 Auf Karte zeigen' in before:
        return match.group(0)
    
    button = f'<a href="buildings_map_all.html?lat={lat}&lon={lon}" target="_blank" style="background: #667eea; color: white; padding: 5px 12px; border-radius: 5px; text-decoration: none; display: inline-block; font-weight: 600; margin-left: 10px;">📍 Auf Karte zeigen</a>'
    
    return before + button + after

# Apply replacement
new_content = re.sub(pattern, add_button, content, flags=re.DOTALL)

# Write back
with open(report_path, 'w', encoding='utf-8') as f:
    f.write(new_content)

print(f"✅ Buttons hinzugefügt zum Report!")
print(f"Anzahl der Änderungen: {content.count('TIM-online NRW')}")
