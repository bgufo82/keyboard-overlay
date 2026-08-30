@echo off
REM Builds KeyOverlay.exe from key_overlay.py using PyInstaller.
REM Run this ON WINDOWS, inside this folder (double-click it, or run from cmd).

echo Installing dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo.
echo Building KeyOverlay.exe ...
REM --hidden-import PIL._tkinter_finder is required: PyInstaller's static
REM analysis misses this module, which Pillow needs to register its image
REM type with Tk. Without it, ImageTk.PhotoImage silently fails only in the
REM built exe (works fine when run as a plain script) - showing as blank
REM black squares with no border or text.
python -m PyInstaller --onefile --noconsole --name KeyOverlay ^
    --hidden-import=PIL._tkinter_finder ^
    --collect-submodules=PIL ^
    key_overlay.py

echo.
echo Done. Your exe is in the "dist" folder: dist\KeyOverlay.exe
echo overlay_config.json will be created next to the exe the first time you run it.
pause
