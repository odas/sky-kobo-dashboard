import ephem
import math
import time
import threading
import requests
from flask import Flask, render_template_string
from datetime import datetime

app = Flask(__name__)

# ── Pune Airport ──────────────────────────────────────────
LAT   = '18.5793'
LON   = '73.9089'
ELEV  = 559        # metres

# ── Bright named stars (ephem catalogue) ─────────────────
STAR_NAMES = [
    'Sirius', 'Canopus', 'Arcturus', 'Vega', 'Capella',
    'Rigel', 'Procyon', 'Achernar', 'Betelgeuse', 'Aldebaran',
    'Spica', 'Antares', 'Pollux', 'Fomalhaut', 'Deneb',
    'Regulus', 'Adhara', 'Castor', 'Shaula', 'Bellatrix',
    'Elnath', 'Alioth', 'Dubhe', 'Mirfak', 'Wezen',
]

PLANETS = {
    'Mercury': ephem.Mercury,
    'Venus':   ephem.Venus,
    'Mars':    ephem.Mars,
    'Jupiter': ephem.Jupiter,
    'Saturn':  ephem.Saturn,
}

# ── Cache ─────────────────────────────────────────────────
_cache   = {'data': None, 'ts': 0}
CACHE_TTL = 1800   # 30 minutes


# ── Astronomy helpers ─────────────────────────────────────

def make_observer():
    obs           = ephem.Observer()
    obs.lat       = LAT
    obs.lon       = LON
    obs.elevation = ELEV
    obs.date      = ephem.now()
    return obs


def altaz_to_xy(alt_deg, az_deg, cx=300, cy=300, r=260):
    """
    Map sky position to SVG pixel.
    Zenith (alt=90) → centre of circle.
    Horizon (alt=0) → edge of circle.
    Azimuth 0=North, clockwise.
    """
    dist   = r * (1.0 - alt_deg / 90.0)
    az_rad = math.radians(az_deg)
    x      = cx + dist * math.sin(az_rad)
    y      = cy - dist * math.cos(az_rad)
    return round(x, 1), round(y, 1)


def mag_to_r(mag):
    """Star apparent magnitude → SVG dot radius. Brighter = bigger."""
    if mag < 0:    return 4.5
    if mag < 1.0:  return 3.5
    if mag < 1.5:  return 3.0
    if mag < 2.0:  return 2.5
    if mag < 2.5:  return 2.0
    if mag < 3.0:  return 1.5
    return 1.0


def build_svg(obs):
    cx, cy, r = 300, 300, 268
    p = []   # SVG parts list

    # ── Check if sun is up ────────────────────────────────
    sun     = ephem.Sun(obs)
    sun_alt = math.degrees(sun.alt)

    # Sky background circle
    p.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#000" stroke="#222" stroke-width="1"/>')

    # Compass labels
    for label, az in [('N', 0), ('E', 90), ('S', 180), ('W', 270)]:
        lx, ly = altaz_to_xy(0, az, cx, cy, r + 14)
        p.append(
            f'<text x="{lx}" y="{ly}" text-anchor="middle" '
            f'dominant-baseline="middle" fill="#555" '
            f'font-size="10" font-family="Georgia">{label}</text>'
        )

    if sun_alt > -6:
        # Twilight or daytime — stars not visible
        sunset = ephem.localtime(obs.next_setting(ephem.Sun())).strftime('%H:%M')
        p.append(
            f'<text x="{cx}" y="{cy - 20}" text-anchor="middle" '
            f'fill="#666" font-size="13" font-family="Georgia">Sky visible after</text>'
        )
        p.append(
            f'<text x="{cx}" y="{cy + 10}" text-anchor="middle" '
            f'fill="#aaa" font-size="22" font-family="Georgia" font-weight="bold">{sunset}</text>'
        )
    else:
        # ── Stars ─────────────────────────────────────────
        for name in STAR_NAMES:
            try:
                star = ephem.star(name)
                star.compute(obs)
                alt = math.degrees(star.alt)
                az  = math.degrees(star.az)
                if alt > 3:
                    x, y  = altaz_to_xy(alt, az, cx, cy, r)
                    dot_r = mag_to_r(star.mag)
                    p.append(f'<circle cx="{x}" cy="{y}" r="{dot_r}" fill="#fff"/>')
                    if star.mag < 1.2:   # label only the very brightest
                        p.append(
                            f'<text x="{x + dot_r + 3}" y="{y + 3}" '
                            f'fill="#888" font-size="8" font-family="Georgia">{name}</text>'
                        )
            except Exception:
                pass

        # ── Planets ───────────────────────────────────────
        for name, Cls in PLANETS.items():
            try:
                planet = Cls(obs)
                alt    = math.degrees(planet.alt)
                az     = math.degrees(planet.az)
                if alt > 3:
                    x, y = altaz_to_xy(alt, az, cx, cy, r)
                    # ringed dot for planets
                    p.append(f'<circle cx="{x}" cy="{y}" r="5" fill="#fff"/>')
                    p.append(f'<circle cx="{x}" cy="{y}" r="7" fill="none" stroke="#fff" stroke-width="1"/>')
                    p.append(
                        f'<text x="{x + 10}" y="{y + 3}" '
                        f'fill="#ddd" font-size="9" font-family="Georgia" '
                        f'font-style="italic">{name}</text>'
                    )
            except Exception:
                pass

        # ── Moon ──────────────────────────────────────────
        try:
            moon     = ephem.Moon(obs)
            moon_alt = math.degrees(moon.alt)
            moon_az  = math.degrees(moon.az)
            phase    = round(moon.phase)
            if moon_alt > 3:
                x, y = altaz_to_xy(moon_alt, moon_az, cx, cy, r)
                p.append(f'<circle cx="{x}" cy="{y}" r="9" fill="#ccc"/>')
                p.append(
                    f'<text x="{x + 13}" y="{y + 3}" '
                    f'fill="#ccc" font-size="9" font-family="Georgia">Moon {phase}%</text>'
                )
            else:
                rise     = obs.next_rising(ephem.Moon())
                rise_str = ephem.localtime(rise).strftime('%H:%M')
                p.append(
                    f'<text x="{cx}" y="{cy + r - 18}" text-anchor="middle" '
                    f'fill="#444" font-size="9" font-family="Georgia">Moon rises {rise_str}</text>'
                )
        except Exception:
            pass

    # Zenith marker
    p.append(f'<circle cx="{cx}" cy="{cy}" r="2" fill="#333"/>')

    return (
        f'<svg viewBox="0 0 600 600" width="100%" '
        f'xmlns="http://www.w3.org/2000/svg">{"".join(p)}</svg>'
    )


# ── Weather ───────────────────────────────────────────────

def fetch_weather():
    try:
        wx = requests.get(
            f'https://api.open-meteo.com/v1/forecast'
            f'?latitude={LAT}&longitude={LON}'
            f'&current=temperature_2m,uv_index',
            timeout=5
        ).json()['current']
        aqi = requests.get(
            f'https://air-quality-api.open-meteo.com/v1/air-quality'
            f'?latitude={LAT}&longitude={LON}&current=us_aqi',
            timeout=5
        ).json()['current']['us_aqi']
        return {'temp': round(wx['temperature_2m']), 'uv': round(wx['uv_index'], 1), 'aqi': round(aqi)}
    except Exception:
        return _cache['data']['weather'] if _cache['data'] else {'temp': 'N/A', 'uv': 'N/A', 'aqi': 'N/A'}


# ── Refresh ───────────────────────────────────────────────

def refresh():
    obs     = make_observer()
    weather = fetch_weather()
    sky     = build_svg(obs)
    now     = datetime.now().strftime('%d %b  %H:%M')
    date    = datetime.now().strftime('%A, %d %B')
    _cache['data'] = {'weather': weather, 'sky': sky, 'now': now, 'date': date}
    _cache['ts']   = time.time()
    print(f"[{now}] Cache refreshed.")


def background_refresh():
    while True:
        time.sleep(CACHE_TTL)
        refresh()


# ── HTML template ─────────────────────────────────────────

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
<meta http-equiv="refresh" content="1800">
<title>OD · Sky</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
html, body {
  width:100%; height:100%;
  background:#000; color:#fff;
  font-family: Georgia, 'Times New Roman', serif;
  overflow:hidden;
}
.frame {
  width:100%; height:100%;
  transform: rotate(180deg);
  transform-origin: 50% 50%;
  display:-webkit-flex; display:flex;
  -webkit-flex-direction:column; flex-direction:column;
}
.strip {
  -webkit-flex-shrink:0; flex-shrink:0;
  padding: 10px 18px 8px;
  border-bottom: 1px solid #222;
}
.date {
  font-size:10px; letter-spacing:3px;
  text-transform:uppercase; color:#555;
  margin-bottom:5px;
}
.weather-row {
  display:-webkit-flex; display:flex;
  gap:18px; -webkit-align-items:baseline; align-items:baseline;
}
.temp { font-size:30px; font-weight:bold; letter-spacing:-1px; }
.meta { font-size:12px; color:#666; letter-spacing:1px; }
.refreshed { font-size:8px; color:#333; letter-spacing:2px; margin-top:5px; text-transform:uppercase; }
.sky {
  -webkit-flex:1; flex:1;
  display:-webkit-flex; display:flex;
  -webkit-align-items:center; align-items:center;
  -webkit-justify-content:center; justify-content:center;
  padding:6px;
  overflow:hidden;
}
</style>
</head>
<body>
<div class="frame">
  <div class="strip">
    <div class="date">Pune · {{ d.date }}</div>
    <div class="weather-row">
      <span class="temp">{{ d.weather.temp }}°C</span>
      <span class="meta">UV {{ d.weather.uv }}</span>
      <span class="meta">AQI {{ d.weather.aqi }}</span>
    </div>
    <div class="refreshed">{{ d.now }}</div>
  </div>
  <div class="sky">{{ d.sky | safe }}</div>
</div>
</body>
</html>"""


# ── Routes ────────────────────────────────────────────────

@app.route('/')
def dashboard():
    return render_template_string(HTML, d=_cache['data'])


# ── Startup ───────────────────────────────────────────────

if __name__ == '__main__':
    print("Building sky map...")
    refresh()
    print("Ready.")
    threading.Thread(target=background_refresh, daemon=True).start()
    app.run(host='0.0.0.0', port=5001, debug=False)
