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
import html
import json
import logging
import logging.handlers
import os
import re
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

__version__ = "1.6.0"
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


class _TokenMaskFilter(logging.Filter):
    """Redact Telegram bot tokens from every log record.

    The python-telegram-bot/httpx stack logs request URLs like
    ``https://api.telegram.org/bot<digits>:<secret>/getMe`` at INFO level.
    Without this filter the token would land in bot.log (on disk) and in
    the GUI log panel in clear text. We rewrite the secret to ``***``.
    """

    _RX = re.compile(r"(bot\d{6,}:)[A-Za-z0-9_\-]{10,}")

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            if isinstance(record.msg, str):
                record.msg = self._RX.sub(r"\1***", record.msg)
            if record.args:
                record.args = tuple(
                    self._RX.sub(r"\1***", a) if isinstance(a, str) else a
                    for a in record.args
                )
        except Exception:  # noqa: BLE001 — never let logging crash the app
            pass
        return True


_mask_filter = _TokenMaskFilter()
_file_handler = logging.handlers.RotatingFileHandler(
    LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
)
_file_handler.setFormatter(_formatter)
_file_handler.addFilter(_mask_filter)
_console_handler = logging.StreamHandler()
_console_handler.setFormatter(_formatter)
_console_handler.addFilter(_mask_filter)

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    handlers=[_file_handler, _console_handler],
)

# Third-party HTTP/Telegram loggers are chatty and (worse) put the bot
# token in their request URLs — keep them at WARNING so they stay quiet
# and never out-log our own messages.
for _noisy in ("httpx", "httpcore", "telegram", "telegram.ext"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

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

# MP3 quality for the ffmpeg transcode. Settable from the GUI; only the
# three common rates are accepted, anything else falls back to 192.
_ALLOWED_BITRATES = {"128", "192", "320"}
AUDIO_BITRATE: str = os.getenv("AUDIO_BITRATE", "192").strip()
if AUDIO_BITRATE not in _ALLOWED_BITRATES:
    AUDIO_BITRATE = "192"

# Telegram bot API hard limit for uploaded audio. Files above this can never
# be sent, so we skip + record them rather than retrying forever. Leave a
# small margin below the real 50 MB ceiling for protocol overhead.
_TG_AUDIO_LIMIT_BYTES: int = 49 * 1024 * 1024


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
    seen: set[str] = set()

    def _add(name: str, playlist: str, telegram: str) -> None:
        # Disambiguate the state-file key if two channels share a display
        # name, so they never read/write each other's "already sent" history
        # (which would make each mark the other's videos as posted).
        key = name
        suffix = 2
        while key in seen:
            key = f"{name}_{suffix}"
            suffix += 1
        seen.add(key)
        channels.append(
            ChannelConfig(
                name=name,
                playlist_id=playlist,
                channel_id=telegram,
                sent_videos_file=_app_path(f"sent_videos_{key}.json"),
                pinned_msgs_file=_app_path(f"pinned_msgs_{key}.json"),
            )
        )

    # Format 1 — numbered pairs (CHANNEL_1_*, CHANNEL_2_*, …)
    index = 1
    while True:
        playlist = os.getenv(f"CHANNEL_{index}_PLAYLIST")
        telegram = os.getenv(f"CHANNEL_{index}_TELEGRAM")
        if not playlist or not telegram:
            break
        name = os.getenv(f"CHANNEL_{index}_NAME", f"channel{index}")
        _add(name, playlist, telegram)
        index += 1

    if channels:
        return channels

    # Format 2 — legacy named pairs (only if no numbered pairs were found)
    for name, playlist_var, channel_var in _LEGACY_PAIRS:
        playlist = os.getenv(playlist_var)
        telegram = os.getenv(channel_var)
        if playlist and telegram:
            _add(name, playlist, telegram)

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

    Returns an empty dict if the file does not exist or is corrupt (e.g. a
    crash truncated a previous write). A corrupt state file is backed up to
    ``<path>.corrupt`` rather than silently overwritten, so it never wedges
    a channel permanently.
    """
    if not os.path.exists(path):
        logger.debug("State file not found, starting fresh: %s", path)
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)  # type: ignore[no-any-return]
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.warning(
            "State file is corrupt (%s) — backing up and starting fresh: %s",
            exc, path,
        )
        try:
            os.replace(path, f"{path}.corrupt")
        except OSError:
            pass
        return {}


def save_json(path: str, data: dict[str, Any]) -> None:
    """Serialise *data* to *path* as pretty-printed UTF-8 JSON.

    Writes to a temporary file and atomically replaces the target so a crash
    mid-write can never leave a half-written (corrupt) state file behind.
    """
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
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
    decorator sleeps for ``delay * attempt`` seconds (linear back-off:
    ``delay``, ``2·delay``, ``3·delay`` …).

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
                "preferredquality": AUDIO_BITRATE,
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
    # Escape the title: it comes from YouTube and may contain &, <, > which
    # would otherwise break Telegram's HTML parser (parse_mode="HTML") and
    # make the whole send fail — silently dropping that track forever.
    safe_title = html.escape(title)
    caption = f"🎵 <b>{safe_title}</b>\n\n📺 <a href=\"{yt_url}\">Watch on YouTube</a>"
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

    # ── 1-deep download pipeline ──────────────────────────────────────
    # Start each track's download + ffmpeg transcode while the PREVIOUS
    # track is still uploading/pinning, so the two slow phases (download
    # and upload) overlap instead of running strictly back-to-back. Posts
    # still happen in order. The thread pool (max_workers=2) comfortably
    # holds the current + next download.
    def _schedule_dl(zero_idx: int):
        if 0 <= zero_idx < len(new_videos):
            return loop.run_in_executor(
                _executor, _download_audio, new_videos[zero_idx]["id"]
            )
        return None

    # Clear orphaned downloads from a previously interrupted run (e.g. the bot
    # was stopped mid-prefetch) so DOWNLOAD_DIR doesn't accumulate. Only the
    # bot's own artefacts (audio + yt-dlp temp files) are removed, never
    # unrelated files — DOWNLOAD_DIR may be a folder the user also keeps things
    # in, so a blanket wipe could destroy their data.
    _DL_ARTEFACT_EXTS = (
        ".mp3", ".m4a", ".webm", ".opus", ".ogg", ".mp4",
        ".part", ".ytdl", ".temp", ".tmp",
    )
    if os.path.isdir(DOWNLOAD_DIR):
        for _f in os.listdir(DOWNLOAD_DIR):
            if _f.lower().endswith(_DL_ARTEFACT_EXTS):
                try:
                    os.remove(os.path.join(DOWNLOAD_DIR, _f))
                except OSError:
                    pass

    pending = _schedule_dl(0)  # prefetch the first track

    for i, video in enumerate(new_videos, 1):
        video_id: str = video["id"]
        title: str = video["title"]
        mp3_path: str | None = None
        dl_future = pending
        pending = _schedule_dl(i)  # prefetch the NEXT track (overlaps this upload)

        try:
            logger.info(
                "[%s] [%d/%d] Downloading: %s", channel.name, i, len(new_videos), title
            )
            mp3_path = await dl_future

            # Telegram bot API rejects audio files larger than 50 MB. Such a
            # track would fail to send on every cycle forever — instead mark
            # it as handled (skipped) so we don't retry it endlessly.
            size = os.path.getsize(mp3_path)
            if size > _TG_AUDIO_LIMIT_BYTES:
                logger.warning(
                    "[%s] [%d/%d] Too large for Telegram (%.1f MB > 50 MB), skipping: %s",
                    channel.name, i, len(new_videos), size / 1_048_576, title,
                )
                sent_videos[video_id] = {
                    "title": title,
                    "skipped": "too_large",
                    "size_bytes": size,
                    "posted_at": datetime.now(UTC).isoformat(),
                }
                save_json(channel.sent_videos_file, sent_videos)
                continue

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


# ---------------------------------------------------------------------------
# Interactive setup wizard — turns the app into a guided, .env-free experience
# ---------------------------------------------------------------------------
def _extract_playlist_id(text: str) -> str:
    """Extract a YouTube playlist ID from a URL, or return the trimmed input.

    Accepts a full playlist URL (``...?list=PLxxxx``) or a bare ID.
    """
    text = text.strip()
    match = re.search(r"[?&]list=([A-Za-z0-9_-]+)", text)
    return match.group(1) if match else text


def _normalise_handle(text: str) -> str:
    """Normalise a Telegram channel reference to ``@name``.

    Accepts ``@name``, ``name`` or a ``t.me/name`` link.
    """
    text = text.strip()
    link = re.search(r"t\.me/([A-Za-z0-9_]+)", text)
    if link:
        text = link.group(1)
    text = text.lstrip("@")
    return f"@{text}" if text else ""


async def _verify_token(token: str) -> str | None:
    """Return the bot's username if *token* is valid, else ``None``."""
    try:
        me = await Bot(token=token).get_me()
        return me.username
    except Exception:  # noqa: BLE001
        return None


async def _verify_channel(token: str, channel: str) -> str | None:
    """Return the channel title if reachable, else ``None``."""
    try:
        chat = await Bot(token=token).get_chat(channel)
        return chat.title or channel
    except Exception:  # noqa: BLE001
        return None


async def _test_post(token: str, channel: str) -> tuple[bool, str]:
    """Actually post (and delete) a test message in *channel*.

    Unlike ``get_chat`` — which only checks reachability — this proves the
    bot is an admin with *post* rights, the real failure mode users hit.

    Returns ``(ok, human_message)``.
    """
    try:
        bot = Bot(token=token)
        msg = await bot.send_message(
            chat_id=channel,
            text="✅ Space Music Hub — тест связи. Бот может писать сюда. "
                 "Это сообщение сейчас удалится.",
        )
        # Clean up so the channel isn't littered with test posts.
        try:
            await bot.delete_message(chat_id=channel, message_id=msg.message_id)
        except Exception:  # noqa: BLE001 — delete is best-effort
            pass
        chat = await bot.get_chat(channel)
        return True, (chat.title or channel)
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def _do_test() -> int:
    """`--bot-test` entry: read token+channel from env, post a test message.

    Used by the GUI wizard's "Test channel" button. Reads SMH_TEST_TOKEN
    and SMH_TEST_CHANNEL from the environment so the secret never appears
    on the command line / process list.
    """
    token   = os.getenv("SMH_TEST_TOKEN", "").strip()
    channel = os.getenv("SMH_TEST_CHANNEL", "").strip()
    if not token or not channel:
        print("TEST_FAIL|missing token or channel", flush=True)
        return 1
    ok, info = asyncio.run(_test_post(token, channel))
    if ok:
        print(f"TEST_OK|{info}", flush=True)
        return 0
    print(f"TEST_FAIL|{info}", flush=True)
    return 1


def _write_env_file(
    token: str,
    channels: list[tuple[str, str, str]],
    *,
    download_dir: str = "C:\\Temp\\music_bot",
) -> None:
    """Write a fresh ``.env`` from wizard answers (next to the app)."""
    lines = [
        "# === Space Music Hub configuration ===",
        "# Generated by the setup wizard. You can also edit it by hand.",
        "",
        f"TELEGRAM_BOT_TOKEN={token}",
        "",
    ]
    for i, (name, playlist, handle) in enumerate(channels, 1):
        lines += [
            f"CHANNEL_{i}_NAME={name}",
            f"CHANNEL_{i}_PLAYLIST={playlist}",
            f"CHANNEL_{i}_TELEGRAM={handle.lstrip('@')}",
            "",
        ]
    lines += [f"DOWNLOAD_DIR={download_dir}", ""]
    with open(_app_path(".env"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _line(ch: str = "=") -> None:
    print(ch * 62)


def setup_wizard() -> bool:
    """Run the guided first-time setup (RU). Returns True if config was saved."""
    print()
    _line()
    print("  SPACE MUSIC HUB  —  Настройка (3 шага)")
    _line()
    print("Привет! Эта программа берёт музыку из твоего плейлиста YouTube")
    print("и сама публикует её в твой Telegram-канал.")
    print("Мастер всё объяснит по шагам — просто следуй подсказкам.\n")

    # --- Шаг 1: бот --------------------------------------------------------
    _line("-")
    print("  ШАГ 1 из 3 — Создай своего Telegram-бота")
    _line("-")
    print("Бот — это помощник, которым управляет программа. Бесплатно, 1 минута:\n")
    print("  1. Открой Telegram. В поиске сверху набери:   @BotFather")
    print("  2. Открой его (с синей галочкой) и отправь:   /newbot")
    print("  3. Придумай имя боту (любое, например: Моя Музыка)")
    print("  4. Придумай логин боту — латиницей, в конце 'bot'")
    print("       например:  moya_muzyka_2026_bot")
    print("  5. BotFather пришлёт ТОКЕН — длинную строку вида:")
    print("       8123456789:AAH-xxxxxxxxxxxxxxxxxxxxxxxxxxx")
    print("  6. Скопируй токен и вставь сюда")
    print("       (правый клик в этом окне = Вставить).\n")
    while True:
        token = input("  Вставь токен бота (пусто = отмена): ").strip()
        if not token:
            print("  Настройка отменена.")
            return False
        print("  Проверяю токен...")
        username = asyncio.run(_verify_token(token))
        if username:
            print(f"  ОК — бот @{username} подключён.\n")
            break
        print("  Токен неверный. Скопируй заново у @BotFather и попробуй ещё раз.")

    # --- Шаг 2: канал ------------------------------------------------------
    _line("-")
    print("  ШАГ 2 из 3 — Твой Telegram-канал")
    _line("-")
    print("Сюда программа будет публиковать музыку.\n")
    print("  1. Создай канал: меню Telegram -> Создать канал (или открой свой).")
    print("  2. Сделай канал ПУБЛИЧНЫМ с именем (@...):")
    print("       Управление каналом -> Тип канала -> Публичный -> задай ссылку.")
    print("  3. Добавь своего бота в администраторы канала:")
    print("       Управление каналом -> Администраторы -> Добавить ->")
    print("       найди бота по его логину -> добавь.")
    print("  4. Включи боту права: 'Публикация сообщений' и 'Закрепление'.\n")
    channels: list[tuple[str, str, str]] = []
    while True:
        if channels:
            print(f"  --- Канал #{len(channels) + 1} ---")
        handle = ""
        while not handle:
            handle = _normalise_handle(
                input("  Имя канала (например @my_music): ")
            )
            if not handle:
                print("  Введи имя канала, например @my_music")
        print("  Проверяю канал...")
        title = asyncio.run(_verify_channel(token, handle))
        if title:
            print(f"  ОК — канал найден: {title}")
        else:
            print("  Внимание: канал пока не виден. Проверь, что бот добавлен")
            print("  в администраторы и канал публичный. Сохраню как есть.")

        # --- Шаг 3: плейлист ----------------------------------------------
        print()
        _line("-")
        print("  ШАГ 3 из 3 — Твой плейлист YouTube")
        _line("-")
        print("Программа будет следить за этим плейлистом.\n")
        print("  1. Открой YouTube, зайди в нужный плейлист")
        print("       (свой плейлист или 'Понравившиеся').")
        print("  2. Плейлист должен быть 'Открытый' или 'Доступ по ссылке'")
        print("       (приватный программа прочитать не сможет).")
        print("  3. Скопируй адрес из браузера — он выглядит так:")
        print("       https://www.youtube.com/playlist?list=PLxxxxxxxx")
        print("  4. Вставь сюда всю ссылку целиком.\n")
        playlist_id = _extract_playlist_id(
            input("  Вставь ссылку на плейлист: ")
        )
        print("  Проверяю плейлист...")
        try:
            videos = _get_playlist_videos(playlist_id)
            print(f"  ОК — найдено треков: {len(videos)}")
        except Exception:  # noqa: BLE001
            print("  Внимание: не удалось прочитать плейлист. Сохраню как есть.")
        channels.append((handle.lstrip("@"), playlist_id, handle))

        print()
        more = input("  Добавить ещё один канал? (да/нет): ").strip().lower()
        if more not in ("д", "да", "y", "yes"):
            break
        print()

    # --- сохранение --------------------------------------------------------
    print("\nСохраняю настройки...")
    _write_env_file(token, channels)
    print(f"  Готово. Файл настроек: {_app_path('.env')}")
    print("\n✓ Настройка завершена!\n")
    return True


def _reload_config() -> None:
    """Reload globals from .env after the wizard rewrites it."""
    global TELEGRAM_BOT_TOKEN, ADMIN_CHAT_ID, DOWNLOAD_DIR, CHANNELS
    load_dotenv(_app_path(".env"), override=True)
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "")
    DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", "downloads")
    CHANNELS = _load_channels()


# ---------------------------------------------------------------------------
# Entry point helpers
# ---------------------------------------------------------------------------
def _pause_if_frozen() -> None:
    """Keep the console window open when launched as a double-clicked .exe."""
    if getattr(sys, "frozen", False):
        try:
            input("\nНажми Enter, чтобы закрыть...")
        except (EOFError, KeyboardInterrupt):
            pass


def _setup_console() -> None:
    """Make the Windows console render UTF-8 so Cyrillic text displays correctly."""
    if os.name == "nt":
        try:
            os.system("chcp 65001 >nul 2>&1")
        except Exception:  # noqa: BLE001
            pass
    for stream in (sys.stdout, sys.stderr, sys.stdin):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except Exception:  # noqa: BLE001
            pass


def _pid_alive(pid: int) -> bool:
    """Return True if a process with *pid* is currently running."""
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, False, pid
        )
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return True  # can't determine — assume alive (fail safe)
            return code.value == STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _acquire_lock(lock_file: str) -> bool:
    """Atomically acquire the single-instance lock.

    Returns True on success. Uses ``O_CREAT | O_EXCL`` so check-and-create is
    atomic (no TOCTOU race). If a lock already exists but the PID that wrote it
    is no longer alive, the stale lock is reclaimed instead of blocking forever
    (e.g. after a crash, on Task Scheduler where no GUI sweeps it).
    """
    for _ in range(2):
        try:
            fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                with open(lock_file, encoding="utf-8") as fh:
                    owner = int(fh.read().strip() or "0")
            except (OSError, ValueError):
                owner = 0
            if owner and _pid_alive(owner):
                return False
            # Stale lock — its owner is gone. Remove and retry once.
            try:
                os.remove(lock_file)
            except OSError:
                return False
            continue
        else:
            with os.fdopen(fd, "w") as fh:
                fh.write(str(os.getpid()))
            return True
    return False


def _do_run() -> int:
    """Perform a real run (download + post) guarded by a single-instance lock."""
    lock_file = _app_path("bot.lock")
    if not _acquire_lock(lock_file):
        logger.error(
            "Another instance is already running (lock file: %s). "
            "If the previous run crashed, delete it and try again.",
            lock_file,
        )
        return 1

    exit_code = 0
    try:
        logger.info("=== space-music-hub bot v%s starting ===", __version__)
        asyncio.run(main())
        logger.info("=== bot run complete ===")
    except OSError as exc:
        logger.error("Configuration error: %s", exc)
        print(f"\n[X] {exc}")
        exit_code = 1
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error: %s", exc)
        print(f"\n[X] Unexpected error: {exc}\nSee bot.log for details.")
        exit_code = 1
    finally:
        if os.path.exists(lock_file):
            os.remove(lock_file)
    return exit_code


def _do_check() -> int:
    """Validate config and count new tracks without posting anything."""
    try:
        logger.info("=== space-music-hub check v%s ===", __version__)
        asyncio.run(check())
    except OSError as exc:
        logger.error("Configuration error: %s", exc)
        print(f"\n[X] {exc}\n\nRU: запусти настройку заново (пункт меню).")
        return 1
    except Exception as exc:  # noqa: BLE001
        logger.exception("Check failed: %s", exc)
        print(f"\n[X] Ошибка проверки: {exc}\nПодробности в bot.log.")
        return 1
    return 0


def _format_interval(seconds: int) -> str:
    """Human-friendly interval label for logs (RU)."""
    if seconds % 604800 == 0:
        n = seconds // 604800
        return "раз в неделю" if n == 1 else f"каждые {n} нед."
    if seconds % 86400 == 0:
        n = seconds // 86400
        return "раз в день" if n == 1 else f"каждые {n} дн."
    if seconds % 3600 == 0:
        n = seconds // 3600
        return "каждый час" if n == 1 else f"каждые {n} ч."
    return f"каждые {max(1, seconds // 60)} мин"


async def watch() -> None:
    """Run forever: post new tracks, then re-check every WATCH_INTERVAL seconds.

    This is the "leave it running" mode — while the window is open the program
    keeps checking the playlist and posts new tracks automatically.
    """
    _validate_config()
    interval = max(60, int(os.getenv("WATCH_INTERVAL", "900")))
    human = _format_interval(interval)
    print()
    print("Программа работает. ОСТАВЬ ЭТО ОКНО ОТКРЫТЫМ —")
    print(f"новые треки проверяются {human} и сами уходят в канал.")
    print("Чтобы остановить — закрой окно или нажми Ctrl+C.\n")
    logger.info("Watch mode started (interval: %s).", human)

    cycle = 0
    while True:
        cycle += 1
        posted = 0
        for channel in CHANNELS:
            result = await post_new_videos(channel)
            posted += result.posted
        logger.info(
            "Cycle %d done — posted %d. Next check %s.", cycle, posted, human
        )
        await asyncio.sleep(interval)


def _do_watch() -> int:
    """Run :func:`watch` under the single-instance lock until interrupted."""
    lock_file = _app_path("bot.lock")
    if not _acquire_lock(lock_file):
        logger.error(
            "Похоже, программа уже запущена (есть файл %s). "
            "Если прошлый запуск завис — удали этот файл и попробуй снова.",
            lock_file,
        )
        return 1

    exit_code = 0
    try:
        logger.info("=== space-music-hub watch v%s starting ===", __version__)
        asyncio.run(watch())
    except KeyboardInterrupt:
        print("\nОстановлено. Пока!")
    except OSError as exc:
        logger.error("Configuration error: %s", exc)
        print(f"\n[X] {exc}")
        exit_code = 1
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error: %s", exc)
        print(f"\n[X] Ошибка: {exc}\nПодробности в bot.log.")
        exit_code = 1
    finally:
        if os.path.exists(lock_file):
            os.remove(lock_file)
    return exit_code


def _interactive_menu() -> int:
    """Show the main menu for a double-clicked / terminal interactive session."""
    while True:
        print()
        _line()
        print("  SPACE MUSIC HUB")
        _line()
        print("  1) Запустить (авто)  — следить и публиковать новые треки")
        print("  2) Запустить 1 раз   — опубликовать новые и выйти")
        print("  3) Проверка          — проверить настройки (без публикации)")
        print("  4) Перенастроить     — пройти мастер заново")
        print("  5) Выход")
        choice = input("  Выбор (1-5): ").strip()
        if choice == "1":
            return _do_watch()
        if choice == "2":
            return _do_run()
        if choice == "3":
            _do_check()
        elif choice == "4":
            if setup_wizard():
                _reload_config()
        elif choice == "5":
            return 0
        else:
            print("  Не понял выбор, попробуй ещё раз.")


def _run_cli() -> int:
    """Console entry point. Returns a process exit code.

    Modes:
      --watch          run forever, post new tracks as they appear
      --run            single headless run (used by Task Scheduler) — no prompts
      --check/--dry-run validate + count, no posting
      --setup          force the setup wizard
      (no args)        interactive: wizard on first run, otherwise a menu
    """
    _setup_console()
    args = sys.argv[1:]

    if "--check" in args or "--dry-run" in args:
        return _do_check()

    if "--setup" in args:
        ok = setup_wizard()
        _pause_if_frozen()
        return 0 if ok else 1

    if "--watch" in args:
        return _do_watch()

    if "--run" in args:
        # Single headless run (safe for Task Scheduler / cron) — never prompts.
        return _do_run()

    # No arguments → interactive experience.
    if not os.getenv("TELEGRAM_BOT_TOKEN") or not CHANNELS:
        # First run: nothing configured yet — launch the guided wizard.
        if setup_wizard():
            _reload_config()
            print("Всё настроено! Программа будет следить за плейлистом и сама")
            print("публиковать новые треки, пока это окно открыто.")
            answer = input("Запустить сейчас? (да/нет): ").strip().lower()
            if answer in ("", "д", "да", "y", "yes"):
                code = _do_watch()
                _pause_if_frozen()
                return code
        _pause_if_frozen()
        return 0

    code = _interactive_menu()
    _pause_if_frozen()
    return code


if __name__ == "__main__":
    raise SystemExit(_run_cli())
