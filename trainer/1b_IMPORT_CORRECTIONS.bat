@echo off
rem Reads your corrected DotDotGoose files (*.pnt) and/or Colony Counter app backups (*.json)
rem from the countpics folder and its Batch folders, and updates annotations\points.csv.
rem Run this after correcting dots and before 2_TRAIN.bat.
cd /d "%~dp0"
if exist .venv\Scripts\python.exe (call .venv\Scripts\activate.bat)
python scripts\import_annotations.py --images ..
pause
