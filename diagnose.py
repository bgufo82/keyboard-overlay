"""
Diagnostic for Key Overlay rendering issues.

Run this directly:
    python diagnose.py

It opens four small windows, one at a time, each testing one more piece of
what the real overlay needs (each stays open ~4 seconds, then auto-closes
and the next one opens). Please watch each one and report back EXACTLY
which numbered tests show a clear white "Q" on a dark square with a blue
border, and which ones are blank/black. A screenshot of each is even more
useful if you're able to share one - I can look at it directly.
"""

import tkinter as tk

print(__doc__)

SECONDS_PER_TEST = 4


def run_window(build_fn, label):
    print(f"\n--- {label} ---")
    print(f"Opening now, watch it for {SECONDS_PER_TEST} seconds...")
    win = build_fn()
    win.after(SECONDS_PER_TEST * 1000, win.destroy)
    win.mainloop()
    print("(closed)")


def test1():
    w = tk.Tk()
    w.title("Test 1")
    w.geometry("220x140+200+200")
    tk.Label(w, text="Q", font=("Segoe UI", 40, "bold"),
             bg="#1e1e1e", fg="#ffffff").pack(fill="both", expand=True)
    return w


def test2():
    w = tk.Tk()
    w.overrideredirect(True)
    w.attributes("-topmost", True)
    w.geometry("220x140+200+200")
    tk.Label(w, text="Q", font=("Segoe UI", 40, "bold"),
             bg="#1e1e1e", fg="#ffffff").pack(fill="both", expand=True)
    return w


def test3():
    w = tk.Tk()
    w.overrideredirect(True)
    w.attributes("-topmost", True)
    w.geometry("220x140+200+200")
    w.attributes("-alpha", 0.85)
    tk.Label(w, text="Q", font=("Segoe UI", 40, "bold"),
             bg="#1e1e1e", fg="#ffffff").pack(fill="both", expand=True)
    return w


def test4():
    w = tk.Tk()
    w.overrideredirect(True)
    w.attributes("-topmost", True)
    w.geometry("220x140+200+200")
    w.attributes("-alpha", 0.85)
    c = tk.Canvas(w, width=220, height=140, bg="#1e1e1e", highlightthickness=0)
    c.pack(fill="both", expand=True)
    c.create_rectangle(10, 10, 210, 130, fill="#1e1e1e", outline="#4da3ff", width=3)
    c.create_text(110, 70, text="Q", fill="#ffffff", font=("Segoe UI", 40, "bold"))
    return w


run_window(test1, "Test 1: plain normal window (baseline - should clearly show white Q)")
run_window(test2, "Test 2: borderless + always-on-top, fully opaque (no transparency)")
run_window(test3, "Test 3: borderless + 85% opacity (this is what the real overlay uses)")
run_window(test4, "Test 4: borderless + 85% opacity + Canvas rectangle/text")

print("\nAll tests done.")
print("Please tell me, for each of the 4 tests, whether you saw a clear")
print("white 'Q' on a dark square with a blue border, or a blank/black box.")
