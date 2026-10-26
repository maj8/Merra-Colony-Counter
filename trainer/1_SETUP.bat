@echo off
rem One-off setup: creates a private Python environment in this folder and installs the
rem deep-learning libraries (PyTorch + Ultralytics YOLO). Takes 5-15 minutes, needs internet.
cd /d "%~dp0"
where py >nul 2>nul && (set PY=py -3) || (set PY=python)
if not exist .venv\Scripts\python.exe (
  echo Creating Python environment...
  %PY% -m venv .venv || goto :nopython
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
where nvidia-smi >nul 2>nul
if %errorlevel%==0 (
  echo NVIDIA GPU found - installing GPU version of PyTorch
  pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
) else (
  echo No NVIDIA GPU found - installing CPU version of PyTorch ^(training will be slow^)
  pip install torch torchvision
)
pip install ultralytics pillow numpy
python -c "import torch; print('PyTorch', torch.__version__, '| GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'none')"
echo.
echo Setup finished. Next: double-click 2_TRAIN.bat
pause
exit /b 0

:nopython
echo Python 3.9 or newer is needed. Install it from https://www.python.org/downloads/ (tick "Add to PATH"), then run this again.
pause
exit /b 1
