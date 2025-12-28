const express = require('express');
const path = require('path');
const compression = require('compression');

const app = express();
const PORT = process.env.PORT || 3000;

// Kompression für große HTML-Dateien
app.use(compression());

// Statische Dateien servieren
app.use(express.static(path.join(__dirname), {
    maxAge: '1h'
}));

// Fallback auf index.html
app.get('*', (req, res) => {
    res.sendFile(path.join(__dirname, 'index.html'));
});

app.listen(PORT, () => {
    console.log('Server läuft auf Port ' + PORT);
});
