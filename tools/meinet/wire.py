"""MeiNet wire format (docs/BROADCAST.md): packets, Hamming 8/4, CRC-16, and a reference
receiver used by the tests."""

SYNC = b"\x55\xA7"
PACKET = 64
PAYLOAD = 52
ROW_BYTES = PAYLOAD
MAX_ROWS = 64
FILL_PAGE = 0xFFF
EPOCH_2000 = 946684800          # Unix time of 2000-01-01 00:00:00 UTC


def hamming84_encode(nibble):
    d1, d2, d3, d4 = (nibble >> 0) & 1, (nibble >> 1) & 1, (nibble >> 2) & 1, (nibble >> 3) & 1
    p1 = 1 ^ d1 ^ d3 ^ d4
    p2 = 1 ^ d1 ^ d2 ^ d4
    p3 = 1 ^ d1 ^ d2 ^ d3
    p4 = 1 ^ p1 ^ d1 ^ p2 ^ d2 ^ p3 ^ d3 ^ d4
    return p1 | d1 << 1 | p2 << 2 | d2 << 3 | p3 << 4 | d3 << 5 | p4 << 6 | d4 << 7


HAMMING = [hamming84_encode(n) for n in range(16)]


def _build_decode():
    table = []
    for b in range(256):
        best = min(range(16), key=lambda n: bin(b ^ HAMMING[n]).count("1"))
        dist = bin(b ^ HAMMING[best]).count("1")
        table.append((best, dist) if dist <= 1 else (-1, 2))
    return table


HAMMING_DECODE = _build_decode()     # byte -> (nibble or -1, errors 0/1/2)


def crc16(data, crc=0xFFFF):
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def header_word(page_id, row, last, version):
    return (page_id & 0xFFFF) | (row & 63) << 16 | (1 << 23 if last else 0) | (version & 0xFF) << 24


def packet(page_id, row, last, version, payload):
    """One 64-byte packet. page_id = kind << 12 | page."""
    assert len(payload) <= PAYLOAD
    payload = bytes(payload) + bytes(PAYLOAD - len(payload))
    h = header_word(page_id, row, last, version)
    hb = h.to_bytes(4, "little")
    c = crc16(hb + payload)
    coded = bytes(HAMMING[(h >> (4 * i)) & 15] for i in range(8))
    return SYNC + coded + payload + c.to_bytes(2, "little")


def filler():
    return packet(FILL_PAGE, 0, True, 0, b"")


def decode_packet(p):
    """Returns (header word, payload, corrected) or None if the packet is bad (sync not
    checked here)."""
    h = 0
    corrected = False
    for i in range(8):
        n, e = HAMMING_DECODE[p[2 + i]]
        if n < 0:
            return None
        corrected |= e == 1
        h |= n << (4 * i)
    payload = bytes(p[10:62])
    if crc16(h.to_bytes(4, "little") + payload) != p[62] | p[63] << 8:
        return None
    return h, payload, corrected


class Receiver:
    """A Python model of the console's decoder (packet layer and page assembly), for tests
    and for checking recordings: feed bytes, read .pages[page_id] = (version, rows dict, count)."""

    def __init__(self):
        self.buf = bytearray()
        self.locked = False
        self.misses = 0
        self.ok = self.fixed = self.dropped = 0
        self.pages = {}
        self.log = []          # (byte offset of the sync, header word) of every accepted packet
        self.pos = 0           # stream offset of buf[0]

    def _accept(self, h, payload):
        pid, row, last, ver = h & 0xFFFF, (h >> 16) & 63, (h >> 23) & 1, h >> 24
        self.log.append((self.pos, h))
        if pid & 0xFFF == FILL_PAGE:
            return
        cur = self.pages.get(pid)
        if cur is None or cur[0] != ver:
            cur = (ver, {}, [0])
            self.pages[pid] = cur
        cur[1][row] = payload
        if last:
            cur[2][0] = row + 1

    def complete(self, pid):
        p = self.pages.get(pid)
        return p is not None and p[2][0] > 0 and all(r in p[1] for r in range(p[2][0]))

    def page_bytes(self, pid):
        p = self.pages[pid]
        return b"".join(p[1][r] for r in range(p[2][0]))

    def _shift(self, n):
        del self.buf[:n]
        self.pos += n

    def feed(self, data):
        self.buf += data
        while True:
            if not self.locked:
                i = self.buf.find(SYNC)
                if i < 0:
                    keep = 1 if self.buf[-1:] == b"\x55" else 0
                    self._shift(len(self.buf) - keep)
                    return
                self._shift(i)
                if len(self.buf) < PACKET:
                    return
                r = decode_packet(self.buf[:PACKET])
                if r:
                    self.ok += 1
                    self.fixed += r[2]
                    self.locked, self.misses = True, 0
                    self._accept(r[0], r[1])
                    self._shift(PACKET)
                else:
                    self._shift(1)
            else:
                if len(self.buf) < PACKET:
                    return
                sync_err = bin(self.buf[0] ^ 0x55).count("1") + bin(self.buf[1] ^ 0xA7).count("1")
                r = decode_packet(self.buf[:PACKET]) if sync_err <= 2 else None
                if r:
                    self.ok += 1
                    self.fixed += r[2]
                    self.misses = 0
                    self._accept(r[0], r[1])
                    self._shift(PACKET)
                    continue
                self.dropped += 1
                self.misses += 1
                if sync_err > 2 or self.misses >= 4:
                    self.locked = False
                    self._shift(1)
                else:
                    self._shift(PACKET)


def add_noise(data, ber, rng):
    """Invert each bit with probability ber (rng: random.Random)."""
    if ber <= 0:
        return bytes(data)
    out = bytearray(data)
    nbits = len(out) * 8
    # geometric skipping: the gap to the next flipped bit
    import math
    pos = -1
    lg = math.log(1.0 - ber) if ber < 1 else None
    while True:
        if lg is None:
            pos += 1
        else:
            pos += 1 + int(math.log(1.0 - rng.random()) / lg)
        if pos >= nbits:
            break
        out[pos >> 3] ^= 1 << (pos & 7)
    return bytes(out)
