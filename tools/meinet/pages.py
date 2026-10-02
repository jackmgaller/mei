"""MeiNet page payloads (docs/BROADCAST.md, "Payloads"). Every encoder returns a list of
52-byte rows."""
import struct

from wire import EPOCH_2000, ROW_BYTES

TIME_PAGE = 0x100
INDEX_PAGE = 0x101
HOME_PAGE = 0x400
NATIONAL_PAGE = 0x4FF
KIND_CURRENT, KIND_DAILY, KIND_HOURLY, KIND_MAP = 0, 1, 2, 3
MAP_W, MAP_H = 64, 48
FLAG_STALE = 2

TEMP_UNKNOWN = -128


def pid(page, kind):
    return kind << 12 | page


def rows_of(data):
    data = bytes(data)
    n = max(1, (len(data) + ROW_BYTES - 1) // ROW_BYTES)
    data += bytes(n * ROW_BYTES - len(data))
    return [data[i * ROW_BYTES:(i + 1) * ROW_BYTES] for i in range(n)]


def name_field(text, size):
    raw = (text or "").encode("ascii", "replace")[:size - 2]
    return bytes([len(raw)]) + raw + bytes(size - 1 - len(raw))


def secs2000(unix):
    return max(0, int(unix) - EPOCH_2000) & 0xFFFFFFFF if unix else 0


def days2000(unix_local):
    return (int(unix_local) - EPOCH_2000) // 86400


def weekday(days):
    return (days + 6) % 7            # 2000-01-01 was a Saturday; 0 = Sunday


def temp(t):
    if t is None:
        return TEMP_UNKNOWN
    return max(-127, min(127, int(round(t * 2))))


def u8(v, scale=1, top=254):
    if v is None:
        return 255
    return max(0, min(top, int(round(v * scale))))


def pct(v):
    return u8(v, top=100)


def wdir(deg):
    if deg is None:
        return 255
    return int(round(deg * 256 / 360)) & 255


def pressure(hpa):
    if hpa is None:
        return 0xFFFF
    return max(0, min(0xFFFE, int(round(hpa * 10)) - 9000))


def offset_steps(seconds):
    return int(round(seconds / 900))


def minutes_local(unix, utc_offset):
    if unix is None:
        return 0xFFFF
    return (int(unix) + utc_offset) % 86400 // 60


def time_page(unix, utc_offset, dst, tz_abbr, home_tz):
    """utc_offset in seconds; local fields computed from it."""
    local = int(unix) + utc_offset
    days = days2000(local)
    y, m, d = civil_from_days(days)
    sod = (local - EPOCH_2000) % 86400
    flags = (1 if dst else 0) | (2 if home_tz else 0)
    data = struct.pack("<IbBHBBBBBB", secs2000(unix), offset_steps(utc_offset), flags, y, m, d,
                       weekday(days), sod // 3600, sod // 60 % 60, sod % 60)
    data += name_field(tz_abbr, 8)
    return rows_of(data)


def civil_from_days(days2k):
    """(year, month, day) of days since 2000-01-01 (Howard Hinnant's algorithm)."""
    z = days2k + 10957 + 719468
    era = (z if z >= 0 else z - 146096) // 146097
    doe = z - era * 146097
    yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365
    y = yoe + era * 400
    doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
    mp = (5 * doy + 2) // 153
    d = doy - (153 * mp + 2) // 5 + 1
    m = mp + 3 if mp < 10 else mp - 9
    return (y + (m <= 2), m, d)


def current_page(loc):
    c, day0 = loc["current"], loc["daily"][0]
    off = loc["utc_offset"]
    flags = (1 if c.get("is_day") else 0) | (FLAG_STALE if loc.get("stale") else 0)
    data = struct.pack("<IbbBBBBBBHBBbbBBbB", secs2000(c["time"]), temp(c["temp"]), temp(c["feels"]),
                       pct(c["humidity"]), u8(c["wmo"]), wdir(c["wind_dir"]), u8(c["wind"]),
                       u8(c["gusts"]), pct(c["cloud"]), pressure(c["pressure"]),
                       u8(c["precip"], 10), flags, temp(day0["high"]), temp(day0["low"]),
                       pct(day0["pop"]), u8(day0["uv"], 10), offset_steps(off), 0)
    data += name_field(loc["city"], 16)
    data += struct.pack("<HH", minutes_local(day0.get("sunrise"), off), minutes_local(day0.get("sunset"), off))
    assert len(data) == 42
    return rows_of(data)


def daily_page(loc):
    off = loc["utc_offset"]
    days = loc["daily"][:5]
    d0 = days2000(days[0]["date"] + off)
    data = struct.pack("<HBB", d0, len(days), FLAG_STALE if loc.get("stale") else 0)
    for i, d in enumerate(days):
        data += struct.pack("<BbbBBBBB", u8(d["wmo"]), temp(d["high"]), temp(d["low"]), pct(d["pop"]),
                            u8(d["precip"]), u8(d["wind"]), wdir(d["wind_dir"]), weekday(d0 + i))
    data += bytes(4 + 40 - len(data))
    data += struct.pack("<b", offset_steps(off))
    return rows_of(data)


def hourly_page(loc):
    off = loc["utc_offset"]
    h = loc["hourly"]
    hours = h["hours"][:24]
    start = int(h["start"])
    data = struct.pack("<IBBBb", secs2000(start), len(hours), (start + off) % 86400 // 3600,
                       FLAG_STALE if loc.get("stale") else 0, offset_steps(off))
    for e in hours:
        data += struct.pack("<bBBB", temp(e["temp"]), u8(e["wmo"]), pct(e["pop"]), u8(e["wind"]))
    data += bytes(104 - len(data))
    rows = rows_of(data)
    assert len(rows) == 2
    return rows


# ---- maps ----

def map_scale(grid, national):
    if national:
        return -20, 4
    vals = [v for row in grid for v in row]
    lo, hi = min(vals), max(vals)
    for step in (1, 2, 3, 4, 5):
        base = (int(lo // step)) * step
        if base + 16 * step > hi:
            return base, step
    return int(lo // 5) * 5, 5


def bands(grid, base, step):
    return [[max(0, min(15, int((v - base) // step))) for v in row] for row in grid]


def _runs(vals):
    out = bytearray()
    i = 0
    while i < len(vals):
        j = i
        while j < len(vals) and vals[j] == vals[i] and j - i < 16:
            j += 1
        out.append((j - i - 1) << 4 | vals[i])
        i = j
    return bytes(out)


def encode_map_row(row, above, y):
    """Shortest of raw / runs / delta runs (no delta on key rows y % 8 == 0)."""
    raw = bytes([0]) + bytes(row[2 * i] | row[2 * i + 1] << 4 for i in range(MAP_W // 2))
    cands = [raw, bytes([1]) + _runs(row)]
    if y % 8 != 0 and above is not None:
        cands.append(bytes([2]) + _runs([(v - a) & 15 for v, a in zip(row, above)]))
    best = raw
    for c in cands:
        if len(c) <= ROW_BYTES and len(c) < len(best):
            best = c
    return best


def decode_map_row(data, above):
    mode = data[0]
    if mode == 0:
        return [(data[1 + x // 2] >> (4 * (x & 1))) & 15 for x in range(MAP_W)]
    out = []
    i = 1
    while len(out) < MAP_W:
        if i >= len(data):
            return None
        b = data[i]
        out += [b & 15] * ((b >> 4) + 1)
        i += 1
    if len(out) != MAP_W:
        return None
    if mode == 2:
        if above is None:
            return None
        out = [(d + a) & 15 for d, a in zip(out, above)]
    elif mode != 1:
        return None
    return out


def hundredths(deg):
    return int(round(deg * 100))


def map_page(m):
    """m: {'grid': 48 x 64 temperatures (deg C), 'box': (south, north, west, east), 'name',
    'time', 'national', 'stale'}"""
    base, step = map_scale(m["grid"], m.get("national"))
    b = bands(m["grid"], base, step)
    s, n, w, e = m["box"]
    head = struct.pack("<BBBBIhhhhbBBB", 0, MAP_W, MAP_H, FLAG_STALE if m.get("stale") else 0,
                       secs2000(m["time"]), hundredths(n), hundredths(s), hundredths(w), hundredths(e),
                       base * 2, step * 2, 0, 0)
    head += name_field(m["name"], 16)
    rows = rows_of(head)
    above = None
    for y in range(MAP_H):
        rows += rows_of(encode_map_row(b[y], above, y))
        above = b[y]
    return rows, b


def index_page(entries, data_time, home_set, any_stale):
    """entries: dicts with page, kinds, flags, versions[4], lat, lon, box (s, n, w, e), region, city."""
    head = struct.pack("<BBBBI", len(entries), 1, (1 if home_set else 0) | (2 if any_stale else 0), 0,
                       secs2000(data_time))
    head += name_field("MEINET WEATHER", 16)
    rows = rows_of(head)
    for en in entries:
        s, n, w, e = en["box"]
        data = struct.pack("<HBB4Bhhhhhh", en["page"], en["kinds"], en["flags"], *en["versions"],
                           hundredths(en["lat"]), hundredths(en["lon"]),
                           hundredths(s), hundredths(n), hundredths(w), hundredths(e))
        data += name_field(en["region"], 16) + name_field(en["city"], 16)
        assert len(data) == 52
        rows.append(data)
    return rows
