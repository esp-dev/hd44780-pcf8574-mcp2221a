from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Callable, Optional, Protocol


class LineAction(IntEnum):
    NONE = 0
    OK = 1
    LEFT = 2
    RIGHT = 3
    UP = 4
    DOWN = 5
    ON_ENTER = 6
    ON_LEAVE = 7
    BREAK = 8
    DIGIT_BASE = 9


class LineInh(Protocol):
    disable_select: bool

    def print(self, line: "Line", size: int) -> str: ...

    def action(self, line: "Line", action: int) -> int: ...

    def submenu(self, line: "Line") -> Optional["Menu"]: ...

    def grab(self, line: "Line") -> bool: ...


def _fit(text: str, size: int, fill: str = " ") -> str:
    if size <= 0:
        return ""
    if len(text) >= size:
        return text[:size]
    return text + (fill * (size - len(text)))


@dataclass(slots=True)
class Line:
    inh: LineInh
    owner: object

    def print(self, size: int) -> str:
        return _fit(self.inh.print(self, size), size)

    def action(self, action: int) -> int:
        return int(self.inh.action(self, int(action)))

    def submenu(self) -> Optional["Menu"]:
        return self.inh.submenu(self)

    def grab(self) -> bool:
        return bool(self.inh.grab(self))

    def select_disabled(self) -> bool:
        return bool(getattr(self.inh, "disable_select", False))


MenuEvent = Callable[["Menu", int, int], None]


class LCDSLike(Protocol):
    @property
    def cols(self) -> int: ...

    @property
    def rows(self) -> int: ...

    def write_at(self, col: int, row: int, text: str) -> None: ...

    def flush(self) -> None: ...


@dataclass(slots=True)
class Menu(LineInh):
    name: str = ""
    event: Optional[MenuEvent] = None

    line: Line = field(init=False)
    lines: list[Line] = field(default_factory=list)
    child_it: int = 0
    cur_line: int = 0
    sub: Optional["Menu"] = None

    disable_select: bool = False

    def __post_init__(self) -> None:
        self.line = Line(inh=self, owner=self)

    # LineInh
    def print(self, line: Line, size: int) -> str:
        return self.name

    def submenu(self, line: Line) -> Optional["Menu"]:
        return self

    def grab(self, line: Line) -> bool:
        return False

    def action(self, line: Line, action: int) -> int:
        return self.menu_action(action)

    # Menu API
    def add_line(self, line: Line) -> bool:
        self.lines.append(line)
        return True

    def menu_action(self, action: int) -> int:
        if self.sub is not None:
            rv = self.sub.menu_action(action)
            if rv == LineAction.BREAK:
                self.sub = None
                return int(LineAction.NONE)
            return int(action)

        if not self.lines:
            return int(LineAction.NONE)

        action = int(action)
        current = self.lines[self.child_it]

        if action == LineAction.NONE:
            pass

        elif action == LineAction.DOWN:
            if current.grab():
                pass
            else:
                current.action(LineAction.ON_LEAVE)
                self.child_it = (self.child_it + 1) % len(self.lines)
                self.lines[self.child_it].action(LineAction.ON_ENTER)
                if (self.cur_line < 1_000_000) and (self.cur_line < (self._rows_hint() - 1)) and (
                    self.cur_line < (len(self.lines) - 1)
                ):
                    self.cur_line += 1

        elif action == LineAction.UP:
            if current.grab():
                pass
            else:
                current.action(LineAction.ON_LEAVE)
                if self.child_it > 0:
                    self.child_it -= 1
                else:
                    self.child_it = len(self.lines) - 1
                self.lines[self.child_it].action(LineAction.ON_ENTER)
                if self.cur_line > 0:
                    self.cur_line -= 1

        elif action in (LineAction.RIGHT, LineAction.LEFT, LineAction.ON_ENTER, LineAction.ON_LEAVE):
            if current.submenu() is None:
                current.action(action)

        elif action == LineAction.OK:
            self.sub = current.submenu()
            if self.sub is None:
                rv = current.action(action)
                if self.event is not None:
                    self.event(self, action, self.child_it)
                return int(rv)
            current.action(LineAction.ON_ENTER)

        else:
            if (current.submenu() is None) or current.grab():
                current.action(action)
            else:
                self.sub = None

        if self.event is not None:
            self.event(self, action, self.child_it)
        return int(action)

    def render(self, cols: int, rows: int) -> list[str]:
        if cols <= 0 or rows <= 0:
            return []

        if self.sub is not None:
            return self.sub.render(cols, rows)

        out: list[str] = []
        n = len(self.lines)

        for i in range(rows):
            prefix = "  "
            body = "".ljust(max(0, cols - 2))
            if i < n:
                idx = (self.child_it + i + n - self.cur_line) % n
                body = self.lines[idx].print(cols - 2)
                if i == self.cur_line:
                    prefix = "> "
            out.append(_fit(prefix + body, cols))

        return out

    def draw_to_lcds(self, lcds: LCDSLike) -> None:
        rows = int(getattr(lcds, "rows"))
        cols = int(getattr(lcds, "cols"))
        lines = self.render(cols, rows)
        for y in range(rows):
            text = lines[y] if y < len(lines) else "".ljust(cols)
            lcds.write_at(0, y, text)
        lcds.flush()

    # Internal: C version uses LCD_LINES for cur_line limiting; we approximate by the last render.
    _last_rows: int = 2

    def _rows_hint(self) -> int:
        return max(1, int(self._last_rows))

    def set_rows_hint(self, rows: int) -> None:
        self._last_rows = max(1, int(rows))
