from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence

from .core import Line, LineAction, LineInh, Menu, _fit


def _bracket(open_on: bool, close_on: bool) -> tuple[str, str]:
    return ("<" if open_on else "[", ">" if close_on else "]")


@dataclass(slots=True)
class Space(LineInh):
    line: Line = field(init=False)
    disable_select: bool = False

    def __post_init__(self) -> None:
        self.line = Line(inh=self, owner=self)

    def print(self, line: Line, size: int) -> str:
        return "-" * max(0, size)

    def action(self, line: Line, action: int) -> int:
        return int(LineAction.NONE)

    def submenu(self, line: Line) -> Optional[Menu]:
        return None

    def grab(self, line: Line) -> bool:
        return False


@dataclass(slots=True)
class SwitchItem(LineInh):
    name: str
    line: Line = field(init=False)
    enter: bool = False
    select: bool = False

    disable_select: bool = False

    def __post_init__(self) -> None:
        self.line = Line(inh=self, owner=self)

    def print(self, line: Line, size: int) -> str:
        if size < 4:
            return ""
        base = _fit(self.name, size)
        base = base[: max(0, size - 3)]
        base = _fit(base, size - 3)
        o, c = _bracket(self.enter, self.enter)
        mid = "*" if self.select else " "
        return base + o + mid + c

    def action(self, line: Line, action: int) -> int:
        action = int(action)
        if action == LineAction.ON_ENTER:
            self.enter = True
        elif action == LineAction.ON_LEAVE:
            self.enter = False
        elif action in (LineAction.LEFT, LineAction.RIGHT):
            self.select = not self.select
        return action

    def submenu(self, line: Line) -> Optional[Menu]:
        return None

    def grab(self, line: Line) -> bool:
        return False

    def set(self, value: bool) -> None:
        self.select = bool(value)

    def get(self) -> bool:
        return bool(self.select)


@dataclass(slots=True)
class Edit(LineInh):
    max_len: int = 50

    line: Line = field(init=False)

    input: list[int] = field(default_factory=list)
    children_num: int = 0
    child_it: int = 0
    cur_line: int = 0
    enter: bool = False

    disable_select: bool = False

    def __post_init__(self) -> None:
        self.line = Line(inh=self, owner=self)
        if not self.input:
            self.input = [0] * self.max_len

    def set(self, text: str) -> None:
        if not text:
            return
        self.child_it = 0
        self.children_num = 0
        self.cur_line = 0
        raw = text.encode("latin-1", errors="replace")
        for b in raw[: self.max_len - 1]:
            self.input[self.children_num] = b
            self.child_it += 1
            self.children_num += 1

    def get(self, size: int) -> str:
        if size <= 0:
            return ""
        take = min(size - 1, self.children_num)
        raw = bytes(self.input[:take])
        return raw.decode("latin-1", errors="replace")

    def print(self, line: Line, size: int) -> str:
        if size <= 0:
            return ""
        if size < 2:
            return "".ljust(size)

        inner = max(0, size - 2)
        view: list[int] = [0] * inner
        for i in range(inner):
            if i < self.children_num:
                src = self.cur_line + i
                if src < (self.max_len - 1):
                    view[i] = self.input[src % (self.max_len - 1)]

        cursor = "|"
        buf = bytes(view).split(b"\x00", 1)[0]
        if not buf:
            content = cursor.ljust(inner)
        else:
            content = buf.decode("latin-1", errors="replace")
            place = max(0, self.child_it - self.cur_line)
            if place > len(content):
                place = len(content)
            content = content[:place] + cursor + content[place:]
            content = _fit(content, inner)

        o, c = _bracket(self.enter, self.enter)
        return o + content + c

    def action(self, line: Line, action: int) -> int:
        action = int(action)
        inner_visible = 12  # fallback when not printed yet
        # Try to infer current visible width from cursor scroll state.
        # This is only for scrolling heuristics; print() always trunc/pads properly.
        if self.cur_line <= self.child_it:
            inner_visible = max(inner_visible, (self.child_it - self.cur_line) + 1)

        if action == LineAction.ON_ENTER:
            self.enter = True
        elif action == LineAction.ON_LEAVE:
            self.enter = False
        elif action == LineAction.RIGHT:
            if self.child_it < self.children_num:
                self.child_it += 1
                if (self.child_it - self.cur_line) > (inner_visible - 1):
                    self.cur_line += 1
        elif action == LineAction.LEFT:
            if self.child_it > 0:
                self.child_it -= 1
            if self.cur_line > 0:
                self.cur_line -= 1
        elif action == LineAction.BREAK:
            if self.children_num and self.child_it:
                delete_at = self.child_it - 1
                for i in range(delete_at, self.children_num - 1):
                    self.input[i] = self.input[i + 1]
                self.input[self.children_num - 1] = 0
                self.child_it -= 1
                self.children_num -= 1
                if self.cur_line > 0:
                    self.cur_line -= 1
        else:
            if self.children_num < (self.max_len - 2):
                ch = action - int(LineAction.DIGIT_BASE)
                ch &= 0xFF
                if self.child_it == self.children_num:
                    self.input[self.child_it] = ch
                else:
                    for i in range(self.children_num, self.child_it, -1):
                        if i >= (self.max_len - 1):
                            continue
                        self.input[i] = self.input[i - 1]
                    self.input[self.child_it] = ch
                self.child_it += 1
                self.children_num += 1
                if (self.child_it - self.cur_line) > (inner_visible - 1):
                    self.cur_line += 1

        return action

    def submenu(self, line: Line) -> Optional[Menu]:
        return None

    def grab(self, line: Line) -> bool:
        return False


@dataclass(slots=True)
class Switch(LineInh):
    pin: int
    eep: int = 0
    name: str = ""

    line: Line = field(init=False)

    edit: Optional[Edit] = None
    counter: int = 0
    enter: bool = False
    select: bool = False

    disable_select: bool = False

    def __post_init__(self) -> None:
        self.line = Line(inh=self, owner=self)

    def print(self, line: Line, size: int) -> str:
        if size < 4:
            return ""
        if self.edit is not None:
            return self.edit.print(self.edit.line, size)

        base = _fit(self.name, size)
        base = base[: max(0, size - 3)]
        base = _fit(base, size - 3)
        sel = " "  # storage_get_pin disabled in original
        o, c = _bracket(self.enter, self.enter)
        return base + o + sel + c

    def action(self, line: Line, action: int) -> int:
        action = int(action)
        if self.edit is not None:
            if action == LineAction.OK:
                self.name = self.edit.get(100)
                self.edit = None
            else:
                self.edit.action(self.edit.line, action)
            return int(LineAction.BREAK)

        if action == LineAction.ON_ENTER:
            self.enter = True
        elif action == LineAction.ON_LEAVE:
            self.enter = False
        elif action in (LineAction.LEFT, LineAction.RIGHT):
            self.counter = 0
            self.select = not self.select
        elif action == LineAction.OK:
            self.edit = Edit()
            if self.name:
                self.edit.set(self.name)
            self.edit.action(self.edit.line, LineAction.ON_ENTER)
        return action

    def submenu(self, line: Line) -> Optional[Menu]:
        return None

    def grab(self, line: Line) -> bool:
        return self.edit is not None


@dataclass(slots=True)
class RangeItem(LineInh):
    name: str
    min: int
    max: int
    line: Line = field(init=False)
    current: int = 0
    enter: bool = False

    disable_select: bool = False

    def __post_init__(self) -> None:
        self.line = Line(inh=self, owner=self)

    def print(self, line: Line, size: int) -> str:
        if size <= 0:
            return ""
        value = str(int(self.current))
        buf = (" " * size)
        left = (self.name or "")
        if left:
            buf = left[:size].ljust(size)
        o, c = _bracket(self.enter, self.enter)
        pos = max(0, size - len(value) - 2)
        out = list(buf)
        if pos < size:
            out[pos] = o
        start = pos + 1
        for i, ch in enumerate(value[: max(0, size - start - 1)]):
            if start + i < size - 1:
                out[start + i] = ch
        if size >= 1:
            out[size - 1] = c
        return "".join(out)

    def action(self, line: Line, action: int) -> int:
        action = int(action)
        if action == LineAction.ON_ENTER:
            self.enter = True
        elif action == LineAction.ON_LEAVE:
            self.enter = False
        elif action == LineAction.RIGHT:
            if self.current < self.max:
                self.current += 1
        elif action == LineAction.LEFT:
            if self.current > self.min:
                self.current -= 1
        return action

    def submenu(self, line: Line) -> Optional[Menu]:
        return None

    def grab(self, line: Line) -> bool:
        return False

    def get_value(self) -> int:
        return int(self.current)

    def set_value(self, value: int) -> bool:
        value = int(value)
        if value < self.min or value > self.max:
            return False
        self.current = value
        return True


@dataclass(slots=True)
class EnumItem(LineInh):
    name: str
    positions: Sequence[str]
    line: Line = field(init=False)
    pos: int = 0
    enter: bool = False

    disable_select: bool = False

    def __post_init__(self) -> None:
        self.line = Line(inh=self, owner=self)
        if not self.positions:
            raise ValueError("positions must not be empty")

    def print(self, line: Line, size: int) -> str:
        if size <= 0:
            return ""
        value = str(self.positions[self.pos])
        buf = (" " * size)
        left = (self.name or "")
        if left:
            buf = left[:size].ljust(size)
        o, c = _bracket(self.enter, self.enter)
        pos = max(0, size - len(value) - 2)
        out = list(buf)
        if pos < size:
            out[pos] = o
        start = pos + 1
        for i, ch in enumerate(value[: max(0, size - start - 1)]):
            if start + i < size - 1:
                out[start + i] = ch
        if size >= 1:
            out[size - 1] = c
        return "".join(out)

    def action(self, line: Line, action: int) -> int:
        action = int(action)
        if action == LineAction.ON_ENTER:
            self.enter = True
        elif action == LineAction.ON_LEAVE:
            self.enter = False
        elif action == LineAction.RIGHT:
            self.pos = (self.pos + 1) % len(self.positions)
        elif action == LineAction.LEFT:
            self.pos = (self.pos - 1) % len(self.positions)
        return action

    def submenu(self, line: Line) -> Optional[Menu]:
        return None

    def grab(self, line: Line) -> bool:
        return False

    def set_pos(self, pos: int) -> bool:
        pos = int(pos)
        if pos < 0 or pos >= len(self.positions):
            return False
        self.pos = pos
        return True

    def get_pos(self) -> int:
        return int(self.pos)


@dataclass(slots=True)
class TimeItem(LineInh):
    line: Line = field(init=False)
    h: int = 0
    m: int = 0
    s: int = 0
    it: int = 0
    enter: bool = False

    disable_select: bool = False

    def __post_init__(self) -> None:
        self.line = Line(inh=self, owner=self)

    def print(self, line: Line, size: int) -> str:
        it = self.it if self.enter else 255
        parts = [self.h, self.m, self.s]
        out = []
        for i, v in enumerate(parts):
            seg = f"{int(v):02d}"
            if it == i:
                seg = "<" + seg + ">"
            out.append(seg)
        return _fit(":".join(out), size)

    def action(self, line: Line, action: int) -> int:
        action = int(action)
        if action == LineAction.ON_ENTER:
            self.enter = True
        elif action == LineAction.ON_LEAVE:
            self.enter = False
        elif action == LineAction.OK:
            self.it = (self.it + 1) % 3
        elif action == LineAction.RIGHT:
            if self.it == 0:
                self.h = (self.h + 1) % 24
            elif self.it == 1:
                self.m = (self.m + 1) % 60
            else:
                self.s = (self.s + 1) % 60
        return action

    def submenu(self, line: Line) -> Optional[Menu]:
        return None

    def grab(self, line: Line) -> bool:
        return False

    def get_value(self) -> tuple[int, int, int]:
        return int(self.h), int(self.m), int(self.s)

    def set_value(self, hour: int, minute: int, second: int) -> None:
        self.h = int(hour) % 24
        self.m = int(minute) % 60
        self.s = int(second) % 60


@dataclass(slots=True)
class NameItem(LineInh):
    index: int
    get_name: Callable[[int, int], str]

    line: Line = field(init=False)

    disable_select: bool = False

    def __post_init__(self) -> None:
        self.line = Line(inh=self, owner=self)

    def print(self, line: Line, size: int) -> str:
        return _fit(str(self.get_name(size, int(self.index))), size)

    def action(self, line: Line, action: int) -> int:
        return int(LineAction.NONE)

    def submenu(self, line: Line) -> Optional[Menu]:
        return None

    def grab(self, line: Line) -> bool:
        return False


@dataclass(slots=True)
class InputItem(LineInh):
    name: str
    pin: int

    line: Line = field(init=False)

    disable_select: bool = False

    def __post_init__(self) -> None:
        self.line = Line(inh=self, owner=self)

    def print(self, line: Line, size: int) -> str:
        if size < 4:
            return ""
        base = _fit(self.name, size)
        base = base[: max(0, size - 3)]
        base = _fit(base, size - 3)
        return base + "(" + " " + ")"

    def action(self, line: Line, action: int) -> int:
        return int(LineAction.NONE)

    def submenu(self, line: Line) -> Optional[Menu]:
        return None

    def grab(self, line: Line) -> bool:
        return False


@dataclass(slots=True)
class Ok(LineInh):
    commit: Optional[Callable[[int], None]] = None
    index: int = 0
    enter: bool = False

    line: Line = field(init=False)

    disable_select: bool = False

    def __post_init__(self) -> None:
        self.line = Line(inh=self, owner=self)

    def print(self, line: Line, size: int) -> str:
        return _fit("Save", size)

    def action(self, line: Line, action: int) -> int:
        action = int(action)
        if action == LineAction.ON_ENTER:
            self.enter = True
        elif action == LineAction.ON_LEAVE:
            self.enter = False
        elif action == LineAction.OK:
            if self.commit is not None:
                self.commit(int(self.index))
            return int(LineAction.BREAK)
        return action

    def submenu(self, line: Line) -> Optional[Menu]:
        return None

    def grab(self, line: Line) -> bool:
        return False

    def set_index(self, index: int) -> None:
        self.index = int(index)

    def get_index(self) -> int:
        return int(self.index)
