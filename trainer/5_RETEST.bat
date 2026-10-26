@echo off
rem Merra Colony Counter training kit - optional.
rem Re-runs only the testing step (no retraining) on the held-back photos.
rem Results in results_val\ and runs\colony\best_conf.txt
cd /d "%~dp0"
call .venv\Scripts\activate.bat
python scripts\train.py --skip-train
pause
