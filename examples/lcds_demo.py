from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Allow running directly via: `python examples/lcds_demo.py`
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from py_hd44780_i2c_pcf8574 import HD44780_PCF8574, LCDS, VARIANT_A, VARIANT_B, VARIANT_C
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
    parser = argparse.ArgumentParser(description="lcds-like buffered refresh demo")
    parser.add_argument("--address", default="0x3F", help="PCF8574 7-bit I2C address (default: 0x3F)")
    parser.add_argument("--scan", action="store_true", help="Scan I2C and use first responding address")
    parser.add_argument(
        "--backlight",
        choices=["on", "off", "toggle"],
        default=None,
        help="Set backlight state (on/off) or blink once (toggle) after init",
    )
    parser.add_argument(
        "--seconds",
        type=float,
        default=None,
        help="Run demo for N seconds and exit (default: run forever)",
    )
    parser.add_argument(
        "--variant",
        choices=["A", "B", "C"],
        default="A",
        help="PCF8574->HD44780 pin mapping variant (default: A)",
    )
    args = parser.parse_args()

    address_7bit = int(args.address, 0)

    i2c = MCP2221AI2C(i2c_speed_hz=100_000).open()
    if args.scan:
        found = _scan_i2c(i2c)
        if not found:
            raise SystemExit("No I2C devices found during scan")
        address_7bit = found[0]
        print(f"Using I2C address 0x{address_7bit:02X} (first found)")

    mapping = {"A": VARIANT_A, "B": VARIANT_B, "C": VARIANT_C}[args.variant]
    lcd = HD44780_PCF8574(i2c=i2c, mapping=mapping)
    lcd._cfg.address_7bit = address_7bit  # keep demo simple
    lcd.init()

    if args.backlight == "on":
        lcd.set_backlight(True)
    elif args.backlight == "off":
        lcd.set_backlight(False)
    elif args.backlight == "toggle":
        before = bool(getattr(lcd, "_backlight_on", True))
        lcd.set_backlight(not before)
        time.sleep(0.25)
        lcd.set_backlight(before)

    scr = LCDS(lcd)

    # NOTE: `LCDS.puts()` is line-oriented and clears only the current line
    # at the beginning of each call.
    # it remembers the current line between calls and clears only that line.
    # For a stable "dashboard"-style demo, use `write_at()` for each row.

    start = time.time()
    end = (start + float(args.seconds)) if args.seconds is not None else None

    try:
        while end is None or time.time() < end:
            t = int(time.time() - start)
            scr.write_at(0, 0, "LCDS buffer demo".ljust(scr.cols)[: scr.cols])
            if scr.rows > 1:
                scr.write_at(0, 1, f"sec={t:04d}".ljust(scr.cols)[: scr.cols])
            scr.flush()
            time.sleep(0.2)
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    main()
