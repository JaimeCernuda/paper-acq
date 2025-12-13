"""Configuration management for Paper PDF Retriever."""

from pathlib import Path
from dataclasses import dataclass, field
from typing import Any
import os

import yaml


@dataclass
class Config:
    """Configuration for the paper retriever."""

    email: str = ""
    api_keys: dict[str, str | None] = field(default_factory=dict)
    institutional: dict[str, Any] = field(default_factory=dict)
    sources: dict[str, dict[str, Any]] = field(default_factory=dict)
    unofficial: dict[str, Any] = field(default_factory=dict)
    download: dict[str, Any] = field(default_factory=dict)
    rate_limits: dict[str, Any] = field(default_factory=dict)
    batch: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, config_path: str | Path = "config.yaml") -> "Config":
        """Load configuration from file and environment variables."""
        config_file = Path(config_path)

        if config_file.exists():
            with open(config_file) as f:
                data = yaml.safe_load(f) or {}
        else:
            data = {}

        # Extract user info
        user_data = data.get("user", {})
        email = os.getenv("PAPER_RETRIEVER_EMAIL", user_data.get("email", ""))

        # API keys with environment variable overrides
        api_keys = data.get("api_keys", {})
        api_keys["ncbi"] = os.getenv("NCBI_API_KEY", api_keys.get("ncbi"))
        api_keys["semantic_scholar"] = os.getenv(
            "SEMANTIC_SCHOLAR_API_KEY", api_keys.get("semantic_scholar")
        )
        api_keys["crossref_plus"] = os.getenv(
            "CROSSREF_PLUS_API_KEY", api_keys.get("crossref_plus")
        )

        # Default source configuration
        default_sources = {
            "unpaywall": {"enabled": True, "priority": 1},
            "arxiv": {"enabled": True, "priority": 2},
            "pmc": {"enabled": True, "priority": 3},
            "biorxiv": {"enabled": True, "priority": 4},
            "semantic_scholar": {"enabled": True, "priority": 5},
            "institutional": {"enabled": False, "priority": 6},
            "scihub": {"enabled": False, "priority": 7},
            "libgen": {"enabled": False, "priority": 8},
            "web_search": {"enabled": True, "priority": 9},
        }
        sources = data.get("sources", {})
        for source, defaults in default_sources.items():
            if source not in sources:
                sources[source] = defaults
            else:
                # Merge with defaults
                for key, value in defaults.items():
                    if key not in sources[source]:
                        sources[source][key] = value

        # Default download configuration
        default_download = {
            "output_dir": "./downloads",
            "filename_format": "{first_author}_{year}_{title_short}.pdf",
            "max_title_length": 50,
            "create_subfolders": False,
            "skip_existing": True,
        }
        download = data.get("download", {})
        for key, value in default_download.items():
            if key not in download:
                download[key] = value

        # Default rate limits
        default_rate_limits = {
            "global_delay": 1.0,
            "per_source_delays": {
                "crossref": 0.5,
                "unpaywall": 0.1,
                "arxiv": 3.0,
                "pmc": 0.34,
                "semantic_scholar": 3.0,
                "biorxiv": 1.0,
            },
        }
        rate_limits = data.get("rate_limits", {})
        for key, value in default_rate_limits.items():
            if key not in rate_limits:
                rate_limits[key] = value

        # Default batch configuration
        default_batch = {
            "max_concurrent": 3,
            "retry_failed": True,
            "max_retries": 2,
            "save_progress": True,
            "progress_file": ".retrieval_progress.json",
        }
        batch = data.get("batch", {})
        for key, value in default_batch.items():
            if key not in batch:
                batch[key] = value

        # Default institutional configuration
        default_institutional = {
            "enabled": False,
            "vpn_enabled": False,
            "vpn_script": None,  # Script to run for VPN connection
            "vpn_disconnect_script": None,  # Script to run for VPN disconnect
            "proxy_url": None,  # e.g., "https://ezproxy.gl.iit.edu/login?url="
            "cookies_file": ".institutional_cookies.pkl",
            "university": None,
        }
        institutional = data.get("institutional", {})
        for key, value in default_institutional.items():
            if key not in institutional:
                institutional[key] = value

        return cls(
            email=email,
            api_keys=api_keys,
            institutional=institutional,
            sources=sources,
            unofficial=data.get("unofficial", {}),
            download=download,
            rate_limits=rate_limits,
            batch=batch,
        )

    def is_unofficial_enabled(self) -> bool:
        """Check if unofficial sources are enabled with disclaimer."""
        return self.unofficial.get("disclaimer_accepted", False)

    def get_source_delay(self, source: str) -> float:
        """Get the rate limit delay for a specific source."""
        per_source = self.rate_limits.get("per_source_delays", {})
        return per_source.get(source, self.rate_limits.get("global_delay", 1.0))

    def is_source_enabled(self, source: str) -> bool:
        """Check if a source is enabled."""
        source_config = self.sources.get(source, {})
        return source_config.get("enabled", False)

    def get_sorted_sources(self) -> list[str]:
        """Get sources sorted by priority."""
        sources = []
        for name, config in self.sources.items():
            if config.get("enabled", False):
                sources.append((name, config.get("priority", 99)))
        return [name for name, _ in sorted(sources, key=lambda x: x[1])]
