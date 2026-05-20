# OD · Kobo Sky Dashboard

A real-time night sky map served to a Kobo Touch e-reader via its beta browser.
Built with Flask + PyEphem. Displays stars, planets, moon phase, weather and AQI.

## What it shows
- Current night sky visible from Pune, India
- Bright named stars positioned accurately by altitude/azimuth
- Planets (Mercury, Venus, Mars, Jupiter, Saturn) with ring markers
- Moon position and phase percentage
- Temperature, UV index, AQI (Open-Meteo, no API key needed)
- Rotated 180° for upside-down wall mounting

## How it works
- PyEphem calculates which stars/planets are above the horizon right now
- Altitude + azimuth converted to SVG x,y coordinates
- Flask serves one HTML page with the SVG embedded
- Kobo browser auto-refreshes every 30 minutes
- Background thread pre-caches data — page loads instantly

## Run locally
```bash
pip install -r requirements.txt
python app.py
# visit http://localhost:5001
# on Kobo: http://YOUR_MAC_LOCAL_IP:5001
```

## Deploy to Render.com
1. Push to GitHub
2. New Web Service on render.com → connect repo
3. Build command: `pip install -r requirements.txt`
4. Render automatically detects the configuration from the `Procfile` and builds the environment
5. Free tier — always on (refreshes keep it alive)

## Customise
- Change `LAT` / `LON` / `ELEV` for your location
- Add star names to `STAR_NAMES` list (must be in ephem catalogue)
- Adjust `CACHE_TTL` for refresh frequency
