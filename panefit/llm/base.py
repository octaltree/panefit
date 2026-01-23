"""
Base LLM provider interface.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LLMAnalysisResult:
    """Result of LLM-based analysis."""

    importance_score: float = 0.5
    interestingness_score: float = 0.5
    summary: str = ""
    topics: list[str] = field(default_factory=list)
    predicted_activity: str = "medium"  # high, medium, low
    relationships: dict[str, float] = field(default_factory=dict)
    raw_response: Optional[str] = None


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider is configured and available."""
        pass

    @abstractmethod
    def analyze_content(
        self,
        content: str,
        context: Optional[str] = None
    ) -> LLMAnalysisResult:
        """Analyze pane content."""
        pass

    def analyze_relationships(
        self,
        panes: list[tuple[str, str]]
    ) -> dict[tuple[str, str], float]:
        """
        Analyze relationships between panes.

        Args:
            panes: List of (pane_id, content) tuples.

        Returns:
            Dictionary mapping (id1, id2) to relevance score.
        """
        return {}
