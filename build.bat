@echo off
echo ========================================
echo  Building Photobooth Automation
echo ========================================
echo.

echo [1/2] Building Operator app...
python -m PyInstaller --onefile --windowed --name PhotoboothOperator main.py
echo.

echo [2/2] Building User app...
python -m PyInstaller --onefile --windowed --name PhotoboothUser user.py
echo.

echo ========================================
echo  Done!
echo ========================================
echo.
echo Output:
echo   dist\PhotoboothOperator.exe  (operator - full control)
echo   dist\PhotoboothUser.exe      (user - send/print only)
echo.
echo Place these files next to the .exe:
echo   - credentials.json
echo   - config.json (created on first run)
echo   - photos\ folder
echo.
pause
