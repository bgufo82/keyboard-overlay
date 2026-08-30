# Key Overlay

A lightweight, always-on-top Windows overlay that shows the last **up to 5**
keys pressed, as fading squares — handy for streaming, tutorials, or ASMR
typing videos.

- Squares fade **in** the instant a key is pressed, and fade **out** after a
  short hold, driven directly by real keyboard events (not a fixed timer
  loop unrelated to input).
- Fully resizable squares, adjustable opacity, colors, fonts, position, and
  timing — all via `overlay_config.json`.
- Click-through by default, so it never blocks clicks to whatever's underneath.
- Config file is auto-reloaded if you edit it while the app is running (or
  press `Ctrl+Alt+R`).

## Why you're getting a script + build script, not a raw .exe

I built and tested this from a Linux sandbox. PyInstaller has to run *on
the target OS* to produce a working native executable — it doesn't
cross-compile Windows binaries from Linux. So instead I've packaged
everything so you get a real `KeyOverlay.exe` in under a minute on your own
Windows machine, with no coding needed on your end.

## Build it (one-time, ~30 seconds)

1. Install Python 3.9+ on Windows if you don't have it: https://python.org/downloads
   (tick "Add Python to PATH" during install).
2. Put `key_overlay.py`, `requirements.txt`, `build_exe.bat`, and
   `overlay_config.json` in the same folder.
3. Double-click **`build_exe.bat`**. It installs `keyboard` + `pyinstaller`
   and builds the exe.
4. Your app is at `dist\KeyOverlay.exe`. Copy `overlay_config.json` next to
   it if you want your customized settings to travel with the exe (otherwise
   a default one is auto-created on first run).

## Running it

- Double-click `KeyOverlay.exe`, or right-click → **Run as administrator**
  if key capture doesn't work in certain elevated apps/games (Windows
  requires matching privilege level for global key hooks to see keys going
  to a higher-privilege window).
- Quit with `Ctrl+Alt+Q` (there's no window/taskbar icon — it's a pure overlay).
- Reload config live with `Ctrl+Alt+R`.

## Customizing (`overlay_config.json`)

| Key | What it does |
|---|---|
| `num_slots` | Max simultaneous keys shown (1–5). |
| `square_size` | Pixel size of each square. |
| `gap` | Space between squares. |
| `corner_radius` | Rounded-corner radius. |
| `max_opacity` | 0.0–1.0, how opaque a fully-shown key gets. |
| `fade_in_ms` / `hold_ms` / `fade_out_ms` | Timing of the fade in → hold → fade out cycle. |
| `bg_color` / `text_color` / `border_color` | Hex colors. |
| `font_family` / `font_size` | Key label font. |
| `anchor` | `bottom-center`, `bottom-left`, `bottom-right`, `top-center`, `top-left`, `top-right`, or `custom`. |
| `margin` | Distance from the screen edge for non-custom anchors. |
| `position_x` / `position_y` | Only used when `anchor` is `"custom"`. |
| `click_through` | `true` = mouse clicks pass through the overlay. |
| `quit_hotkey` / `reload_hotkey` | Global hotkeys (keyboard-lib syntax, e.g. `"ctrl+alt+q"`). |

Edit the file, save, and the running overlay updates automatically (no restart needed).

## Notes

- Held/repeating keys refresh their own square's timer instead of stealing
  a new slot, so holding a key doesn't cause flicker across all 5 slots.
- If a 6th distinct key is pressed while all 5 slots are busy, the
  oldest slot is recycled (round-robin) for the new key.
- Key labels are rendered as a bitmap (via Pillow) rather than tkinter's
  native text drawing, because native GDI text routinely fails to draw
  inside a semi-transparent Windows overlay window even when shapes render
  fine in the same window. If you ever see a square with no letter again,
  it means Pillow couldn't find a usable font on that machine - check that
  `Pillow` installed correctly via `build_exe.bat`.
- This only *displays* key presses on your own screen — it doesn't log,
  store, or send input anywhere.
