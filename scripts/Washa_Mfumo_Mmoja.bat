@echo off
chcp 65001 >nul
title LUMC — Washa Mfumo
color 0A

set "GIS_ROOT=D:\MFUMO LUMC\LUMC\tanzania_gis"
set "URL=http://localhost:8000/"

echo.
echo  ========================================
echo   LUMC — Land Use Management System
echo  ========================================
echo.
echo  Inaanza server otomatiki...
echo  URL: %URL%
echo.
echo  Usifunge dirisha hili wakati unatumia mfumo.
echo  Bofya Ctrl+C au funga dirisha ili kuzima.
echo.

cd /d "%GIS_ROOT%"
if not exist "venv\Scripts\python.exe" (
    echo  HITILAFU: venv haipo. Angalia: %GIS_ROOT%\venv
    pause
    exit /b 1
)

REM Fungua browser baada ya sekunde chache
start "" cmd /c "timeout /t 3 /nobreak >nul & start \"\" \"%URL%\""

venv\Scripts\python.exe scripts\unified_server.py
if errorlevel 1 (
    echo.
    echo  Server imesimama kwa hitilafu.
    pause
)
