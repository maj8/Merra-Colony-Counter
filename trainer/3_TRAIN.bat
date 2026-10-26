@echo off
rem Merra Colony Counter training kit - step 3.
rem Builds the training set from annotations\points.csv, trains the detector, then tests it on
rem the held-back photos (annotations\val_photos.txt). Expect 20-60 min with an NVIDIA GPU,
rem many hours on CPU only.
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Run 1_SETUP.bat first.
  pause
  exit /b 1
)
call .venv\Scripts\activate.bat
python scripts\train.py
echo.
echo Training log and charts: runs\colony   Model: runs\colony\weights\best.pt
echo Next: put photos in new_photos and run 4_COUNT_NEW_PHOTOS.bat
pause
