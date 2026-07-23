@echo off
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "SRC=%~dp0Washa_Mfumo_Mmoja.bat"
copy /Y "%SRC%" "%STARTUP%\Washa_LUMC.bat" >nul
echo.
echo Imewekwa kwenye Startup ? mfumo utawasha otomatiki unapowasha PC.
echo Mahali: %STARTUP%\Washa_LUMC.bat
echo.
pause
