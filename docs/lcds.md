# `lcds`: buffered screen + diff refresh

`LCDS` is a small helper that keeps a full-screen RAM buffer and updates the physical HD44780 display by writing only the cells that changed.

It is designed for efficient refresh on slow links (I2C via PCF8574), and for building stable “dashboard-style” UIs.

For wiring and the MCP2221A adapter setup, see: [docs/wiring.md](wiring.md)

## Quick start

```python
from py_hd44780_i2c_pcf8574 import HD44780_PCF8574, LCDS, VARIANT_A
from py_hd44780_i2c_pcf8574.mcp2221a_i2c import MCP2221AI2C

i2c = MCP2221AI2C(i2c_speed_hz=100_000).open()

lcd = HD44780_PCF8574(i2c=i2c, mapping=VARIANT_A)
lcd._cfg.address_7bit = 0x3F
lcd.init()

scr = LCDS(lcd)

scr.clear()  # clears the RAM buffer (not the physical LCD)
scr.write_at(0, 0, "Hello")
scr.write_at(0, 1, "World")
scr.flush()  # pushes only changed cells
```

## `LCDSConfig`

- `cols` / `rows`: screen size
- `use_dynamic_chars` (default: `True`)

If you set `use_dynamic_chars=False`, all non-ASCII/non-ROM-friendly characters will be written as best-effort byte codes or fallbacks.

## Buffer operations

### Properties

- `cols` / `rows`

### `clear()`

Clears the in-memory buffer to spaces.

Note: this does not send the HD44780 clear command. Call `flush()` afterwards to update the physical display.

### `clear_line(row)`

Sets the given buffer row to spaces.

### `write_at(col, row, text)`

Writes `text` into the buffer starting at `(col, row)`.

Rules:

- `row` must be in range; otherwise it does nothing.
- `col < 0` is clamped to `0`.
- `col >= cols` does nothing.
- The text is truncated to the available space on the row.

This is the recommended API for building stable multi-line screens.

## `puts(text)`: line-based write (specific semantics)

`puts()` is a convenience method for line-oriented printing.

Semantics (exact):

- It remembers only the **current line** between calls.
- At the **beginning of each call**, it clears **only that current line**.
- Each call starts writing at **column 0**.
- For each `\n`:
  - move to the next line (`(line + 1) % rows`)
  - reset column to `0`
  - it does **not** clear the new line
- When the column reaches `cols`, it wraps **within the same line** using modulo (`col = (col + 1) % cols`).

Practical consequences:

- `puts()` is great for “single-line status updates” where clearing that one line per call is desired.
- For stable dashboards where each row is independent, prefer `write_at()` per row and then `flush()`.

## `flush()`: diff refresh

`flush()` compares the buffer with a shadow copy and updates only changed cells.

Behavior highlights:

- First `flush()` forces a full screen write (shadow is initialized to a different value).
- Cursor positioning is minimized, but it will explicitly call `set_cursor()` when:
  - a character write is not adjacent to the last write
  - the write crosses a row boundary (HD44780 DDRAM rows are not linearly mapped)
  - a CGRAM character was (re)programmed, which changes the LCD’s internal address state

### Dynamic characters (CGRAM)

HD44780 has only 8 custom character slots (CGRAM locations 0..7). `LCDS` can map selected Unicode characters to those slots dynamically.

- Default dynamic charset includes (among others): Polish letters `ą ć ę ł ń ó ś ź ż`, some symbols, and a CGRAM backslash (`\\`) for ROMs that show `¥` instead of `\\`.
- Each mapped character has a fallback `alt` character used when no CGRAM slot can be allocated.
- When all 8 slots are in use, `flush()` frees one slot in a round-robin manner *before* handling the next changed cell.

Useful methods:

- `reset_dynamic_chars()` clears the dynamic mapping state (slots will be reallocated on subsequent `flush()` calls).

## Typical UI patterns

### Dashboard (recommended)

Update each row explicitly:

```python
scr.write_at(0, 0, f"Temp {t:4.1f}C".ljust(scr.cols)[:scr.cols])
scr.write_at(0, 1, f"RPM  {rpm:5d}".ljust(scr.cols)[:scr.cols])
scr.flush()
```

### Simple line printing

```python
scr.clear()
scr.puts("Line1\nLine2")
scr.flush()
```

## Scope

- `LCDS` is deliberately not a terminal emulator. It does not parse VT100/ANSI escape sequences.
- It focuses on predictable buffering and efficient refresh.
