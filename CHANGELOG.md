# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
