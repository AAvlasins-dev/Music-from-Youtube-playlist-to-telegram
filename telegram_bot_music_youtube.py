import asyncio
import json
import logging
import logging.handlers
import os
import time
from datetime import datetime, timezone

from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
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
# Global settings
# ---------------------------------------------------------------------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

RETRY_ATTEMPTS = int(os.getenv("RETRY_ATTEMPTS", "3"))
RETRY_DELAY = float(os.getenv("RETRY_DELAY", "5"))
POST_DELAY = float(os.getenv("POST_DELAY", "1"))

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


def _validate_config() -> None:
    base = [k for k in ("TELEGRAM_TOKEN", "YOUTUBE_API_KEY") if not os.getenv(k)]
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


# ---------------------------------------------------------------------------
# Retry decorator
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
# YouTube
# ---------------------------------------------------------------------------
@with_retry()
def _fetch_page(youtube, playlist_id: str, page_token: str | None) -> dict:
    return (
        youtube.playlistItems()
        .list(
            part="snippet,contentDetails",
            playlistId=playlist_id,
            maxResults=50,
            pageToken=page_token,
        )
        .execute()
    )


def get_playlist_videos(playlist_id: str) -> list[dict]:
    logger.info("Fetching playlist: %s", playlist_id)
    youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
    videos: list[dict] = []
    next_page_token = None
    page = 0

    while True:
        page += 1
        try:
            response = _fetch_page(youtube, playlist_id, next_page_token)
        except HttpError as e:
            logger.error("YouTube API error on page %d: %s", page, e)
            break

        for item in response.get("items", []):
            video_id = item["contentDetails"]["videoId"]
            title = item["snippet"]["title"]
            published_at = item["snippet"]["publishedAt"]
            videos.append({"id": video_id, "title": title, "published_at": published_at})

        next_page_token = response.get("nextPageToken")
        logger.debug("Page %d fetched, total so far: %d", page, len(videos))
        if not next_page_token:
            break

    logger.info("Playlist fetched: %d videos total", len(videos))
    return videos


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------
@with_retry()
async def _send_message(bot: Bot, chat_id: str, text: str):
    return await bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")


@with_retry()
async def _pin_message(bot: Bot, chat_id: str, message_id: int) -> None:
    await bot.pin_chat_message(chat_id=chat_id, message_id=message_id, disable_notification=True)


@with_retry()
async def _unpin_message(bot: Bot, chat_id: str, message_id: int) -> None:
    await bot.unpin_chat_message(chat_id=chat_id, message_id=message_id)


async def post_new_videos(channel: dict) -> None:
    name = channel["name"]
    playlist_id = channel["playlist_id"]
    channel_id = channel["channel_id"]
    sent_videos_file = channel["sent_videos_file"]
    pinned_msgs_file = channel["pinned_msgs_file"]

    logger.info("--- Processing channel: %s ---", name)

    sent_videos: dict = load_json(sent_videos_file)
    pinned_msgs: dict = load_json(pinned_msgs_file)

    bot = Bot(token=TELEGRAM_TOKEN)
    videos = get_playlist_videos(playlist_id)
    new_videos = [v for v in videos if v["id"] not in sent_videos]

    if not new_videos:
        logger.info("[%s] No new videos to post.", name)
        return

    logger.info("[%s] %d new video(s) to post.", name, len(new_videos))
    posted = 0

    for video in new_videos:
        url = f"https://www.youtube.com/watch?v={video['id']}"
        text = f"🎵 *{video['title']}*\n\n{url}"

        try:
            message = await _send_message(bot, channel_id, text)
            sent_videos[video["id"]] = {
                "title": video["title"],
                "message_id": message.message_id,
                "posted_at": datetime.now(timezone.utc).isoformat(),
            }
            logger.info("[%s] [%d/%d] Posted: %s", name, posted + 1, len(new_videos), video["title"])

            prev_id = pinned_msgs.get("last_message_id")
            if prev_id:
                try:
                    await _unpin_message(bot, channel_id, prev_id)
                except tg_error.TelegramError as e:
                    logger.warning("[%s] Could not unpin message %s: %s", name, prev_id, e)

            await _pin_message(bot, channel_id, message.message_id)
            pinned_msgs["last_message_id"] = message.message_id
            posted += 1

        except tg_error.TelegramError as e:
            logger.error("[%s] Failed to post %s (%s): %s", name, video["id"], video["title"], e)

        if posted < len(new_videos):
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
