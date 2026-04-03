@echo off
echo Building PhotoboothAutomation.exe ...
python -m PyInstaller --onefile --windowed --name PhotoboothAutomation main.py
echo.
echo Done! Output: dist\PhotoboothAutomation.exe
echo.
echo Don't forget to copy these next to the .exe:
echo   - config.json
echo   - credentials.json
echo   - photos\ folder
pause
