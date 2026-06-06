"""Unit tests for the Space Music Hub bot.

These cover the pure, side-effect-free building blocks: JSON state I/O,
new-video filtering, the retry decorator (sync + async), and config validation.
Network/Telegram calls are intentionally not exercised here.
"""

import asyncio

import pytest

import telegram_bot_music_youtube as bot

REQUIRED_ENV = (
    "TELEGRAM_BOT_TOKEN",
    "PLAYLIST_ANDREY",
    "TELEGRAM_CHANNEL_ANDREY",
    "PLAYLIST_BAYBA",
    "TELEGRAM_CHANNEL_BAYBA",
)


# --------------------------------------------------------------------------- #
# JSON state helpers
# --------------------------------------------------------------------------- #
def test_load_json_missing_returns_empty(tmp_path):
    assert bot.load_json(str(tmp_path / "does_not_exist.json")) == {}


def test_save_and_load_roundtrip(tmp_path):
    path = str(tmp_path / "state.json")
    data = {"abc123": {"title": "Зной — трек", "message_id": 42}}
    bot.save_json(path, data)
    assert bot.load_json(path) == data


# --------------------------------------------------------------------------- #
# New-video filtering
# --------------------------------------------------------------------------- #
def test_filter_new_videos_keeps_unseen():
    videos = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
    sent = {"b": {"title": "x"}}
    assert [v["id"] for v in bot.filter_new_videos(videos, sent)] == ["a", "c"]


def test_filter_new_videos_all_seen():
    videos = [{"id": "a"}, {"id": "b"}]
    sent = {"a": {}, "b": {}}
    assert bot.filter_new_videos(videos, sent) == []


def test_filter_new_videos_empty_state():
    videos = [{"id": "a"}]
    assert bot.filter_new_videos(videos, {}) == videos


# --------------------------------------------------------------------------- #
# Retry decorator — sync
# --------------------------------------------------------------------------- #
def test_with_retry_sync_succeeds_after_failures():
    calls = {"n": 0}

    @bot.with_retry(attempts=3, delay=0)
    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise ValueError("boom")
        return "ok"

    assert flaky() == "ok"
    assert calls["n"] == 3


def test_with_retry_sync_exhausts_and_reraises():
    calls = {"n": 0}

    @bot.with_retry(attempts=2, delay=0)
    def always_fails():
        calls["n"] += 1
        raise RuntimeError("nope")

    with pytest.raises(RuntimeError):
        always_fails()
    assert calls["n"] == 2


# --------------------------------------------------------------------------- #
# Retry decorator — async
# --------------------------------------------------------------------------- #
def test_with_retry_async_succeeds_after_failures():
    calls = {"n": 0}

    @bot.with_retry(attempts=3, delay=0)
    async def flaky():
        calls["n"] += 1
        if calls["n"] < 2:
            raise ValueError("boom")
        return "ok"

    assert asyncio.run(flaky()) == "ok"
    assert calls["n"] == 2


def test_with_retry_async_exhausts_and_reraises():
    @bot.with_retry(attempts=2, delay=0)
    async def always_fails():
        raise RuntimeError("nope")

    with pytest.raises(RuntimeError):
        asyncio.run(always_fails())


# --------------------------------------------------------------------------- #
# Config validation
# --------------------------------------------------------------------------- #
def test_validate_config_raises_when_missing(monkeypatch):
    for var in REQUIRED_ENV:
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(EnvironmentError):
        bot._validate_config()


def test_validate_config_passes_when_present(monkeypatch):
    for var in REQUIRED_ENV:
        monkeypatch.setenv(var, "dummy")
    bot._validate_config()  # must not raise
