from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running directly via: `python examples/print_lcd.py ...`
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from py_hd44780_i2c_pcf8574 import HD44780_PCF8574, LCDS, VARIANT_A, VARIANT_B, VARIANT_C
from py_hd44780_i2c_pcf8574.lcdx import HD44780Config
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


def _maybe_unescape(text: str) -> str:
    # Optional convenience for shells: allows passing "Line1\\nLine2".
    # Keep it conservative: only a few common escapes.
    return (
        text.replace("\\\\", "\\")
        .replace("\\n", "\n")
        .replace("\\r", "\r")
        .replace("\\t", "\t")
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Print text on HD44780 via PCF8574 (MCP2221A)")
    parser.add_argument("text", help="Text to display (use literal newlines or pass --unescape with \\n)")
    parser.add_argument("--address", default="0x3F", help="PCF8574 7-bit I2C address (default: 0x3F)")
    parser.add_argument("--scan", action="store_true", help="Scan I2C and use first responding address")
    parser.add_argument(
        "--variant",
        choices=["A", "B", "C"],
        default="A",
        help="PCF8574->HD44780 pin mapping variant (default: A)",
    )
    parser.add_argument(
        "--unescape",
        action="store_true",
        help=r"Interpret \\n, \\r, \\t and \\\\ in the input text",
    )
    args = parser.parse_args()

    text = _maybe_unescape(args.text) if args.unescape else args.text

    address_7bit = int(args.address, 0)
    mapping = {"A": VARIANT_A, "B": VARIANT_B, "C": VARIANT_C}[args.variant]

    i2c = MCP2221AI2C(i2c_speed_hz=100_000).open()
    if args.scan:
        found = _scan_i2c(i2c)
        if not found:
            raise SystemExit("No I2C devices found during scan")
        address_7bit = found[0]
        print(f"Using I2C address 0x{address_7bit:02X} (first found)")

    lcd = HD44780_PCF8574(i2c=i2c, mapping=mapping, config=HD44780Config(address_7bit=address_7bit))
    lcd.init()

    scr = LCDS(lcd)

    # Simple behavior: clear and write text line-based.
    scr.clear()
    scr.puts(text)
    scr.flush()


if __name__ == "__main__":
    main()
