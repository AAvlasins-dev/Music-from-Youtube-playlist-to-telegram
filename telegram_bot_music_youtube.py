import asyncio
import json
import logging
import logging.handlers
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import yt_dlp
from dotenv import load_dotenv
from telegram import Bot
from telegram import error as tg_error

load_dotenv()

# ---------------------------------------------------------------------------
# Logging: console + rotating file
# ---------------------------------------------------------------------------
LOG_FILE = os.getenv("LOG_FILE", "bot.log")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

_formatter = logging.Formatter(
    fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
_file_handler = logging.handlers.RotatingFileHandler(
    LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
)
_file_handler.setFormatter(_formatter)
_console_handler = logging.StreamHandler()
_console_handler.setFormatter(_formatter)

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    handlers=[_file_handler, _console_handler],
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", "downloads")

RETRY_ATTEMPTS = int(os.getenv("RETRY_ATTEMPTS", "3"))
RETRY_DELAY = float(os.getenv("RETRY_DELAY", "5"))
POST_DELAY = float(os.getenv("POST_DELAY", "2"))

# ---------------------------------------------------------------------------
# Channel configs: one entry per (playlist → channel) pair
# ---------------------------------------------------------------------------
CHANNELS = [
    {
        "name": "andrey",
        "playlist_id": os.getenv("PLAYLIST_ANDREY"),
        "channel_id": os.getenv("TELEGRAM_CHANNEL_ANDREY"),
        "sent_videos_file": "sent_videos_andrey.json",
        "pinned_msgs_file": "pinned_msgs_andrey.json",
    },
    {
        "name": "bayba",
        "playlist_id": os.getenv("PLAYLIST_BAYBA"),
        "channel_id": os.getenv("TELEGRAM_CHANNEL_BAYBA"),
        "sent_videos_file": "sent_videos_bayba.json",
        "pinned_msgs_file": "pinned_msgs_bayba.json",
    },
]

executor = ThreadPoolExecutor(max_workers=2)


def _validate_config() -> None:
    base = [k for k in ("TELEGRAM_BOT_TOKEN",) if not os.getenv(k)]
    channel_vars = [
        var
        for name in ("ANDREY", "BAYBA")
        for var in (f"PLAYLIST_{name}", f"TELEGRAM_CHANNEL_{name}")
        if not os.getenv(var)
    ]
    missing = base + channel_vars
    if missing:
        raise EnvironmentError(f"Missing required environment variables: {', '.join(missing)}")


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------
def load_json(path: str) -> dict:
    if not os.path.exists(path):
        logger.debug("State file not found, starting fresh: %s", path)
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.debug("State saved: %s", path)


def filter_new_videos(videos: list[dict], sent_videos: dict) -> list[dict]:
    """Return only the videos whose id is not already present in the sent state."""
    return [v for v in videos if v["id"] not in sent_videos]


# ---------------------------------------------------------------------------
# Retry decorator (supports both sync and async functions)
# ---------------------------------------------------------------------------
def with_retry(attempts: int = RETRY_ATTEMPTS, delay: float = RETRY_DELAY):
    def decorator(func):
        import inspect

        async def async_wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(1, attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as exc:
                    last_exc = exc
                    logger.warning(
                        "Attempt %d/%d failed for %s: %s",
                        attempt, attempts, func.__name__, exc,
                    )
                    if attempt < attempts:
                        await asyncio.sleep(delay * attempt)
            logger.error("All %d attempts exhausted for %s", attempts, func.__name__)
            raise last_exc

        def sync_wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(1, attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:
                    last_exc = exc
                    logger.warning(
                        "Attempt %d/%d failed for %s: %s",
                        attempt, attempts, func.__name__, exc,
                    )
                    if attempt < attempts:
                        time.sleep(delay * attempt)
            logger.error("All %d attempts exhausted for %s", attempts, func.__name__)
            raise last_exc

        return async_wrapper if inspect.iscoroutinefunction(func) else sync_wrapper
    return decorator


# ---------------------------------------------------------------------------
# yt-dlp: playlist info
# ---------------------------------------------------------------------------
@with_retry()
def _get_playlist_videos(playlist_id: str) -> list[dict]:
    url = f"https://www.youtube.com/playlist?list={playlist_id}"
    logger.info("Fetching playlist: %s", playlist_id)
    ydl_opts = {
        "quiet": True,
        "extract_flat": True,
        "no_warnings": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
    videos = [
        {
            "id": e["id"],
            "title": e.get("title", "Unknown"),
            "duration": e.get("duration"),
        }
        for e in info.get("entries", [])
        if e and e.get("id")
    ]
    logger.info("Playlist fetched: %d videos total", len(videos))
    return videos


# ---------------------------------------------------------------------------
# yt-dlp: audio download → MP3 via ffmpeg
# ---------------------------------------------------------------------------
@with_retry()
def _download_audio(video_id: str) -> str:
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    output_template = os.path.join(DOWNLOAD_DIR, f"{video_id}.%(ext)s")
    ydl_opts = {
        "format": "bestaudio/best",
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
        "outtmpl": output_template,
        "quiet": True,
        "no_warnings": True,
    }
    url = f"https://www.youtube.com/watch?v={video_id}"
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    mp3_path = os.path.join(DOWNLOAD_DIR, f"{video_id}.mp3")
    if not os.path.exists(mp3_path):
        raise FileNotFoundError(f"MP3 not found after download: {mp3_path}")
    return mp3_path


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------
@with_retry()
async def _send_audio(bot: Bot, chat_id: str, mp3_path: str, title: str):
    with open(mp3_path, "rb") as audio_file:
        return await bot.send_audio(
            chat_id=chat_id,
            audio=audio_file,
            title=title,
        )


@with_retry()
async def _pin_message(bot: Bot, chat_id: str, message_id: int) -> None:
    await bot.pin_chat_message(
        chat_id=chat_id, message_id=message_id, disable_notification=True
    )


@with_retry()
async def _unpin_message(bot: Bot, chat_id: str, message_id: int) -> None:
    await bot.unpin_chat_message(chat_id=chat_id, message_id=message_id)


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------
async def post_new_videos(channel: dict) -> None:
    name = channel["name"]
    playlist_id = channel["playlist_id"]
    channel_id = f"@{channel['channel_id']}"
    sent_videos_file = channel["sent_videos_file"]
    pinned_msgs_file = channel["pinned_msgs_file"]

    logger.info("--- Processing channel: %s ---", name)

    loop = asyncio.get_event_loop()
    sent_videos: dict = load_json(sent_videos_file)
    pinned_msgs: dict = load_json(pinned_msgs_file)

    videos = await loop.run_in_executor(executor, _get_playlist_videos, playlist_id)
    new_videos = filter_new_videos(videos, sent_videos)

    if not new_videos:
        logger.info("[%s] No new videos to post.", name)
        return

    logger.info("[%s] %d new video(s) to post.", name, len(new_videos))
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    posted = 0

    for i, video in enumerate(new_videos, 1):
        video_id = video["id"]
        title = video["title"]
        mp3_path = None

        try:
            logger.info("[%s] [%d/%d] Downloading: %s", name, i, len(new_videos), title)
            mp3_path = await loop.run_in_executor(executor, _download_audio, video_id)
            logger.info("[%s] Downloaded: %s", name, mp3_path)

            message = await _send_audio(bot, channel_id, mp3_path, title)
            sent_videos[video_id] = {
                "title": title,
                "message_id": message.message_id,
                "posted_at": datetime.now(timezone.utc).isoformat(),
            }
            logger.info("[%s] [%d/%d] Posted: %s", name, i, len(new_videos), title)

            prev_id = pinned_msgs.get("last_message_id")
            if prev_id:
                try:
                    await _unpin_message(bot, channel_id, prev_id)
                except tg_error.TelegramError as e:
                    logger.warning("[%s] Could not unpin message %s: %s", name, prev_id, e)

            await _pin_message(bot, channel_id, message.message_id)
            pinned_msgs["last_message_id"] = message.message_id
            posted += 1

        except Exception as e:
            logger.error("[%s] Failed to process %s (%s): %s", name, video_id, title, e)

        finally:
            if mp3_path and os.path.exists(mp3_path):
                os.remove(mp3_path)
                logger.debug("[%s] Cleaned up: %s", name, mp3_path)

        if i < len(new_videos):
            await asyncio.sleep(POST_DELAY)

    save_json(sent_videos_file, sent_videos)
    save_json(pinned_msgs_file, pinned_msgs)
    logger.info("[%s] Done. Posted %d/%d video(s).", name, posted, len(new_videos))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
async def main() -> None:
    _validate_config()
    for channel in CHANNELS:
        await post_new_videos(channel)


if __name__ == "__main__":
    logger.info("=== space-music-hub bot starting ===")
    asyncio.run(main())
    logger.info("=== bot run complete ===")
