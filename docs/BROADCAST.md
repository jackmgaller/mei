# Broadcast

Mei can receive a **data broadcast**, in the spirit of Teletext and the Satellaview: a one-way
signal that repeats a loop of pages (a *carousel*) forever. There is no uplink. A receiver
tunes in at any moment, picks out the pages it wants as they go by, and assembles each one
from its rows. The service, **MeiNet**, carries the time and US weather: current conditions,
a 5-day forecast, a 24-hour forecast and a temperature map per region.

The console has a **broadcast decoder chip**, modelled on Teletext decoders such as the
SAA5246. It finds packets in the byte stream, corrects and checks them, and assembles up to
eight selected pages in its own page memory. It works on its own: it costs the CPU nothing,
and a cart only reads registers and copies finished pages into RAM. Carts that want the raw
bytes can read them from a FIFO instead.

On the host, a gateway (`tools/meinet/`) fetches the weather from Open-Meteo, encodes the
pages, runs the carousel and serves the byte stream over TCP. The desktop player tunes in to
it; the headless runner replays a recording; the web build has no signal.

## The signal

| | |
|---|---|
| Rate | 9,600 baud: 960 bytes per second, exactly **16 bytes per 60 Hz tick** |
| Unit | 64-byte packets, sent back to back: 15 packets per second, one per 4 ticks |
| Errors | none on a clean line; an optional bit-error rate can be added (noise) |
| Carrier | present while a signal is being received (a gateway is connected, or a recording plays) |

The line carries bytes only; there is no framing below the packet. Bytes may arrive in
bursts or with gaps (the live socket does that), which only shifts when packets complete.

**Noise.** The player, the headless runner and the gateway can each add a bit-error rate:
every bit of the stream is inverted independently with that probability. It is off by
default. The console's own noise is deterministic (see [Determinism](#determinism)).

## Packets

Every packet is 64 bytes:

| Bytes | Contents |
|---|---|
| 0–1 | sync word `55 A7` |
| 2–9 | header: a 32-bit word *H*, sent as eight Hamming 8/4 bytes, one per nibble |
| 10–61 | payload, 52 bytes |
| 62–63 | CRC-16 of *H* and the payload, low byte first |

Byte 2 + *i* carries nibble *i* of *H* (bits 4*i* to 4*i* + 3), so byte 2 holds bits 0–3.

**The header word** *H*:

| Bits | Field |
|---|---|
| 0–11 | page number, `0x000`–`0xFFF` |
| 12–15 | kind, 0–15: which of a page number's sub-pages this is |
| 16–21 | row, 0–63 |
| 22 | reserved, sent as 0 |
| 23 | last: this is the page's final row (the page has *row* + 1 rows) |
| 24–31 | version, 0–255 |

The low 16 bits (kind and page number) form the **page id**, which is how carts name a page:
`0x0401` is page `0x401` kind 0, `0x3401` is page `0x401` kind 3. Page ids are written in
hexadecimal with the kind as the first digit. Each page id is a page in its own right, with its
own rows, version, completeness and changed flag: Chicago's current conditions (`0x0403`) can
be complete while its map (`0x3403`) is still arriving, and the decoder, the registers and the
standard library all work per page id.

*Why a 52-byte payload.* A 4-byte header becomes 8 bytes once each nibble is Hamming coded.
Keeping packets at 64 bytes keeps them aligned to ticks (4 ticks each) and to seconds (15 per
second), which the time page relies on, so the payload is 64 − 2 − 8 − 2 = 52 bytes.

### Hamming 8/4

Each header nibble is sent as one byte of the Hamming 8/4 code used by Teletext (ETS 300 706,
§8.2). With data bits D1–D4 (D1 = the nibble's bit 0) and protection bits P1–P4:

```
P1 = 1 ^ D1 ^ D3 ^ D4
P2 = 1 ^ D1 ^ D2 ^ D4
P3 = 1 ^ D1 ^ D2 ^ D3
P4 = 1 ^ P1 ^ D1 ^ P2 ^ D2 ^ P3 ^ D3 ^ D4       (odd parity over all eight bits)
byte = P1 | D1<<1 | P2<<2 | D2<<3 | P3<<4 | D3<<5 | P4<<6 | D4<<7
```

| Nibble | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | A | B | C | D | E | F |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Byte | `15` | `02` | `49` | `5E` | `64` | `73` | `38` | `2F` | `D0` | `C7` | `8C` | `9B` | `A1` | `B6` | `FD` | `EA` |

The 16 code bytes differ pairwise in at least 4 bits. A received byte is decoded by its
distance to them: distance 0 is the nibble; distance 1 (one bit flipped, 128 of the 256 byte
values) is **corrected** to the one code byte that close; distance 2 (the other 112 values) is
a **detected double error** and the packet is dropped. Three or more errors can decode to a
wrong nibble; the CRC catches that.

### CRC

CRC-16/CCITT (also called CRC-16/CCITT-FALSE): polynomial `0x1021`
(x¹⁶ + x¹² + x⁵ + 1), initial value `0xFFFF`, bits processed most significant first, no
reflection, no final XOR. The check value of the ASCII string `123456789` is `0x29B1`.

It covers 56 bytes: the four bytes of the **decoded** header word *H*, low byte first, then
the 52 payload bytes. The result is sent in bytes 62–63, low byte first. A packet whose CRC
does not match is dropped.

```
crc = 0xFFFF
for each byte b:
    crc ^= b << 8
    repeat 8 times: crc = (crc & 0x8000) ? ((crc << 1) ^ 0x1021) & 0xFFFF : (crc << 1) & 0xFFFF
```

### Receiving

A receiver is either **hunting** or **locked**.

- **Hunting.** It searches the stream byte by byte for `55 A7`, then decodes the 64 bytes that
  start there. If the header decodes and the CRC matches, the packet is accepted and the
  receiver locks. Otherwise the search resumes at the byte after that `55`, so a sync word
  that happens to appear inside a payload costs nothing. Failed candidates while hunting are
  not counted.
- **Locked.** It takes the next 64 bytes as the next packet (a flywheel). The sync word may
  have up to 2 bits wrong. A packet that fails (header or CRC) is counted as dropped and the
  receiver stays locked; after 4 failures in a row, or a sync word with more than 2 bits wrong
  (also counted as dropped), it falls back to hunting from the second byte of that packet.
- Losing the carrier, or turning the receiver off, ends the lock and discards a partial
  packet.

## Pages and the carousel

A page is a run of rows, 0 to *n* − 1, at most 64. Each row is one packet, so a page holds up
to 64 × 52 = 3,328 bytes. The receiver knows a page's length once it has seen the row marked
*last*. Rows may arrive in any order and over several passes of the loop; a page is
**complete** when every row from 0 to the last has arrived with the same version.

**Versions.** Each page has an 8-bit version, 1–255, that the gateway increments whenever the
page's contents change, wrapping from 255 to 1 (the index uses 0 for "not on air"; only the
time page, whose version is its time's low byte, uses 0). Two versions alias only after 255
changes, about two and a half days of 15-minute refreshes. Rows of the same version are identical every time they
are sent, so a receiver that already has a complete page ignores them. When a row with a
different version arrives, the receiver starts the page again from empty. Carts therefore
copy a page out when it completes with a new version, and otherwise leave it alone.

### Page numbers

| Page | Kinds | Contents |
|---|---|---|
| `0x000`–`0x0FF` | | reserved |
| `0x100` | 0 | [time](#time-page-0x100) |
| `0x101` | 0 | [index](#index-page-0x101) |
| `0x102`–`0x3FF` | | reserved for other services |
| `0x400` | 0–3 | weather for the **home city** (set in the gateway's config; not sent when unset) |
| `0x401`–`0x408` | 0–3 | weather for the eight US regions below |
| `0x409`–`0x4FE` | 0–3 | further regions, if the gateway config adds them |
| `0x4FF` | 3 | national map of the contiguous United States |
| `0x500`–`0xFFE` | | reserved |
| `0xFFF` | any | filler: receivers ignore it |

Weather pages are `0x4RR`, where RR is the region number. Their kinds:

| Kind | Page id | Contents | Rows |
|---|---|---|---|
| 0 | `0x04RR` | [current conditions](#current-conditions-kind-0) | 1 |
| 1 | `0x14RR` | [5-day forecast](#5-day-forecast-kind-1) | 1 |
| 2 | `0x24RR` | [24-hour forecast](#24-hour-forecast-kind-2) | 2 |
| 3 | `0x34RR` | [temperature map](#map-kind-3) | 49 |

The regions, each with one representative city:

| Page | Region | City | City lat, lon | Map box: south–north, west–east |
|---|---|---|---|---|
| `0x401` | Northeast | New York | 40.71, −74.01 | 37.0–47.5, −80.5 to −67.0 |
| `0x402` | Southeast | Atlanta | 33.75, −84.39 | 25.0–37.0, −91.5 to −75.5 |
| `0x403` | Midwest | Chicago | 41.88, −87.63 | 36.0–49.5, −97.5 to −80.5 |
| `0x404` | South | Dallas | 32.78, −96.80 | 25.5–37.0, −106.5 to −88.5 |
| `0x405` | Mountain | Denver | 39.74, −104.99 | 37.0–49.0, −117.0 to −102.0 |
| `0x406` | Southwest | Phoenix | 33.45, −112.07 | 31.3–37.0, −120.0 to −103.0 |
| `0x407` | West | Los Angeles | 34.05, −118.24 | 32.5–42.0, −124.5 to −114.0 |
| `0x408` | Pacific NW | Seattle | 47.61, −122.33 | 42.0–49.0, −124.8 to −111.0 |
| `0x4FF` | United States | — | 39.0, −96.0 | 24.5–49.5, −125.0 to −66.5 |

The home city's map box is 2.5° of latitude and 3.5° of longitude either side of it.

### The schedule

The carousel is built from 1-second frames of 15 packets.

- **Packet 0 of every second is the time page.** The gateway starts its stream on a whole
  second, so the time page's sync word begins exactly on each second.
- The other 14 packets of each second carry the **loop**: 280 packets, 20 seconds. The loop is
  four 5-second quarters (70 packets each). Every quarter starts with the index page and then
  every region's current conditions. The first quarter adds every region's 5-day forecast and
  the second every 24-hour forecast. The rest of each quarter carries map rows.
- Maps go out one after another, each from its header row to its last row, so a map paints top
  to bottom; the map sequence carries on across quarters and loops. With the home city, eight
  regions and the national map, a loop carries about 3.5 maps, and every map comes round in
  about a minute.
- Packets nothing else needs are filler (page `0xFFF`).

So in 20 seconds a receiver sees the time 20 times, the index and each current-conditions
page 4 times, each forecast once, and about a third of the maps. A page's rows are taken from
one snapshot of its data, made when the page is scheduled (for a map, when its header row is
scheduled), so a refresh never mixes versions within one pass.

## Field types

All multi-byte values are little-endian. Fields are placed at offsets that are multiples of
their size, so the layouts below map straight onto Akari structs.

| Type | Encoding | Unknown |
|---|---|---|
| time | u32, seconds since 2000-01-01 00:00:00 UTC (Unix time − 946,684,800) | 0 |
| date | u16, days since 2000-01-01 | 0 |
| temperature | s8, half degrees Celsius: −64.0 to +63.5 °C (−40 °F to 146 °F) | −128 (`0x80`) |
| wind direction | u8, 256ths of a circle clockwise from north, the direction the wind blows **from** | 255 |
| wind speed | u8, km/h (clamped to 254) | 255 |
| pressure | u16, mean sea-level hPa × 10 − 9,000 (1013.2 hPa = 1132) | `0xFFFF` |
| percentage | u8, 0–100 (humidity, chance of precipitation, cloud cover) | 255 |
| conditions | u8, WMO weather code (the [Open-Meteo subset](#weather-codes)) | 255 |
| UTC offset | s8, 15-minute steps (−5 h = −20) | |
| name | *n* bytes: a length byte, then the text, NUL-padded; at most *n* − 2 characters, so the text at offset 1 is always NUL-terminated | length 0 |

Text is printable ASCII, upper and lower case.

## Payloads

### Time page (`0x100`)

One row. The time is true at the first byte of the packet's sync word. The gateway sends it
in the first packet of every second, and its version is the low 8 bits of the time, so it
changes every second.

| Offset | Type | Field |
|---|---|---|
| +0 | u32 | time: seconds since 2000-01-01 00:00:00 UTC |
| +4 | s8 | UTC offset of local time, in 15-minute steps (includes daylight saving) |
| +5 | u8 | flags: bit 0 daylight saving in effect; bit 1 the local time zone is the home city's (otherwise the gateway host's) |
| +6 | u16 | local year |
| +8 | u8 | local month, 1–12 |
| +9 | u8 | local day, 1–31 |
| +10 | u8 | local weekday, 0 = Sunday |
| +11 | u8 | local hour, 0–23 |
| +12 | u8 | local minute |
| +13 | u8 | local second |
| +14 | name, 8 | time zone abbreviation, e.g. `CDT` |
| +22 | 30 | reserved, 0 |

The local fields are the UTC time plus the offset, given so carts need no calendar code.

### Index page (`0x101`)

Row 0 is a header and rows 1 to *n* are one entry each. The index lists every weather page on
air with its versions, so a cart can watch the index alone and fetch only what changed.

Header (row 0):

| Offset | Type | Field |
|---|---|---|
| +0 | u8 | number of entries, *n* |
| +1 | u8 | format, 1 |
| +2 | u8 | flags: bit 0 a home city is set; bit 1 some data is stale |
| +3 | u8 | reserved |
| +4 | time | when the newest weather data was fetched |
| +8 | name, 16 | service name, `MEINET WEATHER` |
| +24 | 28 | reserved |

Entry (rows 1 to *n*, in page order):

| Offset | Type | Field |
|---|---|---|
| +0 | u16 | page number, `0x4RR` |
| +2 | u8 | kinds on air: bit *k* set when kind *k* is being sent |
| +3 | u8 | flags: bit 0 the home city; bit 1 stale; bit 2 national (no city) |
| +4 | 4 × u8 | the current version of kinds 0–3 (0 when not on air) |
| +8 | s16 | city latitude, hundredths of a degree (north positive) |
| +10 | s16 | city longitude, hundredths of a degree (east positive) |
| +12 | 4 × s16 | map box: south, north, west, east, hundredths of a degree |
| +20 | name, 16 | region name, e.g. `Pacific NW` (`Home` for `0x400`) |
| +36 | name, 16 | city name, e.g. `Seattle` (empty for the national map) |

### Current conditions (kind 0)

One row.

| Offset | Type | Field |
|---|---|---|
| +0 | time | observation time |
| +4 | temperature | temperature |
| +5 | temperature | apparent ("feels like") temperature |
| +6 | percentage | relative humidity |
| +7 | conditions | weather code |
| +8 | wind direction | wind direction |
| +9 | wind speed | wind speed (10 m) |
| +10 | wind speed | gusts |
| +11 | percentage | cloud cover |
| +12 | pressure | pressure |
| +14 | u8 | precipitation in the last hour, 0.1 mm (max 25.4 mm; 255 unknown) |
| +15 | u8 | flags: bit 0 daytime; bit 1 stale |
| +16 | temperature | today's high |
| +17 | temperature | today's low |
| +18 | percentage | today's chance of precipitation |
| +19 | u8 | today's maximum UV index × 10 (255 unknown) |
| +20 | s8 | the city's UTC offset, 15-minute steps |
| +21 | u8 | reserved |
| +22 | name, 16 | city name |
| +38 | u16 | sunrise, minutes after local midnight (`0xFFFF` none) |
| +40 | u16 | sunset, minutes after local midnight (`0xFFFF` none) |
| +42 | 10 | reserved |

**Stale** means the gateway could not refresh this data and is still sending the last data it
got (see [Failures](#failures)).

### 5-day forecast (kind 1)

One row: today and the next four days, local dates.

| Offset | Type | Field |
|---|---|---|
| +0 | date | local date of day 0 (today) |
| +2 | u8 | number of days, 5 |
| +3 | u8 | flags: bit 1 stale |
| +4 | 5 × 8 | days 0–4, below |
| +44 | s8 | the city's UTC offset, 15-minute steps |
| +45 | 7 | reserved |

Each day:

| Offset | Type | Field |
|---|---|---|
| +0 | conditions | the day's weather code |
| +1 | temperature | high |
| +2 | temperature | low |
| +3 | percentage | chance of precipitation |
| +4 | u8 | precipitation total, whole mm (max 254; 255 unknown) |
| +5 | wind speed | maximum wind speed |
| +6 | wind direction | dominant wind direction |
| +7 | u8 | weekday, 0 = Sunday |

### 24-hour forecast (kind 2)

Two rows (104 bytes): the current hour and the 23 after it.

| Offset | Type | Field |
|---|---|---|
| +0 | time | start of the first hour |
| +4 | u8 | number of hours, 24 |
| +5 | u8 | local hour of the first entry, 0–23 |
| +6 | u8 | flags: bit 1 stale |
| +7 | s8 | the city's UTC offset, 15-minute steps |
| +8 | 24 × 4 | hours 0–23: temperature, conditions, chance of precipitation (percentage), wind speed |

Row 0 holds bytes 0–51 (the header and hours 0–10), row 1 bytes 52–103 (hours 11–23).

### Map (kind 3)

A 64 × 48 grid of **bands** 0–15, 4 bits each, covering the map box. Row 0 is the header and
rows 1–48 are grid rows 0–47, top (north) to bottom, one per packet. The grid is
equirectangular: cell (*x*, *y*) is centred at longitude west + (*x* + ½) × (east − west) ÷ 64
and latitude north − (*y* + ½) × (north − south) ÷ 48.

Header (row 0):

| Offset | Type | Field |
|---|---|---|
| +0 | u8 | layer: 0 = temperature (the only layer so far) |
| +1 | u8 | width, 64 |
| +2 | u8 | height, 48 |
| +3 | u8 | flags: bit 1 stale |
| +4 | time | when the data was fetched |
| +8 | 4 × s16 | box: north, south, west, east, hundredths of a degree |
| +16 | temperature | band base |
| +17 | u8 | band step, half degrees |
| +18 | 2 | reserved |
| +20 | name, 16 | map name (the region's) |
| +36 | 16 | reserved |

Band *b* covers base + *b* × step up to base + (*b* + 1) × step, except that band 0 also holds
everything colder and band 15 everything warmer: band = clamp(⌊(t − base) ÷ step⌋, 0, 15).
The national map uses base −20 °C and step 4 °C. A region's map uses the smallest step of 1,
2, 3, 4 or 5 °C whose 16 bands cover its range, with the base a multiple of the step, so its
bands show detail; carts should draw the legend from the header.

**Grid rows.** Each of rows 1–48 starts with a mode byte:

| Mode | Bytes after it |
|---|---|
| 0, raw | 32 bytes: 64 bands, two per byte, the low nibble the left (even) column |
| 1, runs | runs of bands |
| 2, delta runs | runs of differences from the previous grid row: d = (band − above) & 15, where *above* is the band in the same column one row up |

A run is one byte: bits 4–7 are the run length − 1 (1–16 cells) and bits 0–3 the value. Runs
cover the 64 columns exactly; bytes after them are padding (0) and are ignored. The gateway
picks the shortest form for each row, and prefers modes 0 or 1 when they are no longer.
Decoding mode 2 needs the decoded row above it.

**Key rows.** Grid rows 0, 8, 16, 24, 32 and 40 are never delta coded. A row lost to noise
then spoils at most the delta-coded rows below it up to the next key row (at most 7), until it
comes round again, instead of the rest of the map. Since a grid row always fits a packet
(raw is 33 bytes), compression does not change a map's airtime: every map is 49 packets
whatever its contents. What it buys is room: a compressed row leaves the rest of its payload
free for future use, and the key rows cost only bytes that would be padding anyway. Measured on
the test recording's nine maps (432 grid rows): raw 14,256 bytes, runs only 9,374, delta runs
everywhere 7,222, and with key rows 7,429 (2.9 % more than delta everywhere).

The data comes from a coarse grid of points sampled from Open-Meteo across the whole country
and upsampled bilinearly by the gateway, so maps show broad patterns, not local detail.

### Weather codes

The conditions byte is a WMO code as Open-Meteo reports it. The standard library maps it to an
icon class:

| Codes | Meaning | Icon class |
|---|---|---|
| 0 | clear | `BC_ICON_CLEAR` 0 |
| 1, 2 | mainly clear, partly cloudy | `BC_ICON_PARTLY` 1 |
| 3 | overcast | `BC_ICON_CLOUDY` 2 |
| 45, 48 | fog, rime fog | `BC_ICON_FOG` 3 |
| 51, 53, 55, 56, 57 | drizzle, freezing drizzle | `BC_ICON_DRIZZLE` 4 |
| 61, 63, 65, 66, 67 | rain, freezing rain | `BC_ICON_RAIN` 5 |
| 80, 81, 82 | rain showers | `BC_ICON_SHOWERS` 6 |
| 71, 73, 75, 77, 85, 86 | snow, snow grains, snow showers | `BC_ICON_SNOW` 7 |
| 95, 96, 99 | thunderstorm (with hail) | `BC_ICON_THUNDER` 8 |
| anything else | | `BC_ICON_UNKNOWN` 9 |

Whether to draw a sun or a moon for clear and partly cloudy is up to the cart (current
conditions carry a daytime flag).

## The decoder

### Registers (`0xFF0600`)

The I/O region grows to `0xFF0000`–`0xFF06FF`. All registers are 32-bit and accessed with
`lw`/`sw`; the usual rules apply (other widths fault *Bad I/O width*, writing a read-only
register faults *Read-only write*, and `0xFF0648`–`0xFF06FF` faults *Unmapped address*).

| Offset | Name | Access | Purpose |
|---|---|---|---|
| +00 | `BC_CTRL` | Read/write | bit 0 receiver on; bit 1 raw FIFO capture. Other bits read 0 |
| +04 | `BC_STATUS` | Read | bit 0 carrier; bit 1 locked; bit 2 FIFO overflowed; bits 8–15 page complete, slots 0–7; bits 16–23 page changed, slots 0–7 |
| +08 | `BC_CMD` | Write | run a command (below) |
| +0C | `BC_RESULT` | Read | error of the last command |
| +10 | `BC_SLOT` | Read/write | the slot, 0–7, that `BC_PAGE`…`BC_STAMP` and the page commands use |
| +14 | `BC_PAGE` | Read/write | the slot's page id. Writing 0–`0xFFFF` selects that page and clears the slot; writing a value with bit 31 set frees the slot. Reads `0xFFFFFFFF` when free |
| +18 | `BC_PSTAT` | Read | the slot's page status (below) |
| +1C | `BC_ROWS0` | Read | bit *r*: row *r* (0–31) has arrived |
| +20 | `BC_ROWS1` | Read | bit *r*: row 32 + *r* has arrived |
| +24 | `BC_STAMP` | Read | the `FRAME` value of the tick in which the sync word of the slot's most recent row began |
| +28 | `BC_BUF` | Read/write | RAM address for copies |
| +2C | `BC_LEN` | Read/write | length for copies; commands write back the bytes copied |
| +30 | `BC_ROW` | Read/write | row number for `READ_ROW` |
| +34 | `BC_OK` | Read | packets accepted |
| +38 | `BC_FIXED` | Read | accepted packets that needed a header correction |
| +3C | `BC_DROPPED` | Read | packets lost while locked |
| +40 | `BC_FIFO` | Read | raw mode: bits 0–7 the next byte and bit 8 set, or 0 when the FIFO is empty |
| +44 | `BC_FIFO_LEVEL` | Read | raw mode: bytes waiting in the FIFO |

`BC_PSTAT`:

| Bits | Meaning |
|---|---|
| 0 | complete: every row up to the last has arrived, all with the same version |
| 1 | changed: complete, and not read with `READ_PAGE` since it completed |
| 2 | on air: at least one row has arrived since the page was selected |
| 8–15 | version of the rows in the slot |
| 16–23 | rows that have arrived |
| 24–31 | the page's row count, or 0 until its last row has arrived |

Commands (written to `BC_CMD`; each completes at once and sets `BC_RESULT`):

| Code | Command | Effect |
|---|---|---|
| 1 | `READ_PAGE` | Copy the slot's page to `BC_BUF`: row count × 52 bytes (64 × 52 while the count is unknown), at most `BC_LEN`. Rows that have not arrived read as zeros. `BC_LEN` = bytes copied. Clears the changed flag |
| 2 | `READ_ROW` | Copy row `BC_ROW` of the slot's page (52 bytes, at most `BC_LEN`) to `BC_BUF`; `BC_LEN` = bytes copied. Error 4 if the row has not arrived |
| 3 | `READ_FIFO` | Copy up to `BC_LEN` bytes from the FIFO to `BC_BUF`; `BC_LEN` = bytes copied. Clears the overflow flag |
| 4 | `CLEAR_COUNTERS` | Set `BC_OK`, `BC_FIXED` and `BC_DROPPED` to 0 |

Errors (`BC_RESULT`): 0 none, 1 bad command, 2 bad address (the destination must lie in RAM),
3 the slot is free, 4 the row has not arrived.

### Behaviour

- **Reset** turns the receiver off, frees every slot, clears the counters and empties the FIFO.
  The signal itself carries on: a broadcast is not rewound by a reset. Nothing changes for a
  cart that never turns the receiver on.
- **Timing.** During each tick the line delivers up to 16 bytes. The decoder takes them at the
  end of the tick, after the CPU, so their effects are visible from the next tick. A packet
  completes in the tick its 64th byte arrives.
- **Selecting.** Writing `BC_PAGE` empties the slot (rows, version, flags and memory) and makes
  it collect that page. Two slots may select the same page. A slot keeps one copy of its page:
  when rows of a new version arrive, the slot is emptied and assembly starts again, so copy a
  page out when it changes if the old version is still needed.
- **Page memory**: eight slots of 64 rows × 52 bytes (26 KB). A row is stored for every slot
  whose page id matches the packet's; filler packets and unselected pages are only counted.
- **Changed** is set when a page completes and cleared by `READ_PAGE`, by a new version
  starting, and by selecting. `BC_STATUS` bits 16–23 mirror it for all slots.
- **Counters** are 32-bit and wrap. `BC_OK` counts every accepted packet (also filler and
  unselected pages); `BC_FIXED` counts the accepted ones with at least one corrected header
  nibble; `BC_DROPPED` counts packets lost while locked (see [Receiving](#receiving)).
- **Raw mode.** While `BC_CTRL` bit 1 is set (and the receiver is on), every byte received,
  after noise, also goes into a 1,024-byte FIFO, whatever the packet decoder does with it.
  When the FIFO is full new bytes are lost and the overflow flag is set. Setting bit 1 empties
  the FIFO. A cart reading 16 bytes a tick keeps up.
- **Receiver off** (`BC_CTRL` bit 0 clear): incoming bytes are ignored and the lock is lost;
  slots and their pages are kept. **No carrier** has the same effect.
- Copies cost the CPU nothing, like the memory card controller's.

## Standard library (`broadcast.akr`)

Part of the prelude. Pages are named by page id (`BC_MAP | 0x401`).

| | |
|---|---|
| `bc_select(page) -> s32` | collect a page: returns its slot (an existing one if already selected) or −1 when all 8 are in use. Turns the receiver on |
| `bc_release(page)` | free its slot |
| `bc_ready(page) -> bool` | complete |
| `bc_changed(page) -> bool` | complete and not yet read |
| `bc_read(page, buf: *u8) -> s32` | copy a complete page into `buf` and clear changed; returns its length in bytes, or 0 if it is not complete or not selected. `buf` must hold `bc_rows(page) * 52` bytes (`BC_PAGE_MAX` = 3,328 always does) |
| `bc_read_row(page, row, buf: *u8) -> bool` | copy one 52-byte row if it has arrived |
| `bc_row_ready(page, row) -> bool`, `bc_rows(page) -> s32` | has a row arrived; the page's row count (0 until known) |
| `bc_version(page) -> s32` | version of the rows held, or −1 before any has arrived |
| `bc_stamp(page) -> u32` | `FRAME` when the sync of its latest row began |
| `bc_on()`, `bc_off()` | receiver power (`bc_select` turns it on) |
| `bc_carrier() -> bool`, `bc_locked() -> bool` | signal present; receiver locked |
| `bc_packets_ok() -> u32`, `bc_packets_fixed() -> u32`, `bc_packets_dropped() -> u32`, `bc_clear_counters()` | the counters |
| `bc_signal() -> s32` | signal bars, 0–4: 0 no carrier, 1 carrier but not locked, 2–4 by the share of packets dropped since the counters were last cleared (4: under 1 %, 3: under 10 %) |
| `bc_time(t: *BcTime) -> bool` | the latest time page (selects page `0x100` when needed); false until it has arrived |
| `bc_now() -> u32` | seconds since 2000 UTC now: the time page plus the ticks since its sync ÷ 60; 0 until known |
| `bc_local_now() -> u32` | the same in local time (plus the UTC offset) |
| `bc_datetime(secs: u32, out: *BcDateTime)` | split seconds since 2000 into year, month, day, weekday, hour, minute, second |
| `bc_icon(code) -> s32`, `bc_wmo_text(code) -> *u8` | icon class of a weather code; a short description (`"Rain"`) |
| `bc_temp_c(t) -> s32`, `bc_temp_f(t) -> s32`, `bc_temp_fixed(t) -> fixed` | a half-degree temperature in whole °C or °F (rounded), or as `fixed` °C |
| `bc_pressure(p) -> fixed` | hPa |
| `bc_compass(dir) -> *u8` | 16-point compass name (`"NNE"`) |
| `bc_name(field: *u8) -> *u8` | the text of a name field |
| `bc_map_decode(map: *BcMap, bands: *u8) -> bool` | decode a whole map page into 64 × 48 bytes, one band per byte; false on a malformed row |
| `bc_map_row(row: *u8, above: *u8, out: *u8) -> bool` | decode one grid row (the 52 bytes of page row *y* + 1) given the decoded row above (`null` for the top row), for painting as rows arrive |
| `bc_raw(on: bool)`, `bc_raw_level() -> s32`, `bc_raw_byte() -> s32`, `bc_raw_read(buf: *u8, max) -> s32` | raw FIFO: turn capture on or off, bytes waiting, the next byte (−1 when empty), copy out up to `max` bytes |
| `bc_hamming(b) -> s32`, `bc_crc16(crc: u32, p: *u8, n) -> u32` | for decoding raw packets: a Hamming 8/4 byte's nibble (−1 for a double error); the CRC-16 of `n` bytes continuing from `crc` (start with `0xFFFF`) |

Structures for the payloads, matching the tables above field for field: `BcTime`,
`BcIndexHeader`, `BcIndexEntry`, `BcIndex` (header and 63 entries), `BcCurrent`, `BcDay`,
`BcDaily`, `BcHour`, `BcHourly`, `BcMapHeader`, `BcMap` (header and 48 rows of 52 bytes), and
`BcDateTime`. Constants: `BC_TIME_PAGE`, `BC_INDEX_PAGE`, `BC_HOME` (`0x400`),
`BC_NATIONAL` (`0x4FF`), the kinds `BC_CURRENT` (`0x0000`), `BC_DAILY` (`0x1000`),
`BC_HOURLY` (`0x2000`), `BC_MAP` (`0x3000`), `BC_ROW_BYTES` (52), `BC_PAGE_MAX` (3,328),
`BC_TEMP_UNKNOWN` (−128), the `BC_ICON_*` classes and the registers.

```
var now: BcCurrent

fn init() { bc_select(BC_CURRENT | 0x403) }        // Chicago

fn update() {
    if bc_changed(BC_CURRENT | 0x403) { bc_read(BC_CURRENT | 0x403, &now) }
}

fn draw() {
    if bc_version(BC_CURRENT | 0x403) < 0 { text(8, 8, "Tuning...", WHITE); return }
    text(8, 8, bc_name(&now.city[0]), WHITE)
    text_int(8, 20, bc_temp_f(now.temp), WHITE)
}
```

## The gateway (`tools/meinet/`)

`tools/meinet/meinet.py` runs the service on the host. Python 3 standard library only.

```
python3 tools/meinet/meinet.py                      # live: fetch weather, serve on 127.0.0.1:9600
python3 tools/meinet/meinet.py --record out.bin     # ... and save the stream
python3 tools/meinet/meinet.py --fixture            # canned data and a fixed clock, no network
python3 tools/meinet/meinet.py --fixture --no-serve --seconds 64 --record stream.bin
```

| Option | |
|---|---|
| `--config FILE` | config file (default `tools/meinet/meinet.conf`; built-in defaults if it is missing) |
| `--port N`, `--host ADDR` | where to listen (default `127.0.0.1:9600`) |
| `--record FILE` | write every byte sent to `FILE` |
| `--seconds N` | stop after N seconds of stream |
| `--fixture` | use canned data (`fixture.py`) and start the clock at 2026-09-30 18:00:00 UTC; the data is "refreshed" once, 40 seconds in, so versions change |
| `--no-serve` | don't listen or pace in real time: generate `--seconds` of stream as fast as possible (needs `--record`) |
| `--noise BER` | invert each bit with this probability before sending (default 0) |
| `-v` | log fetches and clients |

### Config

`tools/meinet/meinet.conf` is the user's own file and is not in git;
`tools/meinet/meinet.example.conf` is the template. Copy it and edit:

```
[meinet]
home = Portland, Oregon     ; the home city, page 0x400 (empty: none)
port = 9600
refresh_minutes = 15
map_refresh_minutes = 180
noise = 0
```

| Key | Default | |
|---|---|---|
| `home` | empty | home city name, looked up with Open-Meteo's geocoding API. `City, Qualifier` narrows the match (`Portland, Oregon`, `Paris, France`): the first result whose state, region or country contains the qualifier wins |
| `home_lat`, `home_lon`, `home_name` | | skip the lookup and use these |
| `host`, `port` | `127.0.0.1`, `9600` | listening address |
| `refresh_minutes` | 15 | how often current conditions and forecasts are fetched |
| `map_refresh_minutes` | 180 | how often the map grid is fetched |
| `map_grid` | `30x14` | the coarse national grid, columns × rows (420 points) |
| `noise` | 0 | bit-error rate added to the stream |
| `[regions]` | the eight above | `N = Region; City; lat; lon; south; north; west; east` replaces or adds region N (1–254) |

The time page uses the home city's time zone, or the host's when no home city is set.

### Data

From `api.open-meteo.com/v1/forecast` (free, no key): one request for every city's current
conditions, daily and hourly forecasts (`timeformat=unixtime`, `timezone=auto`), and the map
grid in batches of 100 points (`current=temperature_2m`). Region and home maps are cut from
the national grid when they lie inside it (otherwise the home map gets its own 8 × 6 grid),
bilinearly upsampled to 64 × 48 and quantised to bands. With the defaults this is about 6,000
location-requests a day, inside Open-Meteo's free allowance.

A page's version is incremented whenever its encoded bytes change; the index carries every
weather page's version, so it changes with each refresh.

### Failures

If a fetch fails (no network, an HTTP error, bad JSON), the gateway keeps sending the last data
it has with the stale flag set (which changes the pages, so their versions change), retries
after 2 minutes, and clears the flag when a fetch succeeds. Before the first successful fetch,
no weather pages are on air: the time and index pages still go out, and the index lists no
entries. The time page never depends on the network.

### TCP protocol

The gateway listens on `127.0.0.1:9600` (configurable) and sends each client the raw byte
stream, nothing else: no handshake, no framing, and nothing is read from the client. A client
that connects mid-packet simply hunts for the next sync word. The stream is paced to the wall
clock: 16 bytes every 1/60 second, starting on a whole second with that second's time page.
All clients receive the same bytes. A client that falls more than 2 seconds behind is
disconnected. `nc 127.0.0.1 9600 | xxd` shows the stream.

A recording (`--record`) is exactly the bytes of the stream from the gateway's first byte, so
it starts with a time page on a whole second.

## Platforms

| Platform | Signal |
|---|---|
| Desktop (`mei`) | Connects to the gateway with a non-blocking socket. `--broadcast HOST:PORT` (default `127.0.0.1:9600`), `--no-broadcast`, `--broadcast-noise BER`. Without a gateway it reports no carrier and quietly retries every 3 seconds. Each tick it passes up to 16 received bytes to the core; if more than half a second of bytes has built up (after a stall), the oldest are dropped down to 64 |
| Headless (`mei-headless`) | `--broadcast FILE` replays a recording at exactly 16 bytes per tick from tick 0, with the carrier on until the file ends; `--broadcast-noise BER` adds noise |
| Web | No signal: the carrier is always off |

Core API (`mei.h`): `mei_broadcast_carrier(m, on)`, `mei_broadcast_feed(m, bytes, n)` (queues
up to 16 bytes for the current tick and returns how many it took) and
`mei_broadcast_noise(m, errors_per_million_bits, seed)`.

## Determinism

- **Replay is exact.** With `--broadcast FILE`, byte *i* of the file is delivered in tick
  ⌊*i* ÷ 16⌋, so the same cart, input and recording always give the same result.
- **Noise is deterministic.** The core's noise is an xorshift32 generator (the same step as
  `RAND`) seeded by `mei_broadcast_noise` (the runners use seed `0x4D454E4F`). Each delivered
  byte draws 8 numbers, one per bit from bit 0 up, and a bit is inverted when the number
  modulo 1,000,000 is below the rate in errors per million bits. Noise is drawn for every
  delivered byte, whether or not the receiver is on, so it depends only on the stream.
- **The time page is true at the first byte of its sync word.** In a replay of a gateway
  recording the time page of second *s* begins exactly at tick 60 *s*, so `bc_now()` is exact.
  Over the live socket it is approximate: the gateway writes that byte on the second, and it
  reaches the core after the socket's latency, the player's buffering (up to half a second)
  and up to a tick of scheduling, typically within a few tens of milliseconds.
- The OS does not use the broadcast: `SYS_TIME`/`SYS_DATE` still come from the host clock. The
  time page is a data feed for carts.
