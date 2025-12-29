from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Allow running directly via: `python examples/lcds_manual_test.py`
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from py_hd44780_i2c_pcf8574 import HD44780_PCF8574, LCDS, LCDSConfig, VARIANT_A, VARIANT_B, VARIANT_C
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


def _ask_yes_no(prompt: str) -> bool:
    while True:
        ans = input(f"{prompt} [Y/N]: ").strip().lower()
        if ans in {"y", "yes"}:
            return True
        if ans in {"n", "no"}:
            return False
        print("Please answer Y or N.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Manual (interactive) test for LCDS (buffered puts/flush) on HD44780 via PCF8574 (MCP2221A)"
    )
    parser.add_argument("--address", default="0x3F", help="PCF8574 7-bit I2C address (default: 0x3F)")
    parser.add_argument("--scan", action="store_true", help="Scan I2C and use the first responding address")
    parser.add_argument(
        "--variant",
        choices=["A", "B", "C"],
        default="A",
        help="PCF8574->HD44780 pin mapping variant (default: A)",
    )
    parser.add_argument("--cols", type=int, default=16, help="LCD columns (default: 16)")
    parser.add_argument("--rows", type=int, default=2, help="LCD rows (default: 2)")
    parser.add_argument(
        "--no-dynamic",
        action="store_true",
        help="Disable dynamic CGRAM charset (Polish letters will fall back to ASCII)",
    )
    parser.add_argument(
        "--skip-diff-test",
        action="store_true",
        help="Skip the visual 'minimal diff flush' test (flicker/stability check)",
    )
    args = parser.parse_args()

    if args.rows < 1 or args.cols < 1:
        raise SystemExit("cols/rows must be >= 1")

    address_7bit = int(args.address, 0)
    mapping = {"A": VARIANT_A, "B": VARIANT_B, "C": VARIANT_C}[args.variant]

    i2c = MCP2221AI2C(i2c_speed_hz=100_000).open()
    if args.scan:
        found = _scan_i2c(i2c)
        if not found:
            raise SystemExit("No I2C devices found during scan")
        address_7bit = found[0]
        print(f"Using I2C address 0x{address_7bit:02X} (first found)")

    lcd = HD44780_PCF8574(
        i2c=i2c,
        mapping=mapping,
        config=HD44780Config(cols=args.cols, rows=args.rows, address_7bit=address_7bit),
    )
    lcd.init()

    cfg = LCDSConfig(cols=args.cols, rows=args.rows, use_dynamic_chars=(not args.no_dynamic))
    scr = LCDS(lcd, config=cfg)

    print("This test checks LCDS.puts() + LCDS.flush() behavior step-by-step.")
    print("Important: LCDS.puts() is line-oriented:")
    print("- It clears ONLY the current line at the beginning of each call")
    print("- It remembers the current line between calls")
    print("- Column wraps modulo width (long lines overwrite from col 0)")
    input("Press Enter to continue...")

    failures: list[str] = []

    def check(step_name: str, expected_lines: list[str]) -> None:
        print(f"\n--- {step_name} ---")
        print("Expected on LCD (conceptually):")
        print("\n".join(expected_lines))
        ok = _ask_yes_no("Do you see exactly this (or the described effect)?")
        if not ok:
            failures.append(step_name)

    def clear_and_flush() -> None:
        scr.clear()
        scr.flush()
        time.sleep(0.2)

    # 1) clear
    clear_and_flush()
    check("Clear + flush", ["(All rows blank)"])

    # 2) simple puts on initial line (line=0)
    scr.puts("LCDS TEST")
    scr.flush()
    time.sleep(0.2)
    check("puts('LCDS TEST')", ["LCDS TEST (row 0)", "(row 1 unchanged / blank)"])

    # 3) overwrite same line (still line=0 because no newline)
    scr.puts("1234567890123456")
    scr.flush()
    time.sleep(0.2)
    check("puts(16 chars)", ["1234567890123456", "(row 1 unchanged)"])

    # 4) column wrap modulo width (18 chars on 16 cols overwrites col0/1)
    if args.cols >= 4:
        text = "ABCDEFGHIJKLMNOPQR"  # 18 chars
        # Expected for cols=16: QR + CDEFGHIJKLMNOP
        if args.cols == 16:
            expected0 = "QR" + "CDEFGHIJKLMNOP"
        else:
            # Generic explanation for other widths
            expected0 = "(Long line wraps: last 2 chars overwrite col0/1)"
        scr.puts(text)
        scr.flush()
        time.sleep(0.2)
        check("puts() wrap modulo width", [expected0, "(row 1 unchanged)"])

    # 5) newline writes into next row and updates remembered line
    if args.rows >= 2:
        scr.puts("L0-A\nL1-ABCDEFG")
        scr.flush()
        time.sleep(0.2)
        check("puts('L0-A\\nL1-...')", ["L0-A", "L1-ABCDEFG"])

        # Now remembered line is 1, so next call clears row 1 (not row 0)
        scr.puts("ZZZ")
        scr.flush()
        time.sleep(0.2)
        check(
            "puts('ZZZ') clears remembered row",
            ["Row 0 should still start with L0-A", "Row 1 should now start with ZZZ"],
        )

        # Newline at start: clears current row (row 1), then jumps to row 0 and writes there.
        scr.puts("\nTOP")
        scr.flush()
        time.sleep(0.2)
        check(
            "puts('\\nTOP') wraps row",
            ["Row 0 should start with TOP", "Row 1 should be cleared (spaces)"] ,
        )

    # 6) write_at should not clear line
    clear_and_flush()
    scr.write_at(5, 0, "X")
    scr.flush()
    time.sleep(0.2)
    check("write_at(5,0,'X')", ["Row 0: X at col 5", "(other cells blank)"])

    # 7) dynamic characters (optional)
    clear_and_flush()
    demo = "Zażółć\ngęślą"
    scr.puts(demo)
    scr.flush()
    time.sleep(0.2)
    if args.no_dynamic:
        check(
            "Polish chars (dynamic disabled)",
            ["Should be readable ASCII fallback", "(no custom glyphs)"],
        )
    else:
        check(
            "Polish chars (dynamic enabled)",
            ["Zażółć", "gęślą"],
        )

    # 8) minimal diff flush (visual stability / no full-screen redraw)
    if not args.skip_diff_test:
        clear_and_flush()

        # Fill all rows with a stable pattern so any unintended redraw/flicker is noticeable.
        # Use distinct rows to make row jumps obvious.
        for r in range(args.rows):
            fill = ("ABCDEFGHIJKLMNOPQRSTUVWXYZ" if (r % 2) == 0 else "0123456789")
            line = (fill * ((args.cols // len(fill)) + 1))[: args.cols]
            scr.write_at(0, r, line)
        scr.flush()
        time.sleep(0.2)

        target_row = min(0, args.rows - 1)
        target_col = max(0, min(args.cols - 1, args.cols // 2))

        # Blink/toggle a single cell a few times.
        for i in range(20):
            scr.write_at(target_col, target_row, "#" if (i % 2) == 0 else " ")
            scr.flush()
            time.sleep(0.12)

        check(
            "flush() minimal diff (stability)",
            [
                f"Only one cell should toggle at row {target_row}, col {target_col}.",
                "The rest of the screen should stay stable (no noticeable full redraw / flicker).",
            ],
        )

    print("\n=== Result ===")
    if failures:
        print("FAILED steps:")
        for name in failures:
            print(f"- {name}")
        raise SystemExit(1)

    print("All steps passed.")


if __name__ == "__main__":
    main()
