"""
Panefit type definitions.

Core data structures used throughout the library.
"""

from dataclasses import dataclass, field
from typing import Optional, Union
from enum import Enum


class LayoutStrategy(Enum):
    """Available layout strategies."""

    IMPORTANCE = "importance"
    ENTROPY = "entropy"
    ACTIVITY = "activity"
    BALANCED = "balanced"
    RELATED = "related"


class LayoutType(Enum):
    """Layout arrangement types."""

    AUTO = "auto"
    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"
    TILED = "tiled"


@dataclass
class PaneData:
    """Input data for a pane."""

    id: str
    content: str
    width: int = 80
    height: int = 24
    x: int = 0
    y: int = 0
    active: bool = False
    title: str = ""
    command: str = ""


@dataclass
class AnalysisResult:
    """Result of content analysis for a single pane."""

    pane_id: str

    # Entropy metrics
    char_entropy: float = 0.0
    word_entropy: float = 0.0

    # Content metrics
    word_count: int = 0
    line_count: int = 0
    char_count: int = 0
    unique_word_ratio: float = 0.0
    vocabulary_richness: float = 0.0
    avg_word_length: float = 0.0

    # Derived scores (0-1)
    surprisal_score: float = 0.0
    recent_activity_score: float = 0.0
    importance_score: float = 0.0
    interestingness_score: float = 0.0

    # Content hash for change detection
    content_hash: str = ""

    # LLM-enhanced fields (optional)
    summary: str = ""
    topics: list[str] = field(default_factory=list)
    predicted_activity: str = "medium"


@dataclass
class RelevanceResult:
    """Relevance analysis between two panes."""

    pane_id_1: str
    pane_id_2: str
    shared_keywords: list[str] = field(default_factory=list)
    jaccard_similarity: float = 0.0
    topic_similarity: float = 0.0
    combined_score: float = 0.0


@dataclass
class PaneLayout:
    """Calculated layout for a single pane."""

    id: str
    x: int
    y: int
    width: int
    height: int

    @property
    def area(self) -> int:
        return self.width * self.height

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height


@dataclass
class WindowLayout:
    """Complete calculated layout for a window."""

    window_width: int
    window_height: int
    panes: list[PaneLayout] = field(default_factory=list)
    strategy: LayoutStrategy = LayoutStrategy.BALANCED

    def get_pane(self, pane_id: str) -> Optional[PaneLayout]:
        """Get layout for a specific pane."""
        for pane in self.panes:
            if pane.id == pane_id:
                return pane
        return None


@dataclass
class AnalysisBatch:
    """Batch analysis results for multiple panes."""

    results: dict[str, AnalysisResult] = field(default_factory=dict)
    relevance_matrix: dict[tuple[str, str], RelevanceResult] = field(default_factory=dict)

    def get(self, pane_id: str) -> Optional[AnalysisResult]:
        return self.results.get(pane_id)

    def get_relevance(self, id1: str, id2: str) -> Optional[RelevanceResult]:
        return self.relevance_matrix.get((id1, id2)) or self.relevance_matrix.get((id2, id1))


class LayoutOperation(Enum):
    """Operations to transform layout."""

    SWAP = "swap"          # Swap two panes
    RESIZE = "resize"      # Resize a pane
    MOVE = "move"          # Move pane to another window
    JOIN = "join"          # Join pane next to another
    BREAK = "break"        # Break pane to new window


@dataclass
class LayoutStep:
    """A single step in layout transformation."""

    operation: LayoutOperation
    pane_id: str
    target_id: Optional[str] = None  # For swap/join
    width: Optional[int] = None
    height: Optional[int] = None
    vertical: bool = False  # For join: split direction

    def __str__(self) -> str:
        if self.operation == LayoutOperation.SWAP:
            return f"swap {self.pane_id} <-> {self.target_id}"
        elif self.operation == LayoutOperation.RESIZE:
            return f"resize {self.pane_id} to {self.width}x{self.height}"
        elif self.operation == LayoutOperation.JOIN:
            dir_str = "below" if self.vertical else "right of"
            return f"join {self.pane_id} {dir_str} {self.target_id}"
        else:
            return f"{self.operation.value} {self.pane_id}"


@dataclass
class LayoutPlan:
    """Plan to transform current layout to target."""

    steps: list[LayoutStep] = field(default_factory=list)
    target: Optional["WindowLayout"] = None

    @property
    def step_count(self) -> int:
        return len(self.steps)

    def __str__(self) -> str:
        return f"{self.step_count} steps: " + " → ".join(str(s) for s in self.steps)
