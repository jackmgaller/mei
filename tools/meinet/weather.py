"""Weather data from Open-Meteo (https://open-meteo.com, free, no key), turned into the
gateway's data model: one dict per city, plus temperature grids for the maps."""
import json
import urllib.parse
import urllib.request

FORECAST = "https://api.open-meteo.com/v1/forecast"
GEOCODE = "https://geocoding-api.open-meteo.com/v1/search"
USER_AGENT = "MeiNet/0.1 (Mei fantasy console broadcast gateway)"

CURRENT = ("temperature_2m,relative_humidity_2m,apparent_temperature,is_day,precipitation,"
           "weather_code,cloud_cover,pressure_msl,wind_speed_10m,wind_direction_10m,wind_gusts_10m")
DAILY = ("weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,"
         "precipitation_sum,wind_speed_10m_max,wind_direction_10m_dominant,sunrise,sunset,uv_index_max")
HOURLY = "temperature_2m,weather_code,precipitation_probability,wind_speed_10m"


def _get(url, params, timeout=30):
    q = urllib.parse.urlencode(params, safe=",")
    req = urllib.request.Request(url + "?" + q, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read().decode("utf-8"))
    if isinstance(data, dict) and data.get("error"):
        raise RuntimeError(data.get("reason", "Open-Meteo error"))
    return data


def geocode(name):
    """'City' or 'City, Qualifier' -> dict(name, lat, lon, timezone) or None."""
    city, _, qual = name.partition(",")
    city, qual = city.strip(), qual.strip().lower()
    data = _get(GEOCODE, {"name": city, "count": 20, "language": "en", "format": "json"})
    for r in data.get("results") or []:
        fields = " ".join(str(r.get(k, "")) for k in ("admin1", "admin2", "country", "country_code")).lower()
        if not qual or qual in fields:
            return {"name": r["name"], "lat": r["latitude"], "lon": r["longitude"],
                    "timezone": r.get("timezone")}
    return None


def _at(arr, i):
    return arr[i] if arr is not None and 0 <= i < len(arr) else None


def fetch_cities(cities, now):
    """cities: list of dicts with lat, lon. Returns one weather dict per city (current, daily,
    hourly, utc_offset, tz_abbr)."""
    params = {
        "latitude": ",".join("%.4f" % c["lat"] for c in cities),
        "longitude": ",".join("%.4f" % c["lon"] for c in cities),
        "current": CURRENT, "daily": DAILY, "hourly": HOURLY,
        "timezone": "auto", "timeformat": "unixtime", "forecast_days": 5,
    }
    data = _get(FORECAST, params)
    if isinstance(data, dict):
        data = [data]
    if len(data) != len(cities):
        raise RuntimeError("expected %d locations, got %d" % (len(cities), len(data)))
    return [_city(d, now) for d in data]


def _city(d, now):
    c, dl, hr = d["current"], d["daily"], d["hourly"]
    out = {"utc_offset": int(d.get("utc_offset_seconds", 0)), "tz_abbr": d.get("timezone_abbreviation", "")}
    out["current"] = {
        "time": c["time"], "temp": c.get("temperature_2m"), "feels": c.get("apparent_temperature"),
        "humidity": c.get("relative_humidity_2m"), "wmo": c.get("weather_code"),
        "wind_dir": c.get("wind_direction_10m"), "wind": c.get("wind_speed_10m"),
        "gusts": c.get("wind_gusts_10m"), "cloud": c.get("cloud_cover"), "pressure": c.get("pressure_msl"),
        "precip": c.get("precipitation"), "is_day": c.get("is_day"),
    }
    out["daily"] = [{
        "date": dl["time"][i], "wmo": _at(dl.get("weather_code"), i),
        "high": _at(dl.get("temperature_2m_max"), i), "low": _at(dl.get("temperature_2m_min"), i),
        "pop": _at(dl.get("precipitation_probability_max"), i), "precip": _at(dl.get("precipitation_sum"), i),
        "wind": _at(dl.get("wind_speed_10m_max"), i), "wind_dir": _at(dl.get("wind_direction_10m_dominant"), i),
        "sunrise": _at(dl.get("sunrise"), i), "sunset": _at(dl.get("sunset"), i), "uv": _at(dl.get("uv_index_max"), i),
    } for i in range(min(5, len(dl["time"])))]
    times = hr["time"]
    start = 0
    for i, t in enumerate(times):
        if t <= now:
            start = i
    hours = [{"temp": _at(hr.get("temperature_2m"), i), "wmo": _at(hr.get("weather_code"), i),
              "pop": _at(hr.get("precipitation_probability"), i), "wind": _at(hr.get("wind_speed_10m"), i)}
             for i in range(start, min(start + 24, len(times)))]
    out["hourly"] = {"start": times[start], "hours": hours}
    if len(hours) < 24 or len(out["daily"]) < 5:
        raise RuntimeError("short forecast")
    return out


def fetch_grid(points, batch=100):
    """points: list of (lat, lon). Returns the current 2 m temperature at each."""
    temps = []
    for i in range(0, len(points), batch):
        chunk = points[i:i + batch]
        data = _get(FORECAST, {
            "latitude": ",".join("%.3f" % p[0] for p in chunk),
            "longitude": ",".join("%.3f" % p[1] for p in chunk),
            "current": "temperature_2m", "timeformat": "unixtime",
        })
        if isinstance(data, dict):
            data = [data]
        if len(data) != len(chunk):
            raise RuntimeError("grid: expected %d points, got %d" % (len(chunk), len(data)))
        temps += [d["current"]["temperature_2m"] for d in data]
    return temps


def fetch_points(points, batch=100):
    """points: list of (lat, lon). Returns the current conditions at each, as dicts with
    temp (deg C), wmo and is_day, in batched multi-location requests."""
    out = []
    for i in range(0, len(points), batch):
        chunk = points[i:i + batch]
        data = _get(FORECAST, {
            "latitude": ",".join("%.2f" % p[0] for p in chunk),
            "longitude": ",".join("%.2f" % p[1] for p in chunk),
            "current": "temperature_2m,weather_code,is_day", "timeformat": "unixtime",
        })
        if isinstance(data, dict):
            data = [data]
        if len(data) != len(chunk):
            raise RuntimeError("cities: expected %d points, got %d" % (len(chunk), len(data)))
        for d in data:
            c = d["current"]
            out.append({"temp": c.get("temperature_2m"), "wmo": c.get("weather_code"), "is_day": c.get("is_day")})
    return out


def grid_points(box, cols, rows):
    """Coarse grid over box (south, north, west, east), corners included, north row first."""
    s, n, w, e = box
    return [(n - (n - s) * y / (rows - 1), w + (e - w) * x / (cols - 1)) for y in range(rows) for x in range(cols)]


def upsample(coarse, cols, rows, src_box, dst_box, width=64, height=48):
    """Bilinear sample of a coarse grid (list, row-major, north first, corners at src_box edges)
    at the cell centres of a width x height grid over dst_box."""
    s0, n0, w0, e0 = src_box
    s, n, w, e = dst_box
    out = []
    for y in range(height):
        lat = n - (y + 0.5) * (n - s) / height
        gy = min(max((n0 - lat) / (n0 - s0) * (rows - 1), 0.0), rows - 1.0)
        y0 = min(int(gy), rows - 2)
        fy = gy - y0
        row = []
        for x in range(width):
            lon = w + (x + 0.5) * (e - w) / width
            gx = min(max((lon - w0) / (e0 - w0) * (cols - 1), 0.0), cols - 1.0)
            x0 = min(int(gx), cols - 2)
            fx = gx - x0
            a = coarse[y0 * cols + x0]
            b = coarse[y0 * cols + x0 + 1]
            c = coarse[(y0 + 1) * cols + x0]
            d = coarse[(y0 + 1) * cols + x0 + 1]
            row.append((a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy)
        out.append(row)
    return out


def inside(box, outer):
    return outer[0] <= box[0] and box[1] <= outer[1] and outer[2] <= box[2] and box[3] <= outer[3]
