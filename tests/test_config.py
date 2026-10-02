"""Unit tests for Gemini Nexus core configuration."""

from gemini_nexus.core.config import (
    APP_NAME,
    APP_VERSION,
    AUTHOR,
    DEFAULT_DB_FILE,
    DEFAULT_MODELS,
    STATUS_COLORS,
    STATUS_RU,
)


def test_config_constants():
    """Verify application identity and core constants."""
    assert "Gemini Nexus" in APP_NAME
    assert APP_VERSION == "14.0.0"
    assert AUTHOR == "NeuroStarNet"
    assert DEFAULT_DB_FILE == "gemini_keys.db"


def test_default_models():
    """Verify default Gemini 3.x models list."""
    assert isinstance(DEFAULT_MODELS, list)
    assert len(DEFAULT_MODELS) > 0
    assert "gemini-3.8-flash" in DEFAULT_MODELS
    assert "gemini-3.8-flash-high" in DEFAULT_MODELS
    assert "gemini-3.7-flash" in DEFAULT_MODELS


def test_status_mappings():
    """Verify status dictionaries and localization."""
    assert "OK" in STATUS_RU
    assert STATUS_RU["OK"] == "Работает"
    assert "UNCHECKED" in STATUS_RU

    assert "OK" in STATUS_COLORS
    assert STATUS_COLORS["OK"] == "#2ecc71"
    # Every status in STATUS_RU should have a corresponding color
    for status in STATUS_RU:
        assert status in STATUS_COLORS
