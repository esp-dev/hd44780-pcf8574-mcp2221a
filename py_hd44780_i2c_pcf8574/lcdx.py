from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

from .mcp2221a_i2c import I2CDevice
from .pins import PinMapping, bit_mask


@dataclass(slots=True)
class HD44780Config:
    cols: int = 16
    rows: int = 2
    address_7bit: int = 0x3F
    i2c_speed_hz: int = 100_000


class HD44780_PCF8574:
    """HD44780 (4-bit) over PCF8574 I2C backpack.

    Low-level driver that supports commands/data/cursor control.
    """

    # Commands
    LCDC_CLS = 0x01
    LCDC_HOME = 0x02
    LCDC_MODE = 0x04
    LCDC_MODER = 0x02
    LCDC_MODEMOVE = 0x01
    LCDC_ON = 0x08
    LCDC_ONDISPLAY = 0x04
    LCDC_ONCURSOR = 0x02
    LCDC_ONBLINK = 0x01
    LCDC_SHIFT = 0x10
    LCDC_SHIFTDISP = 0x08
    LCDC_SHIFTR = 0x04
    LCDC_FUNC = 0x20
    LCDC_FUNC8b = 0x10
    LCDC_FUNC4b = 0x00
    LCDC_FUNC2L = 0x08
    LCDC_FUNC1L = 0x00
    LCDC_FUNC5x10 = 0x04
    LCDC_FUNC5x7 = 0x00
    LCDC_CGA = 0x40
    LCDC_DDA = 0x80

    def __init__(
        self,
        i2c: I2CDevice,
        mapping: PinMapping,
        config: Optional[HD44780Config] = None,
    ) -> None:
        self._i2c = i2c
        self._mapping = mapping
        self._cfg = config or HD44780Config()

        self._pcf_state = 0x00
        self._backlight_on = True

        self._row_offsets = [0x00, 0x40, 0x14, 0x54]

        # Software cursor iterator: linear index in the virtual screen.
        self._it: int = 0

        # Cache masks
        self._rs_mask = bit_mask(mapping.rs)
        self._rw_mask = bit_mask(mapping.rw)
        self._e_mask = bit_mask(mapping.e)
        self._bl_mask = bit_mask(mapping.bl)
        self._d4_mask = bit_mask(mapping.d4)
        self._d5_mask = bit_mask(mapping.d5)
        self._d6_mask = bit_mask(mapping.d6)
        self._d7_mask = bit_mask(mapping.d7)

    def init(self) -> None:
        """Initialize LCD in 4-bit mode."""
        self._pcf_state = 0x00
        self.set_backlight(True)

        # Wait for LCD to power up.
        time.sleep(0.05)  # 50ms

        # Per HD44780 init: 0x3 (8-bit) x3, then 0x2 (4-bit)
        self._write4bits(0x03, rs=False)
        time.sleep(0.005)  # 4.1ms+; use 5ms
        self._write4bits(0x03, rs=False)
        time.sleep(0.00015)  # 100us+; use 150us
        self._write4bits(0x03, rs=False)
        time.sleep(0.00015)
        self._write4bits(0x02, rs=False)

        # Function set
        func = self.LCDC_FUNC | self.LCDC_FUNC4b
        func |= self.LCDC_FUNC2L if self._cfg.rows > 1 else self.LCDC_FUNC1L
        func |= self.LCDC_FUNC5x7
        self.command(func)

        # Display off, clear, entry mode, display on
        self.command(self.LCDC_ON)
        self.clear()
        self.command(self.LCDC_MODE | self.LCDC_MODER)
        self.command(self.LCDC_ON | self.LCDC_ONDISPLAY)

        self._it = 0

    def set_backlight(self, on: bool) -> None:
        self._backlight_on = bool(on)
        self._apply_backlight_to_state()
        self._write_pcf(self._pcf_state)

    def clear(self) -> None:
        self.command(self.LCDC_CLS)
        time.sleep(0.002)  # clear needs ~1.52ms
        self._it = 0

    def home(self) -> None:
        self.command(self.LCDC_HOME)
        time.sleep(0.002)
        self._it = 0

    def command(self, cmd: int) -> None:
        self._send(cmd & 0xFF, rs=False)

    def write_char(self, ch: int) -> None:
        self._send(ch & 0xFF, rs=True)

    def write(self, text: str, encoding: str = "latin-1", errors: str = "replace") -> None:
        data = text.encode(encoding, errors=errors)
        for b in data:
            self.write_char(b)

    def set_cursor(self, col: int, row: int) -> None:
        if row < 0:
            row = 0
        if col < 0:
            col = 0
        if row >= self._cfg.rows:
            row = self._cfg.rows - 1
        if col >= self._cfg.cols:
            col = self._cfg.cols - 1

        addr = col + self._row_offsets[row]
        self.command(self.LCDC_DDA | addr)

        self._it = row * self._cfg.cols + col

    def cursor_on(self, blink: bool = False) -> None:
        cmd = self.LCDC_ON | self.LCDC_ONDISPLAY | self.LCDC_ONCURSOR
        if blink:
            cmd |= self.LCDC_ONBLINK
        self.command(cmd)

    def create_char(self, location: int, pattern: bytes) -> None:
        if not (0 <= location <= 7):
            raise ValueError("CGRAM location must be 0..7")
        if len(pattern) != 8:
            raise ValueError("pattern must be exactly 8 bytes")
        self.command(self.LCDC_CGA | (location << 3))
        for b in pattern:
            self.write_char(b)

    # --- convenience helpers (no lcd_ prefix) ---

    def curon(self) -> None:
        self.cursor_on(blink=False)

    def curoff(self) -> None:
        self.command(self.LCDC_ON | self.LCDC_ONDISPLAY)

    def line1(self) -> None:
        self.command(self.LCDC_DDA)
        self._it = 0

    def line2(self) -> None:
        if self._cfg.rows < 2:
            return
        self.command(self.LCDC_DDA | 0x40)
        self._it = self._cfg.cols

    def gotoxy(self, x: int, y: int) -> None:
        if x < 0 or x >= self._cfg.cols:
            return
        if y < 0 or y >= self._cfg.rows:
            return
        self.set_cursor(x, y)

    def data_it(self, value: int) -> None:
        self.write_char(value)
        self.curright()

    def up(self) -> None:
        col = self._it % self._cfg.cols
        row = self._it // self._cfg.cols
        if row <= 0:
            return
        self.set_cursor(col, row - 1)

    def down(self) -> None:
        col = self._it % self._cfg.cols
        row = self._it // self._cfg.cols
        if row >= (self._cfg.rows - 1):
            return
        self.set_cursor(col, row + 1)

    def curleft(self) -> None:
        size = self._cfg.cols * self._cfg.rows
        if size <= 0:
            self._it = 0
            return
        self._it -= 1
        if self._it < 0:
            self._it = size - 1
        self.set_cursor(self._it % self._cfg.cols, self._it // self._cfg.cols)

    def curright(self) -> None:
        size = self._cfg.cols * self._cfg.rows
        if size <= 0:
            self._it = 0
            return
        self._it += 1
        if self._it >= size:
            self._it = 0

        if (self._it % self._cfg.cols) == 0:
            self.set_cursor(0, self._it // self._cfg.cols)

    def back(self) -> None:
        self.curleft()
        self.write_char(ord(" "))
        self.curleft()

    def str(self, text: str, *, encoding: str = "latin-1", errors: str = "replace") -> None:
        if not text:
            return
        for b in text.encode(encoding, errors=errors):
            self.data_it(b)

    def str_P(self, text: str | bytes, *, encoding: str = "latin-1", errors: str = "replace") -> None:
        if not text:
            return
        if isinstance(text, (bytes, bytearray, memoryview)):
            s = bytes(text).decode(encoding, errors=errors)
        else:
            s = text
        self.str(s, encoding=encoding, errors=errors)

    def hex(self, value: int) -> None:
        value &= 0xFF
        digits = "0123456789ABCDEF"
        self.data_it(ord(digits[(value >> 4) & 0x0F]))
        self.data_it(ord(digits[value & 0x0F]))

    def dec(self, value: int) -> None:
        self.str(str(int(value)))

    # --- low level ---

    def _apply_backlight_to_state(self) -> None:
        if self._mapping.bl_active_high:
            if self._backlight_on:
                self._pcf_state |= self._bl_mask
            else:
                self._pcf_state &= ~self._bl_mask
        else:
            if self._backlight_on:
                self._pcf_state &= ~self._bl_mask
            else:
                self._pcf_state |= self._bl_mask

    def _write_pcf(self, value: int) -> None:
        self._i2c.i2c_write(self._cfg.address_7bit, bytes([value & 0xFF]))

    def _pulse_enable(self, data: int) -> None:
        # E high
        self._write_pcf(data | self._e_mask)
        time.sleep(0.000001)  # 1us
        # E low
        self._write_pcf(data & ~self._e_mask)
        time.sleep(0.00005)  # ~50us (matches lcdx delay after nibble)

    def _write4bits(self, nibble: int, rs: bool) -> None:
        nibble &= 0x0F

        # Base state: keep backlight, RW low
        state = self._pcf_state
        state &= ~self._rw_mask

        # RS
        if rs:
            state |= self._rs_mask
        else:
            state &= ~self._rs_mask

        # Clear data bits then set per nibble
        state &= ~(self._d4_mask | self._d5_mask | self._d6_mask | self._d7_mask)
        if nibble & 0x01:
            state |= self._d4_mask
        if nibble & 0x02:
            state |= self._d5_mask
        if nibble & 0x04:
            state |= self._d6_mask
        if nibble & 0x08:
            state |= self._d7_mask

        self._write_pcf(state)
        self._pulse_enable(state)

    def _send(self, value: int, rs: bool) -> None:
        self._write4bits(value >> 4, rs=rs)
        self._write4bits(value & 0x0F, rs=rs)
