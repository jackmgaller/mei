"""Canned weather for --fixture: deterministic, no network. Made-up numbers from simple
formulas (only + and *, so every platform computes the same floats)."""

# 2026-09-30 18:00:00 UTC
START = 1790791200
REFRESH_AT = 40          # seconds into the stream: the data changes once, so versions change
HOME = {"name": "Meiville", "lat": 38.90, "lon": -95.20}     # a made-up town, mid-country
UTC_OFFSET = -5 * 3600   # CDT
TZ_ABBR = "CDT"

WMO_CYCLE = [0, 1, 2, 3, 45, 61, 80, 95, 71, 51]


def city(index, lat, lon, now, generation):
    """Weather for the index-th city (0 = home). generation 0 before the refresh, 1 after."""
    g = generation
    t = 30.0 - 0.75 * (lat - 25.0) + 0.5 * index + g
    wmo = WMO_CYCLE[(index + g) % len(WMO_CYCLE)]
    hour0 = now - now % 3600
    midnight = (now + UTC_OFFSET) // 86400 * 86400 - UTC_OFFSET
    return {
        "utc_offset": UTC_OFFSET, "tz_abbr": TZ_ABBR,
        "current": {"time": now - now % 900, "temp": t, "feels": t - 1.5, "humidity": 40 + 5 * index,
                    "wmo": wmo, "wind_dir": 45.0 * index, "wind": 10 + index + 3 * g, "gusts": 20 + 2 * index,
                    "cloud": 10 * index, "pressure": 1013.2 + index - g, "precip": 0.1 * index, "is_day": 1},
        "daily": [{"date": midnight + 86400 * d, "wmo": WMO_CYCLE[(index + d) % len(WMO_CYCLE)],
                   "high": t + 3 - d, "low": t - 7 - d, "pop": 10 * d + index, "precip": 2.0 * d,
                   "wind": 15 + d, "wind_dir": 90.0 * d, "sunrise": midnight + 6 * 3600 + 60 * index,
                   "sunset": midnight + 18 * 3600 + 60 * index, "uv": 5.5 - d} for d in range(5)],
        "hourly": {"start": hour0, "hours": [{"temp": t - 0.5 * h, "wmo": WMO_CYCLE[h % len(WMO_CYCLE)],
                                              "pop": 4 * h, "wind": 5 + h} for h in range(24)]},
    }


def grid(points, generation):
    """Temperature at each (lat, lon): warm south, cool north, a ridge in the middle, and
    north-south stripes (so map rows have many runs and delta coding pays)."""
    out = []
    for lat, lon in points:
        dx = lon + 95.0
        stripes = (int((lon + 125.0) / 2.0) % 3) * 3.0
        out.append(34.0 - 0.9 * (lat - 25.0) - 0.004 * dx * dx + stripes + 2.0 * generation)
    return out


def point(lat, lon, generation):
    """Current conditions at a map city (kind 4 pages): the grid's temperature there, a little
    warmer in town, and a weather code picked by the place."""
    t = grid([(lat, lon)], generation)[0] + 1.0
    k = int(round(lat * 100)) * 7 + int(round(lon * 100)) * 3 + generation
    return {"temp": t, "wmo": WMO_CYCLE[k % len(WMO_CYCLE)], "is_day": 1}
