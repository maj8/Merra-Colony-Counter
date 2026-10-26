@echo off
rem Builds the training set from annotations\points.csv, trains the detector, then tests it on
rem the three held-back photos. Expect ~20-60 min with an NVIDIA GPU, many hours on CPU only.
rem Photos are found in the folder above this one (and its Batch subfolders).
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Run 1_SETUP.bat first.
  pause
  exit /b 1
)
call .venv\Scripts\activate.bat
python scripts\train.py --images ..
echo.
echo Training log and charts: runs\colony   Model: runs\colony\weights\best.pt
pause
