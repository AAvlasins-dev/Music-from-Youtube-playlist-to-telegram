# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [1.5.0] — 2026-06-08

### Added
- **Interactive setup wizard** — on first launch (or `--setup`) the app guides
  the user through entering the bot token, channel(s) and playlist(s), verifying
  each one live (token via `getMe`, channel via `getChat`, playlist via yt-dlp),
  then writes `.env` automatically. **No manual config-file editing required.**
- **Menu-driven console app** — after setup, launching shows a menu:
  Run now / Check / Reconfigure / Exit. Turns the bot into a real desktop app.
- **`--run` flag** — headless run with no prompts, for Task Scheduler / cron.
- **`--setup` flag** — force the setup wizard at any time.
- Smart input parsing: full YouTube playlist URLs and `t.me/...` channel links
  are accepted and normalised automatically (`_extract_playlist_id`,
  `_normalise_handle`).
- 9 new unit tests (46 → 55) for the wizard's parsing and `.env` writing.

### Changed
- Double-clicking the `.exe` now opens the wizard/menu instead of requiring a
  pre-written `.env`.
- Task Scheduler now uses `SpaceMusicHub.exe --run` (documented in INSTALL.md).
- INSTALL.md rewritten around the wizard-first flow.

---

## [1.4.0] — 2026-06-08

### Added
- **Standalone Windows executable** — `build_exe.bat` produces `SpaceMusicHub.exe`
  (PyInstaller, one-file). Bundles Python + yt-dlp + python-telegram-bot; ships
  next to `.env` and `ffmpeg.exe`. No Python install required on the target PC.
- **`--check` / `--dry-run` mode** — validates config, verifies the bot token,
  and counts new tracks per channel **without downloading or posting anything**.
  Safe to run any time.
- **Dynamic channel loading** (`_load_channels`) — unlimited numbered pairs
  `CHANNEL_N_PLAYLIST` / `CHANNEL_N_TELEGRAM` / `CHANNEL_N_NAME`; legacy
  `PLAYLIST_ANDREY` / `TELEGRAM_CHANNEL_ANDREY` still supported.
- **Single-instance lock** (`bot.lock`) — a second run exits immediately instead
  of re-posting tracks (root cause of earlier duplicate posts).
- **Incremental state save** — state is flushed after every posted track, so a
  crash or restart resumes from the last success instead of starting over.
- 21 new unit tests (25 → 46): channel loading, ffmpeg discovery, audio
  download, and the full `post_new_videos` posting loop.
- Detailed Russian installation guide (`INSTALL.md`).

### Changed
- Schedule switched from every-2-days to **daily** (Task Scheduler + CI cron).
- App is now path-independent: `.env`, logs, state and lock files resolve
  relative to the executable/script via `_app_dir()` — works no matter the
  working directory or when frozen into an `.exe`.
- `_find_ffmpeg()` now also checks for `ffmpeg.exe` next to the app first.
- Friendly error messages + "Press Enter to close" pause when run as an `.exe`.

---

## [1.3.0] — 2026-06-07

### Added
- **ffmpeg auto-discovery** (`_find_ffmpeg`): checks `FFMPEG_PATH` env var → system PATH → `ffmpeg-downloader` bundle, so the bot works without any manual PATH setup
- `ffmpeg-downloader` added to `requirements.txt` — installs a portable ffmpeg binary with a single `pip install`
- `FFMPEG_PATH` env var for explicit ffmpeg override

### Fixed
- **`[Errno 22] Invalid argument`** on Windows: ffmpeg fails when the output path contains non-ASCII characters (Cyrillic, etc.). Fixed by defaulting `DOWNLOAD_DIR` to `C:\Temp\music_bot` and documenting that it must be an ASCII-only path
- **Relative ffmpeg path** (`.\ffmpeg.EXE`) broke yt-dlp when the process was started from a different working directory. `_find_ffmpeg()` now always returns an absolute path
- `yt-dlp` updated from `2025.1.15` → `2026.3.17` — resolves YouTube format-not-available errors on the current YouTube API

### Changed
- `_download_audio` gracefully falls back to native container (m4a/mp4) when ffmpeg is unavailable — Telegram accepts both formats
- `DOWNLOAD_DIR` default changed from `downloads` (relative, may be Cyrillic) to `C:\Temp\music_bot`

---

## [1.2.0] — 2026-06-06

### Changed
- **Rewrote the bot to download and send real MP3 files** via `yt-dlp` + `ffmpeg` instead of posting YouTube links — no YouTube Data API key required anymore
- Playlist reading now uses `yt-dlp` flat extraction (`_get_playlist_videos`)
- Audio is downloaded as `bestaudio` and converted to 192 kbps MP3 (`_download_audio`), sent via `bot.send_audio`, then deleted after a successful send
- Renamed `TELEGRAM_TOKEN` → `TELEGRAM_BOT_TOKEN`
- State is now stored per channel: `sent_videos_<name>.json` / `pinned_msgs_<name>.json`
- `requirements.txt` now pins `yt-dlp==2025.1.15`; dropped `google-api-python-client`

### Fixed
- **CI state persistence:** the workflow committed empty un-suffixed `sent_videos.json` / `pinned_msgs.json`, so real per-channel state was never saved and every run re-posted the whole playlist. Now force-adds `sent_videos_*.json` / `pinned_msgs_*.json`
- Removed the unused `YOUTUBE_API_KEY` secret from the workflow
- Deleted the empty legacy `sent_videos.json` / `pinned_msgs.json` from the repo

### Added
- `tests/` with `pytest` unit tests and `ruff` linting, wired into CI

---

## [1.1.0] — 2026-05-20

### Added
- Retry logic with exponential back-off for YouTube API and Telegram API calls (`RETRY_ATTEMPTS`, `RETRY_DELAY` env vars)
- Configurable delay between consecutive posts (`POST_DELAY` env var)
- Rotating file handler for `bot.log` (max 5 MB × 3 backups) alongside console logging
- `LOG_LEVEL` and `LOG_FILE` environment variables for runtime log configuration
- Startup config validation — fails fast with a clear error when required env vars are missing
- `SENT_VIDEOS_FILE` and `PINNED_MSGS_FILE` env vars to override default state file paths
- `Dockerfile` for containerised deployment (Python 3.12-slim, state persisted in `/app/data` volume)
- `docker-compose.yml` for one-command local and server deployment
- `requirements.txt` with pinned dependency versions
- Rewritten `README.md` — badges, architecture diagram, full configuration reference (EN + RU)

### Changed
- Logging format upgraded to `YYYY-MM-DD HH:MM:SS | LEVEL | module | message`
- `datetime.utcnow()` replaced with timezone-aware `datetime.now(timezone.utc)`
- YouTube page fetches extracted to a dedicated `_fetch_page()` function (retried independently)
- Telegram send/pin/unpin extracted to `_send_message()`, `_pin_message()`, `_unpin_message()` (each retried independently)
- Progress counter added to per-video log lines: `[1/5] Posted: …`

---

## [1.0.0] — 2026-05-20

### Added
- Initial release
- Fetch all videos from a YouTube playlist via YouTube Data API v3
- Post new videos to a Telegram channel (skip already-sent ones)
- Auto-pin the latest posted message, unpin the previous one
- State persistence in `sent_videos.json` and `pinned_msgs.json`
- Basic `logging` to stdout
- `.env`-based configuration via `python-dotenv`
- `.gitignore` and `.env.example`
