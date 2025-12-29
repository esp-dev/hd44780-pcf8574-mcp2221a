from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .lcdx import HD44780_PCF8574


@dataclass(slots=True)
class LCDSConfig:
    """Buffered LCD helper.

    - Keeps an in-memory buffer for the whole display
    - `puts()` updates the buffer (line-based)
    - `flush()` writes only the changed characters (diff refresh)

    Designed for efficient refresh by tracking changes.
    """

    cols: int = 16
    rows: int = 2
    use_dynamic_chars: bool = True


@dataclass(frozen=True, slots=True)
class DynamicCharDef:
    pattern: bytes  # 8 bytes, 5-bit rows
    alt: str        # fallback single-char replacement


def _default_dynamic_charset() -> dict[str, DynamicCharDef]:
    """Default dynamic set.

    HD44780 provides only 8 CGRAM slots, so this mapping is managed dynamically.
    """

    def p(*rows: int) -> bytes:
        if len(rows) != 8:
            raise ValueError("pattern must have 8 rows")
        return bytes(int(r) & 0x1F for r in rows)

    return {
        # Polish letters
        "ą": DynamicCharDef(p(0x00, 0x0E, 0x01, 0x0F, 0x11, 0x0F, 0x02, 0x01), alt="a"),
        "Ą": DynamicCharDef(p(0x0E, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x02, 0x01), alt="A"),
        "ć": DynamicCharDef(p(0x02, 0x04, 0x0E, 0x10, 0x10, 0x11, 0x0E, 0x00), alt="c"),
        "Ć": DynamicCharDef(p(0x02, 0x04, 0x0E, 0x11, 0x10, 0x11, 0x0E, 0x00), alt="C"),
        "ę": DynamicCharDef(p(0x00, 0x0E, 0x11, 0x1F, 0x10, 0x0E, 0x02, 0x01), alt="e"),
        "Ę": DynamicCharDef(p(0x1F, 0x10, 0x1C, 0x10, 0x10, 0x1F, 0x02, 0x01), alt="E"),
        "ł": DynamicCharDef(p(0x0C, 0x04, 0x06, 0x04, 0x0C, 0x04, 0x0E, 0x00), alt="l"),
        "Ł": DynamicCharDef(p(0x08, 0x08, 0x0A, 0x0C, 0x18, 0x08, 0x0F, 0x00), alt="L"),
        "ń": DynamicCharDef(p(0x02, 0x04, 0x16, 0x19, 0x11, 0x11, 0x11, 0x00), alt="n"),
        "Ń": DynamicCharDef(p(0x02, 0x15, 0x11, 0x19, 0x15, 0x13, 0x11, 0x00), alt="N"),
        "ó": DynamicCharDef(p(0x02, 0x04, 0x0E, 0x11, 0x11, 0x11, 0x0E, 0x00), alt="o"),
        "Ó": DynamicCharDef(p(0x02, 0x04, 0x0E, 0x11, 0x11, 0x11, 0x0E, 0x00), alt="O"),
        "ś": DynamicCharDef(p(0x02, 0x04, 0x0E, 0x10, 0x0E, 0x01, 0x1E, 0x00), alt="s"),
        "Ś": DynamicCharDef(p(0x02, 0x04, 0x0F, 0x10, 0x1E, 0x01, 0x1E, 0x00), alt="S"),
        "ż": DynamicCharDef(p(0x02, 0x04, 0x1F, 0x02, 0x04, 0x08, 0x1F, 0x00), alt="z"),
        "Ż": DynamicCharDef(p(0x02, 0x04, 0x1F, 0x02, 0x04, 0x08, 0x1F, 0x00), alt="Z"),
        "ź": DynamicCharDef(p(0x04, 0x00, 0x1F, 0x02, 0x04, 0x08, 0x1F, 0x00), alt="z"),
        "Ź": DynamicCharDef(p(0x04, 0x00, 0x1F, 0x02, 0x04, 0x08, 0x1F, 0x00), alt="Z"),

        # Common symbols
        "±": DynamicCharDef(p(0x04, 0x04, 0x1F, 0x04, 0x04, 0x00, 0x1F, 0x00), alt=" "),
        "»": DynamicCharDef(p(0x00, 0x14, 0x0A, 0x05, 0x0A, 0x14, 0x00, 0x00), alt=">"),
        "°": DynamicCharDef(p(0x06, 0x09, 0x09, 0x06, 0x00, 0x00, 0x00, 0x00), alt="*"),

        # HD44780 ROM variants often render '\\' as '¥'. Provide a CGRAM backslash.
        "\\": DynamicCharDef(p(0x10, 0x08, 0x04, 0x02, 0x01, 0x00, 0x00, 0x00), alt="/"),
    }


class LCDS:
    def __init__(self, lcd: HD44780_PCF8574, config: LCDSConfig | None = None) -> None:
        self._lcd = lcd
        self._cfg = config or LCDSConfig(cols=lcd._cfg.cols, rows=lcd._cfg.rows)

        size = self._cfg.cols * self._cfg.rows
        self._buf: list[str] = [" "] * size
        self._shadow: list[str] = ["\0"] * size  # force first flush to write everything

        self._puts_line = 0

        self._dyn_charset = _default_dynamic_charset()
        self._dyn_char_to_slot: dict[str, int] = {}
        self._dyn_slot_to_char: list[Optional[str]] = [None] * 8
        self._dyn_used_mask: int = 0
        self._dyn_rotate_index: int = 0

    @property
    def cols(self) -> int:
        return self._cfg.cols

    @property
    def rows(self) -> int:
        return self._cfg.rows

    def clear(self) -> None:
        for i in range(len(self._buf)):
            self._buf[i] = " "

    def clear_line(self, row: int) -> None:
        row = max(0, min(self.rows - 1, row))
        start = row * self.cols
        for i in range(start, start + self.cols):
            self._buf[i] = " "

    def write_at(self, col: int, row: int, text: str) -> None:
        if row < 0 or row >= self.rows:
            return
        if col < 0:
            col = 0
        if col >= self.cols:
            return

        if not text:
            return

        max_len = self.cols - col
        text = text[:max_len]

        start = row * self.cols + col
        for i, ch in enumerate(text):
            self._buf[start + i] = ch

    def puts(self, text: str) -> None:
        """Line-based write.

        Semantics:
        - Remembers only the current line between calls.
        - Clears ONLY that current line at the beginning of the call.
        - Starts writing at column 0 for this call.
        - On '\n': move to next line (wrap rows), reset column to 0.
        - When column reaches `cols`: wraps within the same line.
        - Does NOT auto-clear lines after '\n'.
        """

        if not text:
            return

        line = self._puts_line
        col = 0

        self.clear_line(line)

        for ch in text:
            if ch == "\n":
                line = (line + 1) % self.rows
                col = 0
                continue

            self._buf[line * self.cols + col] = ch
            col = (col + 1) % self.cols

        self._puts_line = line

    def reset_dynamic_chars(self) -> None:
        self._dyn_char_to_slot.clear()
        self._dyn_slot_to_char = [None] * 8
        self._dyn_used_mask = 0
        self._dyn_rotate_index = 0

    def _age_dynamic_mask_if_full(self) -> None:
        """When the dynamic-slot mask is full, free one slot (round-robin)."""

        if self._dyn_used_mask == 0xFF:
            slot = self._dyn_rotate_index
            self._dyn_used_mask &= ~(1 << slot)
            self._dyn_rotate_index = (self._dyn_rotate_index + 1) % 8

    def _alloc_dynamic_slot(self, ch: str) -> tuple[int, bool] | None:
        """Return (slot, created) or None if cannot allocate."""

        existing = self._dyn_char_to_slot.get(ch)
        if existing is not None:
            return existing, False

        # Slot aging is handled by `_age_dynamic_mask_if_full()` in the refresh loop.

        for slot in range(8):
            if not (self._dyn_used_mask & (1 << slot)):
                old = self._dyn_slot_to_char[slot]
                if old is not None:
                    self._dyn_char_to_slot.pop(old, None)

                self._dyn_char_to_slot[ch] = slot
                self._dyn_slot_to_char[slot] = ch
                self._dyn_used_mask |= 1 << slot

                dyn = self._dyn_charset.get(ch)
                if dyn is None:
                    return None
                self._lcd.create_char(slot, dyn.pattern)
                return slot, True

        return None

    def _encode_for_lcd(self, ch: str) -> tuple[int, bool]:
        """Return (byte_code, cursor_reset_needed)."""

        # Dynamic CGRAM mapping (Polish letters etc.)
        if self._cfg.use_dynamic_chars and ch in self._dyn_charset:
            allocated = self._alloc_dynamic_slot(ch)
            if allocated is not None:
                slot, created = allocated
                return slot, created
            # No slot: use fallback
            ch = self._dyn_charset[ch].alt

        if not ch:
            return ord(" "), False
        code = ord(ch)
        if 0 <= code <= 0xFF:
            return code, False
        return ord("?"), False

    def flush(self) -> None:
        """Refresh the physical LCD by writing only changed cells."""

        last_written = -10_000
        for i, ch in enumerate(self._buf):
            if self._shadow[i] == ch:
                continue

            # When all 8 CGRAM slots are marked used, free one bit in a
            # round-robin way *before* handling this cell.
            self._age_dynamic_mask_if_full()

            self._shadow[i] = ch

            code, cursor_reset = self._encode_for_lcd(ch)

            # If we just programmed CGRAM, the LCD cursor moved.
            # Also, HD44780 DDRAM is not linearly mapped between rows, so crossing
            # a buffer row boundary requires an explicit cursor set.
            if (
                cursor_reset
                or (i - last_written) != 1
                or ((i // self.cols) != (last_written // self.cols))
            ):
                col = i % self.cols
                row = i // self.cols
                self._lcd.set_cursor(col, row)

            self._lcd.write_char(code)
            last_written = i

