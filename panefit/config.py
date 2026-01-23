"""
Panefit configuration management.

Handles loading, saving, and defaults for CLI/plugin settings.
"""

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


@dataclass
class LLMConfig:
    """LLM integration settings."""

    enabled: bool = False
    provider: str = "auto"  # auto, openai, anthropic, ollama
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
class TmuxConfig:
    """tmux plugin settings."""

    keybinding: str = "R"
    auto_reflow: bool = False
    history_lines: int = 100


@dataclass
class PanefitConfig:
    """Main configuration container."""

    llm: LLMConfig = field(default_factory=LLMConfig)
    layout: LayoutConfig = field(default_factory=LayoutConfig)
    session: SessionConfig = field(default_factory=SessionConfig)
    tmux: TmuxConfig = field(default_factory=TmuxConfig)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "llm": asdict(self.llm),
            "layout": asdict(self.layout),
            "session": asdict(self.session),
            "tmux": asdict(self.tmux),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PanefitConfig":
        """Create from dictionary."""
        return cls(
            llm=LLMConfig(**data.get("llm", {})),
            layout=LayoutConfig(**data.get("layout", {})),
            session=SessionConfig(**data.get("session", {})),
            tmux=TmuxConfig(**data.get("tmux", {})),
        )


def get_config_path() -> Path:
    """Get configuration file path."""
    xdg_config = os.environ.get("XDG_CONFIG_HOME", "~/.config")
    return Path(xdg_config).expanduser() / "panefit" / "config.json"


def load_config(path: Optional[Path] = None) -> PanefitConfig:
    """
    Load configuration from file.

    Args:
        path: Config file path. Uses default if None.

    Returns:
        PanefitConfig with loaded or default values.
    """
    config_path = path or get_config_path()

    if config_path.exists():
        try:
            with open(config_path) as f:
                data = json.load(f)
            return PanefitConfig.from_dict(data)
        except (json.JSONDecodeError, TypeError, KeyError):
            pass

    return PanefitConfig()


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
