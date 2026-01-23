"""
Panefit - Content-aware intelligent pane layout engine.

Analyzes terminal pane content and calculates optimal layouts based on
importance, entropy, and activity metrics.

Basic Usage:
    from panefit import Analyzer, LayoutCalculator, PaneData

    # Create analyzer
    analyzer = Analyzer()

    # Define panes
    panes = [
        PaneData(id="1", content="vim editing...", width=80, height=24),
        PaneData(id="2", content="npm run build...", width=80, height=24),
    ]

    # Analyze
    results = analyzer.analyze_panes(panes)

    # Calculate layout
    calc = LayoutCalculator(strategy="balanced")
    layout = calc.calculate(panes, results, window_width=200, window_height=50)

With Provider (e.g., tmux integration):
    from panefit import Analyzer, LayoutCalculator
    from panefit.providers import Provider  # Abstract interface

    # Terminal-specific providers are in integrations/
    # e.g., from integrations.tmux import TmuxProvider

    provider: Provider = ...  # Get from integration
    panes = provider.get_panes()
    width, height = provider.get_window_size()

    analyzer = Analyzer()
    results = analyzer.analyze_panes(panes)

    calc = LayoutCalculator()
    layout = calc.calculate(panes, results, width, height)
    provider.apply_layout(layout)
"""

__version__ = "0.1.0"
__author__ = "Panefit Contributors"

# Core types
from .types import (
    PaneData,
    AnalysisResult,
    RelevanceResult,
    PaneLayout,
    WindowLayout,
    AnalysisBatch,
    LayoutStrategy,
    LayoutType,
)

# Core classes
from .analyzer import Analyzer
from .layout import LayoutCalculator
from .session import SessionOptimizer

# Configuration
from .config import (
    PanefitConfig,
    LLMConfig,
    LayoutConfig,
    SessionConfig,
    load_config,
    save_config,
    get_config_path,
)

# Note: tmux/MCP specific config is managed by their respective integrations,
# not by this library. They can override settings via environment variables.

# Providers (optional import to avoid circular dependencies)
from . import providers
from . import llm

__all__ = [
    # Version
    "__version__",

    # Types
    "PaneData",
    "AnalysisResult",
    "RelevanceResult",
    "PaneLayout",
    "WindowLayout",
    "AnalysisBatch",
    "LayoutStrategy",
    "LayoutType",

    # Core
    "Analyzer",
    "LayoutCalculator",
    "SessionOptimizer",

    # Configuration
    "PanefitConfig",
    "LLMConfig",
    "LayoutConfig",
    "SessionConfig",
    "load_config",
    "save_config",
    "get_config_path",

    # Submodules
    "providers",
    "llm",
]
