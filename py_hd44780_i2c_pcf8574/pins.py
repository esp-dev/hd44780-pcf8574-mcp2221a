from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PinMapping:
    """PCF8574 bit mapping for an HD44780 in 4-bit mode.

    Bits are PCF8574 pin indices (0..7).

    This mirrors variants in `pcf8574_hd44780_pins.h`.
    """

    rs: int
    rw: int
    e: int
    bl: int
    d4: int
    d5: int
    d6: int
    d7: int
    bl_active_high: bool = True


# Variant A (very common): P0=RS, P1=RW, P2=E, P3=BL, P4..P7=D4..D7
VARIANT_A = PinMapping(rs=0, rw=1, e=2, bl=3, d4=4, d5=5, d6=6, d7=7, bl_active_high=True)

# Variant B (RW/E swapped): P0=RS, P1=E, P2=RW, P3=BL, P4..P7=D4..D7
VARIANT_B = PinMapping(rs=0, rw=2, e=1, bl=3, d4=4, d5=5, d6=6, d7=7, bl_active_high=True)

# Variant C (data on low bits): P0..P3=D4..D7, P4=RS, P5=RW, P6=E, P7=BL
VARIANT_C = PinMapping(rs=4, rw=5, e=6, bl=7, d4=0, d5=1, d6=2, d7=3, bl_active_high=True)


def bit_mask(bit: int) -> int:
    if not 0 <= bit <= 7:
        raise ValueError(f"PCF8574 bit must be 0..7, got {bit}")
    return 1 << bit
