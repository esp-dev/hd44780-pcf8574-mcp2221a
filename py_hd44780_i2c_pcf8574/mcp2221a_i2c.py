from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Protocol, Union


class I2CDevice(Protocol):
    def i2c_write(self, address_7bit: int, data: bytes) -> None: ...
    def i2c_read(self, address_7bit: int, length: int) -> bytes: ...


@dataclass(slots=True)
class MCP2221AI2C(I2CDevice):
    """Small adapter over PyMCP2221A.

    The upstream library has had multiple API variants across forks.
    This wrapper tries a couple of common import/class shapes.
    """

    i2c_speed_hz: int = 100_000
    _dev: Optional[object] = None

    def open(self) -> "MCP2221AI2C":
        if self._dev is not None:
            return self

        # Try a few known import styles.
        last_err: Optional[Exception] = None

        for importer in (self._try_import_style_a, self._try_import_style_b, self._try_import_style_c):
            try:
                self._dev = importer()
                break
            except Exception as exc:  # pragma: no cover
                last_err = exc

        if self._dev is None:
            raise RuntimeError(
                "Could not initialize MCP2221A via PyMCP2221A. "
                "Please verify the package is installed and compatible."
            ) from last_err

        self._configure_speed()
        return self

    def _try_import_style_a(self) -> object:
        # from PyMCP2221A import PyMCP2221A
        # dev = PyMCP2221A.PyMCP2221A()
        from PyMCP2221A import PyMCP2221A  # type: ignore

        return PyMCP2221A.PyMCP2221A()

    def _try_import_style_b(self) -> object:
        # from PyMCP2221A import MCP2221A
        # dev = MCP2221A.MCP2221A()
        from PyMCP2221A import MCP2221A  # type: ignore

        return MCP2221A.MCP2221A()

    def _try_import_style_c(self) -> object:
        # from pymcp2221a import MCP2221A
        # dev = MCP2221A()
        from pymcp2221a import MCP2221A  # type: ignore

        return MCP2221A()

    def _configure_speed(self) -> None:
        # Different forks use different method names.
        for method_name in ("I2C_speed", "i2c_setspeed", "i2c_set_speed", "I2C_SetSpeed"):
            method = getattr(self._dev, method_name, None)
            if callable(method):
                try:
                    method(self.i2c_speed_hz)
                    return
                except TypeError:
                    # Some variants want kHz.
                    method(int(self.i2c_speed_hz / 1000))
                    return

        # If we cannot set speed, we still proceed at default.

    def i2c_write(self, address_7bit: int, data: bytes) -> None:
        if self._dev is None:
            raise RuntimeError("MCP2221AI2C not opened. Call .open() first.")
        if not (0 <= address_7bit <= 0x7F):
            raise ValueError(f"I2C 7-bit address must be 0..0x7F, got 0x{address_7bit:02X}")

        # Try common method names.
        for method_name in (
            "I2C_write",
            "i2c_write",
            "I2C_Write",
            "i2c_writeto",
        ):
            method = getattr(self._dev, method_name, None)
            if callable(method):
                try:
                    method(address_7bit, data)
                except TypeError:
                    # Some APIs want list of ints.
                    method(address_7bit, list(data))
                return

        raise RuntimeError("PyMCP2221A object has no recognized I2C write method")

    def i2c_read(self, address_7bit: int, length: int) -> bytes:
        if self._dev is None:
            raise RuntimeError("MCP2221AI2C not opened. Call .open() first.")
        if not (0 <= address_7bit <= 0x7F):
            raise ValueError(f"I2C 7-bit address must be 0..0x7F, got 0x{address_7bit:02X}")
        if length <= 0:
            raise ValueError(f"length must be > 0, got {length}")

        for method_name in (
            "I2C_read",
            "i2c_read",
            "I2C_Read",
            "i2c_readfrom",
        ):
            method = getattr(self._dev, method_name, None)
            if callable(method):
                out: object = method(address_7bit, length)
                if isinstance(out, (bytes, bytearray)):
                    return bytes(out)
                if isinstance(out, list):
                    return bytes(int(x) & 0xFF for x in out)
                if isinstance(out, tuple):
                    return bytes(int(x) & 0xFF for x in out)
                if isinstance(out, memoryview):
                    return out.tobytes()
                raise RuntimeError(f"Unrecognized I2C read return type: {type(out)!r}")

        raise RuntimeError("PyMCP2221A object has no recognized I2C read method")
