# 🚀 Space Music Hub

![CI](https://github.com/AAvlasins-dev/Music-from-Youtube-playlist-to-telegram/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)
![python-telegram-bot](https://img.shields.io/badge/python--telegram--bot-21.6-blue?logo=telegram)
![yt-dlp](https://img.shields.io/badge/yt--dlp-2025.1.15-red?logo=youtube)
![ffmpeg](https://img.shields.io/badge/ffmpeg-required-007808?logo=ffmpeg)
![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker)
![License](https://img.shields.io/badge/License-MIT-green)

---

## 🌐 Select Language · Выберите язык · Izvēlieties valodu

[🇬🇧 English](#english) · [🇷🇺 Русский](#русский) · [🇱🇻 Latviešu](#latviešu)

---

<a id="english"></a>

## 🇬🇧 English

A Telegram bot that **downloads real MP3 audio** from new videos of two YouTube playlists (via `yt-dlp` + `ffmpeg`) and publishes them as audio files to two separate Telegram channels — pinning the latest track in each. No YouTube API key required.

### ✨ Features

| Feature | Description |
|---|---|
| 🎵 Real MP3 audio | Downloads each new video's audio with `yt-dlp` and converts it to 192 kbps MP3 via `ffmpeg`, then sends it as a Telegram audio file |
| 📋 Playlist tracking | Reads a YouTube playlist with `yt-dlp` (flat extraction) and posts only videos not seen before |
| 📌 Auto-pinning | Unpins the previous track and pins the newest one automatically |
| 🗂 Two channels | Handles two independent playlist → channel pairs in a single run, each with its own state |
| 💾 State persistence | Tracks posted videos per channel in `sent_videos_<name>.json` across runs |
| 🔁 Retry logic | Retries failed download / Telegram calls with exponential back-off (works for both sync and async calls) |
| 🧹 Auto cleanup | Deletes the downloaded MP3 right after a successful send — no disk bloat |
| 📝 Structured logging | Logs to console **and** a rotating `bot.log` (5 MB × 3 backups) with INFO/WARNING/ERROR levels |
| 🐳 Docker-ready | Ships with `Dockerfile` (ffmpeg baked in) and `docker-compose.yml` |
| ⚙️ Fully configurable | All behaviour is controlled via environment variables |
| ☁️ Free 24/7 hosting | Runs on a GitHub Actions cron schedule — no server needed (see below) |

### 🏗 Architecture

```
┌────────────────────────────────────────────────────────┐
│                  space-music-hub bot                   │
│                                                        │
│  ┌───────────┐   ┌─────────────────────┐               │
│  │  yt-dlp   │──▶│ _get_playlist_videos │  flat list    │
│  │ (playlist)│   │     (per channel)    │  of video IDs │
│  └───────────┘   └──────────┬──────────┘               │
│                             │                          │
│                  ┌──────────▼──────────┐               │
│                  │  Filter new videos   │               │
│                  │ (sent_videos_*.json) │               │
│                  └──────────┬──────────┘               │
│                             │                          │
│  ┌───────────┐   ┌──────────▼──────────┐               │
│  │  yt-dlp   │──▶│  _download_audio     │  bestaudio    │
│  │ + ffmpeg  │   │  → 192 kbps MP3      │  → MP3 file   │
│  └───────────┘   └──────────┬──────────┘               │
│                             │                          │
│  ┌───────────┐   ┌──────────▼──────────┐               │
│  │ Telegram  │◀──│  send_audio + pin    │  + retry      │
│  │ Bot API   │   │  + unpin previous    │               │
│  └───────────┘   └──────────┬──────────┘               │
│                             │                          │
│                  ┌──────────▼──────────┐               │
│                  │ Save state + cleanup │               │
│                  │ downloaded MP3 file  │               │
│                  └─────────────────────┘               │
└────────────────────────────────────────────────────────┘
```

### 🚀 Quick Start

> **Note:** `ffmpeg` must be available on the host (Docker image already includes it).

#### Option 1 — Docker (recommended)

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

#### Option 2 — Local Python

```bash
# 1. Clone & enter the project
git clone https://github.com/AAvlasins-dev/Music-from-Youtube-playlist-to-telegram.git
cd Music-from-Youtube-playlist-to-telegram

# 2. Install ffmpeg (system dependency)
sudo apt-get install ffmpeg        # Debian/Ubuntu
# brew install ffmpeg              # macOS
# winget install ffmpeg            # Windows

# 3. Create virtual environment
python -m venv .venv
source .venv/bin/activate          # Linux/macOS
.venv\Scripts\activate             # Windows

# 4. Install dependencies
pip install -r requirements.txt

# 5. Configure environment
cp .env.example .env
# Edit .env and fill in your credentials

# 6. Run
python telegram_bot_music_youtube.py
```

### ☁️ Free 24/7 Hosting (GitHub Actions)

This bot is a **batch job** — it runs, posts new tracks, then exits. The repository already ships a scheduled GitHub Actions workflow ([.github/workflows/bot.yml](.github/workflows/bot.yml)) that runs it for free, forever. To enable it:

1. Go to **Settings → Secrets and variables → Actions → New repository secret** and add:
   `TELEGRAM_BOT_TOKEN`, `PLAYLIST_ANDREY`, `TELEGRAM_CHANNEL_ANDREY`, `PLAYLIST_BAYBA`, `TELEGRAM_CHANNEL_BAYBA`.
2. The workflow runs on a cron schedule (default: every 2 days at 09:00 UTC) and can also be triggered manually from the **Actions** tab.
3. Posted-video state is committed back to the repo automatically, so videos are never re-posted.

Adjust the frequency by editing the `cron` line in the workflow (e.g. `0 */6 * * *` for every 6 hours).

### ⚙️ Configuration

Copy `.env.example` to `.env` and fill in the values. **No YouTube API key is needed** — `yt-dlp` reads playlists directly.

| Variable | Required | Description |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | ✅ | Bot token from [@BotFather](https://t.me/BotFather) |
| `PLAYLIST_ANDREY` | ✅ | YouTube playlist ID for Andrey's channel |
| `TELEGRAM_CHANNEL_ANDREY` | ✅ | Telegram channel for Andrey (`@channel` username or numeric chat ID) |
| `PLAYLIST_BAYBA` | ✅ | YouTube playlist ID for Bayba's channel |
| `TELEGRAM_CHANNEL_BAYBA` | ✅ | Telegram channel for Bayba (`@channel` username or numeric chat ID) |
| `DOWNLOAD_DIR` | ➖ | Where MP3s are temporarily stored (default: `downloads`) |
| `RETRY_ATTEMPTS` | ➖ | Number of retry attempts on errors (default: `3`) |
| `RETRY_DELAY` | ➖ | Base delay in seconds between retries (default: `5`) |
| `POST_DELAY` | ➖ | Delay in seconds between consecutive posts (default: `2`) |
| `LOG_LEVEL` | ➖ | Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR` (default: `INFO`) |
| `LOG_FILE` | ➖ | Path to log file (default: `bot.log`) |

**Getting a YouTube Playlist ID**

Open the playlist on YouTube. The ID is the `list=` parameter in the URL:

```
https://www.youtube.com/playlist?list=PLxxxxxxxxxxxxxxxx
                                       ^^^^^^^^^^^^^^^^
```

**Bot permissions in the channel**

Add the bot as an **Administrator** with the following rights:
- Post messages
- Pin messages

### 📁 Project Structure

```
space-music-hub/
├── telegram_bot_music_youtube.py   # Main bot script
├── requirements.txt                # Python dependencies
├── Dockerfile                      # Docker image definition (ffmpeg included)
├── docker-compose.yml              # Docker Compose config
├── .env.example                    # Environment variables template
├── .gitignore                      # Git ignore rules
├── .github/workflows/bot.yml       # Scheduled GitHub Actions run (free 24/7)
├── tests/                          # Unit tests (pytest)
├── sent_videos_andrey.json         # Runtime state — Andrey posted videos (auto-created)
├── pinned_msgs_andrey.json         # Runtime state — Andrey pinned msg ID (auto-created)
├── sent_videos_bayba.json          # Runtime state — Bayba posted videos (auto-created)
├── pinned_msgs_bayba.json          # Runtime state — Bayba pinned msg ID (auto-created)
├── bot.log                         # Rotating log file (auto-created)
└── README.md
```

### 📦 Dependencies

| Package | Version | Purpose |
|---|---|---|
| `python-telegram-bot` | 21.6 | Telegram Bot API client |
| `yt-dlp` | 2025.1.15 | Playlist reading + audio download |
| `python-dotenv` | 1.0.1 | Load environment variables from `.env` |
| `ffmpeg` | system | Audio → MP3 conversion (used by yt-dlp) |

### 🧪 Tests

```bash
pip install -r requirements-dev.txt
pytest            # run unit tests
ruff check .      # lint
```

### 📝 License

MIT — feel free to use and modify.

---

<a id="русский"></a>

## 🇷🇺 Русский

Telegram-бот, который **скачивает реальное MP3-аудио** из новых видео двух YouTube-плейлистов (через `yt-dlp` + `ffmpeg`) и публикует их как аудиофайлы в два отдельных Telegram-канала, закрепляя последний трек в каждом. **API-ключ YouTube не нужен.**

### ✨ Возможности

| Функция | Описание |
|---|---|
| 🎵 Реальное MP3-аудио | Скачивает аудио каждого нового видео через `yt-dlp` и конвертирует в MP3 192 кбит/с через `ffmpeg`, затем отправляет как аудиофайл Telegram |
| 📋 Отслеживание плейлиста | Читает YouTube-плейлист через `yt-dlp` (flat-режим) и публикует только ранее не виденные видео |
| 📌 Автозакрепление | Открепляет предыдущий трек и автоматически закрепляет новейший |
| 🗂 Два канала | Обрабатывает две независимые пары «плейлист → канал» за один запуск, у каждой своё состояние |
| 💾 Сохранение состояния | Отслеживает опубликованные видео по каналам в `sent_videos_<name>.json` между запусками |
| 🔁 Retry-логика | Повторяет неудачные вызовы скачивания / Telegram с экспоненциальной задержкой (работает и для sync, и для async) |
| 🧹 Автоочистка | Удаляет скачанный MP3 сразу после успешной отправки — диск не засоряется |
| 📝 Структурированные логи | Пишет в консоль **и** в ротируемый `bot.log` (5 МБ × 3) с уровнями INFO/WARNING/ERROR |
| 🐳 Docker-ready | Поставляется с `Dockerfile` (ffmpeg внутри) и `docker-compose.yml` |
| ⚙️ Полная настройка | Всё поведение управляется переменными окружения |
| ☁️ Бесплатный хостинг 24/7 | Работает по расписанию через GitHub Actions — сервер не нужен (см. ниже) |

### 🏗 Архитектура

```
┌────────────────────────────────────────────────────────┐
│                  space-music-hub bot                   │
│                                                        │
│  ┌───────────┐   ┌─────────────────────┐               │
│  │  yt-dlp   │──▶│ _get_playlist_videos │  плоский      │
│  │ (плейлист)│   │     (по каналу)      │  список ID    │
│  └───────────┘   └──────────┬──────────┘               │
│                             │                          │
│                  ┌──────────▼──────────┐               │
│                  │   Фильтр новых видео │               │
│                  │ (sent_videos_*.json) │               │
│                  └──────────┬──────────┘               │
│                             │                          │
│  ┌───────────┐   ┌──────────▼──────────┐               │
│  │  yt-dlp   │──▶│  _download_audio     │  bestaudio    │
│  │ + ffmpeg  │   │  → MP3 192 кбит/с    │  → MP3-файл   │
│  └───────────┘   └──────────┬──────────┘               │
│                             │                          │
│  ┌───────────┐   ┌──────────▼──────────┐               │
│  │ Telegram  │◀──│  send_audio + pin    │  + retry      │
│  │ Bot API   │   │  + открепить старое  │               │
│  └───────────┘   └──────────┬──────────┘               │
│                             │                          │
│                  ┌──────────▼──────────┐               │
│                  │ Сохранить состояние  │               │
│                  │ + удалить MP3-файл   │               │
│                  └─────────────────────┘               │
└────────────────────────────────────────────────────────┘
```

### 🚀 Быстрый старт

> **Важно:** на хосте должен быть установлен `ffmpeg` (в Docker-образе он уже есть).

#### Вариант 1 — Docker (рекомендуется)

```bash
# 1. Клонировать репозиторий
git clone https://github.com/AAvlasins-dev/Music-from-Youtube-playlist-to-telegram.git
cd Music-from-Youtube-playlist-to-telegram

# 2. Создать .env из шаблона
cp .env.example .env
# Заполнить переменные (см. раздел Настройка ниже)

# 3. Запустить один раз
docker compose up --build

# 4. Настроить регулярный запуск (пример cron Linux — каждые 6 часов)
0 */6 * * * docker compose -f /path/to/docker-compose.yml up --build >> /var/log/space-music-hub.log 2>&1
```

#### Вариант 2 — Локальный Python

```bash
# 1. Клонировать и перейти в проект
git clone https://github.com/AAvlasins-dev/Music-from-Youtube-playlist-to-telegram.git
cd Music-from-Youtube-playlist-to-telegram

# 2. Установить ffmpeg (системная зависимость)
sudo apt-get install ffmpeg        # Debian/Ubuntu
# brew install ffmpeg              # macOS
# winget install ffmpeg            # Windows

# 3. Создать виртуальное окружение
python -m venv .venv
source .venv/bin/activate          # Linux/macOS
.venv\Scripts\activate             # Windows

# 4. Установить зависимости
pip install -r requirements.txt

# 5. Настроить окружение
cp .env.example .env
# Отредактировать .env и заполнить данные

# 6. Запустить
python telegram_bot_music_youtube.py
```

### ☁️ Бесплатный хостинг 24/7 (GitHub Actions)

Бот — это **batch-задача**: запускается, постит новые треки и завершается. В репозитории уже есть workflow GitHub Actions ([.github/workflows/bot.yml](.github/workflows/bot.yml)), который запускает его бесплатно и навсегда. Чтобы включить:

1. **Settings → Secrets and variables → Actions → New repository secret** и добавь:
   `TELEGRAM_BOT_TOKEN`, `PLAYLIST_ANDREY`, `TELEGRAM_CHANNEL_ANDREY`, `PLAYLIST_BAYBA`, `TELEGRAM_CHANNEL_BAYBA`.
2. Workflow запускается по расписанию (по умолчанию каждые 2 дня в 09:00 UTC), а также вручную из вкладки **Actions**.
3. Состояние опубликованных видео автоматически коммитится обратно в репозиторий — повторных публикаций не будет.

Частоту можно поменять, отредактировав строку `cron` (например, `0 */6 * * *` — каждые 6 часов).

### ⚙️ Настройка

Скопируй `.env.example` в `.env` и заполни значения. **API-ключ YouTube не требуется** — `yt-dlp` читает плейлисты напрямую.

| Переменная | Обязательна | Описание |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | ✅ | Токен бота от [@BotFather](https://t.me/BotFather) |
| `PLAYLIST_ANDREY` | ✅ | ID плейлиста YouTube для канала Андрея |
| `TELEGRAM_CHANNEL_ANDREY` | ✅ | Telegram-канал Андрея (`@channel` или числовой chat ID) |
| `PLAYLIST_BAYBA` | ✅ | ID плейлиста YouTube для канала Байбы |
| `TELEGRAM_CHANNEL_BAYBA` | ✅ | Telegram-канал Байбы (`@channel` или числовой chat ID) |
| `DOWNLOAD_DIR` | ➖ | Куда временно сохраняются MP3 (по умолчанию: `downloads`) |
| `RETRY_ATTEMPTS` | ➖ | Количество попыток при ошибках (по умолчанию: `3`) |
| `RETRY_DELAY` | ➖ | Базовая задержка в секундах между попытками (по умолчанию: `5`) |
| `POST_DELAY` | ➖ | Задержка в секундах между публикациями (по умолчанию: `2`) |
| `LOG_LEVEL` | ➖ | Уровень логирования: `DEBUG`, `INFO`, `WARNING`, `ERROR` (по умолчанию: `INFO`) |
| `LOG_FILE` | ➖ | Путь к файлу логов (по умолчанию: `bot.log`) |

**Как найти ID плейлиста YouTube**

Открой плейлист на YouTube. ID — это параметр `list=` в URL:

```
https://www.youtube.com/playlist?list=PLxxxxxxxxxxxxxxxx
                                       ^^^^^^^^^^^^^^^^
```

**Права бота в канале**

Добавь бота как **Администратора** со следующими правами:
- Публикация сообщений
- Закрепление сообщений

### 📁 Структура проекта

```
space-music-hub/
├── telegram_bot_music_youtube.py   # Основной скрипт бота
├── requirements.txt                # Зависимости Python
├── Dockerfile                      # Описание Docker-образа (ffmpeg внутри)
├── docker-compose.yml              # Конфигурация Docker Compose
├── .env.example                    # Шаблон переменных окружения
├── .gitignore                      # Правила игнорирования Git
├── .github/workflows/bot.yml       # Запуск по расписанию (бесплатно 24/7)
├── tests/                          # Юнит-тесты (pytest)
├── sent_videos_andrey.json         # Состояние — видео канала Андрея (авто)
├── pinned_msgs_andrey.json         # Состояние — ID закреплённого Андрея (авто)
├── sent_videos_bayba.json          # Состояние — видео канала Байбы (авто)
├── pinned_msgs_bayba.json          # Состояние — ID закреплённого Байбы (авто)
├── bot.log                         # Ротируемый файл логов (создаётся авто)
└── README.md
```

### 📦 Зависимости

| Пакет | Версия | Назначение |
|---|---|---|
| `python-telegram-bot` | 21.6 | Клиент Telegram Bot API |
| `yt-dlp` | 2025.1.15 | Чтение плейлиста + скачивание аудио |
| `python-dotenv` | 1.0.1 | Загрузка переменных окружения из `.env` |
| `ffmpeg` | системная | Конвертация аудио → MP3 (используется yt-dlp) |

### 🧪 Тесты

```bash
pip install -r requirements-dev.txt
pytest            # запустить юнит-тесты
ruff check .      # линтер
```

### 📝 Лицензия

MIT — используй и модифицируй свободно.

---

<a id="latviešu"></a>

## 🇱🇻 Latviešu

Telegram bots, kas **lejupielādē reālu MP3 audio** no divu YouTube atskaņošanas sarakstu jaunajiem videoklipiem (izmantojot `yt-dlp` + `ffmpeg`) un publicē tos kā audio failus divos atsevišķos Telegram kanālos, piespraužot jaunāko ierakstu katrā. **YouTube API atslēga nav nepieciešama.**

### ✨ Iespējas

| Funkcija | Apraksts |
|---|---|
| 🎵 Reāls MP3 audio | Lejupielādē katra jaunā video audio ar `yt-dlp` un konvertē uz 192 kbps MP3 ar `ffmpeg`, pēc tam nosūta kā Telegram audio failu |
| 📋 Saraksta izsekošana | Nolasa YouTube sarakstu ar `yt-dlp` (flat režīms) un publicē tikai iepriekš neredzētus videoklipus |
| 📌 Automātiska piespraušana | Atsprauž iepriekšējo ierakstu un automātiski piesprauž jaunāko |
| 🗂 Divi kanāli | Apstrādā divus neatkarīgus saraksts → kanāls pārus vienā palaišanā, katram savs stāvoklis |
| 💾 Stāvokļa saglabāšana | Izseko publicētos videoklipus pa kanāliem `sent_videos_<name>.json` starp palaišanām |
| 🔁 Atkārtošanas loģika | Atkārto neveiksmīgus lejupielādes / Telegram izsaukumus ar eksponenciālu aizkavi (gan sync, gan async) |
| 🧹 Automātiska tīrīšana | Dzēš lejupielādēto MP3 uzreiz pēc veiksmīgas nosūtīšanas — disks netiek piegružots |
| 📝 Strukturēta reģistrēšana | Reģistrē konsolē **un** rotējošā `bot.log` (5 MB × 3) ar INFO/WARNING/ERROR līmeņiem |
| 🐳 Docker gatavs | Komplektā ar `Dockerfile` (ffmpeg iekļauts) un `docker-compose.yml` |
| ⚙️ Pilnībā konfigurējams | Visu uzvedību kontrolē vides mainīgie |
| ☁️ Bezmaksas 24/7 hostings | Darbojas pēc grafika ar GitHub Actions — serveris nav vajadzīgs (skatīt zemāk) |

### 🏗 Arhitektūra

```
┌────────────────────────────────────────────────────────┐
│                  space-music-hub bot                   │
│                                                        │
│  ┌───────────┐   ┌─────────────────────┐               │
│  │  yt-dlp   │──▶│ _get_playlist_videos │  plakans      │
│  │ (saraksts)│   │     (pa kanālam)     │  ID saraksts  │
│  └───────────┘   └──────────┬──────────┘               │
│                             │                          │
│                  ┌──────────▼──────────┐               │
│                  │  Filtrēt jaunos      │               │
│                  │ (sent_videos_*.json) │               │
│                  └──────────┬──────────┘               │
│                             │                          │
│  ┌───────────┐   ┌──────────▼──────────┐               │
│  │  yt-dlp   │──▶│  _download_audio     │  bestaudio    │
│  │ + ffmpeg  │   │  → 192 kbps MP3      │  → MP3 fails  │
│  └───────────┘   └──────────┬──────────┘               │
│                             │                          │
│  ┌───────────┐   ┌──────────▼──────────┐               │
│  │ Telegram  │◀──│  send_audio + pin    │  + retry      │
│  │ Bot API   │   │  + atsprauž veco     │               │
│  └───────────┘   └──────────┬──────────┘               │
│                             │                          │
│                  ┌──────────▼──────────┐               │
│                  │ Saglabāt stāvokli +  │               │
│                  │ dzēst MP3 failu      │               │
│                  └─────────────────────┘               │
└────────────────────────────────────────────────────────┘
```

### 🚀 Ātrā palaišana

> **Svarīgi:** resursdatorā jābūt instalētam `ffmpeg` (Docker attēlā tas jau ir iekļauts).

#### 1. variants — Docker (ieteicams)

```bash
# 1. Klonēt repozitoriju
git clone https://github.com/AAvlasins-dev/Music-from-Youtube-playlist-to-telegram.git
cd Music-from-Youtube-playlist-to-telegram

# 2. Izveidot .env no veidnes
cp .env.example .env
# Aizpildīt mainīgos (skatīt sadaļu Konfigurācija zemāk)

# 3. Palaist vienu reizi
docker compose up --build

# 4. Ieplānot regulāru palaišanu (Linux cron piemērs — ik 6 stundas)
0 */6 * * * docker compose -f /path/to/docker-compose.yml up --build >> /var/log/space-music-hub.log 2>&1
```

#### 2. variants — Lokālais Python

```bash
# 1. Klonēt un atvērt projektu
git clone https://github.com/AAvlasins-dev/Music-from-Youtube-playlist-to-telegram.git
cd Music-from-Youtube-playlist-to-telegram

# 2. Instalēt ffmpeg (sistēmas atkarība)
sudo apt-get install ffmpeg        # Debian/Ubuntu
# brew install ffmpeg              # macOS
# winget install ffmpeg            # Windows

# 3. Izveidot virtuālo vidi
python -m venv .venv
source .venv/bin/activate          # Linux/macOS
.venv\Scripts\activate             # Windows

# 4. Instalēt atkarības
pip install -r requirements.txt

# 5. Konfigurēt vidi
cp .env.example .env
# Rediģēt .env un aizpildīt akreditācijas datus

# 6. Palaist
python telegram_bot_music_youtube.py
```

### ☁️ Bezmaksas 24/7 hostings (GitHub Actions)

Bots ir **partijas uzdevums**: palaižas, publicē jaunos ierakstus un beidz darbu. Repozitorijā jau ir GitHub Actions workflow ([.github/workflows/bot.yml](.github/workflows/bot.yml)), kas to palaiž bez maksas un mūžīgi. Lai ieslēgtu:

1. **Settings → Secrets and variables → Actions → New repository secret** un pievieno:
   `TELEGRAM_BOT_TOKEN`, `PLAYLIST_ANDREY`, `TELEGRAM_CHANNEL_ANDREY`, `PLAYLIST_BAYBA`, `TELEGRAM_CHANNEL_BAYBA`.
2. Workflow darbojas pēc grafika (pēc noklusējuma ik 2 dienas plkst. 09:00 UTC) un arī manuāli no cilnes **Actions**.
3. Publicēto video stāvoklis tiek automātiski iesniegts atpakaļ repozitorijā — atkārtotas publicēšanas nebūs.

Biežumu var mainīt, rediģējot `cron` rindu (piemēram, `0 */6 * * *` — ik 6 stundas).

### ⚙️ Konfigurācija

Kopē `.env.example` uz `.env` un aizpildi vērtības. **YouTube API atslēga nav nepieciešama** — `yt-dlp` nolasa sarakstus tieši.

| Mainīgais | Nepieciešams | Apraksts |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | ✅ | Bota marķieris no [@BotFather](https://t.me/BotFather) |
| `PLAYLIST_ANDREY` | ✅ | YouTube saraksta ID Andreja kanālam |
| `TELEGRAM_CHANNEL_ANDREY` | ✅ | Telegram kanāls Andrejam (`@channel` vai ciparu ID) |
| `PLAYLIST_BAYBA` | ✅ | YouTube saraksta ID Baibas kanālam |
| `TELEGRAM_CHANNEL_BAYBA` | ✅ | Telegram kanāls Baibai (`@channel` vai ciparu ID) |
| `DOWNLOAD_DIR` | ➖ | Kur īslaicīgi glabā MP3 (noklusējums: `downloads`) |
| `RETRY_ATTEMPTS` | ➖ | Atkārtošanas mēģinājumu skaits kļūdu gadījumā (noklusējums: `3`) |
| `RETRY_DELAY` | ➖ | Bāzes aizkave sekundēs starp mēģinājumiem (noklusējums: `5`) |
| `POST_DELAY` | ➖ | Aizkave sekundēs starp secīgām publikācijām (noklusējums: `2`) |
| `LOG_LEVEL` | ➖ | Reģistrēšanas līmenis: `DEBUG`, `INFO`, `WARNING`, `ERROR` (noklusējums: `INFO`) |
| `LOG_FILE` | ➖ | Ceļš uz žurnālfailu (noklusējums: `bot.log`) |

**Kā atrast YouTube saraksta ID**

Atver atskaņošanas sarakstu YouTube. ID ir parametrs `list=` URL adresē:

```
https://www.youtube.com/playlist?list=PLxxxxxxxxxxxxxxxx
                                       ^^^^^^^^^^^^^^^^
```

**Bota tiesības kanālā**

Pievieno botu kā **Administratoru** ar šādām tiesībām:
- Ziņojumu publicēšana
- Ziņojumu piespraušana

### 📁 Projekta struktūra

```
space-music-hub/
├── telegram_bot_music_youtube.py   # Galvenais bota skripts
├── requirements.txt                # Python atkarības
├── Dockerfile                      # Docker attēla definīcija (ffmpeg iekļauts)
├── docker-compose.yml              # Docker Compose konfigurācija
├── .env.example                    # Vides mainīgo veidne
├── .gitignore                      # Git ignorēšanas noteikumi
├── .github/workflows/bot.yml       # Palaišana pēc grafika (bezmaksas 24/7)
├── tests/                          # Vienības testi (pytest)
├── sent_videos_andrey.json         # Stāvoklis — Andreja video (automātiski)
├── pinned_msgs_andrey.json         # Stāvoklis — Andreja piesprausts ID (automātiski)
├── sent_videos_bayba.json          # Stāvoklis — Baibas video (automātiski)
├── pinned_msgs_bayba.json          # Stāvoklis — Baibas piesprausts ID (automātiski)
├── bot.log                         # Rotējošs žurnālfails (izveidots automātiski)
└── README.md
```

### 📦 Atkarības

| Pakotne | Versija | Nolūks |
|---|---|---|
| `python-telegram-bot` | 21.6 | Telegram Bot API klients |
| `yt-dlp` | 2025.1.15 | Saraksta lasīšana + audio lejupielāde |
| `python-dotenv` | 1.0.1 | Vides mainīgo ielāde no `.env` |
| `ffmpeg` | sistēmas | Audio → MP3 konvertācija (izmanto yt-dlp) |

### 🧪 Testi

```bash
pip install -r requirements-dev.txt
pytest            # palaist vienības testus
ruff check .      # linteris
```

### 📝 Licence

MIT — brīvi izmantojiet un modificējiet.
