/**
 * Building Report Filter and Display Logic
 * Modular JavaScript for the filtered building report
 */

// ============================================================================
// Configuration
// ============================================================================

const ITEMS_PER_PAGE = 50;

// ============================================================================
// State Management
// ============================================================================

let allBuildings = [];
let filteredBuildings = [];
let currentPage = 0;
let roofSegmentsData = {};

// ============================================================================
// Initialization
// ============================================================================

function initializeReport(buildings, segments) {
    console.log('initializeReport called with', buildings?.length, 'buildings');
    allBuildings = buildings || [];
    filteredBuildings = buildings || [];
    roofSegmentsData = segments || {};
    
    // Initial render
    console.log('Rendering first', ITEMS_PER_PAGE, 'buildings');
    try {
        renderBuildings(filteredBuildings.slice(0, ITEMS_PER_PAGE));
        console.log('renderBuildings completed');
    } catch (e) {
        console.error('Error in renderBuildings:', e);
    }
    updateLoadMoreButton();
    updateResultCount(filteredBuildings.length);
    
    // Setup event listeners
    setupEventListeners();
    console.log('initializeReport completed');
}

function setupEventListeners() {
    document.getElementById('minArea')?.addEventListener('input', applyFilters);
    document.getElementById('maxArea')?.addEventListener('input', applyFilters);
    document.getElementById('minYield')?.addEventListener('input', applyFilters);
    document.getElementById('minPanels')?.addEventListener('input', applyFilters);
    document.getElementById('filterPvYes')?.addEventListener('change', applyFilters);
    document.getElementById('filterPvNo')?.addEventListener('change', applyFilters);
    document.getElementById('filterAgeYes')?.addEventListener('change', applyFilters);
    document.getElementById('filterAgeNo')?.addEventListener('change', applyFilters);
}

// ============================================================================
// Filtering Logic
// ============================================================================

function applyFilters() {
    const minArea = parseFloat(document.getElementById('minArea').value) || 0;
    const maxArea = parseFloat(document.getElementById('maxArea').value) || Infinity;
    const minYield = parseFloat(document.getElementById('minYield').value) || 0;
    const minPanels = parseFloat(document.getElementById('minPanels').value) || 0;
    const showPvYes = document.getElementById('filterPvYes').checked;
    const showPvNo = document.getElementById('filterPvNo').checked;
    const showAgeYes = document.getElementById('filterAgeYes').checked;
    const showAgeNo = document.getElementById('filterAgeNo').checked;
    
    filteredBuildings = allBuildings.filter(building => {
        const areaMatch = building.area >= minArea && building.area <= maxArea;
        const yieldMatch = (building.google_solar_yearly_kwh || 0) >= minYield;
        const panelsMatch = (building.google_solar_panels_max || 0) >= minPanels;
        const pvMatch = (building.has_pv && showPvYes) || (!building.has_pv && showPvNo);
        const hasAge = building.pv_min_age > 0;
        const ageMatch = (hasAge && showAgeYes) || (!hasAge && showAgeNo);
        return areaMatch && yieldMatch && panelsMatch && pvMatch && ageMatch;
    });
    
    // Reset pagination
    currentPage = 0;
    renderBuildings(filteredBuildings.slice(0, ITEMS_PER_PAGE));
    updateResultCount(filteredBuildings.length);
    updateLoadMoreButton();
}

function resetFilters() {
    const minAreaInput = document.getElementById('minArea');
    const maxAreaInput = document.getElementById('maxArea');
    
    if (minAreaInput && maxAreaInput) {
        const minArea = Math.min(...allBuildings.map(b => b.area || 0));
        const maxArea = Math.max(...allBuildings.map(b => b.area || 0));
        
        minAreaInput.value = Math.floor(minArea);
        maxAreaInput.value = Math.ceil(maxArea);
    }
    
    document.getElementById('minYield').value = 0;
    document.getElementById('minPanels').value = 0;
    document.getElementById('filterPvYes').checked = true;
    document.getElementById('filterPvNo').checked = true;
    document.getElementById('filterAgeYes').checked = true;
    document.getElementById('filterAgeNo').checked = true;
    
    applyFilters();
}

// ============================================================================
// Rendering Logic
// ============================================================================

function renderBuildings(buildings) {
    console.log('renderBuildings called with', buildings?.length, 'buildings');
    const grid = document.getElementById('buildingsGrid');
    const noResults = document.getElementById('noResults');
    const loadMoreContainer = document.getElementById('loadMoreContainer');
    
    console.log('Grid element:', grid);
    
    if (!grid) {
        console.error('buildingsGrid element not found!');
        return;
    }
    
    if (buildings.length === 0) {
        grid.style.display = 'none';
        noResults.style.display = 'block';
        loadMoreContainer.style.display = 'none';
        return;
    }
    
    grid.style.display = 'grid';
    noResults.style.display = 'none';
    
    try {
        const html = buildings.map(building => createBuildingCard(building)).join('');
        console.log('Generated HTML length:', html.length);
        grid.innerHTML = html;
        console.log('Grid innerHTML set successfully');
    } catch (e) {
        console.error('Error creating building cards:', e);
    }
}

function updateResultCount(count) {
    const resultCountEl = document.getElementById('resultCount');
    if (resultCountEl) {
        resultCountEl.textContent = count.toLocaleString('de-DE');
    }
}

function loadMore() {
    currentPage++;
    const start = currentPage * ITEMS_PER_PAGE;
    const end = start + ITEMS_PER_PAGE;
    const newBuildings = filteredBuildings.slice(start, end);
    
    // Append to existing grid
    const grid = document.getElementById('buildingsGrid');
    newBuildings.forEach(building => {
        const card = createBuildingCard(building);
        grid.insertAdjacentHTML('beforeend', card);
    });
    
    updateLoadMoreButton();
}

function updateLoadMoreButton() {
    const loadMoreBtn = document.getElementById('loadMoreBtn');
    const loadingInfo = document.getElementById('loadingInfo');
    const loadMoreContainer = document.getElementById('loadMoreContainer');
    const shown = Math.min((currentPage + 1) * ITEMS_PER_PAGE, filteredBuildings.length);
    const total = filteredBuildings.length;
    
    if (shown >= total) {
        loadMoreContainer.style.display = 'none';
    } else {
        loadMoreContainer.style.display = 'block';
        const remaining = total - shown;
        if (loadMoreBtn) {
            loadMoreBtn.textContent = `▼ Mehr laden (${Math.min(ITEMS_PER_PAGE, remaining)} weitere)`;
        }
        if (loadingInfo) {
            loadingInfo.textContent = `${shown} von ${total} Gebäuden angezeigt`;
        }
    }
}

// ============================================================================
// Building Card Rendering
// ============================================================================

function createBuildingCard(building) {
    const hasAge = building.pv_min_age > 0;
    const ageClass = hasAge ? ' has-age' : '';
    
    return `
        <div class="building-card${ageClass}" data-building-id="${building.id}">
            ${building.has_image 
                ? `<img src="luftbilder/${building.image_filename}" class="building-image" alt="Luftbild" loading="lazy">`
                : '<div class="no-image-placeholder">Kein Bild verfügbar</div>'
            }
            
            <div class="building-content">
                <div class="building-header">
                    <div class="building-name">${escapeHtml(building.name)}</div>
                    <div class="building-address">${escapeHtml(building.address)}</div>
                </div>
                
                <div class="building-details">
                    ${renderBasicDetails(building)}
                    ${renderPVDetails(building)}
                    ${renderSolarPotential(building)}
                    ${renderRoofSegments(building)}
                    ${renderEconomics(building)}
                </div>
                
                <div class="building-footer">
                    <a href="https://www.google.com/maps?q=${building.lat},${building.lon}" 
                       target="_blank" class="map-link">
                       📍 Google Maps
                    </a>
                    <a href="https://www.tim-online.nrw.de/tim-online2/?center=${building.lon},${building.lat}&scale=500" 
                       target="_blank" class="map-link">
                       🗺️ TIM-online NRW
                    </a>
                </div>
            </div>
        </div>
    `;
}

function renderBasicDetails(building) {
    return `
        <div class="detail-item">
            <span class="detail-label">Fläche</span>
            <span class="detail-value">${formatNumber(building.area)} m²</span>
        </div>
        
        <div class="detail-item">
            <span class="detail-label">PV-Status</span>
            <span class="pv-badge ${building.has_pv ? 'pv-yes' : 'pv-no'}">
                ${building.pv_status}
            </span>
        </div>
        
        <div class="detail-item">
            <span class="detail-label">Gebäudetyp</span>
            <span class="detail-value">${escapeHtml(building.building_type)}</span>
        </div>
        
        <div class="detail-item">
            <span class="detail-label">Landuse</span>
            <span class="detail-value">${escapeHtml(building.landuse)}</span>
        </div>
        
        <div class="detail-item">
            <span class="detail-label">Amenity</span>
            <span class="detail-value">${escapeHtml(building.amenity)}</span>
        </div>
        
        <div class="detail-item">
            <span class="detail-label">Kontakt</span>
            <span class="detail-value">${escapeHtml(building.contact)}</span>
        </div>
    `;
}

function renderPVDetails(building) {
    if (building.pv_count === 0) return '';
    
    return `
        <div class="detail-item">
            <span class="detail-label">PV Anlagen</span>
            <span class="detail-value">${building.pv_count}x</span>
        </div>
        
        <div class="detail-item">
            <span class="detail-label">Datenquelle</span>
            <span class="detail-value">${escapeHtml(building.pv_data_sources || 'Unbekannt')}</span>
        </div>
        
        ${building.pv_capacity_kwp > 0 ? `
            <div class="detail-item">
                <span class="detail-label">Kapazität</span>
                <span class="detail-value">${building.pv_capacity_kwp.toFixed(1)} kWp</span>
            </div>
        ` : ''}
        
        <div class="detail-item">
            <span class="detail-label">Anlagenalter</span>
            <span class="detail-value">${
                building.pv_min_age > 0 
                    ? (building.pv_min_age === building.pv_max_age 
                        ? building.pv_min_age + ' Jahre' 
                        : building.pv_min_age + '-' + building.pv_max_age + ' Jahre')
                    : 'Nicht verfügbar'
            }</span>
        </div>
    `;
}

function renderSolarPotential(building) {
    if (building.google_solar_available !== 'True' && building.pvgis_available !== 'True') {
        return '';
    }
    
    return `
        <div class="apis-container">
            ${building.google_solar_available === 'True' ? renderGoogleSolar(building) : ''}
            ${building.pvgis_yearly_kwh > 0 ? renderPVGIS(building) : ''}
        </div>
    `;
}

function renderGoogleSolar(building) {
    return `
        <div class="detail-section">
            <div class="section-header">☀️ Solar-Potenzial</div>
            
            ${building.google_solar_panels_max > 0 ? `
                <div class="detail-item">
                    <span class="detail-label">Max. Panels</span>
                    <span class="detail-value">${building.google_solar_panels_max}</span>
                </div>
            ` : ''}
            
            ${building.google_solar_area_m2 > 0 ? `
                <div class="detail-item">
                    <span class="detail-label">Nutzbare Fläche</span>
                    <span class="detail-value">${building.google_solar_area_m2.toFixed(1)} m²</span>
                </div>
            ` : ''}
            
            ${building.google_solar_yearly_kwh > 0 ? `
                <div class="detail-item">
                    <span class="detail-label">Jahresertrag</span>
                    <span class="detail-value">${formatNumber(building.google_solar_yearly_kwh)} kWh/Jahr</span>
                </div>
            ` : ''}
            
            ${building.google_solar_co2_offset_kg > 0 ? `
                <div class="detail-item">
                    <span class="detail-label">CO₂-Einsparung</span>
                    <span class="detail-value">${(building.google_solar_co2_offset_kg / 1000).toFixed(1)} t/Jahr</span>
                </div>
            ` : ''}
            
            ${building.main_roof_pitch > 0 ? `
                <div class="detail-item">
                    <span class="detail-label">🏠 Dachneigung</span>
                    <span class="detail-value">${building.main_roof_pitch}° (${getRoofType(building.main_roof_pitch)})</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">🧭 Ausrichtung</span>
                    <span class="detail-value">${building.main_roof_azimuth}° (${getAzimuthDirection(building.main_roof_azimuth)})</span>
                </div>
            ` : ''}
            
            ${building.google_solar_best_orientation ? `
                <div class="detail-item">
                    <span class="detail-label">Best. Ausrichtung</span>
                    <span class="detail-value">${escapeHtml(building.google_solar_best_orientation)}</span>
                </div>
            ` : ''}
            
            ${building.google_solar_sunshine_hours > 0 ? `
                <div class="detail-item">
                    <span class="detail-label">Sonnenstunden</span>
                    <span class="detail-value">${building.google_solar_sunshine_hours.toFixed(0)} h/Jahr</span>
                </div>
            ` : ''}
        </div>
    `;
}

function renderPVGIS(building) {
    return `
        <div class="detail-section">
            <div class="section-header">📊 PVGIS Simulation</div>
            
            <div class="detail-item">
                <span class="detail-label">Jahresertrag (PVGIS)</span>
                <span class="detail-value">${formatNumber(building.pvgis_yearly_kwh)} kWh/Jahr</span>
            </div>
            
            ${building.pvgis_optimal_angle > 0 ? `
                <div class="detail-item">
                    <span class="detail-label">Optimaler Neigungswinkel</span>
                    <span class="detail-value">${building.pvgis_optimal_angle}°</span>
                </div>
            ` : ''}
            
            ${building.pvgis_optimal_azimuth >= 0 ? `
                <div class="detail-item">
                    <span class="detail-label">Optimaler Azimut</span>
                    <span class="detail-value">${building.pvgis_optimal_azimuth}°</span>
                </div>
            ` : ''}
            
            ${building.pvgis_system_loss > 0 ? `
                <div class="detail-item">
                    <span class="detail-label">Systemverluste</span>
                    <span class="detail-value">${building.pvgis_system_loss}%</span>
                </div>
            ` : ''}
        </div>
    `;
}

function renderRoofSegments(building) {
    if (!building.has_roof_segments) return '';
    
    return `
        <div class="detail-section full-width segments-accordion" data-building-id="${building.lat}_${building.lon}">
            <div class="section-header accordion-toggle" onclick="loadRoofSegments(this.parentElement)">
                <span>🏠 Dach-Segmente & Panel-Platzierung (${building.segment_count} Segmente)</span>
                <span class="accordion-icon">▼</span>
            </div>
            <div class="accordion-content">
                <div class="roof-segments">
                    <div class="loading-segments">Klicken zum Laden der Segmente...</div>
                </div>
            </div>
        </div>
    `;
}

function renderEconomics(building) {
    if (building.roi_20_years_percent <= 0) return '';
    
    return `
        <div class="detail-section full-width">
            <div class="section-header">💰 Wirtschaftlichkeit</div>
            
            <div class="detail-item">
                <span class="detail-label">ROI (20 Jahre)</span>
                <span class="detail-value">${building.roi_20_years_percent.toFixed(1)}%</span>
            </div>
            
            ${building.payback_years > 0 ? `
                <div class="detail-item">
                    <span class="detail-label">Amortisation</span>
                    <span class="detail-value">${building.payback_years.toFixed(1)} Jahre</span>
                </div>
            ` : ''}
            
            ${building.estimated_savings_eur > 0 ? `
                <div class="detail-item">
                    <span class="detail-label">Einsparung</span>
                    <span class="detail-value">${formatNumber(building.estimated_savings_eur)} €/Jahr</span>
                </div>
            ` : ''}
            
            ${building.estimated_cost_eur > 0 ? `
                <div class="detail-item">
                    <span class="detail-label">Geschätzte Kosten</span>
                    <span class="detail-value">${formatNumber(building.estimated_cost_eur)} €</span>
                </div>
            ` : ''}
            
            ${building.total_score > 0 ? `
                <div class="detail-item">
                    <span class="detail-label">Score</span>
                    <span class="detail-value">${building.total_score.toFixed(0)} / 100</span>
                </div>
            ` : ''}
            
            ${building.priority ? `
                <div class="detail-item">
                    <span class="detail-label">Priorität</span>
                    <span class="detail-value">${escapeHtml(building.priority)}</span>
                </div>
            ` : ''}
        </div>
    `;
}

// ============================================================================
// Roof Segments Logic
// ============================================================================

function loadRoofSegments(accordionElement) {
    // Toggle accordion
    accordionElement.classList.toggle('expanded');
    
    // If collapsing, do nothing more
    if (!accordionElement.classList.contains('expanded')) {
        return;
    }
    
    const roofSegmentsContainer = accordionElement.querySelector('.roof-segments');
    
    // If already loaded, don't reload
    if (roofSegmentsContainer.dataset.loaded === 'true') {
        return;
    }
    
    // Find building by ID
    const card = accordionElement.closest('.building-card');
    const buildingId = card.dataset.buildingId;
    
    const segments = roofSegmentsData[buildingId]?.segments || [];
    
    if (segments.length === 0) {
        roofSegmentsContainer.innerHTML = '<div class="loading-segments">Keine Segmente verfügbar</div>';
        return;
    }
    
    // Render segments
    roofSegmentsContainer.innerHTML = segments.map((segment, idx) => `
        <div class="roof-segment">
            <div class="segment-header">Segment ${idx + 1}</div>
            <div class="segment-details">
                <div class="detail-item">
                    <span class="detail-label">Neigung</span>
                    <span class="detail-value">${segment.pitch}°</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">Azimut</span>
                    <span class="detail-value">${segment.azimuth}° (${getAzimuthDirection(segment.azimuth)})</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">Fläche</span>
                    <span class="detail-value">${segment.area} m²</span>
                </div>
            </div>
        </div>
    `).join('');
    
    roofSegmentsContainer.dataset.loaded = 'true';
}

// ============================================================================
// Utility Functions
// ============================================================================

function escapeHtml(text) {
    if (text == null) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatNumber(num) {
    if (num == null || isNaN(num)) return '0';
    return parseFloat(num).toLocaleString('de-DE', {
        minimumFractionDigits: 0,
        maximumFractionDigits: 0
    });
}

function getRoofType(pitch) {
    if (pitch < 10) return 'Flachdach';
    if (pitch < 25) return 'Flach geneigt';
    if (pitch < 40) return 'Optimal';
    return 'Steil';
}

function getAzimuthDirection(azimuth) {
    if (azimuth >= 337.5 || azimuth < 22.5) return 'N';
    if (azimuth >= 22.5 && azimuth < 67.5) return 'NO';
    if (azimuth >= 67.5 && azimuth < 112.5) return 'O';
    if (azimuth >= 112.5 && azimuth < 157.5) return 'SO';
    if (azimuth >= 157.5 && azimuth < 202.5) return 'S';
    if (azimuth >= 202.5 && azimuth < 247.5) return 'SW';
    if (azimuth >= 247.5 && azimuth < 292.5) return 'W';
    return 'NW';
}

// ============================================================================
// Global Functions (for onclick handlers)
// ============================================================================

window.applyFilters = applyFilters;
window.resetFilters = resetFilters;
window.loadMore = loadMore;
window.loadRoofSegments = loadRoofSegments;

