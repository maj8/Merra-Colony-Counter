@echo off
rem Merra Colony Counter training kit - step 2.
rem Collects your counts: Merra Colony Counter save files (colony_backup_*.json, from the
rem app's Save button) in your Downloads folder or next to the photos, and DotDotGoose .pnt
rem files. Writes annotations\points.csv. Run it again whenever you have counted or corrected more.
cd /d "%~dp0"
if exist .venv\Scripts\python.exe (call .venv\Scripts\activate.bat) else (
  echo Run 1_SETUP.bat first.
  pause
  exit /b 1
)
python scripts\import_annotations.py
pause
