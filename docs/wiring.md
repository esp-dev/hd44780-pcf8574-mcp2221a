# Wiring: HD44780 + PCF8574AT via MCP2221A (USB–I2C)

This project drives an HD44780-compatible character LCD in 4-bit mode using a PCF8574 I/O expander over I2C. On the PC side, an MCP2221A USB–I2C adapter is used.

## Hardware used

- **USB–I2C adapter:** MCP2221A running at **5V**.
- **I2C pull-ups:** **5.1kΩ** on **SDA** and **SCL** to 5V.
- **Display module:** HD44780 LCD with a permanently soldered **PCF8574AT** controller (“I2C backpack”). It’s a single integrated unit with no visible manufacturer markings; it looks like the common Arduino-compatible modules widely available online.

## Electrical connections

Minimum connections between the MCP2221A and the LCD+PCF8574AT module:

- **GND (MCP2221A)** → **GND (LCD/PCF)**
- **5V (MCP2221A)** → **VCC (LCD/PCF)**
- **SCL (MCP2221A)** → **SCL (LCD/PCF)**
- **SDA (MCP2221A)** → **SDA (LCD/PCF)**

On most MCP2221A boards and PCF8574 backpacks these signals are labeled directly as `5V`, `GND`, `SCL`, `SDA`.

### Notes about I2C pull-ups

- I2C requires pull-up resistors. This setup uses **5.1kΩ to 5V**.
- Some LCD backpacks also include pull-ups. If both the MCP2221A board and the backpack have pull-ups, the effective resistance may become too low (strong pull-up). It often still works, but if you see unstable I2C communication, consider leaving pull-ups only on one side.

## I2C address

PCF8574 / PCF8574A devices are commonly found at these 7-bit I2C addresses:

- `0x27`
- `0x3F`

This repo often uses `0x3F`.

The easiest way to confirm the address is to run a scan:

- Use [examples/i2c_scan.py](../examples/i2c_scan.py)
- Or pass `--scan` to demos (they pick the first responding address)

## PCF8574 → HD44780 pin mapping (Variant A)

Because **Variant A works**, the backpack wiring between PCF8574 and HD44780 matches this bit mapping:

- `P0 = RS`
- `P1 = RW`
- `P2 = E`
- `P3 = BL` (backlight)
- `P4 = D4`
- `P5 = D5`
- `P6 = D6`
- `P7 = D7`

In Python this is `VARIANT_A` in [py_hd44780_i2c_pcf8574/pins.py](../py_hd44780_i2c_pcf8574/pins.py).

### Backlight (BL)

Backlight control is handled via the PCF8574 `BL` pin. On some backpacks the polarity is inverted (depends on the transistor stage): the symptom is that `set_backlight(True)` turns the backlight off instead of on.

If that happens, use inverted polarity (`bl_active_high=False`) by defining a custom `PinMapping`.

## Quick start (smoke tests)

1. Wire as described above.
2. Scan and run the LCDS demo (auto-picks the I2C address):

   `python .\\examples\\lcds_demo.py --scan --variant A`

3. Backlight test:

   `python .\\examples\\lcds_demo.py --scan --variant A --backlight toggle --seconds 2`

4. Menu demo (keyboard-driven):

   `python .\\examples\\menu_demo.py --scan --variant A`

## Photos

Photos of the module and wiring can be added later (for example under `assets/` or `docs/`).
