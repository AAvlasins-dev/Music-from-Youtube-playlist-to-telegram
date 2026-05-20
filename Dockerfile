FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY telegram_bot_music_youtube.py .

# State files live in a mounted volume so they persist across restarts
VOLUME ["/app/data"]

ENV SENT_VIDEOS_FILE=/app/data/sent_videos.json \
    PINNED_MSGS_FILE=/app/data/pinned_msgs.json \
    LOG_FILE=/app/data/bot.log \
    LOG_LEVEL=INFO \
    RETRY_ATTEMPTS=3 \
    RETRY_DELAY=5 \
    POST_DELAY=1

CMD ["python", "telegram_bot_music_youtube.py"]
