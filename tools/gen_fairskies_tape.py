#!/usr/bin/env python3
"""Fair Skies' sample tape: 64 seconds of a MeiNet broadcast with made-up, pleasant early-autumn
weather, recorded through the gateway's own page encoder and carousel (tools/meinet).

The home city is the fictional "Meiville" (in the middle of the country, on Central time), so the
tape is never mistaken for real weather. 64 seconds carry every page, every map included, and the
tape loops seamlessly (it is whole packets, and nothing changes during it).

Writes carts/fairskies/demo_tape.bin.
    python3 tools/gen_fairskies_tape.py
"""
import math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'meinet'))
import meinet          # noqa: E402
import weather         # noqa: E402

OUT = os.path.join(os.path.dirname(HERE), 'carts', 'fairskies', 'demo_tape.bin')
START = 1790953200     # 2026-10-02 15:00 UTC: a Friday, mid-morning in the middle of the country
SECONDS = 64
HOME = ('Meiville', 38.9, -95.2)

# page: (UTC offset hours, now, feels, humidity, wmo, wind dir, wind km/h, cloud %, hPa,
#        today's high/low/pop/uv, then four more days (wmo, high, low, pop))
CITIES = {
    0x400: (-5, 17.0, 17.0, 58, 2, 200, 13, 35, 1016.8, (23.5, 10.5, 10, 5.1),
            [(0, 25.0, 12.0, 0), (80, 20.0, 14.0, 60), (61, 16.5, 10.0, 80), (1, 18.5, 7.5, 10)]),
    0x401: (-4, 15.0, 14.5, 62, 1, 290, 11, 20, 1019.4, (19.5, 11.5, 0, 4.2),
            [(1, 20.5, 12.5, 0), (2, 21.0, 13.0, 10), (3, 18.0, 13.0, 20), (80, 17.0, 11.0, 50)]),
    0x402: (-4, 21.0, 21.5, 66, 0, 120, 6, 5, 1018.1, (27.0, 16.0, 0, 6.0),
            [(0, 27.5, 16.5, 0), (1, 28.0, 17.0, 10), (2, 27.0, 18.0, 20), (95, 25.0, 18.0, 50)]),
    0x403: (-5, 13.0, 11.5, 74, 3, 30, 16, 90, 1013.2, (16.0, 9.0, 30, 2.9),
            [(51, 15.0, 9.5, 40), (2, 17.5, 8.0, 10), (0, 20.0, 9.0, 0), (1, 21.0, 11.0, 0)]),
    0x404: (-5, 24.0, 25.5, 60, 2, 160, 18, 30, 1012.6, (31.0, 20.0, 10, 7.0),
            [(1, 32.0, 21.0, 0), (2, 31.0, 21.5, 10), (95, 28.0, 20.0, 60), (2, 27.0, 18.0, 20)]),
    0x405: (-6, 9.0, 7.5, 40, 0, 250, 10, 0, 1021.0, (21.0, 4.5, 0, 5.6),
            [(1, 22.0, 6.0, 0), (2, 18.0, 4.0, 10), (71, 8.0, -1.0, 70), (1, 12.0, 0.0, 10)]),
    0x406: (-7, 27.0, 26.0, 14, 0, 90, 8, 0, 1011.0, (36.0, 23.5, 0, 7.8),
            [(0, 36.5, 24.0, 0), (0, 35.0, 23.0, 0), (1, 33.0, 21.0, 0), (0, 34.0, 22.0, 0)]),
    0x407: (-7, 17.0, 17.0, 84, 45, 250, 6, 100, 1014.0, (24.0, 16.0, 0, 6.3),
            [(1, 25.0, 16.5, 0), (2, 24.0, 16.0, 0), (45, 22.0, 15.5, 0), (0, 26.0, 16.0, 0)]),
    0x408: (-7, 11.0, 9.5, 88, 61, 200, 19, 100, 1008.4, (14.0, 9.0, 80, 1.4),
            [(80, 14.5, 8.5, 60), (3, 15.0, 9.0, 30), (2, 16.5, 8.0, 10), (61, 13.5, 9.0, 70)]),
}

HOURLY_WX = {    # the next hours' weather codes, repeating
    0x400: [2, 2, 1, 1, 1, 2, 2, 3, 3, 2, 1, 0], 0x401: [1, 1, 0, 0, 1, 2, 1, 0],
    0x402: [0, 0, 1, 1, 0, 0], 0x403: [3, 3, 51, 51, 3, 3, 2, 3], 0x404: [2, 1, 1, 2, 2, 1],
    0x405: [0, 0, 1, 1, 2, 1, 0, 0], 0x406: [0], 0x407: [45, 45, 3, 2, 1, 0, 0, 1, 2, 45],
    0x408: [61, 61, 80, 3, 80, 61, 3, 3],
}


def city(page, lat, lon):
    off, now, feels, hum, wmo, wdir, wind, cloud, hpa, today, days = CITIES[page]
    off_s = off * 3600
    local = START + off_s
    midnight = (local // 86400) * 86400 - off_s
    hi, lo, pop, uv = today
    sunrise = midnight + int(7.2 * 3600)
    sunset = midnight + int(18.9 * 3600)
    daily = [{"date": midnight, "wmo": wmo, "high": hi, "low": lo, "pop": pop, "precip": 0.0,
              "wind": wind + 8, "wind_dir": wdir, "sunrise": sunrise, "sunset": sunset, "uv": uv}]
    for d, (dw, dh, dl, dp) in enumerate(days, 1):
        daily.append({"date": midnight + 86400 * d, "wmo": dw, "high": dh, "low": dl, "pop": dp,
                      "precip": 4.0 * dp / 100, "wind": wind + 4 + d, "wind_dir": (wdir + 40 * d) % 360,
                      "sunrise": sunrise + 86400 * d + 60 * d, "sunset": sunset + 86400 * d - 120 * d, "uv": uv - 0.3 * d})
    hour0 = START - START % 3600
    hours = []
    cyc = HOURLY_WX[page]
    for h in range(24):
        lh = (hour0 + h * 3600 + off_s) % 86400 / 3600.0
        # a day curve: coolest about 6 am, warmest about 3 pm (tomorrow a little warmer or cooler)
        if 6 <= lh <= 15:
            k = 0.5 - 0.5 * math.cos((lh - 6.0) / 9.0 * math.pi)
        else:
            k = 0.5 + 0.5 * math.cos(((lh - 15.0) % 24) / 15.0 * math.pi)
        t = lo + (hi - lo) * k + (days[0][1] - hi) * h / 24.0 * 0.5
        hpop = pop if cyc[h % len(cyc)] >= 50 else max(0, pop // 3 - 5)
        hours.append({"temp": round(t * 2) / 2, "wmo": cyc[h % len(cyc)], "pop": hpop, "wind": wind + (h % 5) - 2})
    is_day = sunrise <= START < sunset
    return {
        "utc_offset": off_s, "tz_abbr": "",
        "current": {"time": START - START % 900, "temp": now, "feels": feels, "humidity": hum, "wmo": wmo,
                    "wind_dir": wdir, "wind": wind, "gusts": int(wind * 1.6), "cloud": cloud,
                    "pressure": hpa, "precip": 0.0 if wmo < 50 else 0.6, "is_day": 1 if is_day else 0},
        "daily": daily,
        "hourly": {"start": hour0, "hours": hours},
    }


def grid_temp(lat, lon):
    """A made-up, smooth temperature field at 15:00 UTC (morning in the west, midday east)."""
    t = 30.5 - 0.62 * (lat - 25.0)                      # warm south, cool north
    hour = (15 + lon / 15.0) % 24                       # local solar time: the west is colder yet
    t -= 4.0 * max(0.0, (11.0 - hour)) / 4.0
    def blob(clat, clon, slat, slon, amp):
        return amp * math.exp(-((lat - clat) / slat) ** 2 - ((lon - clon) / slon) ** 2)
    t += blob(39.5, -107.0, 4.5, 4.0, -9.0)             # the Rockies
    t += blob(33.0, -113.0, 3.0, 4.0, 6.0)              # the desert
    t += blob(44.0, -86.0, 4.0, 6.0, -2.5)              # the Great Lakes
    t += blob(47.5, -123.0, 3.0, 3.0, -2.0)             # the marine Northwest
    t += blob(36.0, -124.0, 4.0, 3.0, -4.0)             # a cool Pacific
    t += blob(29.0, -90.0, 3.0, 6.0, 2.5)               # the Gulf coast
    t += blob(40.0, -96.0, 5.0, 4.0, 2.0)               # a warm afternoon in the Plains
    t += 1.5 * math.sin(lon / 6.0) * math.cos(lat / 5.0)    # a gentle wave
    # a cool front across the Plains, from the upper Midwest down towards Oklahoma
    d = (lat - 39.6) + 0.55 * (lon + 95.5)
    t -= 5.0 / (1.0 + math.exp(-d / 0.8))
    t += 2.0 * math.exp(-(d / 1.2) ** 2) * math.exp(-((lon + 96) / 8) ** 2)   # warm ahead of it
    return t


def main():
    cfg = meinet.load_config(None)
    st = meinet.Station(cfg)
    name, lat, lon = HOME
    st.set_home(name, lat, lon, meinet.FixedTZ(-5 * 3600, 'CDT', True))
    for loc in st.cities():
        st.wx[loc['page']] = city(loc['page'], loc['lat'], loc['lon'])
    cols, rows = cfg['grid']
    pts = weather.grid_points(meinet.NATIONAL_BOX, cols, rows)
    st.grid = ([grid_temp(a, b) for a, b in pts], cols, rows, meinet.NATIONAL_BOX, START - 1800)
    st.data_time = START - 300
    with st.lock:
        st.rebuild()
    car = meinet.Carousel(st)
    data = b''.join(car.second(START + k) for k in range(SECONDS))
    with open(OUT, 'wb') as fh:
        fh.write(data)
    print('%s: %d bytes, %d seconds' % (OUT, len(data), SECONDS))


if __name__ == '__main__':
    main()
