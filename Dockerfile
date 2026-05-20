FROM python:3.12-slim

WORKDIR /app

# ffmpeg is required by yt-dlp for MP3 conversion
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY telegram_bot_music_youtube.py .

# State files and downloads live in a mounted volume so they persist across restarts
VOLUME ["/app/data"]

ENV LOG_FILE=/app/data/bot.log \
    LOG_LEVEL=INFO \
    DOWNLOAD_DIR=/app/data/downloads \
    RETRY_ATTEMPTS=3 \
    RETRY_DELAY=5 \
    POST_DELAY=2

CMD ["python", "telegram_bot_music_youtube.py"]
