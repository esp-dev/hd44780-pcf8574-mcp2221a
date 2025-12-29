# `menu`: line-based UI (widgets + navigation)

This repo contains a small line-based UI framework intended for HD44780 character LCDs. It follows a simple model:

- each UI element is a **Line**
- each line delegates behavior to an **implementation** (`LineInh`)
- a **Menu** is a line that contains multiple lines, provides selection + scrolling, and supports nested submenus

This is designed to work well with `LCDS` (buffered refresh) and a small set of keys (up/down/left/right/ok/backspace).

## Where the code lives

- Core: [py_hd44780_i2c_pcf8574/menu/core.py](../py_hd44780_i2c_pcf8574/menu/core.py)
- Widgets: [py_hd44780_i2c_pcf8574/menu/widgets.py](../py_hd44780_i2c_pcf8574/menu/widgets.py)
- Example: [examples/menu_demo.py](../examples/menu_demo.py)

## Concepts

### `LineInh` (behavior interface)

A `LineInh` implementation provides these operations:

- `print(line, size) -> str` : return a string representation (will be padded/truncated to `size`)
- `action(line, action) -> int` : handle an input action
- `submenu(line) -> Menu | None` : optionally return a submenu
- `grab(line) -> bool` : whether the line should “grab” navigation keys (prevents the menu from moving selection)
- `disable_select: bool` : reserved flag (present for compatibility; not used by the current renderer)

### `Line`

A `Line` is a tiny wrapper that binds:

- `inh`: the behavior object
- `owner`: the owning widget instance

It exposes `print()`, `action()`, `submenu()`, `grab()`.

### `LineAction`

`LineAction` is an `IntEnum` used by the menu and widgets.

Navigation and lifecycle:

- `UP`, `DOWN`, `LEFT`, `RIGHT`
- `OK`
- `ON_ENTER`, `ON_LEAVE` (focus events for the currently selected line)
- `BREAK` (used as a “backspace/delete/back” signal in some widgets, and as a way to exit a submenu)

Text input (for `Edit`):

- `DIGIT_BASE`

To inject a character `ch` into `Edit`, send:

- `int(LineAction.DIGIT_BASE) + ord(ch)`

The widget interprets this as a single byte (0..255).

### `Menu`

`Menu` acts as both a widget and a `LineInh` implementation.

Key behaviors:

- maintains a list of `lines`
- tracks selection by index (`child_it`)
- keeps a cursor position within the visible window (`cur_line`)
- supports nested submenus (`sub`)

The selection marker and layout:

- Each visible LCD row starts with a 2-character prefix:
  - `"> "` for the currently selected line
  - `"  "` for others
- The line body is rendered into `cols - 2` characters.

#### Scrolling (“window”)

The menu uses `cur_line` to keep the selection within the visible rows.

To match a specific display height, call:

- `menu.set_rows_hint(scr.rows)`

before handling navigation actions (or before rendering).

## Rendering

### `Menu.render(cols, rows) -> list[str]`

Returns exactly `rows` strings, each padded/truncated to `cols`.

If a submenu is active, it renders the submenu instead.

### `Menu.draw_to_lcds(lcds)`

Convenience method that writes all rows using `lcds.write_at()` and then calls `lcds.flush()`.

The `lcds` object must look like `LCDS`:

- properties: `cols`, `rows`
- methods: `write_at(col, row, text)` and `flush()`

## Input handling: recommended mapping

A typical key mapping is:

- Up: `LineAction.UP`
- Down: `LineAction.DOWN`
- Left: `LineAction.LEFT`
- Right: `LineAction.RIGHT`
- Enter: `LineAction.OK`
- Backspace: `LineAction.BREAK`
- Printable ASCII: `LineAction.DIGIT_BASE + ord(ch)`

See [examples/menu_demo.py](../examples/menu_demo.py) for a working Windows console implementation (WASD, arrows, Enter, Backspace, Esc).

## Widgets

All widgets below expose `.line` (a `Line` instance) for insertion into a `Menu`.

### `SwitchItem(name, select=False)`

- Displays: `name` plus a trailing bracket group `[*]` / `[ ]`
- `LEFT` / `RIGHT` toggles `select`
- `ON_ENTER` / `ON_LEAVE` affects bracket style

### `RangeItem(name, min, max, current=0)`

- Displays `name` and the current numeric value aligned to the right in brackets
- `LEFT` decrements (down to `min`)
- `RIGHT` increments (up to `max`)

### `EnumItem(name, positions, pos=0)`

- Displays `name` and the current position label aligned to the right
- `LEFT` / `RIGHT` cycles through `positions` (wrap-around)

### `TimeItem(h=0, m=0, s=0)`

- Displays `HH:MM:SS`
- When focused (`enter=True`), the selected segment is wrapped in `< >`
- `OK` cycles the selected segment (H → M → S)
- `RIGHT` increments the selected segment (wrap-around: 24h / 60m / 60s)

### `Edit()`

- In-place editor for a byte string (latin-1 semantics)
- Cursor is rendered as `|`
- `BREAK` deletes the character to the left of the cursor
- Printable input is delivered via `LineAction.DIGIT_BASE + ord(ch)`

### `Ok(commit=None)`

- Displays `Save`
- On `OK`: calls `commit(index)` if provided and returns `BREAK`
  - returning `BREAK` is typically used by parent logic to “exit” a submenu/action

### `Space()`

- Renders a separator line (dashes)

### `Switch(pin, name="", eep=0)`

A composite widget that can enter an edit mode.

- `OK` enters edit mode (internally uses `Edit`)
- While in edit mode:
  - actions are forwarded to the editor
  - `OK` exits edit mode and commits the edited name
  - `grab()` returns `True`, so the menu won’t move selection while editing

## Minimal LCD example

```python
from py_hd44780_i2c_pcf8574 import HD44780_PCF8574, LCDS, VARIANT_A
from py_hd44780_i2c_pcf8574.menu import Menu, SwitchItem, RangeItem, LineAction
from py_hd44780_i2c_pcf8574.mcp2221a_i2c import MCP2221AI2C

i2c = MCP2221AI2C(i2c_speed_hz=100_000).open()
lcd = HD44780_PCF8574(i2c=i2c, mapping=VARIANT_A)
lcd._cfg.address_7bit = 0x3F
lcd.init()

scr = LCDS(lcd)

menu = Menu("Main")
menu.add_line(SwitchItem("WiFi", select=True).line)
menu.add_line(RangeItem("Vol", min=0, max=10, current=5).line)

menu.set_rows_hint(scr.rows)
if menu.lines:
    menu.lines[menu.child_it].action(LineAction.ON_ENTER)

menu.draw_to_lcds(scr)

# Later, after you read a key:
# menu.menu_action(LineAction.DOWN)
# menu.draw_to_lcds(scr)
```
