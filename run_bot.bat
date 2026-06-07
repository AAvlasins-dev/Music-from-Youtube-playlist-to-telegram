@echo off
cd /d "%~dp0"

:: Activate virtual environment if it exists, otherwise use system Python
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

echo [%date% %time%] Starting space-music-hub bot...
python telegram_bot_music_youtube.py
echo [%date% %time%] Bot run finished. Exit code: %errorlevel%
