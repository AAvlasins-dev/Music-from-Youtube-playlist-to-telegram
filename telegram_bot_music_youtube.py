"""Space Music Hub — Telegram bot that mirrors YouTube playlists as MP3 audio.

For each configured (playlist → channel) pair the bot:
  1. Fetches the playlist via yt-dlp (no YouTube Data API key required).
  2. Downloads only *new* videos as 192 kbps MP3 using yt-dlp + ffmpeg.
  3. Sends each track to the Telegram channel and pins the latest one.
  4. Persists state in JSON files so reruns never re-post the same track.

Usage::

    python telegram_bot_music_youtube.py

Configuration is done entirely through environment variables (see .env.example).
"""

from __future__ import annotations

import asyncio
import atexit
import json
import logging
import logging.handlers
import os
import shutil
import sys
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import yt_dlp
from dotenv import load_dotenv
from telegram import Bot, Message
from telegram import error as tg_error


def _app_dir() -> str:
    """Return the directory of the running app.

    When frozen by PyInstaller this is the folder containing the ``.exe``;
    otherwise it is the directory of this source file. Used to locate the
    ``.env`` file and a bundled ``ffmpeg.exe`` regardless of the current
    working directory the app was launched from.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _app_path(filename: str) -> str:
    """Resolve a relative *filename* against :func:`_app_dir`.

    Keeps state, log and lock files next to the app so they are found no
    matter which working directory the app (or .exe) was launched from.
    Absolute paths are returned unchanged.
    """
    if os.path.isabs(filename):
        return filename
    return os.path.join(_app_dir(), filename)


# Load .env from the app directory first (works when double-clicking the exe),
# then fall back to the default search so plain `python script.py` still works.
load_dotenv(os.path.join(_app_dir(), ".env"))
load_dotenv()

# ---------------------------------------------------------------------------
# ffmpeg discovery — support system PATH and ffmpeg-downloader bundle
# ---------------------------------------------------------------------------
def _find_ffmpeg() -> str | None:
    """Return the absolute path to an ffmpeg binary, or *None* if not found.

    Search order:
    1. ``FFMPEG_PATH`` environment variable (explicit override).
    2. ``ffmpeg.exe`` next to the app — bundled with the ``.exe`` release.
    3. ``ffmpeg`` on the system PATH (resolved to an absolute path so that
       yt-dlp can locate it regardless of the working directory at run time).
    4. The binary bundled by *ffmpeg-downloader* (installed via
       ``pip install ffmpeg-downloader && python -m ffmpeg_downloader install``).
    """
    # 1. Explicit override
    env_path = os.getenv("FFMPEG_PATH")
    if env_path and os.path.isfile(env_path):
        return env_path

    # 2. ffmpeg.exe / ffmpeg next to the app (bundled with the .exe release)
    for fname in ("ffmpeg.exe", "ffmpeg"):
        beside = os.path.join(_app_dir(), fname)
        if os.path.isfile(beside):
            return beside

    # 3. System PATH — always resolve to absolute so CWD doesn't matter
    which = shutil.which("ffmpeg")
    if which:
        abs_which = os.path.abspath(which)
        if os.path.isfile(abs_which):
            return abs_which

    # 4. ffmpeg-downloader bundle
    try:
        import ffmpeg_downloader as _ffd  # type: ignore[import]

        bundled: str = str(_ffd.ffmpeg_path)
        if os.path.isfile(bundled):
            return bundled
    except ImportError:
        pass

    return None


_FFMPEG_PATH: str | None = _find_ffmpeg()

__version__ = "1.4.0"
__all__ = [
    "ChannelConfig",
    "RunResult",
    "filter_new_videos",
    "load_json",
    "save_json",
    "with_retry",
]

# ---------------------------------------------------------------------------
# Logging: console + rotating file
# ---------------------------------------------------------------------------
LOG_FILE = _app_path(os.getenv("LOG_FILE", "bot.log"))
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
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
DOWNLOAD_DIR: str = os.getenv("DOWNLOAD_DIR", "downloads")
ADMIN_CHAT_ID: str = os.getenv("ADMIN_CHAT_ID", "")
YOUTUBE_COOKIES_FILE: str = os.getenv("YOUTUBE_COOKIES_FILE", "")

RETRY_ATTEMPTS: int = int(os.getenv("RETRY_ATTEMPTS", "3"))
RETRY_DELAY: float = float(os.getenv("RETRY_DELAY", "5"))
POST_DELAY: float = float(os.getenv("POST_DELAY", "2"))


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ChannelConfig:
    """Immutable configuration for a single YouTube → Telegram channel pair."""

    name: str
    playlist_id: str
    channel_id: str
    sent_videos_file: str
    pinned_msgs_file: str

    @property
    def normalised_channel_id(self) -> str:
        """Return the channel_id with exactly one leading ``@``."""
        raw = self.channel_id.strip()
        return raw if raw.startswith("@") else f"@{raw}"


@dataclass
class RunResult:
    """Statistics for a single channel run."""

    channel: str
    posted: int
    failed: int
    total_new: int

    @property
    def success_rate(self) -> float:
        """Fraction of new videos that were successfully posted (0.0–1.0)."""
        return self.posted / self.total_new if self.total_new else 1.0

    def __str__(self) -> str:
        status = "✅" if self.failed == 0 else "⚠️"
        parts = [f"{status} {self.channel}: posted {self.posted}/{self.total_new}"]
        if self.failed:
            parts.append(f"failed {self.failed}")
        return ", ".join(parts)


# ---------------------------------------------------------------------------
# Channel loading — supports unlimited numbered pairs + legacy named pairs
# ---------------------------------------------------------------------------
# Legacy named pairs kept for backward compatibility with older .env files.
_LEGACY_PAIRS: tuple[tuple[str, str, str], ...] = (
    ("andrey", "PLAYLIST_ANDREY", "TELEGRAM_CHANNEL_ANDREY"),
    ("bayba", "PLAYLIST_BAYBA", "TELEGRAM_CHANNEL_BAYBA"),
)


def _load_channels() -> list[ChannelConfig]:
    """Build the channel list from environment variables.

    Two formats are supported (numbered takes priority):

    1. **Numbered pairs** — unlimited, add a channel without touching code::

           CHANNEL_1_NAME=mychannel          # optional, defaults to "channel1"
           CHANNEL_1_PLAYLIST=PLxxxxxxxx
           CHANNEL_1_TELEGRAM=my_tg_channel

    2. **Legacy named pairs** — backward compatible::

           PLAYLIST_ANDREY / TELEGRAM_CHANNEL_ANDREY
           PLAYLIST_BAYBA  / TELEGRAM_CHANNEL_BAYBA

    Returns:
        A list of :class:`ChannelConfig`, empty if nothing is configured.
    """
    channels: list[ChannelConfig] = []

    # Format 1 — numbered pairs (CHANNEL_1_*, CHANNEL_2_*, …)
    index = 1
    while True:
        playlist = os.getenv(f"CHANNEL_{index}_PLAYLIST")
        telegram = os.getenv(f"CHANNEL_{index}_TELEGRAM")
        if not playlist or not telegram:
            break
        name = os.getenv(f"CHANNEL_{index}_NAME", f"channel{index}")
        channels.append(
            ChannelConfig(
                name=name,
                playlist_id=playlist,
                channel_id=telegram,
                sent_videos_file=_app_path(f"sent_videos_{name}.json"),
                pinned_msgs_file=_app_path(f"pinned_msgs_{name}.json"),
            )
        )
        index += 1

    if channels:
        return channels

    # Format 2 — legacy named pairs (only if no numbered pairs were found)
    for name, playlist_var, channel_var in _LEGACY_PAIRS:
        playlist = os.getenv(playlist_var)
        telegram = os.getenv(channel_var)
        if playlist and telegram:
            channels.append(
                ChannelConfig(
                    name=name,
                    playlist_id=playlist,
                    channel_id=telegram,
                    sent_videos_file=_app_path(f"sent_videos_{name}.json"),
                    pinned_msgs_file=_app_path(f"pinned_msgs_{name}.json"),
                )
            )

    return channels


CHANNELS: list[ChannelConfig] = _load_channels()

# Shared thread pool for blocking yt-dlp operations (I/O + network).
# Two workers: one for playlist fetch, one for audio download.
_executor = ThreadPoolExecutor(max_workers=2)
atexit.register(_executor.shutdown, wait=True)

# yt-dlp options shared by both playlist fetch and audio download
_YDL_COMMON: dict[str, Any] = {
    "quiet": True,
    "no_warnings": True,
    # Use mobile clients — less aggressively rate-limited than the web client
    "extractor_args": {"youtube": {"player_client": ["ios", "android", "web"]}},
    **({"cookiefile": YOUTUBE_COOKIES_FILE} if YOUTUBE_COOKIES_FILE else {}),
}


# ---------------------------------------------------------------------------
# Config validation
# ---------------------------------------------------------------------------
def _validate_config() -> None:
    """Validate that a bot token and at least one channel are configured.

    Raises:
        OSError: If ``TELEGRAM_BOT_TOKEN`` is missing or no channel pair is set.
    """
    if not os.getenv("TELEGRAM_BOT_TOKEN"):
        raise OSError("Missing required environment variable: TELEGRAM_BOT_TOKEN")

    if not _load_channels():
        raise OSError(
            "No channels configured. Define at least one pair — either "
            "CHANNEL_1_PLAYLIST + CHANNEL_1_TELEGRAM, or the legacy "
            "PLAYLIST_ANDREY + TELEGRAM_CHANNEL_ANDREY."
        )


# ---------------------------------------------------------------------------
# JSON state helpers
# ---------------------------------------------------------------------------
def load_json(path: str) -> dict[str, Any]:
    """Load a JSON file and return its contents as a dict.

    Returns an empty dict if the file does not exist.
    """
    if not os.path.exists(path):
        logger.debug("State file not found, starting fresh: %s", path)
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)  # type: ignore[no-any-return]


def save_json(path: str, data: dict[str, Any]) -> None:
    """Serialise *data* to *path* as pretty-printed UTF-8 JSON."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.debug("State saved: %s", path)


# ---------------------------------------------------------------------------
# Video filtering
# ---------------------------------------------------------------------------
def filter_new_videos(
    videos: list[dict[str, Any]],
    sent: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return the subset of *videos* whose IDs are not in *sent*.

    Args:
        videos: Full playlist entries from yt-dlp (each has at least ``"id"``).
        sent:   Mapping of ``video_id → metadata`` loaded from the state file.

    Returns:
        Ordered list of videos not yet posted to the channel.
    """
    return [v for v in videos if v["id"] not in sent]


# ---------------------------------------------------------------------------
# Retry decorator (sync + async)
# ---------------------------------------------------------------------------
def with_retry(
    attempts: int = RETRY_ATTEMPTS,
    delay: float = RETRY_DELAY,
) -> Callable[..., Any]:
    """Decorator that retries a function up to *attempts* times.

    Supports both regular and ``async`` functions.  Between attempts the
    decorator sleeps for ``delay * attempt`` seconds (exponential back-off).

    Args:
        attempts: Maximum number of calls before re-raising.
        delay:    Base sleep duration in seconds between retries.
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        import inspect

        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: Exception | None = None
            for attempt in range(1, attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as exc:  # noqa: BLE001
                    last_exc = exc
                    logger.warning(
                        "Attempt %d/%d failed for %s: %s",
                        attempt, attempts, func.__name__, exc,
                    )
                    if attempt < attempts:
                        await asyncio.sleep(delay * attempt)
            logger.error("All %d attempts exhausted for %s", attempts, func.__name__)
            raise last_exc  # type: ignore[misc]

        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: Exception | None = None
            for attempt in range(1, attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:  # noqa: BLE001
                    last_exc = exc
                    logger.warning(
                        "Attempt %d/%d failed for %s: %s",
                        attempt, attempts, func.__name__, exc,
                    )
                    if attempt < attempts:
                        time.sleep(delay * attempt)
            logger.error("All %d attempts exhausted for %s", attempts, func.__name__)
            raise last_exc  # type: ignore[misc]

        return async_wrapper if inspect.iscoroutinefunction(func) else sync_wrapper

    return decorator


# ---------------------------------------------------------------------------
# yt-dlp: playlist metadata
# ---------------------------------------------------------------------------
@with_retry()
def _get_playlist_videos(playlist_id: str) -> list[dict[str, Any]]:
    """Fetch all entries from a YouTube playlist without downloading.

    Args:
        playlist_id: The ``list=`` parameter value from the playlist URL.

    Returns:
        List of dicts with keys ``"id"``, ``"title"``, and ``"duration"``.
    """
    url = f"https://www.youtube.com/playlist?list={playlist_id}"
    logger.info("Fetching playlist: %s", playlist_id)
    ydl_opts = {**_YDL_COMMON, "extract_flat": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
    videos = [
        {
            "id": entry["id"],
            "title": entry.get("title", "Unknown"),
            "duration": entry.get("duration"),
        }
        for entry in (info or {}).get("entries", [])
        if entry and entry.get("id")
    ]
    logger.info("Playlist fetched: %d videos total", len(videos))
    return videos


# ---------------------------------------------------------------------------
# yt-dlp: audio download
# ---------------------------------------------------------------------------
@with_retry()
def _download_audio(video_id: str) -> str:
    """Download a YouTube video as the best available audio file.

    Converts to MP3 (192 kbps) when ffmpeg is available; otherwise saves the
    native m4a / webm container which Telegram accepts without conversion.

    Args:
        video_id: The YouTube video identifier (the ``v=`` URL parameter).

    Returns:
        Absolute path to the downloaded audio file.

    Raises:
        FileNotFoundError: If no audio file was produced after download.
    """
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    output_template = os.path.join(DOWNLOAD_DIR, f"{video_id}.%(ext)s")

    ydl_opts: dict[str, Any] = {
        **_YDL_COMMON,
        "format": "bestaudio[ext=m4a]/bestaudio/best",
        "outtmpl": output_template,
    }

    if _FFMPEG_PATH:
        logger.debug("Using ffmpeg at: %s", _FFMPEG_PATH)
        ydl_opts["ffmpeg_location"] = _FFMPEG_PATH
        ydl_opts["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ]
    else:
        logger.warning(
            "ffmpeg not found — audio will be downloaded in native format (m4a/mp4). "
            "Run: pip install ffmpeg-downloader && python -m ffmpeg_downloader install"
        )

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([f"https://www.youtube.com/watch?v={video_id}"])

    # Accept any extension yt-dlp may have written; reject suspiciously small files
    _MIN_AUDIO_BYTES = 50_000  # 50 KB — a valid track is always larger
    for ext in ("mp3", "m4a", "webm", "opus", "ogg", "mp4"):
        path = os.path.join(DOWNLOAD_DIR, f"{video_id}.{ext}")
        if os.path.exists(path):
            size = os.path.getsize(path)
            if size < _MIN_AUDIO_BYTES:
                logger.warning(
                    "Downloaded file is suspiciously small (%d B): %s — skipping",
                    size, path,
                )
                os.remove(path)
                continue
            return path

    raise FileNotFoundError(f"No audio file found after download: {video_id}")


# ---------------------------------------------------------------------------
# Telegram helpers
# ---------------------------------------------------------------------------
@with_retry()
async def _send_audio(
    bot: Bot,
    chat_id: str,
    mp3_path: str,
    title: str,
    video_id: str,
) -> Message:
    """Send an MP3 file to *chat_id* with a caption linking back to YouTube."""
    yt_url = f"https://youtu.be/{video_id}"
    caption = f"🎵 <b>{title}</b>\n\n📺 <a href=\"{yt_url}\">Watch on YouTube</a>"
    with open(mp3_path, "rb") as audio_file:
        return await bot.send_audio(
            chat_id=chat_id,
            audio=audio_file,
            title=title,
            caption=caption,
            parse_mode="HTML",
        )


@with_retry()
async def _pin_message(bot: Bot, chat_id: str, message_id: int) -> None:
    """Pin *message_id* in *chat_id* without notifying subscribers."""
    await bot.pin_chat_message(
        chat_id=chat_id,
        message_id=message_id,
        disable_notification=True,
    )


@with_retry()
async def _unpin_message(bot: Bot, chat_id: str, message_id: int) -> None:
    """Unpin a previously pinned message."""
    await bot.unpin_chat_message(chat_id=chat_id, message_id=message_id)


async def _notify_admin(bot: Bot, text: str) -> None:
    """Send *text* to :data:`ADMIN_CHAT_ID` if the variable is configured."""
    if not ADMIN_CHAT_ID:
        return
    try:
        await bot.send_message(chat_id=ADMIN_CHAT_ID, text=text, parse_mode="HTML")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not notify admin: %s", exc)


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------
async def post_new_videos(channel: ChannelConfig) -> RunResult:
    """Check *channel.playlist_id* for new videos and send them to Telegram.

    Downloads each new video as MP3, posts it, updates the pin, and persists
    state so the same video is never posted twice.

    Args:
        channel: Immutable config for the playlist → channel pair.

    Returns:
        :class:`RunResult` with counters for this run.
    """
    chat_id = channel.normalised_channel_id
    logger.info("--- Processing channel: %s (%s) ---", channel.name, chat_id)

    loop = asyncio.get_running_loop()
    sent_videos: dict[str, Any] = load_json(channel.sent_videos_file)
    pinned_msgs: dict[str, Any] = load_json(channel.pinned_msgs_file)

    all_videos = await loop.run_in_executor(
        _executor, _get_playlist_videos, channel.playlist_id
    )
    new_videos = filter_new_videos(all_videos, sent_videos)

    if not new_videos:
        logger.info("[%s] No new videos to post.", channel.name)
        return RunResult(channel=channel.name, posted=0, failed=0, total_new=0)

    logger.info("[%s] %d new video(s) to post.", channel.name, len(new_videos))
    tg_bot = Bot(token=TELEGRAM_BOT_TOKEN)
    posted = 0
    failed = 0

    for i, video in enumerate(new_videos, 1):
        video_id: str = video["id"]
        title: str = video["title"]
        mp3_path: str | None = None

        try:
            logger.info(
                "[%s] [%d/%d] Downloading: %s", channel.name, i, len(new_videos), title
            )
            mp3_path = await loop.run_in_executor(
                _executor, _download_audio, video_id
            )

            message = await _send_audio(tg_bot, chat_id, mp3_path, title, video_id)
            sent_videos[video_id] = {
                "title": title,
                "message_id": message.message_id,
                "posted_at": datetime.now(UTC).isoformat(),
            }
            logger.info(
                "[%s] [%d/%d] Posted: %s", channel.name, i, len(new_videos), title
            )

            # Rotate pin: unpin old, pin new
            prev_id: int | None = pinned_msgs.get("last_message_id")
            if prev_id:
                try:
                    await _unpin_message(tg_bot, chat_id, prev_id)
                except tg_error.TelegramError as exc:
                    logger.warning(
                        "[%s] Could not unpin message %s: %s",
                        channel.name, prev_id, exc,
                    )

            await _pin_message(tg_bot, chat_id, message.message_id)
            pinned_msgs["last_message_id"] = message.message_id
            posted += 1

            # Persist state immediately so a crash/restart never re-posts this track
            save_json(channel.sent_videos_file, sent_videos)
            save_json(channel.pinned_msgs_file, pinned_msgs)

        except Exception as exc:  # noqa: BLE001
            logger.error(
                "[%s] Failed to process %s (%s): %s",
                channel.name, video_id, title, exc,
            )
            failed += 1

        finally:
            if mp3_path and os.path.exists(mp3_path):
                os.remove(mp3_path)
                logger.debug("[%s] Cleaned up: %s", channel.name, mp3_path)

        if i < len(new_videos):
            await asyncio.sleep(POST_DELAY)

    save_json(channel.sent_videos_file, sent_videos)
    save_json(channel.pinned_msgs_file, pinned_msgs)
    result = RunResult(
        channel=channel.name,
        posted=posted,
        failed=failed,
        total_new=len(new_videos),
    )
    logger.info("[%s] Done. %s", channel.name, result)
    return result


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
async def main() -> None:
    """Validate config, process all channels, and send an admin summary."""
    _validate_config()
    tg_bot = Bot(token=TELEGRAM_BOT_TOKEN)
    results: list[RunResult] = []

    for channel in CHANNELS:
        result = await post_new_videos(channel)
        results.append(result)

    if ADMIN_CHAT_ID:
        summary = "<b>🤖 Space Music Hub — run complete</b>\n\n" + "\n".join(
            str(r) for r in results
        )
        await _notify_admin(tg_bot, summary)


async def check() -> None:
    """Dry-run: validate config, verify the bot token and count new tracks.

    Downloads and posts *nothing* — safe to run at any time, even while a real
    run is in progress. Useful to confirm everything is configured correctly.
    """
    _validate_config()
    tg_bot = Bot(token=TELEGRAM_BOT_TOKEN)

    me = await tg_bot.get_me()
    logger.info("Bot token OK — connected as @%s (%s)", me.username, me.first_name)

    loop = asyncio.get_running_loop()
    for channel in CHANNELS:
        videos = await loop.run_in_executor(
            _executor, _get_playlist_videos, channel.playlist_id
        )
        sent = load_json(channel.sent_videos_file)
        new = filter_new_videos(videos, sent)
        logger.info(
            "[%s -> %s] %d tracks in playlist, %d already posted, %d new",
            channel.name, channel.normalised_channel_id,
            len(videos), len(sent), len(new),
        )
    logger.info("Check complete — configuration looks valid.")


def _pause_if_frozen() -> None:
    """Keep the console window open when launched as a double-clicked .exe."""
    if getattr(sys, "frozen", False):
        try:
            input("\nPress Enter to close...")
        except (EOFError, KeyboardInterrupt):
            pass


def _run_cli() -> int:
    """Console entry point. Returns a process exit code."""
    # --check / --dry-run: validate + count, no posting, no lock needed.
    check_only = any(arg in ("--check", "--dry-run") for arg in sys.argv[1:])

    if check_only:
        try:
            logger.info("=== space-music-hub check v%s ===", __version__)
            asyncio.run(check())
        except OSError as exc:
            logger.error("Configuration error: %s", exc)
            print(f"\n[X] {exc}\n\nFix your .env file and run again.")
            _pause_if_frozen()
            return 1
        except Exception as exc:  # noqa: BLE001
            logger.exception("Check failed: %s", exc)
            print(f"\n[X] Check failed: {exc}\nSee bot.log for details.")
            _pause_if_frozen()
            return 1
        _pause_if_frozen()
        return 0

    # Prevent two instances running at the same time (would duplicate posts).
    lock_file = _app_path("bot.lock")
    if os.path.exists(lock_file):
        logger.error(
            "Lock file '%s' already exists — another instance may be running. "
            "If the previous run crashed, delete this file and try again.",
            lock_file,
        )
        _pause_if_frozen()
        return 1

    exit_code = 0
    try:
        with open(lock_file, "w") as lock_handle:
            lock_handle.write(str(os.getpid()))

        logger.info("=== space-music-hub bot v%s starting ===", __version__)
        asyncio.run(main())
        logger.info("=== bot run complete ===")
    except OSError as exc:
        # Configuration problems (missing token / no channels) — show a clear,
        # friendly message instead of a raw traceback.
        logger.error("Configuration error: %s", exc)
        print(f"\n[X] {exc}\n\nFix your .env file and run again.")
        exit_code = 1
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error: %s", exc)
        print(f"\n[X] Unexpected error: {exc}\nSee bot.log for details.")
        exit_code = 1
    finally:
        if os.path.exists(lock_file):
            os.remove(lock_file)

    _pause_if_frozen()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(_run_cli())
