# 🚀 Space Music Hub

![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)
![python-telegram-bot](https://img.shields.io/badge/python--telegram--bot-21.6-blue?logo=telegram)
![YouTube Data API](https://img.shields.io/badge/YouTube%20Data%20API-v3-red?logo=youtube)
![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker)
![License](https://img.shields.io/badge/License-MIT-green)

---

## 🌐 Select Language · Выберите язык · Izvēlieties valodu

[🇬🇧 English](#english) · [🇷🇺 Русский](#русский) · [🇱🇻 Latviešu](#latviešu)

---

<a id="english"></a>

## 🇬🇧 English

A Telegram bot that automatically publishes new videos from a YouTube playlist to a Telegram channel and pins the latest post.

### ✨ Features

| Feature | Description |
|---|---|
| 🎵 Auto-publishing | Fetches all videos from a YouTube playlist and posts only new ones |
| 📌 Auto-pinning | Unpins the previous post, pins the latest one automatically |
| 💾 State persistence | Tracks posted videos in `sent_videos.json` across runs |
| 🔁 Retry logic | Retries failed YouTube API and Telegram API calls with exponential back-off |
| 📋 Structured logging | Logs to both console and a rotating `bot.log` file with INFO/WARNING/ERROR levels |
| 🐳 Docker-ready | Ships with `Dockerfile` and `docker-compose.yml` for one-command deployment |
| ⚙️ Fully configurable | All behaviour is controlled via environment variables |

### 🏗 Architecture

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

### 🚀 Quick Start

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

### ⚙️ Configuration

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
├── Dockerfile                      # Docker image definition
├── docker-compose.yml              # Docker Compose config
├── .env.example                    # Environment variables template
├── .gitignore                      # Git ignore rules
├── sent_videos.json                # Runtime state — posted videos (auto-created)
├── pinned_msgs.json                # Runtime state — pinned message ID (auto-created)
├── bot.log                         # Rotating log file (auto-created)
└── README.md
```

### 📦 Dependencies

| Package | Version | Purpose |
|---|---|---|
| `python-telegram-bot` | 21.6 | Telegram Bot API client |
| `google-api-python-client` | 2.140.0 | YouTube Data API v3 client |
| `python-dotenv` | 1.0.1 | Load environment variables from `.env` |

### 📝 License

MIT — feel free to use and modify.

---

<a id="русский"></a>

## 🇷🇺 Русский

Telegram-бот, который автоматически публикует новые видео из YouTube-плейлиста в Telegram-канал и закрепляет последнее сообщение.

### ✨ Возможности

| Функция | Описание |
|---|---|
| 🎵 Автопубликация | Получает все видео из YouTube-плейлиста и публикует только новые |
| 📌 Автозакрепление | Открепляет предыдущее сообщение, автоматически закрепляет новое |
| 💾 Сохранение состояния | Отслеживает опубликованные видео в `sent_videos.json` между запусками |
| 🔁 Retry-логика | Повторяет неудачные вызовы YouTube API и Telegram API с экспоненциальной задержкой |
| 📋 Структурированные логи | Пишет логи в консоль и в ротируемый файл `bot.log` с уровнями INFO/WARNING/ERROR |
| 🐳 Docker-ready | Поставляется с `Dockerfile` и `docker-compose.yml` для развёртывания одной командой |
| ⚙️ Полная настройка | Всё поведение управляется через переменные окружения |

### 🏗 Архитектура

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
│                     │  Фильтр новых видео │  │
│                     │  (sent_videos.json) │  │
│                     └─────────┬──────────┘  │
│                               │             │
│  ┌──────────────┐    ┌────────▼──────────┐  │
│  │ Telegram API │◀───│  post_new_videos() │  │
│  │  (Bot API)   │    │  + retry-логика    │  │
│  └──────────────┘    └─────────┬──────────┘ │
│                               │             │
│                     ┌─────────▼──────────┐  │
│                     │  Сохранение +       │  │
│                     │  закрепление поста  │  │
│                     └────────────────────┘  │
└─────────────────────────────────────────────┘
```

### 🚀 Быстрый старт

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

# 2. Создать виртуальное окружение
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
.venv\Scripts\activate           # Windows

# 3. Установить зависимости
pip install -r requirements.txt

# 4. Настроить окружение
cp .env.example .env
# Отредактировать .env и заполнить данные

# 5. Запустить
python telegram_bot_music_youtube.py
```

### ⚙️ Настройка

Скопируй `.env.example` в `.env` и заполни значения:

| Переменная | Обязательна | Описание |
|---|---|---|
| `TELEGRAM_TOKEN` | ✅ | Токен бота от [@BotFather](https://t.me/BotFather) |
| `CHANNEL_ID` | ✅ | Юзернейм канала (`@channel`) или числовой chat ID |
| `YOUTUBE_API_KEY` | ✅ | API-ключ из [Google Cloud Console](https://console.cloud.google.com/) |
| `YOUTUBE_PLAYLIST_ID` | ✅ | ID плейлиста YouTube (из URL плейлиста) |
| `RETRY_ATTEMPTS` | ➖ | Количество попыток при ошибках API (по умолчанию: `3`) |
| `RETRY_DELAY` | ➖ | Базовая задержка в секундах между попытками (по умолчанию: `5`) |
| `POST_DELAY` | ➖ | Задержка в секундах между публикациями (по умолчанию: `1`) |
| `LOG_LEVEL` | ➖ | Уровень логирования: `DEBUG`, `INFO`, `WARNING`, `ERROR` (по умолчанию: `INFO`) |
| `LOG_FILE` | ➖ | Путь к файлу логов (по умолчанию: `bot.log`) |
| `SENT_VIDEOS_FILE` | ➖ | Путь к файлу состояния отправленных видео (по умолчанию: `sent_videos.json`) |
| `PINNED_MSGS_FILE` | ➖ | Путь к файлу состояния закреплённых сообщений (по умолчанию: `pinned_msgs.json`) |

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
├── Dockerfile                      # Описание Docker-образа
├── docker-compose.yml              # Конфигурация Docker Compose
├── .env.example                    # Шаблон переменных окружения
├── .gitignore                      # Правила игнорирования Git
├── sent_videos.json                # Состояние — опубликованные видео (создаётся автоматически)
├── pinned_msgs.json                # Состояние — ID закреплённого сообщения (создаётся автоматически)
├── bot.log                         # Ротируемый файл логов (создаётся автоматически)
└── README.md
```

### 📦 Зависимости

| Пакет | Версия | Назначение |
|---|---|---|
| `python-telegram-bot` | 21.6 | Клиент Telegram Bot API |
| `google-api-python-client` | 2.140.0 | Клиент YouTube Data API v3 |
| `python-dotenv` | 1.0.1 | Загрузка переменных окружения из `.env` |

### 📝 Лицензия

MIT — используй и модифицируй свободно.

---

<a id="latviešu"></a>

## 🇱🇻 Latviešu

Telegram bots, kas automātiski publicē jaunus videoklipus no YouTube atskaņošanas saraksta Telegram kanālā un piesprauž jaunāko ziņojumu.

### ✨ Iespējas

| Funkcija | Apraksts |
|---|---|
| 🎵 Automātiska publicēšana | Iegūst visus videoklipus no YouTube atskaņošanas saraksta un publicē tikai jaunos |
| 📌 Automātiska piespraušana | Atsprauž iepriekšējo ziņojumu, automātiski piesprauž jaunāko |
| 💾 Stāvokļa saglabāšana | Izseko publicētos videoklipus `sent_videos.json` starp palaišanas reizēm |
| 🔁 Atkārtošanas loģika | Atkārto neveiksmīgus YouTube API un Telegram API izsaukumus ar eksponenciālu aizkavi |
| 📋 Strukturēta reģistrēšana | Reģistrē gan konsolē, gan rotējošā `bot.log` failā ar INFO/WARNING/ERROR līmeņiem |
| 🐳 Docker gatavs | Komplektā ar `Dockerfile` un `docker-compose.yml` vienkomandas izvietošanai |
| ⚙️ Pilnībā konfigurējams | Visu uzvedību kontrolē vides mainīgie |

### 🏗 Arhitektūra

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
│                     │  Filtrēt jaunos     │  │
│                     │  (sent_videos.json) │  │
│                     └─────────┬──────────┘  │
│                               │             │
│  ┌──────────────┐    ┌────────▼──────────┐  │
│  │ Telegram API │◀───│  post_new_videos() │  │
│  │  (Bot API)   │    │  + atkārt. loģika  │  │
│  └──────────────┘    └─────────┬──────────┘ │
│                               │             │
│                     ┌─────────▼──────────┐  │
│                     │  Saglabāt stāvokli +│  │
│                     │  piespraust ziņojum │  │
│                     └────────────────────┘  │
└─────────────────────────────────────────────┘
```

### 🚀 Ātrā palaišana

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

# 2. Izveidot virtuālo vidi
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
.venv\Scripts\activate           # Windows

# 3. Instalēt atkarības
pip install -r requirements.txt

# 4. Konfigurēt vidi
cp .env.example .env
# Rediģēt .env un aizpildīt akreditācijas datus

# 5. Palaist
python telegram_bot_music_youtube.py
```

### ⚙️ Konfigurācija

Kopē `.env.example` uz `.env` un aizpildi vērtības:

| Mainīgais | Nepieciešams | Apraksts |
|---|---|---|
| `TELEGRAM_TOKEN` | ✅ | Bota marķieris no [@BotFather](https://t.me/BotFather) |
| `CHANNEL_ID` | ✅ | Kanāla lietotājvārds (`@channel`) vai ciparu tērzēšanas ID |
| `YOUTUBE_API_KEY` | ✅ | API atslēga no [Google Cloud Console](https://console.cloud.google.com/) |
| `YOUTUBE_PLAYLIST_ID` | ✅ | YouTube atskaņošanas saraksta ID (no saraksta URL) |
| `RETRY_ATTEMPTS` | ➖ | Atkārtošanas mēģinājumu skaits API kļūdu gadījumā (noklusējums: `3`) |
| `RETRY_DELAY` | ➖ | Bāzes aizkave sekundēs starp mēģinājumiem (noklusējums: `5`) |
| `POST_DELAY` | ➖ | Aizkave sekundēs starp secīgām publikācijām (noklusējums: `1`) |
| `LOG_LEVEL` | ➖ | Reģistrēšanas līmenis: `DEBUG`, `INFO`, `WARNING`, `ERROR` (noklusējums: `INFO`) |
| `LOG_FILE` | ➖ | Ceļš uz žurnālfailu (noklusējums: `bot.log`) |
| `SENT_VIDEOS_FILE` | ➖ | Ceļš uz nosūtīto videoklipu stāvokļa failu (noklusējums: `sent_videos.json`) |
| `PINNED_MSGS_FILE` | ➖ | Ceļš uz piesprausto ziņojumu stāvokļa failu (noklusējums: `pinned_msgs.json`) |

**Kā atrast YouTube atskaņošanas saraksta ID**

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
├── Dockerfile                      # Docker attēla definīcija
├── docker-compose.yml              # Docker Compose konfigurācija
├── .env.example                    # Vides mainīgo veidne
├── .gitignore                      # Git ignorēšanas noteikumi
├── sent_videos.json                # Stāvoklis — publicētie videoklipi (izveidots automātiski)
├── pinned_msgs.json                # Stāvoklis — piesprausto ziņojumu ID (izveidots automātiski)
├── bot.log                         # Rotējošs žurnālfails (izveidots automātiski)
└── README.md
```

### 📦 Atkarības

| Pakotne | Versija | Nolūks |
|---|---|---|
| `python-telegram-bot` | 21.6 | Telegram Bot API klients |
| `google-api-python-client` | 2.140.0 | YouTube Data API v3 klients |
| `python-dotenv` | 1.0.1 | Vides mainīgo ielāde no `.env` |

### 📝 Licence

MIT — brīvi izmantojiet un modificējiet.
