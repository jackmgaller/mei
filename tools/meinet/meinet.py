#!/usr/bin/env python3
"""MeiNet gateway: weather from Open-Meteo, encoded into broadcast pages and sent round a
carousel at 9,600 baud over TCP (docs/BROADCAST.md). Python 3 standard library only.

  meinet.py [--config FILE] [--host ADDR] [--port N] [--record FILE] [--seconds N]
            [--fixture] [--no-serve] [--noise BER] [-v]
"""
import argparse
import asyncio
import collections
import configparser
import datetime
import os
import random
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fixture  # noqa: E402
import pages as pg  # noqa: E402
import weather  # noqa: E402
import wire  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
PACKETS_PER_SECOND = 15
BYTES_PER_SECOND = PACKETS_PER_SECOND * wire.PACKET      # 960
BYTES_PER_TICK = 16
QUARTER = 70                                             # loop packets per 5-second quarter
HOME_SPAN = (2.5, 3.5)                                   # home map box: +-lat, +-lon degrees
NATIONAL_BOX = (24.5, 49.5, -125.0, -66.5)
RETRY_SECONDS = 120

# page: (region, city, lat, lon, (south, north, west, east))
REGIONS = {
    1: ("Northeast", "New York", 40.71, -74.01, (37.0, 47.5, -80.5, -67.0)),
    2: ("Southeast", "Atlanta", 33.75, -84.39, (25.0, 37.0, -91.5, -75.5)),
    3: ("Midwest", "Chicago", 41.88, -87.63, (36.0, 49.5, -97.5, -80.5)),
    4: ("South", "Dallas", 32.78, -96.80, (25.5, 37.0, -106.5, -88.5)),
    5: ("Mountain", "Denver", 39.74, -104.99, (37.0, 49.0, -117.0, -102.0)),
    6: ("Southwest", "Phoenix", 33.45, -112.07, (31.3, 37.0, -120.0, -103.0)),
    7: ("West", "Los Angeles", 34.05, -118.24, (32.5, 42.0, -124.5, -114.0)),
    8: ("Pacific NW", "Seattle", 47.61, -122.33, (42.0, 49.0, -124.8, -111.0)),
}

verbose = False


def log(*a):
    if verbose:
        print(time.strftime("%H:%M:%S"), *a, file=sys.stderr, flush=True)


# ---- configuration ----

def load_config(path):
    cp = configparser.ConfigParser(inline_comment_prefixes=(";", "#"))
    if path and os.path.exists(path):
        cp.read(path)
    s = cp["meinet"] if cp.has_section("meinet") else {}
    cfg = {
        "home": s.get("home", "").strip(),
        "home_lat": s.get("home_lat", "").strip(), "home_lon": s.get("home_lon", "").strip(),
        "home_name": s.get("home_name", "").strip(),
        "host": s.get("host", "127.0.0.1").strip() or "127.0.0.1",
        "port": int(s.get("port", "9600") or 9600),
        "refresh_minutes": float(s.get("refresh_minutes", "15") or 15),
        "map_refresh_minutes": float(s.get("map_refresh_minutes", "180") or 180),
        "map_grid": s.get("map_grid", "30x14").strip() or "30x14",
        "noise": float(s.get("noise", "0") or 0),
    }
    regions = dict(REGIONS)
    if cp.has_section("regions"):
        for k, v in cp["regions"].items():
            n = int(k, 0)
            f = [x.strip() for x in v.split(";")]
            if not 1 <= n <= 254 or len(f) != 8:
                raise SystemExit("bad region %s: want 'Region; City; lat; lon; south; north; west; east'" % k)
            regions[n] = (f[0], f[1], float(f[2]), float(f[3]), tuple(float(x) for x in f[4:8]))
    cfg["regions"] = regions
    cols, _, rows = cfg["map_grid"].partition("x")
    cfg["grid"] = (max(2, int(cols)), max(2, int(rows)))
    return cfg


# ---- time zones ----

class FixedTZ(datetime.tzinfo):
    def __init__(self, offset, name, dst):
        self.off, self.name, self.dst_on = datetime.timedelta(seconds=offset), name, dst

    def utcoffset(self, dt):
        return self.off

    def dst(self, dt):
        return datetime.timedelta(hours=1) if self.dst_on else datetime.timedelta(0)

    def tzname(self, dt):
        return self.name


def tz_info(tz, unix):
    """(offset seconds, dst, abbreviation) at a Unix time; tz None = the host's zone."""
    if tz is None:
        lt = time.localtime(unix)
        return lt.tm_gmtoff, lt.tm_isdst > 0, lt.tm_zone
    dt = datetime.datetime.fromtimestamp(unix, tz)
    d = dt.dst()
    return int(dt.utcoffset().total_seconds()), bool(d and d.total_seconds()), dt.tzname() or ""


# ---- the station: data and pages ----

class Station:
    def __init__(self, cfg):
        self.cfg = cfg
        self.lock = threading.Lock()
        self.locs = {}           # page -> location (region, city, lat, lon, box, home, national)
        for n, (region, city, lat, lon, box) in sorted(cfg["regions"].items()):
            self.locs[0x400 + n] = {"page": 0x400 + n, "region": region, "city": city, "lat": lat,
                                    "lon": lon, "box": box}
        self.locs[pg.NATIONAL_PAGE] = {"page": pg.NATIONAL_PAGE, "region": "United States", "city": "",
                                       "lat": 39.0, "lon": -96.0, "box": NATIONAL_BOX, "national": True}
        self.home = None
        self.tz = None           # None: the host's zone
        self.home_tz = False
        self.wx = {}             # page -> weather dict (+ "stale")
        self.grid = None         # (temps, cols, rows, box, time)
        self.home_grid = None
        self.grid_stale = False
        self.data_time = 0
        self.versions = {}       # page id -> (bytes, version)
        self.pages = {}          # page id -> (version, rows)

    def set_home(self, name, lat, lon, tz=None):
        dlat, dlon = HOME_SPAN
        self.home = {"page": pg.HOME_PAGE, "region": "Home", "city": name, "lat": lat, "lon": lon,
                     "box": (lat - dlat, lat + dlat, lon - dlon, lon + dlon), "home": True}
        self.locs[pg.HOME_PAGE] = self.home
        if tz is not None:
            self.tz, self.home_tz = tz, True

    def cities(self):
        return [l for p, l in sorted(self.locs.items()) if not l.get("national")]

    # -- versions --
    def _set(self, page_id, rows):
        data = b"".join(rows)
        old = self.versions.get(page_id)
        v = 1 if old is None else old[1] if old[0] == data else old[1] % 255 + 1
        self.versions[page_id] = (data, v)
        self.pages[page_id] = (v, rows)

    def rebuild(self):
        """Re-encode every page from the current data (call with the lock held)."""
        on_air = set()
        entries = []
        for page, loc in sorted(self.locs.items()):
            kinds = 0
            w = self.wx.get(page)
            if w and not loc.get("national"):
                full = dict(loc, **w)
                for kind, enc in ((pg.KIND_CURRENT, pg.current_page), (pg.KIND_DAILY, pg.daily_page),
                                  (pg.KIND_HOURLY, pg.hourly_page)):
                    self._set(pg.pid(page, kind), enc(full))
                    on_air.add(pg.pid(page, kind))
                    kinds |= 1 << kind
            m = self.map_for(loc)
            if m:
                rows, _ = pg.map_page(m)
                self._set(pg.pid(page, pg.KIND_MAP), rows)
                on_air.add(pg.pid(page, pg.KIND_MAP))
                kinds |= 1 << pg.KIND_MAP
            if kinds:
                stale = bool(w and w.get("stale")) or (kinds & 8 and self.grid_stale)
                entries.append({
                    "page": page, "kinds": kinds,
                    "flags": (1 if loc.get("home") else 0) | (2 if stale else 0) | (4 if loc.get("national") else 0),
                    "versions": [self.pages[pg.pid(page, k)][0] if kinds >> k & 1 else 0 for k in range(4)],
                    "lat": loc["lat"], "lon": loc["lon"], "box": loc["box"],
                    "region": loc["region"], "city": loc["city"],
                })
        for p in list(self.pages):
            if p not in on_air and p != pg.INDEX_PAGE:
                del self.pages[p]
        any_stale = any(e["flags"] & 2 for e in entries)
        self._set(pg.INDEX_PAGE, pg.index_page(entries, self.data_time, self.home is not None, any_stale))

    def map_for(self, loc):
        g = self.grid
        if loc.get("home") and self.home_grid and not weather.inside(loc["box"], NATIONAL_BOX):
            g = self.home_grid
        if not g:
            return None
        temps, cols, rows, box, t = g
        if not weather.inside(loc["box"], box):
            return None
        return {"grid": weather.upsample(temps, cols, rows, box, loc["box"]), "box": loc["box"],
                "name": loc["region"] if not loc.get("home") else loc["city"], "time": t,
                "national": loc.get("national"), "stale": self.grid_stale}

    def time_page(self, unix):
        off, dst, abbr = tz_info(self.tz, unix)
        return pg.time_page(unix, off, dst, abbr, self.home_tz)

    def snapshot(self):
        with self.lock:
            return dict(self.pages)

    # -- data sources --
    def load_fixture(self, generation, now):
        with self.lock:
            if self.home is None:
                self.set_home(fixture.HOME["name"], fixture.HOME["lat"], fixture.HOME["lon"],
                              FixedTZ(fixture.UTC_OFFSET, fixture.TZ_ABBR, True))
            for i, loc in enumerate(self.cities()):
                self.wx[loc["page"]] = fixture.city(i, loc["lat"], loc["lon"], now, generation)
            cols, rows = self.cfg["grid"]
            pts = weather.grid_points(NATIONAL_BOX, cols, rows)
            self.grid = (fixture.grid(pts, generation), cols, rows, NATIONAL_BOX, now)
            self.data_time = now
            self.rebuild()

    def fetch_home(self):
        c = self.cfg
        if c["home_lat"] and c["home_lon"]:
            self.set_home(c["home_name"] or c["home"] or "Home", float(c["home_lat"]), float(c["home_lon"]))
            return True
        if not c["home"]:
            return True
        g = weather.geocode(c["home"])
        if not g:
            print("meinet: home city %r not found; no page 0x400" % c["home"], file=sys.stderr)
            return True
        tz = None
        if g.get("timezone"):
            try:
                from zoneinfo import ZoneInfo
                tz = ZoneInfo(g["timezone"])
            except Exception:
                tz = None
        with self.lock:
            self.set_home(c["home_name"] or g["name"], g["lat"], g["lon"], tz)
        log("home: %s (%.2f, %.2f) %s" % (g["name"], g["lat"], g["lon"], g.get("timezone")))
        return True

    def fetch_weather(self):
        now = int(time.time())
        cities = self.cities()
        try:
            data = weather.fetch_cities(cities, now)
        except Exception as e:
            print("meinet: weather fetch failed (%s); keeping the last data, marked stale" % e, file=sys.stderr)
            with self.lock:
                for w in self.wx.values():
                    w["stale"] = True
                self.rebuild()
            return False
        with self.lock:
            for loc, w in zip(cities, data):
                w["stale"] = False
                self.wx[loc["page"]] = w
            self.data_time = now
            self.rebuild()
        log("weather: %d cities" % len(cities))
        return True

    def fetch_maps(self):
        cols, rows = self.cfg["grid"]
        now = int(time.time())
        try:
            pts = weather.grid_points(NATIONAL_BOX, cols, rows)
            temps = fill_missing(weather.fetch_grid(pts))
            home_grid = None
            if self.home and not weather.inside(self.home["box"], NATIONAL_BOX):
                hp = weather.grid_points(self.home["box"], 8, 6)
                home_grid = (fill_missing(weather.fetch_grid(hp)), 8, 6, self.home["box"], now)
        except Exception as e:
            print("meinet: map fetch failed (%s); keeping the last maps, marked stale" % e, file=sys.stderr)
            with self.lock:
                self.grid_stale = self.grid is not None
                self.rebuild()
            return False
        with self.lock:
            self.grid = (temps, cols, rows, NATIONAL_BOX, now)
            self.home_grid = home_grid
            self.grid_stale = False
            self.rebuild()
        log("maps: %d points" % (len(pts) + (48 if home_grid else 0)))
        return True


def fill_missing(temps):
    ok = [t for t in temps if t is not None]
    if not ok:
        raise RuntimeError("no temperatures in the grid")
    mean = sum(ok) / len(ok)
    return [mean if t is None else t for t in temps]


def refresher(station, stop):
    """Background thread: geocode the home city, then refresh weather and maps on their
    schedules, retrying failures after RETRY_SECONDS."""
    cfg = station.cfg
    home_done = False
    next_wx = next_map = 0.0
    while not stop.is_set():
        now = time.time()
        if not home_done:
            try:
                home_done = station.fetch_home()
            except Exception as e:
                print("meinet: home lookup failed (%s); retrying" % e, file=sys.stderr)
        if now >= next_wx:
            ok = station.fetch_weather()
            next_wx = now + (cfg["refresh_minutes"] * 60 if ok and home_done else RETRY_SECONDS)
        if now >= next_map:
            ok = station.fetch_maps()
            next_map = now + (cfg["map_refresh_minutes"] * 60 if ok else RETRY_SECONDS)
        stop.wait(5)


# ---- the carousel ----

class Carousel:
    def __init__(self, station):
        self.st = station
        self.queue = collections.deque()
        self.quarter = 0
        self.map_rows = collections.deque()
        self.last_map = -1

    def second(self, unix):
        """The 960 bytes of one second: the time page, then 14 loop packets."""
        out = [wire.packet(pg.TIME_PAGE, 0, True, unix & 0xFF, self.st.time_page(unix)[0])]
        for _ in range(PACKETS_PER_SECOND - 1):
            if not self.queue:
                self._fill()
            out.append(self.queue.popleft())
        return b"".join(out)

    @staticmethod
    def _page(page_id, version, rows):
        return [wire.packet(page_id, r, r == len(rows) - 1, version, rows[r]) for r in range(len(rows))]

    def _fill(self):
        snap = self.st.snapshot()
        block = []
        if pg.INDEX_PAGE in snap:
            block += self._page(pg.INDEX_PAGE, *snap[pg.INDEX_PAGE])
        extra = {0: pg.KIND_DAILY, 1: pg.KIND_HOURLY}.get(self.quarter)
        for kind in (pg.KIND_CURRENT,) + ((extra,) if extra is not None else ()):
            for p in sorted(snap):
                if p >> 12 == kind and p & 0xF00 == 0x400:
                    block += self._page(p, *snap[p])
        self.quarter = (self.quarter + 1) % 4
        while len(block) < QUARTER:
            if not self.map_rows:
                maps = sorted(p for p in snap if p >> 12 == pg.KIND_MAP)
                if not maps:
                    block.append(wire.filler())
                    continue
                nxt = next((p for p in maps if p > self.last_map), maps[0])
                self.last_map = nxt
                self.map_rows.extend(self._page(nxt, *snap[nxt]))
            block.append(self.map_rows.popleft())
        self.queue.extend(block)


# ---- running ----

def generate(station, start, seconds, fixture_mode, noise_rng, ber):
    """Yields each second's bytes (no pacing)."""
    car = Carousel(station)
    for k in range(seconds):
        if fixture_mode and k == fixture.REFRESH_AT:
            station.load_fixture(1, start + k)
        yield wire.add_noise(car.second(start + k), ber, noise_rng)


async def serve(station, args, cfg, ber, noise_rng, record):
    clients = set()

    async def on_client(reader, writer):
        peer = writer.get_extra_info("peername")
        log("client connected", peer)
        clients.add(writer)
        try:
            await reader.read()           # nothing is expected; wait for the client to go
        except Exception:
            pass
        clients.discard(writer)
        writer.close()
        log("client left", peer)

    server = await asyncio.start_server(on_client, cfg["host"], cfg["port"])
    print("meinet: serving on %s:%d%s" % (cfg["host"], cfg["port"], " (fixture)" if args.fixture else ""),
          file=sys.stderr, flush=True)
    car = Carousel(station)
    start = int(time.time()) + 1
    unix0 = fixture.START if args.fixture else start
    while time.time() < start:
        await asyncio.sleep(start - time.time())
    k = 0
    loop = asyncio.get_running_loop()
    try:
        while args.seconds is None or k < args.seconds:
            if args.fixture and k == fixture.REFRESH_AT:
                station.load_fixture(1, unix0 + k)
            sec = wire.add_noise(car.second(unix0 + k), ber, noise_rng)
            if record:
                record.write(sec)
                record.flush()
            for t in range(60):
                due = start + k + t / 60.0
                delay = due - time.time()
                if delay > 0:
                    await asyncio.sleep(delay)
                chunk = sec[t * BYTES_PER_TICK:(t + 1) * BYTES_PER_TICK]
                for w in list(clients):
                    if w.transport.get_write_buffer_size() > 2 * BYTES_PER_SECOND:
                        log("client too slow, dropped")
                        clients.discard(w)
                        w.close()
                        continue
                    w.write(chunk)
            k += 1
    finally:
        server.close()
        for w in clients:
            w.close()
        del loop


def main():
    global verbose
    ap = argparse.ArgumentParser(description="MeiNet broadcast gateway (docs/BROADCAST.md)")
    ap.add_argument("--config", default=os.path.join(HERE, "meinet.conf"))
    ap.add_argument("--host")
    ap.add_argument("--port", type=int)
    ap.add_argument("--record")
    ap.add_argument("--seconds", type=int)
    ap.add_argument("--fixture", action="store_true", help="canned data and a fixed clock, no network")
    ap.add_argument("--no-serve", action="store_true", help="generate --seconds of stream into --record, unpaced")
    ap.add_argument("--noise", type=float, help="bit-error rate added to the stream")
    ap.add_argument("--exit-with-parent", action="store_true",
                    help="quit when the process that started us exits (the desktop player starts the gateway this way)")
    ap.add_argument("-v", action="store_true")
    args = ap.parse_args()
    if args.exit_with_parent:
        parent = os.getppid()

        def watch_parent():
            while os.getppid() == parent:
                time.sleep(1)
            os._exit(0)
        threading.Thread(target=watch_parent, daemon=True).start()
    verbose = args.v
    cfg = load_config(None if args.fixture else args.config)
    if args.host:
        cfg["host"] = args.host
    if args.port:
        cfg["port"] = args.port
    ber = args.noise if args.noise is not None else cfg["noise"]
    noise_rng = random.Random(0x4D454E4F)
    station = Station(cfg)
    record = open(args.record, "wb") if args.record else None

    if args.no_serve:
        if not record or not args.seconds:
            ap.error("--no-serve needs --record and --seconds")
        if args.fixture:
            start = fixture.START
            station.load_fixture(0, start)
        else:
            start = int(time.time())
            station.fetch_home()
            station.fetch_weather()
            station.fetch_maps()
        for sec in generate(station, start, args.seconds, args.fixture, noise_rng, ber):
            record.write(sec)
        record.close()
        return

    stop = threading.Event()
    if args.fixture:
        station.load_fixture(0, fixture.START)
    else:
        with station.lock:
            station.rebuild()
        threading.Thread(target=refresher, args=(station, stop), daemon=True).start()
    try:
        asyncio.run(serve(station, args, cfg, ber, noise_rng, record))
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        if record:
            record.close()


if __name__ == "__main__":
    main()
