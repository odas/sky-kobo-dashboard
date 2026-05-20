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
* { margin: 0; padding: 0; box-sizing: border-box; }

html, body {
  width: 100%;
  height: 100%;
  background: #000;
  color: #fff;
  font-family: Georgia, 'Times New Roman', serif;
  overflow: hidden;
}

/* ── THE 180 DEGREE FLIP ─────────────────────────────────────── */
/* Old Kobo WebKit versions require legacy hardware properties to rotate */
.frame {
  width: 100%;
  height: 100%;
  position: absolute;
  top: 0;
  left: 0;
  
  -webkit-transform: rotate(180deg);
  -moz-transform: rotate(180deg);
  -ms-transform: rotate(180deg);
  transform: rotate(180deg);
  
  /* Forces rendering engine to recalculate layout orientation */
  -webkit-transform-origin: 50% 50%;
  transform-origin: 50% 50%;
}

/* ── THE TEXT STRIP (FAILSAFE TABLE LAYOUT) ───────────────────── */
.strip {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 90px;
  padding: 12px 20px;
  border-bottom: 1px solid #222;
  background: #000;
  z-index: 10;
}

.date {
  font-size: 11px;
  letter-spacing: 3px;
  text-transform: uppercase;
  color: #a0a0a0;
  margin-bottom: 6px;
  display: block;
}

/* Replaced flexbox with old-school table-based columns for perfect spacing */
.weather-table {
  width: 100%;
  border-collapse: collapse;
  margin-bottom: 4px;
}

.weather-table td {
  vertical-align: bottom;
  white-space: nowrap;
}

.temp-col {
  font-size: 32px;
  font-weight: bold;
  letter-spacing: -1px;
  width: 20%; /* Hard bounds prevent overlapping */
}

.meta-col {
  font-size: 14px;
  color: #ccc;
  letter-spacing: 1px;
  padding-left: 15px;
  padding-bottom: 4px;
}

.refreshed {
  font-size: 9px;
  color: #555;
  letter-spacing: 2px;
  text-transform: uppercase;
  margin-top: 2px;
}

/* ── SKY SVG CANVAS ─────────────────────────────────────────── */
.sky {
  position: absolute;
  top: 90px; /* Sits perfectly below the strip */
  bottom: 0;
  left: 0;
  width: 100%;
  text-align: center;
  padding: 10px;
}

.sky svg {
  height: 95%;
  width: auto;
  margin: 0 auto;
  display: block;
}
</style>
</head>
<body>
<div class="frame">
  <div class="strip">
    <div class="date">Pune · {{ d.date }}</div>
    
    <table class="weather-table">
      <tr>
        <td class="temp-col">{{ d.weather.temp }}°C</td>
        <td class="meta-col">UV {{ d.weather.uv }}</td>
        <td class="meta-col">AQI {{ d.weather.aqi }}</td>
      </tr>
    </table>
    
    <div class="refreshed">Updated: {{ d.now }}</div>
  </div>
  
  <div class="sky">
    {{ d.sky | safe }}
  </div>
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