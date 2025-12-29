# `lcdx`: HD44780 over PCF8574 (low-level)

This module provides a low-level driver for an HD44780-compatible character LCD connected through a PCF8574 I/O expander (“I2C backpack”). It sends HD44780 commands/data using 4-bit mode via I2C.

For wiring and the MCP2221A adapter setup, see: [docs/wiring.md](wiring.md)

## Main classes

### `HD44780Config`

Configuration used by the driver:

- `cols` (default: `16`)
- `rows` (default: `2`)
- `address_7bit` (default: `0x3F`)
- `i2c_speed_hz` (default: `100_000`)

### `HD44780_PCF8574`

Constructor:

- `HD44780_PCF8574(i2c, mapping, config=None)`
  - `i2c`: an object implementing `I2CDevice` (see `mcp2221a_i2c.py`)
  - `mapping`: a `PinMapping` (see `pins.py`; typically `VARIANT_A`)
  - `config`: optional `HD44780Config`

## Core methods

### Initialization

- `init()`
  - Puts the LCD into 4-bit mode.
  - Clears the display and enables the display.
  - Also enables the backlight by default.

Typical usage:

```python
from py_hd44780_i2c_pcf8574 import HD44780_PCF8574, VARIANT_A
from py_hd44780_i2c_pcf8574.mcp2221a_i2c import MCP2221AI2C

i2c = MCP2221AI2C(i2c_speed_hz=100_000).open()

lcd = HD44780_PCF8574(i2c=i2c, mapping=VARIANT_A)
# Optionally override address (kept explicit in examples)
lcd._cfg.address_7bit = 0x3F

lcd.init()
```

### Display / cursor

- `clear()`
  - Sends the HD44780 clear command (takes ~1.5ms; driver sleeps ~2ms).
- `home()`
  - Cursor home (also ~2ms delay).
- `set_cursor(col, row)`
  - Clamps `col` and `row` to the configured display size.
- `cursor_on(blink=False)`
  - Enables cursor display; optionally blinking.

### Writing

- `command(cmd: int)`
  - Sends an HD44780 command byte.
- `write_char(ch: int)`
  - Sends a data byte (0..255) to DDRAM/CGRAM.
- `write(text: str, encoding="latin-1", errors="replace")`
  - Encodes a Python string and writes each byte.
  - Characters outside 0..255 are replaced (because HD44780 works with bytes).

### Backlight

- `set_backlight(on: bool)`
  - Toggles the backlight using the PCF8574 bit configured as `bl` in `PinMapping`.
  - Polarity is controlled by `PinMapping.bl_active_high`.

If `set_backlight(True)` turns the backlight *off*, use a mapping with `bl_active_high=False`.

### Custom characters (CGRAM)

- `create_char(location: int, pattern: bytes)`
  - `location` must be `0..7`
  - `pattern` must be exactly 8 bytes (5-bit rows)

This programs one of the 8 CGRAM slots.

## Convenience helpers (no `lcd_` prefix)

These are small helpers meant to mirror a simple “embedded-style” API.

- `curon()` / `curoff()`
- `line1()` / `line2()`
- `gotoxy(x, y)`
- `str(text, encoding="latin-1", errors="replace")`
- `str_P(text_or_bytes, encoding="latin-1", errors="replace")`
- `hex(value)` (2 hex digits, 8-bit)
- `dec(value)`

Cursor iterator helpers:

- `data_it(value)` writes a byte and moves “right” using `curright()`.
- `curright()` advances an internal iterator and only calls `set_cursor()` when it wraps to column 0 (relies on the LCD’s automatic address increment within a row).
- `curleft()` moves left with wrap-around and calls `set_cursor()`.
- `up()` / `down()` move between rows.
- `back()` erases the previous character (space + move left).

## Recommended patterns

- For static text, use low-level `set_cursor()` + `write()`.
- For frequently refreshed UIs (dashboards/menus), use the buffered helper `LCDS` (see [docs/lcds.md](lcds.md)).

## Known limitations / scope

- This driver is intentionally minimal: it sends bytes; it does not implement VT100/ANSI parsing.
- The driver assumes 4-bit mode via PCF8574 and typical HD44780 timings.
