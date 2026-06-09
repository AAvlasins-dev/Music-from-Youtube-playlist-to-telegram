# 🔁 Передача проекта (для новой сессии Claude)

> Открой этот файл первым в новом чате: скажи Claude **«прочитай HANDOFF.md»**.

## Что это за проект
**Space Music Hub** — Telegram-бот + Windows-приложение, которое зеркалит плейлисты
YouTube в Telegram-каналы как MP3. Плюс сайт-презентация на GitHub Pages.

- Репозиторий: https://github.com/AAvlasins-dev/Music-from-Youtube-playlist-to-telegram
- Ветка по умолчанию: `master` (есть ещё `v1-classic` — старая версия)
- Живой сайт: https://aavlasins-dev.github.io/Music-from-Youtube-playlist-to-telegram/

## 🎯 ТЕКУЩАЯ ЗАДАЧА
**Полностью изменить визуал сайта** (`docs/index.html`). Текущий дизайн — тёмный
с оранжевым акцентом, карточки, эквалайзер. Нужен новый облик (обсудить какой).

## Где сайт и как он устроен
- Весь сайт — **один файл**: `docs/index.html` (HTML + CSS + JS внутри, без сборки).
- Картинки/медиа в `docs/`:
  - `docs/logo.png` — логотип Chrono Warden
  - `docs/song.mp3` — песня «Neon Ghosts in a Paper Town» (для плеера)
- Языки: переключатель **EN / LV / RU**, переводы в JS-объекте `I18N` внутри файла,
  тексты помечены атрибутами `data-i18n` / `data-i18n-html`.
- Плеер снизу: play/pause, перемотка (`#seek`), скачивание (`.dl-btn`),
  аудио-эквалайзер на Web Audio (`#viz`).
- Подпись разработчика в подвале: **Chrono Warden** (github.com/AAvlasins-dev).
- Кредит песни: «original concept by Chrono Warden, AI-generated in the style of
  Depeche Mode» (на 3 языках, ключ `footer.song`).

## Как смотреть и публиковать сайт
1. Локальный предпросмотр: открыть `docs/index.html` в браузере.
2. Публикация: `git add docs/index.html && git commit -m "..." && git push`.
   GitHub Pages (Source = master /docs) пересоберёт сайт сам за 1-2 мин.

## Важные факты по боту (если понадобится)
- Главный скрипт: `telegram_bot_music_youtube.py` (версия 1.6.0).
- 55 тестов (`tests/test_bot.py`), линтер ruff — CI зелёный.
- `.exe` собирается через `build_exe.bat` (PyInstaller). Готовый пакет лежит в
  `..\SpaceMusicHub-Готовое\` (рядом с папкой проекта).
- yt-dlp пин: `>=2025.1.15`; ffmpeg-downloader: `>=0.3.0` (важно — НЕ ставить
  несуществующие версии, иначе CI краснеет).
- Деплой реальной работы бота — локально (GitHub Actions блокируется YouTube).

## Как продолжить в новом чате
1. Открой Claude Code **в этой же папке**:
   `C:\Users\СтражВремени\Desktop\СКРИПТЫ\Музыка с Yotube плейлиста`
2. Скажи: «прочитай HANDOFF.md, хочу полностью переделать визуал сайта в стиле …»
3. Все файлы, git-история и доступ к GitHub уже на месте — продолжаем сразу.
