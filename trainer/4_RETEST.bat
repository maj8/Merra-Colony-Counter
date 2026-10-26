@echo off
rem Re-runs only the testing step (no retraining) on the held-back photos, e.g. after
rem changing the counting settings. Results in results_val\ and runs\colony\best_conf.txt
cd /d "%~dp0"
call .venv\Scripts\activate.bat
python scripts\train.py --images .. --skip-train
