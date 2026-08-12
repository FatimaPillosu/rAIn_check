@echo off
REM rAIn_check launcher (dev-mode - see README "Known limitations": this is not yet the
REM conda-pack portable zip the plan specifies for partner machines, S8). Starts the
REM local server and opens the browser once it is actually ready. No registry writes;
REM nothing outside this folder and its own venv is touched.

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment not found. Run these three lines first, from this folder:
    echo   py -3.11 -m venv .venv
    echo   .venv\Scripts\python.exe -m pip install -r requirements.txt
    echo   .venv\Scripts\python.exe -m pip install llama-cpp-python==0.3.34 --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu
    echo.
    pause
    exit /b 1
)

echo Starting rAIn_check...
echo Your browser will open automatically once the server is ready.
echo Leave this window open while you use rAIn_check. Close it to stop the server.
echo.

REM Open the browser after a short delay, in a separate detached window, so it doesn't
REM race the server starting (opening before the server is up looks like "it doesn't
REM work" even though it's still starting).
start "" /min cmd /c "timeout /t 4 /nobreak >nul && start "" http://127.0.0.1:8501"

".venv\Scripts\python.exe" run_dev.py

echo.
echo rAIn_check has stopped (code %errorlevel%). If that was unexpected, scroll up for
echo the error above this line.
pause
