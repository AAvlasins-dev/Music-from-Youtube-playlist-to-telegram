# 🚀 Space Music Hub

[![Run Music Bot](https://github.com/AAvlasins-dev/Music-from-Youtube-playlist-to-telegram/actions/workflows/bot.yml/badge.svg)](https://github.com/AAvlasins-dev/Music-from-Youtube-playlist-to-telegram/actions/workflows/bot.yml)
[![CI](https://github.com/AAvlasins-dev/Music-from-Youtube-playlist-to-telegram/actions/workflows/ci.yml/badge.svg)](https://github.com/AAvlasins-dev/Music-from-Youtube-playlist-to-telegram/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)
![python-telegram-bot](https://img.shields.io/badge/python--telegram--bot-21.6-blue?logo=telegram)
![yt-dlp](https://img.shields.io/badge/yt--dlp-2025.1-red?logo=youtube)
![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker)
![License](https://img.shields.io/badge/License-MIT-green)

---

## 🌐 Select Language · Выберите язык · Izvēlieties valodu

[🇬🇧 English](#english) · [🇷🇺 Русский](#русский) · [🇱🇻 Latviešu](#latviešu)

---

<a id="english"></a>

## 🇬🇧 English

A Telegram bot that automatically downloads audio from YouTube playlists as MP3 files and publishes them to Telegram channels. Supports multiple playlist→channel pairs, auto-pins the latest post, and runs on a schedule via GitHub Actions — **no server required**.

### ✨ Features

| Feature | Description |
|---|---|
| 🎵 MP3 download & send | Downloads audio via `yt-dlp` + `ffmpeg`, sends as a real MP3 file |
| 🔗 YouTube link in caption | Each post includes the original YouTube link |
| 📌 Auto-pinning | Unpins the previous post, pins the latest one automatically |
| 💾 State persistence | Tracks posted videos in JSON files — never re-posts the same track |
| 🔁 Retry logic | Retries failed downloads and Telegram API calls with exponential back-off |
| 📋 Structured logging | Logs to console and a rotating `bot.log` file (5 MB × 3 backups) |
| 🔔 Admin notifications | Optional summary message to your own Telegram on each run |
| 🐳 Docker-ready | Ships with `Dockerfile` and `docker-compose.yml` |
| ⚙️ Fully configurable | All behaviour controlled via environment variables |
| ☁️ Free hosting | Runs on GitHub Actions schedule — zero infrastructure cost |

### 🏗 Architecture

```
┌─────────────────────────────────────────────┐
│              space-music-hub bot             │
│                                             │
│  ┌──────────────┐    ┌───────────────────┐  │
│  │   YouTube    │───▶│  yt-dlp           │  │
│  │  (playlist)  │    │  _get_playlist_   │  │
│  └──────────────┘    │  videos()         │  │
│                      └────────┬──────────┘  │
│                               │             │
│                     ┌─────────▼──────────┐  │
│                     │  Filter new videos  │  │
│                     │  (sent_videos.json) │  │
│                     └─────────┬──────────┘  │
│                               │             │
│  ┌──────────────┐    ┌────────▼──────────┐  │
│  │   YouTube    │───▶│  yt-dlp + ffmpeg  │  │
│  │  (video URL) │    │  _download_audio()│  │
│  └──────────────┘    └────────┬──────────┘  │
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

### 🚀 Quick Start

#### Option 1 — GitHub Actions (recommended, free)

```bash
# 1. Fork or clone the repository
git clone https://github.com/AAvlasins-dev/Music-from-Youtube-playlist-to-telegram.git
cd Music-from-Youtube-playlist-to-telegram

# 2. Add secrets in GitHub → Settings → Secrets and variables → Actions
#    (see Configuration section below)

# 3. Enable the Actions tab, then trigger manually:
#    Actions → Run Music Bot → Run workflow
```

The bot runs automatically every 2 days. No server needed.

#### Option 2 — Docker

```bash
git clone https://github.com/AAvlasins-dev/Music-from-Youtube-playlist-to-telegram.git
cd Music-from-Youtube-playlist-to-telegram
cp .env.example .env   # fill in your credentials
docker compose up --build
```

#### Option 3 — Local Python

```bash
git clone https://github.com/AAvlasins-dev/Music-from-Youtube-playlist-to-telegram.git
cd Music-from-Youtube-playlist-to-telegram
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env   # fill in your credentials
python telegram_bot_music_youtube.py
```

### ⚙️ Configuration

Copy `.env.example` to `.env` and fill in the values:

| Variable | Required | Description |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | ✅ | Bot token from [@BotFather](https://t.me/BotFather) |
| `PLAYLIST_ANDREY` | ✅ | YouTube playlist ID for Andrey's channel |
| `TELEGRAM_CHANNEL_ANDREY` | ✅ | Telegram channel username **without** `@` (e.g. `my_channel`) |
| `PLAYLIST_BAYBA` | ✅ | YouTube playlist ID for Bayba's channel |
| `TELEGRAM_CHANNEL_BAYBA` | ✅ | Telegram channel username **without** `@` |
| `ADMIN_CHAT_ID` | ➖ | Your Telegram chat ID — receive a run summary after each execution |
| `YOUTUBE_COOKIES_FILE` | ➖ | Path to Netscape cookies file — bypasses YouTube bot-detection on CI |
| `RETRY_ATTEMPTS` | ➖ | Retry attempts on API errors (default: `3`) |
| `RETRY_DELAY` | ➖ | Base delay in seconds between retries (default: `5`) |
| `POST_DELAY` | ➖ | Delay between consecutive posts in seconds (default: `2`) |
| `LOG_LEVEL` | ➖ | `DEBUG`, `INFO`, `WARNING`, `ERROR` (default: `INFO`) |
| `LOG_FILE` | ➖ | Path to log file (default: `bot.log`) |
| `DOWNLOAD_DIR` | ➖ | Temporary MP3 directory (default: `downloads`) |

> **GitHub Actions:** add the required secrets under **Settings → Secrets and variables → Actions**. Optionally add `YOUTUBE_COOKIES_B64` (base64-encoded cookies file) and `ADMIN_CHAT_ID`.

**Getting a YouTube Playlist ID** — it's the `list=` parameter in the playlist URL:
```
https://www.youtube.com/playlist?list=PLxxxxxxxxxxxxxxxx
                                       ^^^^^^^^^^^^^^^^
```

**Bot permissions** — add the bot as **Administrator** with: ✅ Post messages · ✅ Pin messages

### 📁 Project Structure

```
space-music-hub/
├── telegram_bot_music_youtube.py   # Main bot script
├── requirements.txt                # Python dependencies
├── Dockerfile                      # Docker image definition
├── docker-compose.yml              # Docker Compose config
├── .env.example                    # Environment variables template
├── .gitignore                      # Git ignore rules
├── CHANGELOG.md                    # Version history
├── .github/
│   └── workflows/
│       ├── bot.yml                 # Scheduled bot runner (every 2 days)
│       └── ci.yml                  # Lint + tests on every push
└── tests/
    └── test_bot.py                 # Unit tests (pytest)
```

### 📦 Dependencies

| Package | Version | Purpose |
|---|---|---|
| `python-telegram-bot` | 21.6 | Telegram Bot API client |
| `yt-dlp` | 2025.1.15 | YouTube playlist extraction + audio download |
| `python-dotenv` | 1.0.1 | Load environment variables from `.env` |

> `ffmpeg` must be installed on the system (included automatically in the Docker image).

### 📝 License

MIT — feel free to use and modify.

---

<a id="русский"></a>

## 🇷🇺 Русский

Telegram-бот, который автоматически скачивает аудио из YouTube-плейлистов в формате MP3 и публикует треки в Telegram-каналы. Поддерживает несколько пар плейлист→канал, автоматически закрепляет последний пост и запускается по расписанию через GitHub Actions — **сервер не нужен**.

### ✨ Возможности

| Функция | Описание |
|---|---|
| 🎵 Скачивание и отправка MP3 | Скачивает аудио через `yt-dlp` + `ffmpeg`, отправляет как настоящий MP3-файл |
| 🔗 Ссылка на YouTube в подписи | Каждый пост содержит оригинальную ссылку на YouTube |
| 📌 Автозакрепление | Открепляет предыдущее сообщение, автоматически закрепляет новое |
| 💾 Сохранение состояния | Отслеживает опубликованные видео — никогда не постит трек повторно |
| 🔁 Retry-логика | Повторяет неудачные загрузки и вызовы API с экспоненциальной задержкой |
| 📋 Структурированные логи | Консоль + ротируемый файл `bot.log` (5 МБ × 3 копии) |
| 🔔 Уведомления администратору | Опциональное итоговое сообщение в Telegram после каждого запуска |
| 🐳 Docker-ready | `Dockerfile` + `docker-compose.yml` для развёртывания одной командой |
| ⚙️ Полная настройка | Всё поведение управляется через переменные окружения |
| ☁️ Бесплатный хостинг | Расписание GitHub Actions — нулевые расходы на инфраструктуру |

### 🚀 Быстрый старт

#### Вариант 1 — GitHub Actions (рекомендуется, бесплатно)

```bash
git clone https://github.com/AAvlasins-dev/Music-from-Youtube-playlist-to-telegram.git
cd Music-from-Youtube-playlist-to-telegram
# Добавь секреты: Settings → Secrets and variables → Actions
# Затем: Actions → Run Music Bot → Run workflow
```

Бот запускается автоматически каждые 2 дня. Сервер не нужен.

#### Вариант 2 — Docker

```bash
cp .env.example .env   # заполни данные
docker compose up --build
```

#### Вариант 3 — Локальный Python

```bash
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env   # заполни данные
python telegram_bot_music_youtube.py
```

### ⚙️ Настройка

| Переменная | Обязательна | Описание |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | ✅ | Токен бота от [@BotFather](https://t.me/BotFather) |
| `PLAYLIST_ANDREY` | ✅ | ID плейлиста YouTube для канала Андрея |
| `TELEGRAM_CHANNEL_ANDREY` | ✅ | Username Telegram-канала **без** `@` (например `my_channel`) |
| `PLAYLIST_BAYBA` | ✅ | ID плейлиста YouTube для канала Байбы |
| `TELEGRAM_CHANNEL_BAYBA` | ✅ | Username Telegram-канала **без** `@` |
| `ADMIN_CHAT_ID` | ➖ | Твой Telegram chat ID — получай итог после каждого запуска |
| `YOUTUBE_COOKIES_FILE` | ➖ | Путь к файлу cookies — обходит блокировку YouTube на CI |
| `RETRY_ATTEMPTS` | ➖ | Количество попыток при ошибках API (по умолчанию: `3`) |
| `RETRY_DELAY` | ➖ | Базовая задержка между попытками в секундах (по умолчанию: `5`) |
| `POST_DELAY` | ➖ | Задержка между публикациями в секундах (по умолчанию: `2`) |
| `LOG_LEVEL` | ➖ | `DEBUG`, `INFO`, `WARNING`, `ERROR` (по умолчанию: `INFO`) |

> **Секреты GitHub Actions:** добавь обязательные переменные в **Settings → Secrets and variables → Actions**. Опционально: `YOUTUBE_COOKIES_B64` и `ADMIN_CHAT_ID`.

**ID плейлиста YouTube** — параметр `list=` в URL плейлиста:
```
https://www.youtube.com/playlist?list=PLxxxxxxxxxxxxxxxx
```

**Права бота в канале** — добавь как **Администратора**: ✅ Публикация · ✅ Закрепление

### 📦 Зависимости

| Пакет | Версия | Назначение |
|---|---|---|
| `python-telegram-bot` | 21.6 | Клиент Telegram Bot API |
| `yt-dlp` | 2025.1.15 | Извлечение плейлистов YouTube и скачивание аудио |
| `python-dotenv` | 1.0.1 | Загрузка переменных окружения из `.env` |

> `ffmpeg` должен быть установлен в системе (в Docker-образе устанавливается автоматически).

### 📝 Лицензия

MIT — используй и модифицируй свободно.

---

<a id="latviešu"></a>

## 🇱🇻 Latviešu

Telegram bots, kas automātiski lejupielādē audio no YouTube atskaņošanas sarakstiem kā MP3 failus un publicē tos Telegram kanālos. Atbalsta vairākus pārus, automātiski piesprauž jaunāko ziņojumu un darbojas pēc grafika — **serveris nav nepieciešams**.

### ✨ Iespējas

| Funkcija | Apraksts |
|---|---|
| 🎵 MP3 lejupielāde un sūtīšana | Lejupielādē audio ar `yt-dlp` + `ffmpeg`, sūta kā īstu MP3 |
| 🔗 YouTube saite parakstā | Katrs ieraksts satur oriģinālo YouTube saiti |
| 📌 Automātiska piespraušana | Atsprauž iepriekšējo, piesprauž jaunāko ziņojumu |
| 💾 Stāvokļa saglabāšana | Izseko publicētos videoklipus — nekad neatkārto ierakstu |
| 🔁 Atkārtošanas loģika | Eksponenciāla aizkave neveiksmīgiem izsaukumiem |
| 🔔 Administratora paziņojumi | Kopsavilkuma ziņojums Telegram pēc katras izpildes |
| ☁️ Bezmaksas hostings | GitHub Actions grafiks — nulles infrastruktūras izmaksas |

### 🚀 Ātrā palaišana

```bash
git clone https://github.com/AAvlasins-dev/Music-from-Youtube-playlist-to-telegram.git
cd Music-from-Youtube-playlist-to-telegram
cp .env.example .env   # aizpildi datus
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python telegram_bot_music_youtube.py
```

### ⚙️ Konfigurācija

| Mainīgais | Nepieciešams | Apraksts |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | ✅ | Bota marķieris no [@BotFather](https://t.me/BotFather) |
| `PLAYLIST_ANDREY` | ✅ | YouTube atskaņošanas saraksta ID |
| `TELEGRAM_CHANNEL_ANDREY` | ✅ | Telegram kanāla lietotājvārds **bez** `@` |
| `PLAYLIST_BAYBA` | ✅ | YouTube atskaņošanas saraksta ID |
| `TELEGRAM_CHANNEL_BAYBA` | ✅ | Telegram kanāla lietotājvārds **bez** `@` |
| `ADMIN_CHAT_ID` | ➖ | Tavs Telegram chat ID kopsavilkuma paziņojumiem |

### 📝 Licence

MIT — brīvi izmantojiet un modificējiet.
