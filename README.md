# 🚀 Space Music Hub

![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)
![python-telegram-bot](https://img.shields.io/badge/python--telegram--bot-21.6-blue?logo=telegram)
![YouTube Data API](https://img.shields.io/badge/YouTube%20Data%20API-v3-red?logo=youtube)
![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker)
![License](https://img.shields.io/badge/License-MIT-green)

> **EN** — A Telegram bot that automatically publishes new videos from a YouTube playlist to a Telegram channel and pins the latest post.
>
> **RU** — Telegram-бот, который автоматически публикует новые видео из YouTube-плейлиста в Telegram-канал и закрепляет последнее сообщение.

---

## ✨ Features / Возможности

| Feature | Description |
|---|---|
| 🎵 Auto-publishing | Fetches all videos from a YouTube playlist and posts only new ones |
| 📌 Auto-pinning | Unpins the previous post, pins the latest one automatically |
| 💾 State persistence | Tracks posted videos in `sent_videos.json` across runs |
| 🔁 Retry logic | Retries failed YouTube API and Telegram API calls with exponential back-off |
| 📋 Structured logging | Logs to both console and a rotating `bot.log` file with INFO/WARNING/ERROR levels |
| 🐳 Docker-ready | Ships with `Dockerfile` and `docker-compose.yml` for one-command deployment |
| ⚙️ Fully configurable | All behaviour is controlled via environment variables |

---

## 🏗 Architecture / Архитектура

```
┌─────────────────────────────────────────────┐
│              space-music-hub bot             │
│                                             │
│  ┌──────────────┐    ┌───────────────────┐  │
│  │ YouTube API  │───▶│  get_playlist_    │  │
│  │    v3        │    │  videos()         │  │
│  └──────────────┘    └────────┬──────────┘  │
│                               │             │
│                     ┌─────────▼──────────┐  │
│                     │  Filter new videos  │  │
│                     │  (sent_videos.json) │  │
│                     └─────────┬──────────┘  │
│                               │             │
│  ┌──────────────┐    ┌────────▼──────────┐  │
│  │ Telegram API │◀───│  post_new_videos() │  │
│  │  (Bot API)   │    │  + retry logic     │  │
│  └──────────────┘    └─────────┬──────────┘ │
│                               │             │
│                     ┌─────────▼──────────┐  │
│                     │  Save state +       │  │
│                     │  pin latest message │  │
│                     └────────────────────┘  │
└─────────────────────────────────────────────┘
```

---

## 🚀 Quick Start / Быстрый старт

### Option 1 — Docker (recommended)

```bash
# 1. Clone the repository
git clone https://github.com/AAvlasins-dev/Music-from-Youtube-playlist-to-telegram.git
cd Music-from-Youtube-playlist-to-telegram

# 2. Create .env from the template
cp .env.example .env
# Fill in the variables (see Configuration section below)

# 3. Run once
docker compose up --build

# 4. Schedule recurring runs (Linux cron example — every 6 hours)
0 */6 * * * docker compose -f /path/to/docker-compose.yml up --build >> /var/log/space-music-hub.log 2>&1
```

### Option 2 — Local Python

```bash
# 1. Clone & enter the project
git clone https://github.com/AAvlasins-dev/Music-from-Youtube-playlist-to-telegram.git
cd Music-from-Youtube-playlist-to-telegram

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
.venv\Scripts\activate           # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env and fill in your credentials

# 5. Run
python telegram_bot_music_youtube.py
```

---

## ⚙️ Configuration / Настройка

Copy `.env.example` to `.env` and fill in the values:

| Variable | Required | Description |
|---|---|---|
| `TELEGRAM_TOKEN` | ✅ | Bot token from [@BotFather](https://t.me/BotFather) |
| `CHANNEL_ID` | ✅ | Channel username (`@channel`) or numeric chat ID |
| `YOUTUBE_API_KEY` | ✅ | API key from [Google Cloud Console](https://console.cloud.google.com/) |
| `YOUTUBE_PLAYLIST_ID` | ✅ | YouTube playlist ID (from the playlist URL) |
| `RETRY_ATTEMPTS` | ➖ | Number of retry attempts on API errors (default: `3`) |
| `RETRY_DELAY` | ➖ | Base delay in seconds between retries (default: `5`) |
| `POST_DELAY` | ➖ | Delay in seconds between consecutive posts (default: `1`) |
| `LOG_LEVEL` | ➖ | Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR` (default: `INFO`) |
| `LOG_FILE` | ➖ | Path to log file (default: `bot.log`) |
| `SENT_VIDEOS_FILE` | ➖ | Path to sent-videos state file (default: `sent_videos.json`) |
| `PINNED_MSGS_FILE` | ➖ | Path to pinned-message state file (default: `pinned_msgs.json`) |

### Getting a YouTube Playlist ID

Open the playlist on YouTube. The ID is the `list=` parameter in the URL:

```
https://www.youtube.com/playlist?list=PLxxxxxxxxxxxxxxxx
                                       ^^^^^^^^^^^^^^^^
```

### Bot permissions in the channel

Add the bot as an **Administrator** with the following rights:
- Post messages
- Pin messages

---

## 📁 Project Structure / Структура проекта

```
space-music-hub/
├── telegram_bot_music_youtube.py   # Main bot script
├── requirements.txt                # Python dependencies
├── Dockerfile                      # Docker image definition
├── docker-compose.yml              # Docker Compose config
├── .env.example                    # Environment variables template
├── .gitignore                      # Git ignore rules
├── sent_videos.json                # Runtime state — posted videos (auto-created)
├── pinned_msgs.json                # Runtime state — pinned message ID (auto-created)
├── bot.log                         # Rotating log file (auto-created)
└── README.md
```

---

## 📦 Dependencies / Зависимости

| Package | Version | Purpose |
|---|---|---|
| `python-telegram-bot` | 21.6 | Telegram Bot API client |
| `google-api-python-client` | 2.140.0 | YouTube Data API v3 client |
| `python-dotenv` | 1.0.1 | Load environment variables from `.env` |

---

## 📝 License

MIT — feel free to use and modify.
