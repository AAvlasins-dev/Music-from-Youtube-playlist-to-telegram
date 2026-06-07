@echo off
REM ===========================================================================
REM  Build SpaceMusicHub.exe — a standalone Windows executable of the bot.
REM
REM  Requirements (one-time):
REM      pip install -r requirements.txt
REM      pip install pyinstaller
REM
REM  Output:
REM      dist\SpaceMusicHub.exe   <- the executable
REM
REM  After building, ship dist\SpaceMusicHub.exe together with:
REM      ffmpeg.exe    (audio conversion — auto-detected next to the exe)
REM  The .env is created automatically by the first-run setup wizard.
REM ===========================================================================

echo.
echo === Building SpaceMusicHub.exe ===
echo.

python -m PyInstaller ^
    --onefile ^
    --name SpaceMusicHub ^
    --console ^
    --collect-all yt_dlp ^
    --collect-all telegram ^
    --collect-all dotenv ^
    --noconfirm ^
    telegram_bot_music_youtube.py

echo.
if exist "dist\SpaceMusicHub.exe" (
    echo === DONE ===
    echo Executable: dist\SpaceMusicHub.exe
) else (
    echo === BUILD FAILED — check the output above ===
)
echo.
pause
