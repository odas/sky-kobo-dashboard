import ephem
import math
import time
import threading
import requests
from flask import Flask, render_template_string
from datetime import datetime, timedelta

app = Flask(__name__)

# ── Location ───────────────────────────────────────────────
LAT  = '18.5793'
LON  = '73.9089'
ELEV = 559          # metres above sea level
IST  = timedelta(hours=5, minutes=30)   # UTC offset for IST

# ── Stars ──────────────────────────────────────────────────
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

# ── Cache ──────────────────────────────────────────────────
FALLBACK_SVG = (
    '<svg viewBox="0 0 600 600" width="100%" xmlns="http://www.w3.org/2000/svg">'
    '<circle cx="300" cy="300" r="270" fill="#000"/>'
    '<text x="300" y="305" text-anchor="middle" fill="#aaa" '
    'font-size="18" font-family="Georgia">Loading sky...</text>'
    '</svg>'
)
_cache = {
    'data': {
        'weather': {'temp': '--', 'uv': '--', 'aqi': '--'},
        'sky': FALLBACK_SVG,
        'now': '--:--',
        'date': '...',
    },
    'ts': 0,
}
CACHE_TTL = 1800


# ── Astronomy ──────────────────────────────────────────────

def make_observer():
    obs           = ephem.Observer()
    obs.lat       = LAT
    obs.lon       = LON
    obs.elevation = ELEV
    obs.date      = ephem.date(datetime.utcnow())   # not deprecated
    return obs


def altaz_to_xy(alt_deg, az_deg, cx=300, cy=300, r=255):
    """Zenith→centre, horizon→edge. Azimuth clockwise from North."""
    dist   = r * (1.0 - alt_deg / 90.0)
    az_rad = math.radians(az_deg)
    x      = cx + dist * math.sin(az_rad)
    y      = cy - dist * math.cos(az_rad)
    return round(x, 1), round(y, 1)


def mag_to_r(mag):
    """Apparent magnitude → dot radius. Brighter star = bigger dot."""
    if mag < 0:    return 7.0
    if mag < 1.0:  return 6.0
    if mag < 1.5:  return 5.0
    if mag < 2.0:  return 4.0
    if mag < 2.5:  return 3.0
    return 2.0


def build_svg(obs):
    cx, cy, r = 300, 300, 258
    p = []

    # black sky circle
    p.append(
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#000" '
        f'stroke="#444" stroke-width="1"/>'
    )

    # compass labels (dim, don't distract)
    for label, az in [('N', 0), ('E', 90), ('S', 180), ('W', 270)]:
        lx, ly = altaz_to_xy(0, az, cx, cy, r + 16)
        p.append(
            f'<text x="{lx}" y="{ly}" text-anchor="middle" '
            f'dominant-baseline="middle" fill="#777" '
            f'font-size="13" font-family="Georgia">{label}</text>'
        )

    # check if sun is up (twilight = sun alt > -6°)
    sun     = ephem.Sun(obs)
    sun_alt = math.degrees(sun.alt)

    if sun_alt > -6:
        # daytime — show when sky returns
        next_set_utc = obs.next_setting(ephem.Sun()).datetime()
        sunset_ist   = next_set_utc + IST
        sunset_str   = sunset_ist.strftime('%H:%M')
        p.append(
            f'<text x="{cx}" y="{cy - 20}" text-anchor="middle" '
            f'fill="#888" font-size="15" font-family="Georgia">Sky map returns at</text>'
        )
        p.append(
            f'<text x="{cx}" y="{cy + 20}" text-anchor="middle" '
            f'fill="#fff" font-size="34" font-family="Georgia" font-weight="bold">'
            f'{sunset_str}</text>'
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
                    if star.mag < 1.4:
                        p.append(
                            f'<text x="{x + dot_r + 4}" y="{y + 4}" '
                            f'fill="#ccc" font-size="11" font-family="Georgia" '
                            f'font-weight="bold">{name}</text>'
                        )
            except Exception:
                pass

        # ── Planets ───────────────────────────────────────
        for name, Cls in PLANETS.items():
            try:
                planet = Cls(obs)
                planet.compute(obs)
                alt = math.degrees(planet.alt)
                az  = math.degrees(planet.az)
                if alt > 3:
                    x, y = altaz_to_xy(alt, az, cx, cy, r)
                    p.append(f'<circle cx="{x}" cy="{y}" r="7" fill="#fff"/>')
                    p.append(
                        f'<circle cx="{x}" cy="{y}" r="10" fill="none" '
                        f'stroke="#fff" stroke-width="1.5"/>'
                    )
                    p.append(
                        f'<text x="{x + 14}" y="{y + 5}" '
                        f'fill="#ddd" font-size="11" font-family="Georgia" '
                        f'font-weight="bold" font-style="italic">{name}</text>'
                    )
            except Exception:
                pass

        # ── Moon ──────────────────────────────────────────
        try:
            moon = ephem.Moon(obs)
            moon.compute(obs)
            moon_alt = math.degrees(moon.alt)
            moon_az  = math.degrees(moon.az)
            phase    = round(moon.phase)
            if moon_alt > 3:
                x, y = altaz_to_xy(moon_alt, moon_az, cx, cy, r)
                p.append(f'<circle cx="{x}" cy="{y}" r="11" fill="#ddd"/>')
                p.append(
                    f'<text x="{x + 15}" y="{y + 5}" '
                    f'fill="#ddd" font-size="11" font-family="Georgia" '
                    f'font-weight="bold">Moon {phase}%</text>'
                )
            else:
                # moon below horizon — show rise time in IST
                next_rise_utc = obs.next_rising(ephem.Moon()).datetime()
                rise_ist      = next_rise_utc + IST
                rise_str      = rise_ist.strftime('%H:%M')
                p.append(
                    f'<text x="{cx}" y="{cy + r - 22}" text-anchor="middle" '
                    f'fill="#666" font-size="11" font-family="Georgia" '
                    f'font-style="italic">Moon rises {rise_str}</text>'
                )
        except Exception:
            pass

    # zenith dot
    p.append(f'<circle cx="{cx}" cy="{cy}" r="2" fill="#555"/>')

    return (
        f'<svg viewBox="0 0 600 600" width="100%" '
        f'xmlns="http://www.w3.org/2000/svg">{"".join(p)}</svg>'
    )


# ── Weather ────────────────────────────────────────────────

def fetch_weather():
    data = {"temp": "--", "uv": "--", "aqi": "--"}

    # temperature — current is valid for temperature_2m
    try:
        resp = requests.get(
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={LAT}&longitude={LON}"
            f"&current=temperature_2m",
            timeout=4
        ).json()
        data["temp"] = round(resp["current"]["temperature_2m"])
    except Exception as e:
        print(f"Temp error: {e}")

    # uv_index — only available as daily max, not current
    try:
        resp_uv = requests.get(
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={LAT}&longitude={LON}"
            f"&daily=uv_index_max&forecast_days=1&timezone=Asia/Kolkata",
            timeout=4
        ).json()
        data["uv"] = round(resp_uv["daily"]["uv_index_max"][0], 1)
    except Exception as e:
        print(f"UV error: {e}")

    # AQI
    try:
        resp_aqi = requests.get(
            f"https://air-quality-api.open-meteo.com/v1/air-quality"
            f"?latitude={LAT}&longitude={LON}&current=us_aqi",
            timeout=4
        ).json()
        data["aqi"] = round(resp_aqi["current"]["us_aqi"])
    except Exception as e:
        print(f"AQI error: {e}")

    return data


# ── Refresh ────────────────────────────────────────────────

def refresh():
    try:
        obs = make_observer()
        sky = build_svg(obs)
    except Exception as e:
        print(f"Sky error: {e}")
        sky = FALLBACK_SVG

    # IST time for display (works regardless of server timezone)
    now_ist  = datetime.utcnow() + IST
    _cache['data'] = {
        'weather': fetch_weather(),
        'sky':     sky,
        'now':     now_ist.strftime('%H:%M'),
        'date':    now_ist.strftime('%a %d %b'),
    }
    _cache['ts'] = time.time()
    print(f"[{now_ist.strftime('%H:%M')}] Refreshed.")


def background_refresh():
    while True:
        time.sleep(CACHE_TTL)
        try:
            refresh()
        except Exception as e:
            print(f"Background error: {e}")


# ── HTML ───────────────────────────────────────────────────
# Uses HTML table for header (universal browser support, no flexbox needed)
# Uses position:absolute for sky (avoids flex on old Kobo WebKit)
# Uses -webkit-transform for rotation

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
<meta http-equiv="refresh" content="1800">
<title>OD · Sky</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
html, body { width:100%; height:100%; background:#fff; overflow:hidden; }

.frame {
  position:absolute; top:0; left:0; width:100%; height:100%;
  -webkit-transform: rotate(180deg);
  -webkit-transform-origin: 50% 50%;
  transform: rotate(180deg);
  transform-origin: 50% 50%;
}

/* Header strip — HTML table avoids flexbox entirely */
.strip {
  width:100%;
  padding: 10px 16px 8px;
  border-bottom: 2px solid #000;
  background:#fff;
}
.strip table { width:100%; border-collapse:collapse; }
.strip td { vertical-align:top; }

.temp {
  font-size:36px; font-weight:900;
  letter-spacing:-1px; color:#000;
  font-family:Georgia,serif;
}
.sub {
  font-size:14px; font-weight:700;
  color:#000; margin-top:3px;
  font-family:Georgia,serif;
}
.date-cell { text-align:right; }
.date {
  font-size:20px; font-weight:900;
  color:#000; font-family:Georgia,serif;
}
.loc {
  font-size:11px; font-weight:700;
  color:#555; margin-top:3px;
  font-family:Georgia,serif;
}

/* Sky fills remaining space using absolute positioning */
.sky {
  position:absolute;
  top:90px; bottom:0; left:0; right:0;
  background:#000;
  text-align:center;
}
.sky svg { height:100%; width:auto; }
</style>
</head>
<body>
<div class="frame">

  <div class="strip">
    <table><tr>
      <td>
        <div class="temp">{{ d.weather.temp }}&deg;C</div>
        <div class="sub">UV {{ d.weather.uv }} &nbsp;&middot;&nbsp; AQI {{ d.weather.aqi }}</div>
      </td>
      <td class="date-cell">
        <div class="date">{{ d.date }}</div>
        <div class="loc">Pune &nbsp;&middot;&nbsp; {{ d.now }}</div>
      </td>
    </tr></table>
  </div>

  <div class="sky">{{ d.sky | safe }}</div>

</div>
</body>
</html>"""


# ── Routes ─────────────────────────────────────────────────

@app.route('/')
def dashboard():
    if not _cache['data']['sky'] or _cache['data']['sky'] == FALLBACK_SVG:
        refresh()
    return render_template_string(HTML, d=_cache['data'])


# ── Start ──────────────────────────────────────────────────

if __name__ == '__main__':
    print("Building sky...")
    refresh()
    print("Ready.")
    threading.Thread(target=background_refresh, daemon=True).start()
    app.run(host='0.0.0.0', port=5001, debug=False)