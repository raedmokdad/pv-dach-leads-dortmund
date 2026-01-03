const express = require('express');
const path = require('path');
const compression = require('compression');

const app = express();
const PORT = process.env.PORT || 3000;

// Kompression für große Dateien
app.use(compression());

// Security headers
app.use((req, res, next) => {
    res.setHeader('X-Content-Type-Options', 'nosniff');
    res.setHeader('X-Frame-Options', 'DENY');
    res.setHeader('X-XSS-Protection', '1; mode=block');
    next();
});

// Statische Dateien servieren
app.use(express.static(path.join(__dirname), {
    maxAge: '1d' // Cache für 1 Tag
}));

// Hauptroute - Report
app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'index.html'));
});

// Karten-Route
app.get('/map', (req, res) => {
    res.sendFile(path.join(__dirname, 'buildings_map_all.html'));
});

// API für Gebäudedaten
app.get('/api/buildings', (req, res) => {
    res.sendFile(path.join(__dirname, 'buildings_complete.json'));
});

// Health Check
app.get('/health', (req, res) => {
    res.json({
        status: 'healthy',
        timestamp: new Date().toISOString(),
        buildings: '5201',
        version: '1.0.0'
    });
});

// Fallback
app.get('*', (req, res) => {
    res.sendFile(path.join(__dirname, 'index.html'));
});

app.listen(PORT, () => {
    console.log(`🚀 PV Analysis Server läuft auf Port ${PORT}`);
    console.log(`📊 Hauptreport: http://localhost:${PORT}/`);
    console.log(`🗺️ Interaktive Karte: http://localhost:${PORT}/map`);
});