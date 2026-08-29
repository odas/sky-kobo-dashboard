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

## Running it for real

There is no cloud deploy. The Kobo reaches the app over local wifi at
`http://<mac-local-ip>:5002`, which is the whole point — no account, no cold
start, no dependency on anything outside the house.

pm2 keeps it up locally as `kobo-sky-5002` (see `~/dev/cockpit`).

The `Procfile` is kept because `gunicorn app:app --bind 0.0.0.0:$PORT` is still
the correct way to run this behind a real server, and `app.py` honours `$PORT`
either way. It is not currently wired to any host.

## Customise
- Change `LAT` / `LON` / `ELEV` for your location
- Add star names to `STAR_NAMES` (must be in the ephem catalogue)
- Adjust `CACHE_TTL` for refresh frequency — keep it in step with the
  `<meta http-equiv="refresh">` value in `HTML`
