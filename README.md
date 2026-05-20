# space-music-hub

Telegram-бот, который автоматически публикует новые видео из YouTube-плейлиста в Telegram-канал и закрепляет последнее сообщение.

## Возможности

- Получает список видео из YouTube-плейлиста через YouTube Data API v3
- Публикует только новые видео (уже отправленные сохраняются в `sent_videos.json`)
- Автоматически открепляет предыдущее сообщение и закрепляет новое
- Хранит ID закреплённых сообщений в `pinned_msgs.json`

## Установка

```bash
pip install python-telegram-bot google-api-python-client python-dotenv
```

## Настройка

1. Скопируй `.env.example` в `.env` и заполни переменные:

```bash
cp .env.example .env
```

2. Получи токен бота у [@BotFather](https://t.me/BotFather).
3. Создай YouTube API ключ в [Google Cloud Console](https://console.cloud.google.com/).
4. Добавь бота администратором канала с правом публикации и закрепления сообщений.

## Запуск

```bash
python telegram_bot_music_youtube.py
```

Для автоматического запуска по расписанию используй cron (Linux/macOS) или Планировщик задач (Windows):

```cron
0 */6 * * * /usr/bin/python3 /path/to/telegram_bot_music_youtube.py
```

## Структура файлов

| Файл | Описание |
|------|----------|
| `telegram_bot_music_youtube.py` | Основной скрипт бота |
| `sent_videos.json` | Кэш уже отправленных видео |
| `pinned_msgs.json` | ID последнего закреплённого сообщения |
| `.env` | Секретные переменные окружения (не коммитить) |
