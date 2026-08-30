"""
Diagnostic #2 for Key Overlay - isolates the Pillow -> Tk image pipeline
specifically (the piece the first diagnostic didn't test).

Run this directly:
    python diagnose2.py

Needs Pillow installed (pip install Pillow) - same as the real app.
"""

import tkinter as tk
from PIL import Image, ImageDraw, ImageTk

print(__doc__)

SECONDS_PER_TEST = 4


def run_window(build_fn, label):
    print(f"\n--- {label} ---")
    print(f"Opening now, watch it for {SECONDS_PER_TEST} seconds...")
    win = build_fn()
    win.after(SECONDS_PER_TEST * 1000, win.destroy)
    win.mainloop()
    print("(closed)")


def test5():
    """Exactly what the real app does: RGBA Pillow image with transparent
    corners (alpha=0 outside the rounded rect) shown via a Label, inside a
    borderless + semi-transparent window."""
    size = 140
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))  # transparent corners
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([2, 2, size - 2, size - 2], radius=12,
                            fill=(30, 30, 30, 255), outline=(77, 163, 255, 255), width=3)
    draw.text((size / 2 - 15, size / 2 - 25), "Q", fill=(255, 255, 255, 255))

    w = tk.Tk()
    w.overrideredirect(True)
    w.attributes("-topmost", True)
    w.attributes("-alpha", 0.85)
    w.geometry(f"{size}x{size}+200+200")
    photo = ImageTk.PhotoImage(img)
    lbl = tk.Label(w, image=photo, bd=0, highlightthickness=0)
    lbl.image = photo  # keep a reference
    lbl.pack(fill="both", expand=True)
    return w


def test6():
    """Same, but the Pillow image is fully OPAQUE (no per-pixel alpha/
    transparent corners at all) - isolates whether the transparent PNG-style
    corners specifically are what's breaking on this machine."""
    size = 140
    img = Image.new("RGB", (size, size), (30, 30, 30))  # solid, no alpha channel
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([2, 2, size - 2, size - 2], radius=12,
                            fill=(30, 30, 30), outline=(77, 163, 255), width=3)
    draw.text((size / 2 - 15, size / 2 - 25), "Q", fill=(255, 255, 255))

    w = tk.Tk()
    w.overrideredirect(True)
    w.attributes("-topmost", True)
    w.attributes("-alpha", 0.85)
    w.geometry(f"{size}x{size}+200+200")
    photo = ImageTk.PhotoImage(img)
    lbl = tk.Label(w, image=photo, bd=0, highlightthickness=0)
    lbl.image = photo  # keep a reference
    lbl.pack(fill="both", expand=True)
    return w


run_window(test5, "Test 5: Pillow RGBA image (transparent corners) via Label - matches real app exactly")
run_window(test6, "Test 6: Pillow RGB image (fully opaque, no per-pixel transparency) via Label")

print("\nBoth tests done.")
print("Please tell me: did Test 5 and/or Test 6 show a clear white 'Q' on a")
print("dark square with a blue border, or blank/black? This tells us whether")
print("the problem is the Pillow image pipeline itself, or specifically the")
print("per-pixel transparent corners within that image.")
