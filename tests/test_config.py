"""Tests for configuration management."""

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from paper_retriever.config import Config


def test_load_default_config():
    """Test loading config with defaults when no file exists."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = Config.load(Path(tmpdir) / "nonexistent.yaml")

        assert config.email == ""
        assert config.sources["unpaywall"]["enabled"] is True
        assert config.sources["unpaywall"]["priority"] == 1
        assert config.download["output_dir"] == "./downloads"
        assert config.download["skip_existing"] is True


def test_load_config_from_file():
    """Test loading config from a YAML file."""
    config_data = {
        "user": {"email": "test@example.com"},
        "sources": {
            "unpaywall": {"enabled": True, "priority": 1},
            "arxiv": {"enabled": False, "priority": 2},
        },
        "download": {"output_dir": "/custom/path"},
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(config_data, f)
        f.flush()

        config = Config.load(f.name)

        assert config.email == "test@example.com"
        assert config.sources["unpaywall"]["enabled"] is True
        assert config.sources["arxiv"]["enabled"] is False
        assert config.download["output_dir"] == "/custom/path"

        os.unlink(f.name)


def test_environment_variable_override():
    """Test that environment variables override file config."""
    os.environ["PAPER_RETRIEVER_EMAIL"] = "env@example.com"

    try:
        config = Config.load("nonexistent.yaml")
        assert config.email == "env@example.com"
    finally:
        del os.environ["PAPER_RETRIEVER_EMAIL"]


def test_get_sorted_sources():
    """Test getting sources sorted by priority."""
    config_data = {
        "user": {"email": "test@example.com"},
        "sources": {
            "unpaywall": {"enabled": True, "priority": 2},
            "arxiv": {"enabled": True, "priority": 1},
            "pmc": {"enabled": False, "priority": 3},
        },
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(config_data, f)
        f.flush()

        config = Config.load(f.name)
        sorted_sources = config.get_sorted_sources()

        # Only enabled sources should be returned
        assert "arxiv" in sorted_sources
        assert "unpaywall" in sorted_sources
        assert "pmc" not in sorted_sources

        # Should be sorted by priority
        assert sorted_sources.index("arxiv") < sorted_sources.index("unpaywall")

        os.unlink(f.name)


def test_is_source_enabled():
    """Test checking if a source is enabled."""
    config_data = {
        "user": {"email": "test@example.com"},
        "sources": {
            "unpaywall": {"enabled": True, "priority": 1},
            "arxiv": {"enabled": False, "priority": 2},
        },
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(config_data, f)
        f.flush()

        config = Config.load(f.name)

        assert config.is_source_enabled("unpaywall") is True
        assert config.is_source_enabled("arxiv") is False

        os.unlink(f.name)


def test_is_unofficial_enabled():
    """Test checking if unofficial sources are enabled."""
    config = Config.load("nonexistent.yaml")
    assert config.is_unofficial_enabled() is False

    config.unofficial = {"disclaimer_accepted": True}
    assert config.is_unofficial_enabled() is True
