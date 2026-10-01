# Memory cards

Mei has two memory card slots. A card is a 128 KB file (`card1.mcd`, `card2.mcd`): 256
blocks of 512 bytes. Block 0 holds the allocation table, so 255 blocks are free for saves.
Carts never see the card as memory. They use a small **card controller** through I/O
registers, which copies whole saves between RAM and the card and enforces that each cart
only touches its own saves. The system ROM can see and manage every save.

## Saves

A save belongs to one cart and has a **save number** (0–15) that the cart chooses, for
example one per save slot in its menu. It holds:

- up to 32,000 bytes of data;
- a title shown in the OS (32 ASCII characters);
- a 16×16 icon of 1–3 frames, 4 bits per pixel, with its own 16-colour palette (colour 0 is
  transparent). The OS loops the frames.

A save uses one header block plus one block per 512 bytes of data, so a small save costs 2
blocks (1 KB).

## Cart IDs

The card controller tells carts apart by the **cart ID** in the cart header: bytes 40–55, up
to 16 ASCII characters, NUL-padded (e.g. `LANTERN-LAKE`). A cart without an ID uses
`T:` + the FNV-1a hash of its title in hex. Changing the ID orphans the cart's old saves.

```
cart "Lantern Lake", "LANTERN-LAKE"          // language
.cart "Lantern Lake", start, "LANTERN-LAKE"  ; assembly
```

## Metadata record

Writes take the title and icon from a 452-byte record in RAM:

| Offset | Size | Field |
|---|---|---|
| +0 | 32 | title, ASCII, NUL-padded |
| +32 | 4 | icon frame count, 1–3 |
| +36 | 32 | palette: 16 colours, 15-bit like the framebuffer |
| +68 | 384 | three 128-byte frames, 16×16 at 4 bits (low nibble = left pixel) |

## Registers (`0xFF0380`)

All 32-bit, accessed with `lw`/`sw`.

| Offset | Name | Access | Purpose |
|---|---|---|---|
| +00 | `CARD_CMD` | Write | Start a command (below) |
| +04 | `CARD_STATUS` | Read | Bit 0 busy. Bits 8–15 the last error. Bits 16–17 card present in slot 1, 2 |
| +08 | `CARD_SLOT` | Read/write | 0 = card 1, 1 = card 2 |
| +0C | `CARD_SAVE` | Read/write | Save number (0–15), or a save handle for system commands |
| +10 | `CARD_BUF` | Read/write | RAM address of the data buffer |
| +14 | `CARD_LEN` | Read/write | Data length in bytes; commands that report a length write it back here |
| +18 | `CARD_META` | Read/write | RAM address of a metadata record |
| +1C | `CARD_RESULT` | Read | Command result (see each command) |

Commands for every cart:

| Code | Command | Effect |
|---|---|---|
| 1 | `STAT` | Does this cart's save `CARD_SAVE` exist? `CARD_RESULT` = 1/0, `CARD_LEN` = its data length |
| 2 | `READ` | Copy the save's data into `CARD_BUF` (at most `CARD_LEN` bytes); `CARD_LEN` = bytes read. If `CARD_META` ≠ 0, also fill the metadata record there |
| 3 | `WRITE` | Create or replace the save with `CARD_LEN` bytes from `CARD_BUF` and the metadata at `CARD_META`. Replacing is atomic: the old save survives if the new one doesn't fit |
| 4 | `DELETE` | Delete the save |
| 5 | `FREE` | `CARD_RESULT` = free blocks on the card |
| 6 | `LIST_MINE` | `CARD_RESULT` = a bitmask of which save numbers this cart has |

System commands (the system ROM only; other carts get *Not allowed*):

| Code | Command | Effect |
|---|---|---|
| 16 | `LIST` | Write a 64-byte entry per save into `CARD_BUF` (at most `CARD_LEN` / 64 entries): cart ID (16), title (32), save number (4), blocks (4), data length (4), handle (4). `CARD_RESULT` = number of saves |
| 17 | `META_ANY` | Fill the metadata record at `CARD_META` for handle `CARD_SAVE` |
| 18 | `DELETE_ANY` | Delete the save with handle `CARD_SAVE` |
| 19 | `COPY_ANY` | Copy the save with handle `CARD_SAVE` to the other slot's card (replacing that cart's save with the same number there) |
| 20 | `FORMAT` | Erase the card |

Errors (`CARD_STATUS` bits 8–15): 0 none, 1 no card, 2 not found, 3 card full, 4 bad
address or length, 5 not allowed, 6 bad command, 7 busy.

## Timing

A command takes effect when it is written, but the controller then stays busy for a while,
like a real serial card: 2 frames, plus 1 frame per block read, plus 3 frames per block
written. A 1 KB save takes about 8 frames to write. Commands issued while busy fail with
error 7. Games should show "Saving…" until `CARD_STATUS` bit 0 clears, and must not reuse
the buffer before then.

## Card file format

Block 0: `"MEICARD1"` (8 bytes), then a 256-byte allocation table at offset 16, one byte
per block: `0x00` free, `0xFF` last block of a save, `0xFE` block 0 itself, otherwise the
next block of the same save. Byte 272 + *n* / 8 bit *n* % 8 marks block *n* as the first
(header) block of a save.

A save's header block: `"SAVE"`, cart ID (16), save number (4), data length (4),
metadata record (452). Its data follows in the chained blocks.

A file that doesn't start with `"MEICARD1"` is treated as a blank card and formatted on first
write. The platform persists cards when they change: files beside the settings on the
desktop, browser storage on the web.
