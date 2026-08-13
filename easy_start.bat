@echo off
setlocal EnableDelayedExpansion
title AirGap Connect - Receiver Launcher

echo ===================================================
echo   AirGap Connect - Setup ^& Launcher
echo ===================================================
echo.

:: -----------------------------------------------------------------
:: 1. Elevate to Administrator (needed for the firewall rule)
:: -----------------------------------------------------------------
net session >nul 2>&1
if %errorLevel% == 0 (
    echo [OK] Administrator permissions confirmed.
) else (
    echo [!] Requesting Administrator privileges to unblock port 5005...
    powershell -NoProfile -Command "Start-Process '%~dpnx0' -Verb RunAs"
    exit /b
)

cd /d "%~dp0Receiver"

:: -----------------------------------------------------------------
:: 2. Locate a usable Python (3.8+), preferring the official launcher
:: -----------------------------------------------------------------
echo.
echo Looking for a compatible Python (3.8 or newer)...
set "PYEXE="

where py >nul 2>&1
if %errorLevel% == 0 (
    py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3,8) else 1)" >nul 2>&1
    if !errorLevel! == 0 set "PYEXE=py -3"
)

if not defined PYEXE (
    where python >nul 2>&1
    if %errorLevel% == 0 (
        python -c "import sys; sys.exit(0 if sys.version_info >= (3,8) else 1)" >nul 2>&1
        if !errorLevel! == 0 set "PYEXE=python"
    )
)

if not defined PYEXE (
    echo.
    echo [XX] No compatible Python installation found ^(need 3.8 or newer^).
    echo.
    echo      Opening the Python download page for you now. On the
    echo      installer's first screen, check "Add python.exe to PATH"
    echo      before clicking Install, then re-run this launcher.
    echo.
    start "" "https://www.python.org/downloads/"
    pause
    exit /b 1
)

for /f "delims=" %%v in ('!PYEXE! -c "import platform; print(platform.python_version())"') do set "PYVER=%%v"
echo [OK] Using Python !PYVER!

:: -----------------------------------------------------------------
:: 3. Create (or reuse) an isolated virtual environment
:: -----------------------------------------------------------------
echo.
if exist ".venv\Scripts\python.exe" (
    echo [OK] Virtual environment already exists ^(Receiver\.venv^).
) else (
    echo Creating an isolated virtual environment in Receiver\.venv ...
    !PYEXE! -m venv .venv
    if not exist ".venv\Scripts\python.exe" (
        echo [!] Virtual environment creation failed. Continuing with the
        echo     system Python instead ^(will install with --user^).
    )
)

if exist ".venv\Scripts\python.exe" (
    set "VENV_PY=.venv\Scripts\python.exe"
    set "PIP_USER_FLAG="
) else (
    set "VENV_PY=!PYEXE!"
    set "PIP_USER_FLAG=--user"
)

:: -----------------------------------------------------------------
:: 4. Install dependencies, with automatic retries on failure
:: -----------------------------------------------------------------
echo.
echo Upgrading pip...
!VENV_PY! -m pip install --upgrade pip --quiet

echo Installing required Python packages ^(this can take a minute^)...
!VENV_PY! -m pip install -r requirements.txt !PIP_USER_FLAG!
if not !errorLevel! == 0 (
    echo.
    echo [!] Install attempt 1 failed. Retrying with a clean cache...
    !VENV_PY! -m pip install -r requirements.txt !PIP_USER_FLAG! --no-cache-dir
)
if not !errorLevel! == 0 (
    echo.
    echo [!] Install attempt 2 failed. Retrying once more with a longer
    echo     network timeout, in case this was a slow-connection issue...
    !VENV_PY! -m pip install -r requirements.txt !PIP_USER_FLAG! --no-cache-dir --timeout 120
)
if not !errorLevel! == 0 (
    echo.
    echo [XX] Package installation failed after 3 attempts. Check your
    echo      internet connection and try again, or see:
    echo      https://github.com/miidhunraj/AirGap_V2#readme
    pause
    exit /b 1
)

:: -----------------------------------------------------------------
:: 5. Verify the install actually works before launching anything
:: -----------------------------------------------------------------
echo.
echo Verifying installation...
!VENV_PY! verify_install.py
if not !errorLevel! == 0 (
    echo.
    echo [!] Verification found problems. Attempting one automatic repair
    echo     ^(force-reinstall of all packages^)...
    !VENV_PY! -m pip install -r requirements.txt !PIP_USER_FLAG! --force-reinstall --no-cache-dir
    !VENV_PY! verify_install.py
    if not !errorLevel! == 0 (
        echo.
        echo [XX] AirGap could not verify a working install. Please review
        echo      the messages above, or open an issue at:
        echo      https://github.com/miidhunraj/AirGap_V2/issues
        pause
        exit /b 1
    )
)

:: -----------------------------------------------------------------
:: 6. Firewall rule (idempotent: drop any stale rule, then add fresh)
:: -----------------------------------------------------------------
echo.
echo Configuring Windows Firewall for port 5005...
netsh advfirewall firewall delete rule name="AirGap Receiver Port 5005" >nul 2>&1
netsh advfirewall firewall add rule name="AirGap Receiver Port 5005" dir=in action=allow protocol=TCP localport=5005 >nul 2>&1
if !errorLevel! == 0 (
    echo [OK] Firewall configured.
) else (
    echo [!] Could not add the firewall rule automatically. If your phone
    echo     can't connect, allow AirGap through Windows Defender Firewall,
    echo     or run this command yourself in an Administrator prompt:
    echo     netsh advfirewall firewall add rule name="AirGap Receiver Port 5005" dir=in action=allow protocol=TCP localport=5005
)

:: -----------------------------------------------------------------
:: 7. Launch
:: -----------------------------------------------------------------
echo.
echo ===================================================
echo   Starting AirGap Receiver...
echo   Close this window to stop the receiver.
echo ===================================================
!VENV_PY! app.py

echo.
echo AirGap has stopped.
pause
