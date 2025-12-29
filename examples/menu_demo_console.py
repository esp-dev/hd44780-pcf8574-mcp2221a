from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

# Allow running directly via: `python examples/menu_demo_console.py`
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from py_hd44780_i2c_pcf8574 import (  # noqa: E402
    Edit,
    EnumItem,
    Line,
    LineAction,
    Menu,
    Ok,
    RangeItem,
    SwitchItem,
    TimeItem,
)


def _get_key() -> str:
    """Read one keypress from console.

    Uses msvcrt on Windows. Returns:
    - single character for normal keys
    - '\x1b' for ESC
    - '\r' for ENTER
    - '\b' for BACKSPACE
    - 'UP'/'DOWN'/'LEFT'/'RIGHT' for arrow keys
    """

    try:
        import msvcrt  # type: ignore
    except Exception:
        s = sys.stdin.read(1)
        return s

    ch = msvcrt.getwch()
    if ch in ("\x00", "\xe0"):
        code = msvcrt.getwch()
        return {"H": "UP", "P": "DOWN", "K": "LEFT", "M": "RIGHT"}.get(code, "")
    return ch


def _to_action(key: str) -> int | None:
    if not key:
        return None

    key_l = key.lower()
    if key_l == "w" or key == "UP":
        return int(LineAction.UP)
    if key_l == "s" or key == "DOWN":
        return int(LineAction.DOWN)
    if key_l == "a" or key == "LEFT":
        return int(LineAction.LEFT)
    if key_l == "d" or key == "RIGHT":
        return int(LineAction.RIGHT)

    if key == "\r":
        return int(LineAction.OK)
    if key == "\b":
        return int(LineAction.BREAK)

    if key == "\x1b":
        return None

    if len(key) == 1 and (" " <= key <= "~"):
        return int(LineAction.DIGIT_BASE) + ord(key)

    return None


def _print_frame(lines: list[str], *, title: str = "") -> None:
    if os.name == "nt":
        os.system("cls")
    else:
        os.system("clear")

    cols = max((len(s) for s in lines), default=0)
    if title:
        print(title)

    border = "+" + ("-" * cols) + "+"
    print(border)
    for s in lines:
        print("|" + s.ljust(cols) + "|")
    print(border)


@dataclass(slots=True)
class SubmenuItem:
    label: str
    target: Menu

    line: Line = field(init=False)

    def __post_init__(self) -> None:
        self.line = Line(inh=self, owner=self)

    disable_select: bool = False

    def print(self, line: Line, size: int) -> str:
        return self.label

    def action(self, line: Line, action: int) -> int:
        return int(action)

    def submenu(self, line: Line) -> Menu | None:
        return self.target

    def grab(self, line: Line) -> bool:
        return False


def _build_menu() -> Menu:
    main = Menu("Main")

    main.add_line(SwitchItem("WiFi", select=True).line)
    main.add_line(RangeItem("Vol", min=0, max=10, current=5).line)
    main.add_line(EnumItem("Mode", ["A", "B", "C"]).line)
    main.add_line(TimeItem(h=12, m=34, s=56).line)

    settings = Menu("Settings")

    ed = Edit()
    ed.set("name")
    settings.add_line(ed.line)

    def _commit(_: int) -> None:
        print("Saved")

    settings.add_line(Ok(commit=_commit).line)

    main.add_line(SubmenuItem("Settings...", settings).line)

    return main


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Menu demo rendered to console (mirrors LCD content via Menu.render())"
    )
    parser.add_argument("--cols", type=int, default=16, help="Virtual LCD columns (default: 16)")
    parser.add_argument("--rows", type=int, default=2, help="Virtual LCD rows (default: 2)")
    parser.add_argument(
        "--lcd",
        action="store_true",
        help="Also mirror output to a real LCD via MCP2221A (uses same args as menu_demo.py)",
    )
    parser.add_argument("--address", default="0x3F", help="PCF8574 7-bit I2C address (default: 0x3F)")
    parser.add_argument("--scan", action="store_true", help="Scan I2C and use first responding address")
    parser.add_argument(
        "--variant",
        choices=["A", "B", "C"],
        default="A",
        help="PCF8574->HD44780 pin mapping variant (default: A)",
    )
    args = parser.parse_args()

    cols = max(1, int(args.cols))
    rows = max(1, int(args.rows))

    scr = None
    if args.lcd:
        from py_hd44780_i2c_pcf8574 import (  # noqa: E402
            HD44780_PCF8574,
            LCDS,
            VARIANT_A,
            VARIANT_B,
            VARIANT_C,
        )
        from py_hd44780_i2c_pcf8574.lcdx import HD44780Config  # noqa: E402
        from py_hd44780_i2c_pcf8574.mcp2221a_i2c import MCP2221AI2C  # noqa: E402

        def _scan_i2c(i2c: MCP2221AI2C) -> list[int]:
            found: list[int] = []
            for addr in range(0x03, 0x78):
                try:
                    i2c.i2c_read(addr, 1)
                    found.append(addr)
                except Exception:
                    pass
            return found

        address_7bit = int(args.address, 0)
        i2c = MCP2221AI2C(i2c_speed_hz=100_000).open()
        if args.scan:
            found = _scan_i2c(i2c)
            if not found:
                raise SystemExit("No I2C devices found during scan")
            address_7bit = found[0]
            print(f"Using I2C address 0x{address_7bit:02X} (first found)")

        mapping = {"A": VARIANT_A, "B": VARIANT_B, "C": VARIANT_C}[args.variant]
        lcd = HD44780_PCF8574(i2c=i2c, mapping=mapping, config=HD44780Config(address_7bit=address_7bit, cols=cols, rows=rows))
        lcd.init()
        scr = LCDS(lcd)

    menu = _build_menu()
    menu.set_rows_hint(rows)

    if menu.lines:
        menu.lines[menu.child_it].action(LineAction.ON_ENTER)

    print("Controls: w/s/a/d or arrows, Enter=OK, Backspace=DEL, Esc=exit")
    time.sleep(0.5)

    while True:
        lines = menu.render(cols, rows)
        _print_frame(lines, title=f"{menu.name} ({cols}x{rows})")

        if scr is not None:
            for y in range(rows):
                scr.write_at(0, y, lines[y])
            scr.flush()

        key = _get_key()
        if key == "\x1b":
            break

        action = _to_action(key)
        if action is None:
            continue

        menu.set_rows_hint(rows)
        menu.menu_action(action)
        time.sleep(0.01)


if __name__ == "__main__":
    main()
