import os

from app.config import get_settings


def test_debug_accepts_release_value(monkeypatch):
    monkeypatch.setenv("DEBUG", "release")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.DEBUG is False
    get_settings.cache_clear()


def test_debug_accepts_development_value(monkeypatch):
    monkeypatch.setenv("DEBUG", "development")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.DEBUG is True
    get_settings.cache_clear()
