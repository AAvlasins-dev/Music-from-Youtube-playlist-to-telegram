"""Unit tests for the Space Music Hub bot.

These cover the pure, side-effect-free building blocks:
  - JSON state I/O
  - Video filtering
  - ChannelConfig helpers
  - RunResult helpers
  - The retry decorator (sync + async)
  - Config validation

Network and Telegram calls are intentionally not exercised here.
"""

from __future__ import annotations

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
class TestJsonHelpers:
    def test_load_missing_returns_empty(self, tmp_path):
        assert bot.load_json(str(tmp_path / "does_not_exist.json")) == {}

    def test_save_and_load_roundtrip(self, tmp_path):
        path = str(tmp_path / "state.json")
        data = {"abc123": {"title": "Зной — трек", "message_id": 42}}
        bot.save_json(path, data)
        assert bot.load_json(path) == data

    def test_unicode_preserved(self, tmp_path):
        path = str(tmp_path / "unicode.json")
        data = {"id": {"title": "Привет мир 🎵"}}
        bot.save_json(path, data)
        loaded = bot.load_json(path)
        assert loaded["id"]["title"] == "Привет мир 🎵"


# --------------------------------------------------------------------------- #
# Video filtering
# --------------------------------------------------------------------------- #
class TestFilterNewVideos:
    def test_keeps_unseen(self):
        videos = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
        sent = {"b": {"title": "x"}}
        assert [v["id"] for v in bot.filter_new_videos(videos, sent)] == ["a", "c"]

    def test_all_seen_returns_empty(self):
        videos = [{"id": "a"}, {"id": "b"}]
        sent = {"a": {}, "b": {}}
        assert bot.filter_new_videos(videos, sent) == []

    def test_empty_state_returns_all(self):
        videos = [{"id": "a"}]
        assert bot.filter_new_videos(videos, {}) == videos

    def test_empty_playlist_returns_empty(self):
        assert bot.filter_new_videos([], {"a": {}}) == []

    def test_preserves_order(self):
        videos = [{"id": "c"}, {"id": "a"}, {"id": "b"}]
        result = bot.filter_new_videos(videos, {"a": {}})
        assert [v["id"] for v in result] == ["c", "b"]


# --------------------------------------------------------------------------- #
# ChannelConfig
# --------------------------------------------------------------------------- #
class TestChannelConfig:
    def _make(self, channel_id: str) -> bot.ChannelConfig:
        return bot.ChannelConfig(
            name="test",
            playlist_id="PL123",
            channel_id=channel_id,
            sent_videos_file="sent.json",
            pinned_msgs_file="pinned.json",
        )

    def test_normalise_without_at(self):
        cfg = self._make("my_channel")
        assert cfg.normalised_channel_id == "@my_channel"

    def test_normalise_with_at(self):
        cfg = self._make("@my_channel")
        assert cfg.normalised_channel_id == "@my_channel"

    def test_normalise_strips_whitespace(self):
        cfg = self._make("  my_channel  ")
        assert cfg.normalised_channel_id == "@my_channel"

    def test_normalise_double_at_not_added(self):
        cfg = self._make("@@oops")
        # only adds @ if not already present — @@ is left as-is (user mistake)
        assert cfg.normalised_channel_id == "@@oops"


# --------------------------------------------------------------------------- #
# RunResult
# --------------------------------------------------------------------------- #
class TestRunResult:
    def test_success_rate_all_posted(self):
        r = bot.RunResult(channel="x", posted=5, failed=0, total_new=5)
        assert r.success_rate == 1.0

    def test_success_rate_partial(self):
        r = bot.RunResult(channel="x", posted=3, failed=2, total_new=5)
        assert r.success_rate == pytest.approx(0.6)

    def test_success_rate_no_new_videos(self):
        r = bot.RunResult(channel="x", posted=0, failed=0, total_new=0)
        assert r.success_rate == 1.0

    def test_str_no_failures(self):
        r = bot.RunResult(channel="andrey", posted=5, failed=0, total_new=5)
        assert "✅" in str(r)
        assert "failed" not in str(r)

    def test_str_with_failures(self):
        r = bot.RunResult(channel="andrey", posted=3, failed=2, total_new=5)
        assert "⚠️" in str(r)
        assert "failed" in str(r)


# --------------------------------------------------------------------------- #
# Retry decorator — sync
# --------------------------------------------------------------------------- #
class TestRetrySync:
    def test_succeeds_after_failures(self):
        calls = {"n": 0}

        @bot.with_retry(attempts=3, delay=0)
        def flaky():
            calls["n"] += 1
            if calls["n"] < 3:
                raise ValueError("boom")
            return "ok"

        assert flaky() == "ok"
        assert calls["n"] == 3

    def test_exhausts_and_reraises(self):
        calls = {"n": 0}

        @bot.with_retry(attempts=2, delay=0)
        def always_fails():
            calls["n"] += 1
            raise RuntimeError("nope")

        with pytest.raises(RuntimeError):
            always_fails()
        assert calls["n"] == 2

    def test_succeeds_first_try(self):
        @bot.with_retry(attempts=3, delay=0)
        def works():
            return 42

        assert works() == 42


# --------------------------------------------------------------------------- #
# Retry decorator — async
# --------------------------------------------------------------------------- #
class TestRetryAsync:
    def test_succeeds_after_failures(self):
        calls = {"n": 0}

        @bot.with_retry(attempts=3, delay=0)
        async def flaky():
            calls["n"] += 1
            if calls["n"] < 2:
                raise ValueError("boom")
            return "ok"

        assert asyncio.run(flaky()) == "ok"
        assert calls["n"] == 2

    def test_exhausts_and_reraises(self):
        @bot.with_retry(attempts=2, delay=0)
        async def always_fails():
            raise RuntimeError("nope")

        with pytest.raises(RuntimeError):
            asyncio.run(always_fails())


# --------------------------------------------------------------------------- #
# Config validation
# --------------------------------------------------------------------------- #
class TestValidateConfig:
    def test_raises_when_missing(self, monkeypatch):
        for var in REQUIRED_ENV:
            monkeypatch.delenv(var, raising=False)
        with pytest.raises(EnvironmentError):
            bot._validate_config()

    def test_passes_when_present(self, monkeypatch):
        for var in REQUIRED_ENV:
            monkeypatch.setenv(var, "dummy")
        bot._validate_config()  # must not raise

    def test_error_message_lists_missing_vars(self, monkeypatch):
        for var in REQUIRED_ENV:
            monkeypatch.delenv(var, raising=False)
        with pytest.raises(EnvironmentError, match="TELEGRAM_BOT_TOKEN"):
            bot._validate_config()
