"""Gateway tests: python3 tools/meinet/test_meinet.py (run by `make test`)."""
import os
import random
import struct
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fixture  # noqa: E402
import meinet  # noqa: E402
import pages as pg  # noqa: E402
import wire  # noqa: E402

FIXTURE_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "tests", "lang", "data", "broadcast.bin")


def fixture_stream(seconds=80):
    st = meinet.Station(meinet.load_config(None))
    st.load_fixture(0, fixture.START)
    return b"".join(meinet.generate(st, fixture.START, seconds, True, random.Random(1), 0))


class Wire(unittest.TestCase):
    def test_hamming_table(self):
        self.assertEqual(wire.HAMMING, [0x15, 0x02, 0x49, 0x5E, 0x64, 0x73, 0x38, 0x2F,
                                        0xD0, 0xC7, 0x8C, 0x9B, 0xA1, 0xB6, 0xFD, 0xEA])
        for n in range(16):
            for bit in range(8):
                self.assertEqual(wire.HAMMING_DECODE[wire.HAMMING[n] ^ 1 << bit], (n, 1))
                for bit2 in range(bit + 1, 8):
                    self.assertEqual(wire.HAMMING_DECODE[wire.HAMMING[n] ^ 1 << bit ^ 1 << bit2][0], -1)

    def test_crc(self):
        self.assertEqual(wire.crc16(b"123456789"), 0x29B1)

    def test_packet_round_trip(self):
        p = wire.packet(0x3401, 17, True, 200, b"hello")
        self.assertEqual(len(p), 64)
        h, payload, corr = wire.decode_packet(p)
        self.assertEqual((h & 0xFFFF, h >> 16 & 63, h >> 23 & 1, h >> 24), (0x3401, 17, 1, 200))
        self.assertEqual(payload[:5], b"hello")
        self.assertFalse(corr)
        bad = bytearray(p)
        bad[3] ^= 0x10
        self.assertTrue(wire.decode_packet(bad)[2])
        bad[20] ^= 1
        self.assertIsNone(wire.decode_packet(bad))


class Pages(unittest.TestCase):
    def test_map_rows(self):
        rnd = random.Random(5)
        above = None
        for y in range(48):
            row = [min(15, (x // 9 + y // 7) % 16) if rnd.random() > 0.1 else rnd.randrange(16) for x in range(64)]
            enc = pg.encode_map_row(row, above, y)
            self.assertLessEqual(len(enc), 52)
            if y % 8 == 0:
                self.assertNotEqual(enc[0], 2)
            self.assertEqual(pg.decode_map_row(enc + bytes(52 - len(enc)), above), row)
            above = row

    def test_cities_page(self):
        cs = [{"name": "Somewhere %d" % i, "lat": 40 + i / 10, "lon": -100 - i / 10, "temp": 10.5 + i,
               "wmo": 3, "is_day": i % 2} for i in range(5)]
        rows = pg.cities_page(cs)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[2][26:], bytes(26))                           # the empty second half
        got = pg.decode_cities(b"".join(rows))
        self.assertEqual([g[5] for g in got], [c["name"] for c in cs])
        self.assertEqual(got[1][:5], (4010, -10010, 23, 3, 1))

    def test_pick_spacing(self):
        box = meinet.REGIONS[3][4]
        got = meinet.ct.pick(box, [], 14)
        self.assertEqual(len(got), 14)
        self.assertEqual(got[0]["name"], "Chicago")
        for a in got:
            for b in got:
                if a is not b:
                    ax, ay = meinet.ct.cell(box, a["lat"], a["lon"])
                    bx, by = meinet.ct.cell(box, b["lat"], b["lon"])
                    self.assertGreaterEqual(((ax - bx) / meinet.ct.SPACE_X) ** 2 + ((ay - by) / meinet.ct.SPACE_Y) ** 2, 1.0)

    def test_civil(self):
        self.assertEqual(pg.civil_from_days(0), (2000, 1, 1))
        self.assertEqual(pg.civil_from_days(9769), (2026, 9, 30))
        self.assertEqual(pg.weekday(9769), 3)          # a Wednesday


class Stream(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = fixture_stream()

    def test_committed_fixture_matches(self):
        with open(FIXTURE_FILE, "rb") as f:
            self.assertEqual(f.read(), self.data, "regenerate with tools/meinet/make_fixture.sh")

    def test_layout(self):
        self.assertEqual(len(self.data), 80 * 960)
        for s in range(80):
            h, payload, _ = wire.decode_packet(self.data[s * 960:s * 960 + 64])
            self.assertEqual(h & 0xFFFF, 0x100)
            secs = struct.unpack_from("<I", payload)[0]
            self.assertEqual(secs, fixture.START - wire.EPOCH_2000 + s)

    def test_assembly(self):
        rx = wire.Receiver()
        rx.feed(self.data[:40 * 960])
        self.assertEqual(rx.dropped, 0)
        for page in [0x400 + i for i in range(9)]:
            for kind in (0, 1, 2):
                self.assertTrue(rx.complete(kind << 12 | page), hex(kind << 12 | page))
        self.assertTrue(rx.complete(pg.INDEX_PAGE))
        idx = rx.page_bytes(pg.INDEX_PAGE)
        self.assertEqual(idx[0], 10)                       # home, 8 regions, national
        cur = rx.page_bytes(0x0403)
        self.assertEqual(cur[22:30], b"\x07Chicago")
        rx.feed(self.data[40 * 960:])
        self.assertEqual(rx.pages[0x0403][0], 2)           # refreshed: version 2
        maps = [p for p in rx.pages if p >> 12 == 3 and rx.complete(p)]
        self.assertGreaterEqual(len(maps), 9)
        m = rx.page_bytes(maps[0])
        above = None
        for y in range(48):
            above = pg.decode_map_row(m[52 * (y + 1):52 * (y + 2)], above)
            self.assertIsNotNone(above)

    def test_cities(self):
        rx = wire.Receiver()
        rx.feed(self.data)
        idx = rx.page_bytes(pg.INDEX_PAGE)
        self.assertEqual(idx[1], pg.INDEX_FORMAT)
        for e in range(idx[0]):
            en = idx[52 * (e + 1):52 * (e + 2)]
            page = en[0] | en[1] << 8
            self.assertTrue(en[2] & 1 << pg.KIND_CITIES, hex(page))          # every location has cities
            self.assertTrue(rx.complete(pg.pid(page, pg.KIND_CITIES)), hex(page))
            self.assertIn(en[35], (1, 2))                                          # their version
            got = pg.decode_cities(rx.page_bytes(pg.pid(page, pg.KIND_CITIES)))
            cap = meinet.NATIONAL_CITIES_CAP if page == pg.NATIONAL_PAGE else meinet.CITIES_CAP
            self.assertTrue(5 <= len(got) <= cap, (hex(page), len(got)))
            s, n, w, e_ = struct.unpack_from("<hhhh", en, 12)
            for lat, lon, t, wmo, flags, name in got:
                self.assertTrue(s < lat < n and w < lon < e_, (hex(page), name))
                self.assertNotEqual(t, pg.TEMP_UNKNOWN)
        home = pg.decode_cities(rx.page_bytes(pg.pid(pg.HOME_PAGE, pg.KIND_CITIES)))
        self.assertEqual(home[0][5], fixture.HOME["name"])                     # home first
        self.assertEqual(pg.decode_cities(rx.page_bytes(0x4403))[1][5], "Chicago")

    def test_cities_before_maps(self):
        """The map sequence sends each page number's cities right before its map."""
        prev = None
        for i in range(0, len(self.data), 64):
            h, _, _ = wire.decode_packet(self.data[i:i + 64])
            pid, row = h & 0xFFFF, h >> 16 & 63
            if pid >> 12 == pg.KIND_MAP and row == 0:
                self.assertEqual(prev, pg.pid(pid & 0xFFF, pg.KIND_CITIES))
            if pid >> 12 in (pg.KIND_MAP, pg.KIND_CITIES):
                prev = pid

    def test_noise(self):
        noisy = wire.add_noise(self.data, 1e-3, random.Random(3))
        rx = wire.Receiver()
        rx.feed(noisy[1000:])                              # mid-stream start
        self.assertGreater(rx.dropped, 0)
        self.assertGreater(rx.fixed, 0)
        self.assertTrue(rx.complete(pg.INDEX_PAGE))


class Failures(unittest.TestCase):
    def test_fetch_failure_keeps_data_marked_stale(self):
        st = meinet.Station(meinet.load_config(None))
        st.load_fixture(0, fixture.START)
        v_before = st.pages[0x0401][0]
        old_get = meinet.weather._get

        def boom(*a, **k):
            raise OSError("network down")
        meinet.weather._get = boom
        try:
            stderr = sys.stderr
            sys.stderr = open(os.devnull, "w")
            try:
                self.assertFalse(st.fetch_weather())
                self.assertFalse(st.fetch_maps())
                self.assertFalse(st.fetch_cities())
            finally:
                sys.stderr.close()
                sys.stderr = stderr
        finally:
            meinet.weather._get = old_get
        v, rows = st.pages[0x0401]
        self.assertEqual(v, v_before + 1)                  # the stale flag changed the page
        self.assertEqual(rows[0][15] & pg.FLAG_STALE, pg.FLAG_STALE)
        self.assertEqual(rows[0][22:31], b"\x08New York")  # the last data is still sent
        self.assertEqual(st.pages[0x3401][1][0][3] & pg.FLAG_STALE, pg.FLAG_STALE)
        cities = pg.decode_cities(b"".join(st.pages[0x4401][1]))
        self.assertTrue(all(c[4] & pg.FLAG_STALE for c in cities))
        idx = st.pages[pg.INDEX_PAGE][1]
        self.assertEqual(idx[0][2] & 2, 2)

    def test_no_data_yet(self):
        st = meinet.Station(meinet.load_config(None))
        with st.lock:
            st.rebuild()
        self.assertEqual(list(st.pages), [pg.INDEX_PAGE])
        self.assertEqual(st.pages[pg.INDEX_PAGE][1][0][0], 0)   # no entries
        car = meinet.Carousel(st)
        sec = car.second(fixture.START)
        rx = wire.Receiver()
        rx.feed(sec)
        self.assertEqual(rx.ok, 15)
        self.assertTrue(rx.complete(pg.TIME_PAGE) and rx.complete(pg.INDEX_PAGE))


if __name__ == "__main__":
    unittest.main()
