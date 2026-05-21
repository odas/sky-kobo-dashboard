import ephem
import math
import time
import threading
import requests
from flask import Flask, render_template_string
from datetime import datetime

app = Flask(__name__)

# ── Pune Airport Coordinates ──────────────────────────────
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

# ── Safe Cache Initialization ─────────────────────────────
_cache = {
    'data': {
        'weather': {'temp': '--', 'uv': '--', 'aqi': '--'},
        'sky': '',
        'now': 'Initializing...',
        'date': 'Loading date...'
    },
    'ts': 0
}
CACHE_TTL = 1800   # 30 minutes

# ── Astronomy helpers ─────────────────────────────────────

def make_observer():
    obs           = ephem.Observer()
    obs.lat       = LAT
    obs.lon       = LON
    obs.elevation = ELEV
    # Works across older Python environments flawlessly
    obs.date      = ephem.date(datetime.utcnow())
    return obs


def altaz_to_xy(alt_deg, az_deg, cx=300, cy=300, r=250):
    dist   = r * (1.0 - alt_deg / 90.0)
    az_rad = math.radians(az_deg)
    x      = cx + dist * math.sin(az_rad)
    y      = cy - dist * math.cos(az_rad)
    return round(x, 1), round(y, 1)


def mag_to_r(mag):
    """Significantly boosted radius sizes for e-ink visibility"""
    if mag < 0:    return 8.0
    if mag < 1.0:  return 6.5
    if mag < 1.5:  return 5.5
    if mag < 2.0:  return 4.5
    if mag < 2.5:  return 3.5
    return 2.5


def build_svg(obs):
    cx, cy, r = 300, 300, 255
    p = []

    sun     = ephem.Sun(obs)
    sun_alt = math.degrees(sun.alt)

    # High contrast sky canvas boundary (Black ring, clean White inside)
    p.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#fff" stroke="#000" stroke-width="3"/>')

    # Compass labels (Darker, slightly pulled out)
    for label, az in [('N', 0), ('E', 90), ('S', 180), ('W', 270)]:
        lx, ly = altaz_to_xy(0, az, cx, cy, r + 18)
        p.append(
            f'<text x="{lx}" y="{ly}" text-anchor="middle" '
            f'dominant-baseline="middle" fill="#000" '
            f'font-size="14" font-family="Georgia" font-weight="bold">{label}</text>'
        )

    if sun_alt > -6:
        # Daytime template state
        sunset = ephem.localtime(obs.next_setting(ephem.Sun())).strftime('%H:%M')
        p.append(
            f'<text x="{cx}" y="{cy - 25}" text-anchor="middle" '
            f'fill="#444" font-size="16" font-family="Georgia">Sky map clears at</text>'
        )
        p.append(
            f'<text x="{cx}" y="{cy + 15}" text-anchor="middle" '
            f'fill="#000" font-size="28" font-family="Georgia" font-weight="bold">{sunset}</text>'
        )
    else:
        # ── Stars (Inverted: Black on White) ─────────────────
        for name in STAR_NAMES:
            try:
                star = ephem.star(name)
                star.compute(obs)
                alt = math.degrees(star.alt)
                az  = math.degrees(star.az)
                if alt > 3:
                    x, y  = altaz_to_xy(alt, az, cx, cy, r)
                    dot_r = mag_to_r(star.mag)
                    
                    # Bold star plot
                    p.append(f'<circle cx="{x}" cy="{y}" r="{dot_r}" fill="#000"/>')
                    
                    # Larger, high-readability star labels
                    if star.mag < 1.6:
                        p.append(
                            f'<text x="{x + dot_r + 4}" y="{y + 4}" '
                            f'fill="#000" font-size="11" font-family="Georgia" font-weight="bold">{name}</text>'
                        )
            except Exception:
                pass

        # ── Planets ───────────────────────────────────────
        for name, Cls in PLANETS.items():
            try:
                planet = Cls(obs)
                planet.compute(obs)
                alt    = math.degrees(planet.alt)
                az     = math.degrees(planet.az)
                if alt > 3:
                    x, y = altaz_to_xy(alt, az, cx, cy, r)
                    # Outer Ringed point for planet layout distinction
                    p.append(f'<circle cx="{x}" cy="{y}" r="8" fill="#000"/>')
                    p.append(f'<circle cx="{x}" cy="{y}" r="11" fill="none" stroke="#000" stroke-width="2"/>')
                    p.append(
                        f'<text x="{x + 15}" y="{y + 5}" '
                        f'fill="#000" font-size="12" font-family="Georgia" '
                        f'font-weight="bold" font-style="italic">{name}</text>'
                    )
            except Exception:
                pass

        # ── Moon ──────────────────────────────────────────
        try:
            moon     = ephem.Moon(obs)
            moon.compute(obs)
            moon_alt = math.degrees(moon.alt)
            moon_az  = math.degrees(moon.az)
            phase    = round(moon.phase)
            if moon_alt > 3:
                x, y = altaz_to_xy(moon_alt, moon_az, cx, cy, r)
                p.append(f'<circle cx="{x}" cy="{y}" r="12" fill="#000"/>')
                p.append(
                    f'<text x="{x + 16}" y="{y + 5}" '
                    f'fill="#000" font-size="12" font-family="Georgia" font-weight="bold">Moon ({phase}%)</text>'
                )
            else:
                rise     = obs.next_rising(ephem.Moon())
                rise_str = ephem.localtime(rise).strftime('%H:%M')
                p.append(
                    f'<text x="{cx}" y="{cy + r - 25}" text-anchor="middle" '
                    f'fill="#333" font-size="12" font-family="Georgia" font-style="italic">Moon rises {rise_str}</text>'
                )
        except Exception:
            pass

    # Zenith marker crosshair
    p.append(f'<circle cx="{cx}" cy="{cy}" r="3" fill="#000"/>')

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
        return _cache['data']['weather']


# ── Refresh Logic ─────────────────────────────────────────

def refresh():
    obs     = make_observer()
    weather = fetch_weather()
    sky     = build_svg(obs)
    now     = datetime.now().strftime('%H:%M')
    date    = datetime.now().strftime('%a, %b %d')
    
    _cache['data'] = {'weather': weather, 'sky': sky, 'now': now, 'date': date}
    _cache['ts']   = time.time()
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Map refreshed.")


def background_refresh():
    while True:
        time.sleep(CACHE_TTL)
        try:
            refresh()
        except Exception as e:
            print(f"Error: {e}")


# ── HTML Template (Clean Medium Post Aesthetic) ───────────
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
  background:#fff; color:#000;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
  overflow:hidden;
}

.frame {
  width:100%; height:100%;
  position:absolute; top:0; left:0;
  -webkit-transform: rotate(180deg);
  transform: rotate(180deg);
  -webkit-transform-origin: 50% 50%;
  transform-origin: 50% 50%;
  padding: 20px; /* Reduced outer padding slightly to give content more room */
}

/* ── COMPACT HEADER PANEL (Tuned to match Medium layout) ── */
.header-panel {
  width: 100%;
  height: 90px; /* Dropped from 125px to reclaim sky space */
  border-bottom: 5px solid #000;
  background: #fff;
}

.table-layout {
  width: 100%;
  border-collapse: collapse;
}

.table-layout td {
  vertical-align: top;
}

/* Left side metrics block */
.left-block {
  width: 45%;
}
.temp-display {
  font-size: 46px; /* Scaled down slightly to fit the compact header height */
  font-weight: 900;
  line-height: 0.95;
  letter-spacing: -2px;
  margin-bottom: 4px;
  color: #000;
}
.sub-metrics {
  font-size: 13px;
  font-weight: 700; /* Pulled back slightly from 900 so large font pops more */
  color: #000;
  letter-spacing: 0.3px;
  -webkit-text-stroke: 0.1px #000; /* Lightened stroke to create elegant weight hierarchy */
}

/* Right side date/time block */
.right-block {
  width: 55%;
  text-align: right;
}
.date-display {
  font-size: 24px; /* Slightly more compact */
  font-weight: 900;
  letter-spacing: -0.5px;
  line-height: 1.0;
  margin-bottom: 4px;
  color: #000;
}
.time-display {
  font-size: 13px;
  font-weight: 700;
  color: #000;
  letter-spacing: 0.1px;
  -webkit-text-stroke: 0.1px #000; /* Cleans up small text anti-aliasing */
}

/* ── EXPANDED SKY CANVAS WRAPPER ────────────────────────── */
.sky-container {
  position: absolute;
  top: 115px; /* Moved up significantly from 165px to grab the empty space */
  bottom: 10px;
  left: 15px;
  right: 15px;
  display: block;
  text-align: center;
}

.sky-container svg {
  height: 100%; /* Pushes the circular chart to fill maximum available frame height */
  width: auto;
  margin: 0 auto;
}
</style>
</head>
<body>
<div class="frame">
  
  <div class="header-panel">
    <table class="table-layout">
      <tr>
        <td class="left-block">
          <div class="temp-display">{{ d.weather.temp }}°C</div>
          <div class="sub-metrics">UV {{ d.weather.uv }} &nbsp;·&nbsp; AQI {{ d.weather.aqi }}</div>
        </td>
        <td class="right-block">
          <div class="date-display">{{ d.date }}</div>
          <div class="time-display">Pune Airport &nbsp;·&nbsp; {{ d.now }}</div>
        </td>
      </tr>
    </table>
  </div>
  
  <div class="sky-container">
    {{ d.sky | safe }}
  </div>

</div>
</body>
</html>"""



# ── Startup ───────────────────────────────────────────────

if __name__ == '__main__':
    print("Building high-contrast sky map...")
    refresh()
    print("Ready.")
    threading.Thread(target=background_refresh, daemon=True).start()
    app.run(host='0.0.0.0', port=5001, debug=False)

    # ── Portfolio Data Config ─────────────────────────────────
MY_TOOLS = [
    {"name": "Instagram Automation Tool", "desc": "Python & SQLite backend managing automated customer/adopter DM workflows.", "url": "#"},
    {"name": "E-Ink Sky & Weather Analytics Canvas", "desc": "Data pipeline translating pyephem tracking calculations directly into Kobo-friendly legacy SVG vectors.", "url": "/"},
    # Add your other project links here!
]

PORTFOLIO_HTML = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Orpita Das · AI-Assisted Tools Portfolio</title>
    <style>
        body { font-family: -apple-system, sans-serif; background: #fafafa; color: #222; max-width: 600px; margin: 40px auto; padding: 20px; }
        h1 { font-size: 24px; margin-bottom: 5px; color: #000; }
        .subtitle { color: #666; margin-bottom: 30px; font-size: 14px; }
        .card { background: #fff; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; margin-bottom: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.02); }
        .card h2 { font-size: 18px; margin: 0 0 8px 0; }
        .card h2 a { color: #002b5c; text-decoration: none; }
        .card h2 a:hover { text-decoration: underline; }
        .card p { font-size: 14px; color: #555; line-height: 1.5; margin: 0; }
    </style>
</head>
<body>
    <h1>Project Engineering Showcase</h1>
    <div class="subtitle">A collection of custom utilities and automated systems.</div>
    
    {% for tool in tools %}
    <div class="card">
        <h2><a href="{{ tool.url }}" target="_blank">{{ tool.name }} &rarr;</a></h2>
        <p>{{ tool.desc }}</p>
    </div>
    {% endfor %}
</body>
</html>"""

# ── Routes ────────────────────────────────────────────────

# ── Safe Mock Fallback Object ─────────────────────────────
SAFE_FALLBACK = {
    'weather': {'temp': '--', 'uv': '--', 'aqi': '--'},
    'sky': '<svg viewBox="0 0 600 600" width="100%" xmlns="http://www.w3.org/2000/svg"><circle cx="300" cy="300" r="255" fill="#fff" stroke="#000" stroke-width="3"/><text x="300" y="300" text-anchor="middle" fill="#000">Loading Map Data...</text></svg>',
    'now': '--:--',
    'date': 'Refreshing...'
}

# ── Routes ────────────────────────────────────────────────

@app.route('/')
def dashboard():
    # 1. Grab current cache layer
    cached_data = _cache.get('data')
    
    # 2. Defend against 'None' type assignment crashes
    if not cached_data or cached_data.get('weather') is None:
        try:
            refresh()
            cached_data = _cache.get('data')
        except Exception:
            cached_data = SAFE_FALLBACK

    return render_template_string(HTML, d=cached_data)

@app.route('/portfolio')
def portfolio():
    return render_template_string(PORTFOLIO_HTML, tools=MY_TOOLS)