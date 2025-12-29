from __future__ import annotations

import sys
from pathlib import Path

# Allow running directly via: `python examples/i2c_scan.py`
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from py_hd44780_i2c_pcf8574.mcp2221a_i2c import MCP2221AI2C


def main() -> None:
    i2c = MCP2221AI2C(i2c_speed_hz=100_000).open()

    found: list[int] = []
    for addr in range(0x03, 0x78):
        try:
            # Prefer read: doesn't toggle PCF8574 output latch.
            i2c.i2c_read(addr, 1)
            found.append(addr)
        except Exception:
            pass

    if not found:
        print("No I2C devices found.")
        return

    print("Found I2C devices:")
    for addr in found:
        print(f"- 0x{addr:02X}")


if __name__ == "__main__":
    main()
