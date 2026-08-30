"""
Key Overlay - a lightweight on-screen keystroke display for Windows.

Shows up to 5 squares, one per recently-pressed key. Each square fades in
the instant its key is pressed and fades out after a short hold, in sync
with the actual keyboard input. Size, opacity, colors, timings and position
are all controlled through overlay_config.json (created automatically on
first run, next to the exe / script).

Dependencies:
    pip install keyboard Pillow

Run:
    python key_overlay.py
(On Windows, global key capture generally requires an elevated/admin
terminal, or running the built exe "as administrator".)

Quit:
    Press the quit hotkey (default: ctrl+alt+q)
"""

import ctypes
import json
import os
import queue
import sys
import time
import traceback
import tkinter as tk

try:
    from PIL import Image, ImageDraw, ImageFont, ImageTk
except ImportError:
    print("Missing dependency 'Pillow'. Install it with:\n    pip install Pillow")
    sys.exit(1)

try:
    import keyboard
except ImportError:
    print("Missing dependency 'keyboard'. Install it with:\n    pip install keyboard")
    sys.exit(1)


# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------

def base_dir():
    """Directory the script/exe lives in (works for PyInstaller too)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


CONFIG_PATH = os.path.join(base_dir(), "overlay_config.json")
LOG_PATH = os.path.join(base_dir(), "key_overlay_error.log")


def log_error(message):
    """Best-effort error logging to a plain text file next to the app.

    The app runs with --noconsole (no visible terminal), so without this,
    any failure is completely silent and undiagnosable. This never raises.
    """
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")
    except Exception:
        pass

DEFAULT_CONFIG = {
    "num_slots": 5,             # max keys shown at once (hard cap, see note below)
    "square_size": 70,          # pixel size of each square
    "gap": 10,                  # pixel gap between squares
    "corner_radius": 12,        # rounded-corner radius
    "max_opacity": 0.85,        # 0.0 - 1.0, opacity a fully "on" square reaches
    "fade_in_ms": 120,          # fade-in duration
    "hold_ms": 550,             # time held at full opacity before fading out
    "fade_out_ms": 400,         # fade-out duration
    "bg_color": "#1e1e1e",      # square background color
    "text_color": "#ffffff",    # key label color
    "border_color": "#4da3ff",  # square border/accent color
    "font_family": "Segoe UI",
    "font_size": 20,
    "anchor": "bottom-center",  # bottom-center | bottom-left | bottom-right |
                                 # top-center | top-left | top-right | custom
    "margin": 60,                # distance from the chosen screen edge
    "position_x": None,          # only used when anchor == "custom"
    "position_y": None,          # only used when anchor == "custom"
    "click_through": True,       # let mouse clicks pass through the overlay
    "always_on_top": True,
    "quit_hotkey": "ctrl+alt+q",
    "reload_hotkey": "ctrl+alt+r",
    "ignore_keys": ["unknown"],   # key names to never display
    "fps": 60,
}

# Note on "max 5 keys at a time": num_slots hard-caps this at 5 max (you can
# lower it, but raising it above 5 is intentionally not exposed here since
# the spec is a 5-key overlay).


def load_config():
    if not os.path.exists(CONFIG_PATH):
        save_config(DEFAULT_CONFIG)
        return dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except (json.JSONDecodeError, OSError):
        cfg = {}
    merged = dict(DEFAULT_CONFIG)
    merged.update(cfg)
    merged["num_slots"] = max(1, min(5, int(merged.get("num_slots", 5))))
    return merged


def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


# --------------------------------------------------------------------------
# Key name formatting
# --------------------------------------------------------------------------

KEY_LABELS = {
    "space": "Space", "enter": "Enter", "backspace": "\u232B",
    "tab": "Tab", "esc": "Esc", "escape": "Esc",
    "left": "\u2190", "right": "\u2192", "up": "\u2191", "down": "\u2193",
    "shift": "Shift", "left shift": "Shift", "right shift": "Shift",
    "ctrl": "Ctrl", "left ctrl": "Ctrl", "right ctrl": "Ctrl",
    "alt": "Alt", "alt gr": "AltGr", "left alt": "Alt", "right alt": "Alt",
    "caps lock": "Caps", "delete": "Del", "insert": "Ins",
    "page up": "PgUp", "page down": "PgDn", "home": "Home", "end": "End",
    "windows": "\u2756", "left windows": "\u2756", "right windows": "\u2756",
    "print screen": "PrSc", "num lock": "NumLk", "scroll lock": "ScrLk",
}


def format_key(name):
    name = (name or "").lower().strip()
    if name in KEY_LABELS:
        return KEY_LABELS[name]
    if name.startswith("f") and name[1:].isdigit():
        return name.upper()
    if len(name) == 1:
        return name.upper()
    return name[:6].capitalize()


# --------------------------------------------------------------------------
# Pillow-based square rendering (background + border + key text baked into
# one bitmap). We deliberately do NOT use tkinter's native canvas text
# drawing here: on Windows, GDI-rendered text routinely fails to draw (or
# draws invisibly) inside a semi-transparent ("-alpha") layered window, even
# though solid shape fills render fine in the same window. Rendering the
# whole square - background, rounded border, and the key label - as a single
# Pillow bitmap and displaying that avoids the issue entirely.
# --------------------------------------------------------------------------

def hex_to_rgba(hex_color, alpha=255):
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return (r, g, b, alpha)


_FONT_CACHE = {}


def load_font(family, size, bold=True):
    cache_key = (family, size, bold)
    if cache_key in _FONT_CACHE:
        return _FONT_CACHE[cache_key]

    fam = family.lower().replace(" ", "")
    candidates = []
    if "segoe" in fam:
        candidates += ["segoeuib.ttf", "seguisb.ttf"] if bold else ["segoeui.ttf"]
    elif "arial" in fam:
        candidates += ["arialbd.ttf"] if bold else ["arial.ttf"]
    elif "consolas" in fam:
        candidates += ["consolab.ttf"] if bold else ["consola.ttf"]
    elif "tahoma" in fam:
        candidates += ["tahomabd.ttf"] if bold else ["tahoma.ttf"]
    elif "calibri" in fam:
        candidates += ["calibrib.ttf"] if bold else ["calibri.ttf"]
    else:
        candidates.append(f"{family}.ttf")
    # generic Windows fallbacks, in case the requested family isn't found
    candidates += ["segoeuib.ttf", "arialbd.ttf", "tahomabd.ttf", "arial.ttf"]

    fonts_dir = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts")
    font = None
    for name in candidates:
        path = os.path.join(fonts_dir, name)
        if os.path.exists(path):
            try:
                font = ImageFont.truetype(path, size)
                break
            except OSError:
                continue
    if font is None:
        # last resort: let PIL try to resolve the family name directly
        # (works on some non-Windows setups), else fall back to a basic
        # built-in bitmap font so text is never simply missing.
        try:
            font = ImageFont.truetype(family, size)
        except OSError:
            try:
                font = ImageFont.load_default(size=size)
            except TypeError:
                font = ImageFont.load_default()

    _FONT_CACHE[cache_key] = font
    return font


def render_square_image(size, cfg, text):
    """Render one key square (background + rounded border + centered label)
    as an RGBA Pillow image."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    pad = 2
    radius = max(0, min(cfg["corner_radius"], (size - 2 * pad) // 2))
    bg = hex_to_rgba(cfg["bg_color"])
    border = hex_to_rgba(cfg["border_color"])

    draw.rounded_rectangle(
        [pad, pad, size - pad, size - pad],
        radius=radius, fill=bg, outline=border, width=2,
    )

    if text:
        font = load_font(cfg["font_family"], cfg["font_size"], bold=True)
        text_fill = hex_to_rgba(cfg["text_color"])
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        tx = (size - tw) / 2 - bbox[0]
        ty = (size - th) / 2 - bbox[1]
        draw.text((tx, ty), text, font=font, fill=text_fill)

    return img


# --------------------------------------------------------------------------
# Windows click-through helper
# --------------------------------------------------------------------------

def make_click_through(hwnd):
    if os.name != "nt":
        return
    GWL_EXSTYLE = -20
    WS_EX_LAYERED = 0x00080000
    WS_EX_TRANSPARENT = 0x00000020
    SWP_NOMOVE = 0x0002
    SWP_NOSIZE = 0x0001
    SWP_NOZORDER = 0x0004
    SWP_FRAMECHANGED = 0x0020
    user32 = ctypes.windll.user32
    style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED | WS_EX_TRANSPARENT)
    # Make sure Windows actually re-evaluates the new extended style now,
    # rather than silently keeping the old (opaque, click-blocking) one.
    user32.SetWindowPos(
        hwnd, None, 0, 0, 0, 0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED
    )


# --------------------------------------------------------------------------
# A single fading key square
# --------------------------------------------------------------------------

class KeySlot:
    def __init__(self, root, cfg, x, y):
        self.cfg = cfg
        size = cfg["square_size"]

        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", cfg["always_on_top"])
        # NOTE: we intentionally do NOT use "-transparentcolor" (chroma-key
        # transparency) here. Combining "-transparentcolor" with "-alpha" on
        # the same Windows Toplevel is unreliable and commonly collapses to
        # a solid black window with nothing visible - the earlier
        # "black square" symptom. Instead the window background is simply
        # painted the same color as the square's fill, so the (small)
        # unrounded outer corners are visually indistinguishable from a true
        # cutout, and only "-alpha" (solid/reliable on its own) is used for
        # the fade.
        #
        # We also do NOT use tkinter's native canvas.create_text() to draw
        # the key label: on Windows, GDI-rendered text routinely fails to
        # draw inside a semi-transparent layered ("-alpha") window even
        # though solid shape fills render fine in that same window - which
        # was the "square renders, but no letter shows" symptom. Instead the
        # whole square (background + border + label) is rendered as one
        # Pillow bitmap and shown as a plain image, which is unaffected by
        # that GDI/layered-window text bug.
        self.win.config(bg=cfg["bg_color"])
        self.win.geometry(f"{size}x{size}+{x}+{y}")
        self.win.attributes("-alpha", 0.0)

        self.label = tk.Label(self.win, bd=0, highlightthickness=0, bg=cfg["bg_color"])
        self.label.pack(fill="both", expand=True)

        self.key = ""
        self.photo = None
        self._render(size, cfg, "")

        self.win.update_idletasks()
        self._click_through_applied = False
        self.win.withdraw()

        self.active = False
        self.phase = "out"
        self.phase_start = 0.0
        self.alpha = 0.0

    def _render(self, size, cfg, text):
        self.win.config(bg=cfg["bg_color"])
        self.label.config(bg=cfg["bg_color"])
        try:
            img = render_square_image(size, cfg, text)
            photo = ImageTk.PhotoImage(img)
            # keep a strong reference on the instance - PhotoImage is
            # garbage collected (and the label goes blank) if nothing else
            # refers to it
            self.photo = photo
            self.label.config(image=self.photo, text="", compound="center")
        except Exception:
            # If Pillow's Tk photo-image bridge fails to load in this build
            # (a known PyInstaller packaging gap), fall back to a plain
            # tkinter-drawn square so the key is still visible instead of a
            # blank/black box, and log the real error for diagnosis.
            log_error(
                "Pillow image render/display failed, using plain-text "
                f"fallback for key square. Details:\n{traceback.format_exc()}"
            )
            self.photo = None
            self.label.config(
                image="", compound="center", text=text,
                bg=cfg["bg_color"], fg=cfg["text_color"],
                font=(cfg["font_family"], max(10, cfg["font_size"]), "bold"),
                relief="solid", bd=2, highlightbackground=cfg["border_color"],
            )

    def trigger(self, key_label):
        now = time.time()
        self.key = key_label
        self._render(self.cfg["square_size"], self.cfg, key_label)
        self.active = True
        self.phase = "in"
        # start the fade-in from wherever the alpha currently is, so a key
        # that's re-pressed mid-fade doesn't visually pop
        start_alpha = self.alpha
        fraction_done = start_alpha / self.cfg["max_opacity"] if self.cfg["max_opacity"] else 0
        self.phase_start = now - fraction_done * (self.cfg["fade_in_ms"] / 1000.0)
        self.win.deiconify()

        # Apply click-through only after the window has actually been shown
        # at least once. Modifying a window's extended style via ctypes
        # while it has never been mapped/shown appears to leave some
        # Windows systems unable to later update the window's visible
        # content via "-alpha", even though no error is ever raised - this
        # produces a permanently blank/black square with no exception and
        # no log entry. Applying it after the first real deiconify avoids
        # touching that not-yet-realized window state.
        if self.cfg["click_through"] and not self._click_through_applied:
            self._click_through_applied = True
            try:
                self.win.update_idletasks()
                hwnd = self.win.winfo_id()
                make_click_through(hwnd)
            except Exception:
                log_error("make_click_through failed:\n" + traceback.format_exc())

    def reposition(self, x, y, size, cfg):
        self.cfg = cfg
        self.win.geometry(f"{size}x{size}+{x}+{y}")
        self._render(size, cfg, self.key)

    def update(self, now):
        if not self.active:
            return
        cfg = self.cfg
        elapsed_ms = (now - self.phase_start) * 1000.0
        max_op = cfg["max_opacity"]

        if self.phase == "in":
            t = min(1.0, elapsed_ms / max(1, cfg["fade_in_ms"]))
            self.alpha = t * max_op
            if t >= 1.0:
                self.phase = "hold"
                self.phase_start = now
        elif self.phase == "hold":
            self.alpha = max_op
            if elapsed_ms >= cfg["hold_ms"]:
                self.phase = "out"
                self.phase_start = now
        elif self.phase == "out":
            t = min(1.0, elapsed_ms / max(1, cfg["fade_out_ms"]))
            self.alpha = max_op * (1.0 - t)
            if t >= 1.0:
                self.active = False
                self.win.withdraw()
                return

        try:
            self.win.attributes("-alpha", max(0.0, min(1.0, self.alpha)))
        except tk.TclError:
            pass

    def destroy(self):
        try:
            self.win.destroy()
        except tk.TclError:
            pass


# --------------------------------------------------------------------------
# Overlay manager
# --------------------------------------------------------------------------

class OverlayApp:
    def __init__(self):
        self.cfg = load_config()
        self.event_queue = queue.Queue()

        self.root = tk.Tk()
        self.root.withdraw()  # hidden control window

        self.slots = []
        self._build_slots()

        self._config_mtime = self._get_config_mtime()

        keyboard.hook(self._on_key_event, suppress=False)
        keyboard.add_hotkey(self.cfg["quit_hotkey"], self._request_quit)
        keyboard.add_hotkey(self.cfg["reload_hotkey"], self._request_reload)

        self.running = True
        self._tick()

    # -- layout -----------------------------------------------------------

    def _screen_size(self):
        return self.root.winfo_screenwidth(), self.root.winfo_screenheight()

    def _slot_positions(self):
        cfg = self.cfg
        n = cfg["num_slots"]
        size = cfg["square_size"]
        gap = cfg["gap"]
        total_w = n * size + (n - 1) * gap
        sw, sh = self._screen_size()
        margin = cfg["margin"]
        anchor = cfg["anchor"]

        if anchor == "custom" and cfg.get("position_x") is not None:
            x0 = cfg["position_x"]
            y0 = cfg["position_y"] or margin
        else:
            if "center" in anchor:
                x0 = (sw - total_w) // 2
            elif "left" in anchor:
                x0 = margin
            else:  # right
                x0 = sw - total_w - margin

            if anchor.startswith("top"):
                y0 = margin
            else:  # bottom
                y0 = sh - size - margin

        positions = []
        for i in range(n):
            positions.append((x0 + i * (size + gap), y0))
        return positions

    def _build_slots(self):
        for s in self.slots:
            s.destroy()
        self.slots = []
        positions = self._slot_positions()
        for x, y in positions:
            self.slots.append(KeySlot(self.root, self.cfg, x, y))

    def _apply_config_change(self):
        positions = self._slot_positions()
        n = self.cfg["num_slots"]
        # grow/shrink slot list to match num_slots
        while len(self.slots) < n:
            x, y = positions[len(self.slots)]
            self.slots.append(KeySlot(self.root, self.cfg, x, y))
        while len(self.slots) > n:
            self.slots.pop().destroy()
        for slot, (x, y) in zip(self.slots, positions):
            slot.reposition(x, y, self.cfg["square_size"], self.cfg)

    # -- key events (called from keyboard's hook thread) -------------------

    def _on_key_event(self, event):
        try:
            if event.event_type != "down":
                return
            name = (event.name or "").lower()
            if name in self.cfg["ignore_keys"]:
                return
            self.event_queue.put(name)
        except Exception:
            log_error("Key hook callback failed:\n" + traceback.format_exc())

    def _request_quit(self):
        self.event_queue.put("__QUIT__")

    def _request_reload(self):
        self.event_queue.put("__RELOAD__")

    def _get_config_mtime(self):
        try:
            return os.path.getmtime(CONFIG_PATH)
        except OSError:
            return 0

    # -- main loop ----------------------------------------------------------

    def _handle_key(self, key_name):
        label = format_key(key_name)

        # 1) If this exact key is already showing (in its own square), just
        #    refresh that square's timer. This guarantees a key can never
        #    appear on more than one square at once, and never jumps squares
        #    mid-display.
        for slot in self.slots:
            if slot.active and slot.key == label:
                slot.trigger(label)
                return

        # 2) Otherwise, prefer a completely free (inactive) square, in slot
        #    order, so a new key never interrupts a square that's actively
        #    showing a different key while an empty square sits unused.
        for slot in self.slots:
            if not slot.active:
                slot.trigger(label)
                return

        # 3) All 5 squares are busy with 5 different keys: only now do we
        #    recycle one, and we recycle the OLDEST one (earliest
        #    phase_start), so the square that gets reassigned is always the
        #    one that's been on screen the longest - never an arbitrary or
        #    just-triggered one.
        oldest_slot = min(self.slots, key=lambda s: s.phase_start)
        oldest_slot.trigger(label)

    def _tick(self):
        if not self.running:
            return

        # drain queued key/control events
        try:
            while True:
                item = self.event_queue.get_nowait()
                if item == "__QUIT__":
                    self.shutdown()
                    return
                elif item == "__RELOAD__":
                    self.cfg = load_config()
                    self._apply_config_change()
                else:
                    self._handle_key(item)
        except queue.Empty:
            pass

        # auto-reload if the config file was edited on disk
        mtime = self._get_config_mtime()
        if mtime != self._config_mtime:
            self._config_mtime = mtime
            self.cfg = load_config()
            self._apply_config_change()

        now = time.time()
        for slot in self.slots:
            slot.update(now)

        delay = max(10, int(1000 / max(1, self.cfg.get("fps", 60))))
        self.root.after(delay, self._tick)

    def shutdown(self):
        self.running = False
        try:
            keyboard.unhook_all()
        except Exception:
            pass
        for slot in self.slots:
            slot.destroy()
        self.root.quit()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def main():
    try:
        app = OverlayApp()
    except KeyboardInterrupt:
        return
    except Exception:
        tb = traceback.format_exc()
        log_error("FATAL during startup:\n" + tb)
        _show_fatal_error(tb)
        return

    try:
        app.run()
    except KeyboardInterrupt:
        app.shutdown()
    except Exception:
        tb = traceback.format_exc()
        log_error("FATAL during run:\n" + tb)
        _show_fatal_error(tb)


def _show_fatal_error(tb):
    """Best-effort visible error dialog. The app runs with --noconsole, so
    without this a crash would otherwise be completely silent."""
    try:
        import tkinter.messagebox as messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Key Overlay - error",
            "Key Overlay hit an error and couldn't continue.\n\n"
            f"Details were written to:\n{LOG_PATH}\n\n"
            + tb[-600:],
        )
        root.destroy()
    except Exception:
        pass


if __name__ == "__main__":
    main()
