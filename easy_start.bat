@echo off
title AirGap Connect - Receiver Launcher
echo ===================================================
echo   AirGap Connect - Windows Firewall Configurator
echo ===================================================
echo.

net session >nul 2>&1
if %errorLevel% == 0 (
    echo [OK] Administrator permissions confirmed.
) else (
    echo [!] Requesting Administrator privileges to unblock port 5005 on your Wi-Fi...
    powershell -Command "Start-Process '%~dpnx0' -Verb RunAs"
    exit /b
)

echo.
echo Adding Firewall Rule to allow phone connection...
netsh advfirewall firewall add rule name="AirGap Receiver Port 5005" dir=in action=allow protocol=TCP localport=5005 >nul 2>&1
echo [OK] Firewall configured!

echo.
echo ===================================================
echo   Starting Python Receiver...
echo ===================================================
cd /d "%~dp0Receiver"
echo Installing required Python packages...
pip install -r requirements.txt
echo.
python app.py
pause
