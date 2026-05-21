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

# ── Safe Cache & Failsafe Definitions ─────────────────────
_cache = {
    'data': {
        'weather': {'temp': '--', 'uv': '--', 'aqi': '--'},
        'sky': '',
        'now': '--:--',
        'date': 'Refreshing...'
    },
    'ts': 0
}
CACHE_TTL = 1800   # 30 minutes

SAFE_FALLBACK = {
    'weather': {'temp': '--', 'uv': '--', 'aqi': '--'},
    'sky': '<svg viewBox="0 0 600 600" width="100%" xmlns="http://www.w3.org/2000/svg"><circle cx="300" cy="300" r="255" fill="#fff" stroke="#000" stroke-width="3"/><text x="300" y="300" text-anchor="middle" fill="#000" font-family="sans-serif" font-size="16" font-weight="bold">Loading Map Data...</text></svg>',
    'now': '--:--',
    'date': 'Refreshing...'
}

# ── Portfolio Data Config ─────────────────────────────────
MY_TOOLS = [
    {"name": "E-Ink Sky Canvas & Weather Dashboard", "desc": "A micro-data pipeline optimizing astronomical pyephem computations and Open-Meteo REST endpoints into declarative, ultra-low-power vector matrices tailored specifically for legacy WebKit firmware runtimes.", "url": "/"},
    {"name": "Instagram Automation Tool", "desc": "Python-based microservice orchestrating automated DM responses, utilizing SQLite metadata models for state preservation and high-fidelity operational tracking.", "url": "#"},
]

# ── Astronomy helpers ─────────────────────────────────────

def make_observer():
    obs           = ephem.Observer()
    obs.lat       = LAT
    obs.lon       = LON
    obs.elevation = ELEV
    obs.date      = ephem.date(datetime.utcnow())
    return obs


def altaz_to_xy(alt_deg, az_deg, cx=300, cy=300, r=250):
    dist   = r * (1.0 - alt_deg / 90.0)
    az_rad = math.radians(az_deg)
    x      = cx + dist * math.sin(az_rad)
    y      = cy - dist * math.cos(az_rad)
    return round(x, 1), round(y, 1)


def mag_to_r(mag):
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

    # High contrast sky canvas boundary
    p.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#fff" stroke="#000" stroke-width="3"/>')

    # Compass labels
    for label, az in [('N', 0), ('E', 90), ('S', 180), ('W', 270)]:
        lx, ly = altaz_to_xy(0, az, cx, cy, r + 18)
        p.append(
            f'<text x="{lx}" y="{ly}" text-anchor="middle" '
            f'dominant-baseline="middle" fill="#000" '
            f'font-size="14" font-family="Georgia" font-weight="bold">{label}</text>'
        )

    if sun_alt > -6:
        # 1. Get the raw UTC sunset time from ephem
        next_setting_utc = obs.next_setting(ephem.Sun()).datetime()
        
        # 2. Add 5 hours and 30 minutes to convert UTC to IST
        # (Using a simple timedelta so we don't have to import heavy timezone libraries)
        from datetime import timedelta
        sunset_ist = next_setting_utc + timedelta(hours=5, minutes=30)
        
        # 3. Format the local IST time string
        sunset_str = sunset_ist.strftime('%H:%M')
        
        p.append(
            f'<text x="{cx}" y="{cy - 25}" text-anchor="middle" '
            f'fill="#000" font-size="16" font-family="Georgia" font-weight="bold">Sky map clears at</text>'
        )
        p.append(
            f'<text x="{cx}" y="{cy + 15}" text-anchor="middle" '
            f'fill="#000" font-size="28" font-family="Georgia" font-weight="bold">{sunset_str}</text>'
        )

    else:
        # Stars
        for name in STAR_NAMES:
            try:
                star = ephem.star(name)
                star.compute(obs)
                alt = math.degrees(star.alt)
                az  = math.degrees(star.az)
                if alt > 3:
                    x, y  = altaz_to_xy(alt, az, cx, cy, r)
                    dot_r = mag_to_r(star.mag)
                    p.append(f'<circle cx="{x}" cy="{y}" r="{dot_r}" fill="#000"/>')
                    if star.mag < 1.6:
                        p.append(
                            f'<text x="{x + dot_r + 4}" y="{y + 4}" '
                            f'fill="#000" font-size="11" font-family="Georgia" font-weight="bold">{name}</text>'
                        )
            except Exception:
                pass

        # Planets
        for name, Cls in PLANETS.items():
            try:
                planet = Cls(obs)
                planet.compute(obs)
                alt    = math.degrees(planet.alt)
                az     = math.degrees(planet.az)
                if alt > 3:
                    x, y = altaz_to_xy(alt, az, cx, cy, r)
                    p.append(f'<circle cx="{x}" cy="{y}" r="8" fill="#000"/>')
                    p.append(f'<circle cx="{x}" cy="{y}" r="11" fill="none" stroke="#000" stroke-width="2"/>')
                    p.append(
                        f'<text x="{x + 15}" y="{y + 5}" '
                        f'fill="#000" font-size="12" font-family="Georgia" '
                        f'font-weight="bold" font-style="italic">{name}</text>'
                    )
            except Exception:
                pass

        # Moon
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
                    f'fill="#000" font-size="12" font-family="Georgia" font-style="italic" font-weight="bold">Moon rises {rise_str}</text>'
                )
        except Exception:
            pass

    # Zenith marker
    p.append(f'<circle cx="{cx}" cy="{cy}" r="3" fill="#000"/>')

    return (
        f'<svg viewBox="0 0 600 600" width="100%" '
        f'xmlns="http://www.w3.org/2000/svg">{"".join(p)}</svg>'
    )


# ── Isolated Weather Fetcher ──────────────────────────────

def fetch_weather():
    data = {'temp': '--', 'uv': '--', 'aqi': '--'}
    
    try:
        wx_url = f'https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}&current=temperature_2m,uv_index'
        wx = requests.get(wx_url, timeout=3).json()['current']
        data['temp'] = round(wx['temperature_2m'])
        data['uv'] = round(wx['uv_index'], 1)
    except Exception as e:
        print(f"Weather API unavailable: {e}")

    try:
        aqi_url = f'https://air-quality-api.open-meteo.com/v1/air-quality?latitude={LAT}&longitude={LON}&current=us_aqi'
        aqi = requests.get(aqi_url, timeout=3).json()['current']['us_aqi']
        data['aqi'] = round(aqi)
    except Exception as e:
        print(f"AQI API unavailable: {e}")

    return data


# ── Refresh Management ────────────────────────────────────

def refresh():
    try:
        obs = make_observer()
        sky = build_svg(obs)
    except Exception as e:
        print(f"Astro Engine failure: {e}")
        sky = SAFE_FALLBACK['sky']

    weather = fetch_weather()
    now  = datetime.now().strftime('%H:%M')
    date = datetime.now().strftime('%a, %b %d')
    
    _cache['data'] = {
        'weather': weather, 
        'sky': sky, 
        'now': now, 
        'date': date
    }
    _cache['ts'] = time.time()
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Map cache completely updated.")


def background_refresh():
    while True:
        time.sleep(CACHE_TTL)
        try:
            refresh()
        except Exception as e:
            print(f"Background thread runtime error: {e}")


# ── HTML Template Strings ─────────────────────────────────

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
  padding: 20px;
}
.header-panel {
  width: 100%;
  height: 90px;
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
.left-block {
  width: 45%;
}
.temp-display {
  font-size: 46px;
  font-weight: 900;
  line-height: 0.95;
  letter-spacing: -2px;
  margin-bottom: 4px;
  color: #000;
}
.sub-metrics {
  font-size: 13px;
  font-weight: 700;
  color: #000;
  letter-spacing: 0.3px;
  -webkit-text-stroke: 0.1px #000;
}
.right-block {
  width: 55%;
  text-align: right;
}
.date-display {
  font-size: 24px;
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
  -webkit-text-stroke: 0.1px #000;
}
.sky-container {
  position: absolute;
  top: 115px;
  bottom: 10px;
  left: 15px;
  right: 15px;
  display: block;
  text-align: center;
}
.sky-container svg {
  height: 100%;
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

PORTFOLIO_HTML = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Orpita Das · Portfolio</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #fafafa; color: #222; max-width: 600px; margin: 40px auto; padding: 20px; }
        h1 { font-size: 26px; margin-bottom: 5px; color: #000; letter-spacing: -0.5px; }
        .subtitle { color: #666; margin-bottom: 30px; font-size: 14px; }
        .card { background: #fff; padding: 22px; border-radius: 8px; border: 1px solid #e0e0e0; margin-bottom: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.01); }
        .card h2 { font-size: 18px; margin: 0 0 8px 0; }
        .card h2 a { color: #004b93; text-decoration: none; font-weight: 700; }
        .card h2 a:hover { text-decoration: underline; }
        .card p { font-size: 14px; color: #444; line-height: 1.5; margin: 0; }
    </style>
</head>
<body>
    <h1>Data Infrastructure & Automation Tools</h1>
    <div class="subtitle">A showcase of production-ready components and data services.</div>
    
    {% for tool in tools %}
    <div class="card">
        <h2><a href="{{ tool.url }}" target="_blank">{{ tool.name }} &rarr;</a></h2>
        <p>{{ tool.desc }}</p>
    </div>
    {% endfor %}
</body>
</html>"""

# ── Endpoints ─────────────────────────────────────────────

@app.route('/')
def dashboard():
    cached_data = _cache.get('data')
    if not cached_data or cached_data.get('sky') == '':
        try:
            refresh()
            cached_data = _cache.get('data')
        except Exception:
            cached_data = SAFE_FALLBACK
    return render_template_string(HTML, d=cached_data)


@app.route('/portfolio')
def portfolio():
    return render_template_string(PORTFOLIO_HTML, tools=MY_TOOLS)


# ── Entrypoint Execution ──────────────────────────────────

if __name__ == '__main__':
    print("Pre-rendering baseline sky grid coordinates...")
    refresh()
    print("Cache warm. Initializing background thread daemon...")
    threading.Thread(target=background_refresh, daemon=True).start()
    app.run(host='0.0.0.0', port=5001, debug=False)