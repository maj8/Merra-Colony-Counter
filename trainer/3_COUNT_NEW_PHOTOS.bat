@echo off
rem Counts every photo in the new_photos folder with the trained model.
rem Output in results\: counts.csv, points.csv, app_backup.json and dotted photos.
cd /d "%~dp0"
if not exist runs\colony\weights\best.pt (
  echo No trained model yet - run 2_TRAIN.bat first.
  pause
  exit /b 1
)
if not exist new_photos mkdir new_photos
call .venv\Scripts\activate.bat
set CONF=0.3
if exist runs\colony\best_conf.txt set /p CONF=<runs\colony\best_conf.txt
python scripts\predict.py --model runs\colony\weights\best.pt --images new_photos --out results --conf %CONF%
echo.
echo Done. Open results\counts.csv. Check the dots in results\annotated, or load
echo results\app_backup.json in the Colony Counter app to correct them.
pause
