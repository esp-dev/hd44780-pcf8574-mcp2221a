from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running this file directly via: `python examples/hello_lcd.py`
# by ensuring the project root (parent of `examples/`) is on sys.path.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from py_hd44780_i2c_pcf8574 import HD44780_PCF8574, VARIANT_A
from py_hd44780_i2c_pcf8574.mcp2221a_i2c import MCP2221AI2C


def _scan_i2c(i2c: MCP2221AI2C) -> list[int]:
    found: list[int] = []
    for addr in range(0x03, 0x78):
        try:
            i2c.i2c_read(addr, 1)
            found.append(addr)
        except Exception:
            pass
    return found


def main() -> None:
    parser = argparse.ArgumentParser(description="HD44780 via PCF8574 over MCP2221A (I2C)")
    parser.add_argument(
        "--address",
        default="0x3F",
        help="PCF8574 7-bit I2C address (default: 0x3F)",
    )
    parser.add_argument(
        "--scan",
        action="store_true",
        help="Scan I2C and use the first responding address",
    )
    args = parser.parse_args()

    address_7bit = int(args.address, 0)

    # MCP2221A via PyMCP2221A, I2C @ 100kHz
    i2c = MCP2221AI2C(i2c_speed_hz=100_000).open()

    if args.scan:
        found = _scan_i2c(i2c)
        if not found:
            raise SystemExit("No I2C devices found during scan")
        address_7bit = found[0]
        print(f"Using I2C address 0x{address_7bit:02X} (first found)")

    lcd = HD44780_PCF8574(
        i2c=i2c,
        mapping=VARIANT_A,  # change to VARIANT_B / VARIANT_C if needed
    )

    # Override address if needed
    lcd._cfg.address_7bit = address_7bit  # intentional: keep example simple

    lcd.init()
    lcd.clear()
    lcd.set_cursor(0, 0)
    lcd.write("HD44780 via I2C")
    lcd.set_cursor(0, 1)
    lcd.write(f"PCF8574 @0x{address_7bit:02X}")


if __name__ == "__main__":
    main()
