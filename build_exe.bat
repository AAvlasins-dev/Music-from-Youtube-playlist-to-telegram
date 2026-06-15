@echo off
REM ===========================================================================
REM  Build Space Music Hub — the PyQt6 desktop app — into a standalone folder.
REM
REM  Requirements (one-time):
REM      pip install -r requirements-dev.txt
REM
REM  Output:
REM      dist\SpaceMusicHub\SpaceMusicHub.exe   <- the desktop app
REM
REM  The build recipe (entry point, bundled engine + assets, excluded Qt
REM  modules, icon) lives in SpaceMusicHubGUI.spec. To produce the Windows
REM  installer afterwards, compile installer\SpaceMusicHub.iss with Inno Setup 6.
REM ===========================================================================

echo.
echo === Building Space Music Hub (GUI) ===
echo.

python -m PyInstaller --noconfirm SpaceMusicHubGUI.spec

echo.
if exist "dist\SpaceMusicHub\SpaceMusicHub.exe" (
    echo === DONE ===
    echo App: dist\SpaceMusicHub\SpaceMusicHub.exe
) else (
    echo === BUILD FAILED — check the output above ===
)
echo.
pause
