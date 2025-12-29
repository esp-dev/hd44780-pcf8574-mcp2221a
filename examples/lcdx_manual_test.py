from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Allow running directly via: `python examples/lcdx_manual_test.py`
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from py_hd44780_i2c_pcf8574 import HD44780_PCF8574, VARIANT_A, VARIANT_B, VARIANT_C
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
        description="Manual (interactive) test for lcdx-style API on HD44780 via PCF8574 (MCP2221A)"
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
        "--skip-cursor-tests",
        action="store_true",
        help="Skip curon/curoff visual checks (some modules disable cursor in hardware)",
    )
    args = parser.parse_args()

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

    print("This test will display a sequence of patterns on the LCD.")
    print("After each step, answer Y/N whether the LCD matches the expected text.")
    input("Press Enter to continue...")

    failures: list[str] = []

    def check(step_name: str, expected: str) -> None:
        print(f"\n--- {step_name} ---")
        print("Expected on LCD:")
        print(expected)
        ok = _ask_yes_no("Do you see exactly this?")
        if not ok:
            failures.append(step_name)

    # 1) init + clear
    lcd.init()
    lcd.clear()
    time.sleep(0.2)
    check("Clear screen", "(Both lines should be blank)")

    # 2) line1/line2 + str
    lcd.line1()
    lcd.str("LINE1 OK")
    lcd.line2()
    lcd.str("LINE2 OK")
    time.sleep(0.2)
    check("line1/line2 + str", "LINE1 OK\nLINE2 OK")

    # 3) gotoxy positioning
    lcd.clear()
    lcd.gotoxy(0, 0)
    lcd.str("POS")
    lcd.gotoxy(7, 1)
    lcd.str("X")
    time.sleep(0.2)
    check("gotoxy", "Row0 col0: POS\nRow1 col7: X")

    # 4) hex + dec
    lcd.clear()
    lcd.line1()
    lcd.str("HEX=")
    lcd.hex(0x5A)
    lcd.line2()
    lcd.str("DEC=")
    lcd.dec(1234)
    time.sleep(0.2)
    check("hex + dec", "HEX=5A\nDEC=1234")

    # 5) back (backspace)
    lcd.clear()
    lcd.line1()
    lcd.str("AB")
    lcd.back()
    time.sleep(0.2)
    check("back", "Should show: 'A ' (A then space) on line 1")

    # 6) curon / curoff
    if not args.skip_cursor_tests:
        lcd.clear()
        lcd.gotoxy(0, 0)
        lcd.str("CURSOR")
        # Put cursor at a predictable location: immediately after "CURSOR".
        # On HD44780 this will usually look like: "CURSOR<SP>_" (underline on an empty cell).
        cursor_col = min(len("CURSOR"), args.cols - 1)
        lcd.gotoxy(cursor_col, 0)
        lcd.curon()
        time.sleep(0.2)
        check(
            "curon",
            "Cursor should be visible at row 0 right after 'CURSOR' (typically looks like CURSOR<SP>_)",
        )

        lcd.curoff()
        time.sleep(0.2)
        check(
            "curoff",
            "Cursor should NOT be visible now (text remains)",
        )

    # 7) Row mapping sanity for multi-row displays (especially 20x4)
    if args.rows >= 2:
        lcd.clear()

        # Mark each row with a label at column 0
        for r in range(args.rows):
            lcd.gotoxy(0, r)
            lcd.str(f"R{r}")

        time.sleep(0.2)
        check(
            "Row mapping (R0..Rn labels)",
            "Each physical LCD row should start with R0 / R1 / R2 / R3 ...",
        )

    # 8) Iterator boundary crossing via data_it (wrap col -> next row)
    if args.rows >= 2 and args.cols >= 4:
        lcd.clear()
        lcd.gotoxy(args.cols - 2, 0)
        lcd.str("ABCD")
        time.sleep(0.2)
        check(
            "Iterator boundary (row0 -> row1)",
            f"Row0 last-1/last should show 'AB', row1 col0/1 should show 'CD' (cols={args.cols})",
        )

    if args.rows >= 3 and args.cols >= 4:
        lcd.clear()
        lcd.gotoxy(args.cols - 2, 1)
        lcd.str("WXYZ")
        time.sleep(0.2)
        check(
            "Iterator boundary (row1 -> row2)",
            f"Row1 last-1/last should show 'WX', row2 col0/1 should show 'YZ' (cols={args.cols})",
        )

    if args.rows >= 4 and args.cols >= 4:
        lcd.clear()
        lcd.gotoxy(args.cols - 2, 2)
        lcd.str("1234")
        time.sleep(0.2)
        check(
            "Iterator boundary (row2 -> row3)",
            f"Row2 last-1/last should show '12', row3 col0/1 should show '34' (cols={args.cols})",
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
