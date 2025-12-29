from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running directly via: `python examples/file_head_to_lcd.py <file>`
# and also works when frozen with PyInstaller.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if not getattr(sys, "frozen", False):
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

# NOTE: Hardware-specific imports are intentionally delayed until runtime,
# so `--dry-run` can work on machines without MCP2221A / hidapi.


def _scan_i2c(i2c) -> list[int]:
    found: list[int] = []
    for addr in range(0x03, 0x78):
        try:
            i2c.i2c_read(addr, 1)
            found.append(addr)
        except Exception:
            pass
    return found


def _render_head(text: str, cols: int, rows: int) -> list[str]:
    """Render preview for an LCD.

    Goal: show the first `rows` lines of the file (not wrapped), each truncated/padded to `cols`.
    """

    # Normalize line endings and whitespace for a tiny LCD.
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\t", " ")

    lines = text.split("\n")

    def clean_line(s: str) -> str:
        # Drop other control chars, keep printable.
        return "".join(ch for ch in s if ord(ch) >= 32)

    out_lines: list[str] = []
    for i in range(max(0, rows)):
        s = clean_line(lines[i]) if i < len(lines) else ""
        s = (s[:cols]).ljust(cols)
        out_lines.append(s)

    if not out_lines:
        out_lines = ["".ljust(cols) for _ in range(max(0, rows))]
    return out_lines


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Show the beginning of a text file on HD44780 via PCF8574 (MCP2221A)."
    )
    parser.add_argument(
        "file",
        nargs="?",
        help="Path to a text file (drag&drop onto the .exe supplies this)",
    )
    parser.add_argument("--address", default="0x3F", help="PCF8574 7-bit I2C address (default: 0x3F)")
    parser.add_argument("--scan", action="store_true", help="Scan I2C and use first responding address")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Render to console only (do not access MCP2221A / LCD)",
    )
    parser.add_argument(
        "--variant",
        choices=["A", "B", "C"],
        default="A",
        help="PCF8574->HD44780 pin mapping variant (default: A)",
    )
    parser.add_argument(
        "--encoding",
        default="utf-8",
        help="File encoding (default: utf-8). Invalid bytes are replaced.",
    )
    parser.add_argument(
        "--max-bytes",
        type=int,
        default=4096,
        help="Read at most this many bytes from the file start (default: 4096)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print rendered lines and LCDS buffer to console",
    )
    parser.add_argument(
        "--pause",
        action="store_true",
        help="Wait for Enter before exiting (useful when launched by drag&drop)",
    )
    args = parser.parse_args()

    if not args.file:
        raise SystemExit("No file provided. Drag-and-drop a file onto the exe, or pass a path.")

    file_path = Path(args.file)
    if not file_path.exists() or not file_path.is_file():
        raise SystemExit(f"Not a file: {file_path}")

    raw = file_path.read_bytes()[: max(0, args.max_bytes)]
    text = raw.decode(args.encoding, errors="replace")

    # Dry run: render without talking to hardware.
    if args.dry_run:
        cols, rows = 16, 2
        lines = _render_head(text, cols, rows)
        print(f"File: {file_path}")
        print(f"Virtual LCD geometry: {cols}x{rows}")
        for i, line in enumerate(lines):
            print(f"Rendered line{i + 1}: {line!r}")
        if args.pause:
            try:
                input("Press Enter to exit...")
            except EOFError:
                pass
        return

    address_7bit = int(args.address, 0)

    from py_hd44780_i2c_pcf8574 import HD44780_PCF8574, LCDS, VARIANT_A, VARIANT_B, VARIANT_C
    from py_hd44780_i2c_pcf8574.lcdx import HD44780Config
    from py_hd44780_i2c_pcf8574.mcp2221a_i2c import MCP2221AI2C

    mapping = {"A": VARIANT_A, "B": VARIANT_B, "C": VARIANT_C}[args.variant]

    i2c = MCP2221AI2C(i2c_speed_hz=100_000).open()
    if args.scan:
        found = _scan_i2c(i2c)
        if not found:
            raise SystemExit("No I2C devices found during scan")
        address_7bit = found[0]

    lcd = HD44780_PCF8574(i2c=i2c, mapping=mapping, config=HD44780Config(address_7bit=address_7bit))
    lcd.init()

    scr = LCDS(lcd)

    lines = _render_head(text, scr.cols, scr.rows)
    if args.debug:
        print(f"File: {file_path}")
        print(f"LCD geometry: {scr.cols}x{scr.rows}")
        for i, line in enumerate(lines):
            print(f"Rendered line{i + 1}: {line!r}")

    scr.clear()
    for row, line in enumerate(lines):
        scr.write_at(0, row, line)

    if args.debug:
        for row in range(scr.rows):
            start = row * scr.cols
            end = start + scr.cols
            buf_line = "".join(scr._buf[start:end])
            print(f"LCDS buffer line{row + 1}: {buf_line!r}")

    scr.flush()

    if args.pause:
        try:
            input("Press Enter to exit...")
        except EOFError:
            pass


if __name__ == "__main__":
    main()
