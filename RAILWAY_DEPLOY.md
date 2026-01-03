# Railway Deployment Instructions

## 🚀 Deploy to Railway

### Prerequisites
- Railway account (sign up at railway.app)
- Git repository

### Deployment Steps

1. **Connect Repository to Railway:**
   ```bash
   # Install Railway CLI (optional)
   npm install -g @railway/cli
   
   # Login to Railway
   railway login
   ```

2. **Deploy from GitHub:**
   - Go to railway.app
   - Click "Deploy from GitHub"  
   - Select this repository
   - Railway will auto-detect Node.js and deploy

3. **Manual Deployment:**
   ```bash
   # In project directory
   railway login
   railway create dortmund-pv-analysis
   railway up
   ```

### Environment Variables
No environment variables required - all data is included in the deployment.

### File Structure for Railway
```
/
├── package.json          # Dependencies & scripts
├── server.js             # Express server
├── railway.json          # Railway configuration
├── data/
│   └── final/
│       └── dortmund/
│           ├── complete_buildings_report.html
│           ├── buildings_map_all.html
│           ├── buildings_all_data.js
│           └── buildings_complete.json
```

### Post-Deployment
- Main app: `https://your-app.railway.app/`
- Interactive map: `https://your-app.railway.app/map`
- Health check: `https://your-app.railway.app/health`

### Performance Notes
- Large data files (~4.5MB JavaScript) - Railway handles this well
- Compression enabled for optimal loading
- Static file caching configured
- CDN integration for Leaflet maps

Railway will automatically build and deploy your PV analysis application! 🌟