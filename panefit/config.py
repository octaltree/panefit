"""
Panefit configuration management.

Configuration priority (highest to lowest):
1. CLI arguments (--strategy, etc.)
2. Config file (~/.config/panefit/config.json or platform-specific)
3. Environment variables (PANEFIT_*)
4. Default values (zero-config)

Handles loading, saving, and defaults for CLI settings.
"""

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

import platformdirs


@dataclass
class LLMConfig:
    """LLM integration settings."""

    enabled: bool = False
    provider: str = "auto"  # auto, gemini, openai, anthropic, ollama
    gemini_api_key: str = ""  # Gemini API key
    gemini_model: str = "gemini-2.0-flash"  # Free tier model
    openai_model: str = "gpt-4o-mini"
    anthropic_model: str = "claude-3-haiku-20240307"
    ollama_model: str = "llama3.2"
    ollama_host: str = "http://localhost:11434"
    blend_ratio: float = 0.4  # LLM weight when blending scores


@dataclass
class LayoutConfig:
    """Layout calculation settings."""

    strategy: str = "balanced"  # balanced, importance, entropy, activity, related
    layout_type: str = "auto"  # auto, horizontal, vertical, tiled
    min_width: int = 20
    min_height: int = 5


@dataclass
class SessionConfig:
    """Cross-window session settings."""

    enabled: bool = True
    relevance_threshold: float = 0.3
    importance_threshold: float = 0.2
    auto_park: bool = False
    park_window_name: str = "parked"


@dataclass
class PanefitConfig:
    """Main configuration container."""

    llm: LLMConfig = field(default_factory=LLMConfig)
    layout: LayoutConfig = field(default_factory=LayoutConfig)
    session: SessionConfig = field(default_factory=SessionConfig)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "llm": asdict(self.llm),
            "layout": asdict(self.layout),
            "session": asdict(self.session),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PanefitConfig":
        """Create from dictionary."""
        return cls(
            llm=LLMConfig(**data.get("llm", {})),
            layout=LayoutConfig(**data.get("layout", {})),
            session=SessionConfig(**data.get("session", {})),
        )

    def apply_env_overrides(self) -> "PanefitConfig":
        """
        Apply environment variable overrides.

        Environment variables (set by tmux plugin or shell):
            PANEFIT_LLM_ENABLED - true/false
            PANEFIT_LLM_PROVIDER - auto/openai/anthropic/ollama
            PANEFIT_STRATEGY - balanced/importance/entropy/activity
            PANEFIT_LAYOUT_TYPE - auto/horizontal/vertical/tiled
        """
        # LLM overrides
        if os.environ.get("PANEFIT_LLM_ENABLED"):
            self.llm.enabled = os.environ["PANEFIT_LLM_ENABLED"].lower() == "true"
        if os.environ.get("PANEFIT_LLM_PROVIDER"):
            self.llm.provider = os.environ["PANEFIT_LLM_PROVIDER"]

        # Layout overrides
        if os.environ.get("PANEFIT_STRATEGY"):
            self.layout.strategy = os.environ["PANEFIT_STRATEGY"]
        if os.environ.get("PANEFIT_LAYOUT_TYPE"):
            self.layout.layout_type = os.environ["PANEFIT_LAYOUT_TYPE"]

        return self


def get_config_dir() -> Path:
    """
    Get platform-specific user config directory.

    Returns:
        - Linux: ~/.config/panefit (or $XDG_CONFIG_HOME/panefit)
        - macOS: ~/Library/Application Support/panefit (or ~/.config/panefit if XDG_CONFIG_HOME set)
        - Windows: C:\\Users\\<user>\\AppData\\Roaming\\panefit
    """
    return Path(platformdirs.user_config_dir("panefit", appauthor=False))


def get_config_path() -> Path:
    """Get configuration file path."""
    return get_config_dir() / "config.json"


def load_config(path: Optional[Path] = None, apply_env: bool = True) -> PanefitConfig:
    """
    Load configuration from file.

    Args:
        path: Config file path. Uses default if None.
        apply_env: Apply environment variable overrides.

    Returns:
        PanefitConfig with loaded or default values.
    """
    config_path = path or get_config_path()
    config = PanefitConfig()

    if config_path.exists():
        try:
            with open(config_path) as f:
                data = json.load(f)
            config = PanefitConfig.from_dict(data)
        except (json.JSONDecodeError, TypeError, KeyError):
            pass

    if apply_env:
        config.apply_env_overrides()

    return config


def save_config(config: PanefitConfig, path: Optional[Path] = None) -> bool:
    """
    Save configuration to file.

    Args:
        config: Configuration to save.
        path: Config file path. Uses default if None.

    Returns:
        True if successful.
    """
    config_path = path or get_config_path()

    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w") as f:
            json.dump(config.to_dict(), f, indent=2)
        return True
    except OSError:
        return False


def init_config(path: Optional[Path] = None) -> Path:
    """
    Initialize configuration file with defaults.

    Args:
        path: Config file path. Uses default if None.

    Returns:
        Path to created config file.
    """
    config_path = path or get_config_path()
    config = PanefitConfig()
    save_config(config, config_path)
    return config_path
