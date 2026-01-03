const express = require('express');
const compression = require('compression');
const helmet = require('helmet');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 3000;

// Security and compression middleware
app.use(helmet({
    contentSecurityPolicy: {
        directives: {
            defaultSrc: ["'self'"],
            styleSrc: ["'self'", "'unsafe-inline'", "https://unpkg.com"],
            scriptSrc: ["'self'", "'unsafe-inline'", "https://unpkg.com"],
            imgSrc: ["'self'", "data:", "https:"],
            connectSrc: ["'self'", "https:"]
        }
    }
}));
app.use(compression());

// Serve static files from data/final/dortmund directory
app.use(express.static(path.join(__dirname, 'data/final/dortmund'), {
    maxAge: '1d', // Cache static files for 1 day
    etag: true
}));

// Serve other static assets
app.use('/assets', express.static(path.join(__dirname, 'data/final/dortmund'), {
    maxAge: '7d' // Cache assets for 7 days
}));

// Main route - serve the complete report
app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'data/final/dortmund/complete_buildings_report.html'));
});

// Map route - serve the interactive map
app.get('/map', (req, res) => {
    res.sendFile(path.join(__dirname, 'data/final/dortmund/buildings_map_all.html'));
});

// API endpoint for building data (if needed)
app.get('/api/buildings', (req, res) => {
    res.sendFile(path.join(__dirname, 'data/final/dortmund/buildings_complete.json'));
});

// Health check endpoint
app.get('/health', (req, res) => {
    res.json({
        status: 'healthy',
        timestamp: new Date().toISOString(),
        version: '1.0.0'
    });
});

// 404 handler
app.use('*', (req, res) => {
    res.status(404).sendFile(path.join(__dirname, 'data/final/dortmund/complete_buildings_report.html'));
});

// Error handler
app.use((err, req, res, next) => {
    console.error('Error:', err);
    res.status(500).json({
        error: 'Internal Server Error',
        message: process.env.NODE_ENV === 'development' ? err.message : 'Something went wrong'
    });
});

app.listen(PORT, () => {
    console.log(`🚀 Dortmund PV Analysis Server running on port ${PORT}`);
    console.log(`📊 Main Report: http://localhost:${PORT}/`);
    console.log(`🗺️  Interactive Map: http://localhost:${PORT}/map`);
    console.log(`💚 Health Check: http://localhost:${PORT}/health`);
});