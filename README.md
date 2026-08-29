# OD · Kobo Sky Dashboard

A real-time night sky map served to a Kobo Touch e-reader via its beta browser.
Built with Flask + PyEphem. Displays stars, planets, moon phase, weather and AQI.

## What it shows
- Current night sky visible from Pune, India
- Bright named stars positioned accurately by altitude/azimuth
- Planets (Mercury, Venus, Mars, Jupiter, Saturn) with ring markers
- Moon position and phase percentage
- Temperature and UV (wttr.in), AQI (Open-Meteo) — no API keys needed
- Rotated 180° for upside-down wall mounting

## How it works
- PyEphem calculates which stars/planets are above the horizon right now
- Altitude + azimuth converted to SVG x,y coordinates
- Flask serves one HTML page with the SVG embedded
- Kobo browser auto-refreshes every 30 minutes
- Background thread pre-caches data — page loads instantly
- Daytime shows a "sky map returns at HH:MM" card instead of an empty dome

## Run locally
```bash
pip install -r requirements.txt
python app.py
# visit http://localhost:5002
# on Kobo: http://YOUR_MAC_LOCAL_IP:5002
```

Port 5002 is this app's slot in the local fleet (`~/dev/cockpit/apps.json`).
`app.py` reads `$PORT` and falls back to 5002, which is what both pm2 and
Render pass in.

## Deploy to Render.com
1. Push to GitHub
2. New Web Service on render.com → connect repo
3. Build command: `pip install -r requirements.txt`
4. Render detects the start command from the `Procfile`
5. Free tier — note it sleeps after ~15 min with no **inbound** request. The
   internal refresh thread does not count as traffic, so the Kobo's 30-minute
   page load will usually hit a cold start (~30s). That is expected, not a bug.

## Customise
- Change `LAT` / `LON` / `ELEV` for your location
- Add star names to `STAR_NAMES` (must be in the ephem catalogue)
- Adjust `CACHE_TTL` for refresh frequency — keep it in step with the
  `<meta http-equiv="refresh">` value in `HTML`
