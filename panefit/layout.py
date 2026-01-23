"""
Panefit layout calculator.

Calculates optimal pane layouts based on content analysis results.
"""

from dataclasses import dataclass
from typing import Optional

from .types import (
    PaneData, AnalysisResult, RelevanceResult,
    PaneLayout, WindowLayout, LayoutStrategy, LayoutType
)


@dataclass
class PaneScore:
    """Aggregated score for layout calculation."""

    id: str
    importance: float
    interestingness: float
    activity: float
    combined: float


class LayoutCalculator:
    """Calculates optimal pane layouts."""

    GOLDEN_RATIO = 1.618
    MIN_WIDTH = 20
    MIN_HEIGHT = 5

    def __init__(
        self,
        strategy: LayoutStrategy | str = LayoutStrategy.BALANCED,
        min_width: int = MIN_WIDTH,
        min_height: int = MIN_HEIGHT
    ):
        """
        Initialize calculator.

        Args:
            strategy: Layout strategy to use.
            min_width: Minimum pane width.
            min_height: Minimum pane height.
        """
        if isinstance(strategy, str):
            strategy = LayoutStrategy(strategy)
        self.strategy = strategy
        self.min_width = min_width
        self.min_height = min_height

    def _calculate_scores(
        self,
        panes: list[PaneData],
        analyses: dict[str, AnalysisResult]
    ) -> list[PaneScore]:
        """Calculate combined scores for all panes."""
        scores = []

        for pane in panes:
            analysis = analyses.get(pane.id)
            if analysis:
                importance = analysis.importance_score
                interestingness = analysis.interestingness_score
                activity = analysis.recent_activity_score
            else:
                importance = interestingness = activity = 0.5

            if pane.active:
                importance = min(1.0, importance + 0.2)

            # Calculate combined based on strategy
            if self.strategy == LayoutStrategy.IMPORTANCE:
                combined = importance
            elif self.strategy == LayoutStrategy.ENTROPY:
                combined = interestingness
            elif self.strategy == LayoutStrategy.ACTIVITY:
                combined = activity
            elif self.strategy == LayoutStrategy.BALANCED:
                combined = 0.4 * importance + 0.3 * interestingness + 0.3 * activity
            else:
                combined = (importance + interestingness + activity) / 3

            scores.append(PaneScore(
                id=pane.id,
                importance=importance,
                interestingness=interestingness,
                activity=activity,
                combined=combined
            ))

        # Normalize
        total = sum(s.combined for s in scores)
        if total > 0:
            for score in scores:
                score.combined /= total

        return scores

    def _proportional_sizes(
        self,
        scores: list[PaneScore],
        total_size: int,
        min_size: int
    ) -> list[int]:
        """Calculate sizes proportional to scores."""
        n = len(scores)
        if n == 0:
            return []
        if n == 1:
            return [total_size]

        min_total = min_size * n
        if min_total >= total_size:
            return [total_size // n] * n

        remaining = total_size - min_total
        sizes = [min_size + int(remaining * s.combined) for s in scores]

        # Adjust rounding
        diff = total_size - sum(sizes)
        if diff != 0:
            max_idx = max(range(len(scores)), key=lambda i: scores[i].combined)
            sizes[max_idx] += diff

        return sizes

    def _layout_horizontal(
        self,
        scores: list[PaneScore],
        window_width: int,
        window_height: int
    ) -> list[PaneLayout]:
        """Create horizontal (side-by-side) layout."""
        sorted_scores = sorted(scores, key=lambda s: s.combined, reverse=True)
        widths = self._proportional_sizes(sorted_scores, window_width, self.min_width)

        layouts = []
        x = 0
        for i, score in enumerate(sorted_scores):
            layouts.append(PaneLayout(
                id=score.id,
                x=x,
                y=0,
                width=widths[i],
                height=window_height
            ))
            x += widths[i]

        return layouts

    def _layout_vertical(
        self,
        scores: list[PaneScore],
        window_width: int,
        window_height: int
    ) -> list[PaneLayout]:
        """Create vertical (stacked) layout."""
        sorted_scores = sorted(scores, key=lambda s: s.combined, reverse=True)
        heights = self._proportional_sizes(sorted_scores, window_height, self.min_height)

        layouts = []
        y = 0
        for i, score in enumerate(sorted_scores):
            layouts.append(PaneLayout(
                id=score.id,
                x=0,
                y=y,
                width=window_width,
                height=heights[i]
            ))
            y += heights[i]

        return layouts

    def _layout_tiled(
        self,
        scores: list[PaneScore],
        window_width: int,
        window_height: int
    ) -> list[PaneLayout]:
        """Create tiled layout with main pane and side panes."""
        if len(scores) <= 1:
            return self._layout_horizontal(scores, window_width, window_height)

        sorted_scores = sorted(scores, key=lambda s: s.combined, reverse=True)

        # Main pane uses golden ratio
        main_width = int(window_width / self.GOLDEN_RATIO)
        side_width = window_width - main_width

        layouts = [PaneLayout(
            id=sorted_scores[0].id,
            x=0,
            y=0,
            width=main_width,
            height=window_height
        )]

        # Side panes stacked
        side_scores = sorted_scores[1:]
        heights = self._proportional_sizes(side_scores, window_height, self.min_height)

        y = 0
        for i, score in enumerate(side_scores):
            layouts.append(PaneLayout(
                id=score.id,
                x=main_width,
                y=y,
                width=side_width,
                height=heights[i]
            ))
            y += heights[i]

        return layouts

    def _layout_related(
        self,
        scores: list[PaneScore],
        relevance_matrix: dict[tuple[str, str], RelevanceResult],
        window_width: int,
        window_height: int
    ) -> list[PaneLayout]:
        """Create layout grouping related panes."""
        if len(scores) <= 2:
            return self._layout_tiled(scores, window_width, window_height)

        sorted_scores = sorted(scores, key=lambda s: s.combined, reverse=True)
        main_pane = sorted_scores[0]

        # Sort others by relevance to main
        related_scores = []
        for score in sorted_scores[1:]:
            key1 = (main_pane.id, score.id)
            key2 = (score.id, main_pane.id)
            rel = relevance_matrix.get(key1) or relevance_matrix.get(key2)
            rel_score = rel.combined_score if rel else 0
            related_scores.append((score, rel_score))

        related_scores.sort(key=lambda x: x[1], reverse=True)
        reordered = [main_pane] + [s for s, _ in related_scores]

        return self._layout_tiled(reordered, window_width, window_height)

    def calculate(
        self,
        panes: list[PaneData],
        analyses: dict[str, AnalysisResult],
        window_width: int,
        window_height: int,
        relevance_matrix: Optional[dict[tuple[str, str], RelevanceResult]] = None,
        layout_type: LayoutType | str = LayoutType.AUTO
    ) -> WindowLayout:
        """
        Calculate optimal layout.

        Args:
            panes: List of pane data.
            analyses: Analysis results by pane ID.
            window_width: Window width.
            window_height: Window height.
            relevance_matrix: Optional relevance scores.
            layout_type: Layout arrangement type.

        Returns:
            WindowLayout with calculated positions.
        """
        if isinstance(layout_type, str):
            layout_type = LayoutType(layout_type)

        scores = self._calculate_scores(panes, analyses)

        if layout_type == LayoutType.HORIZONTAL:
            layouts = self._layout_horizontal(scores, window_width, window_height)
        elif layout_type == LayoutType.VERTICAL:
            layouts = self._layout_vertical(scores, window_width, window_height)
        elif layout_type == LayoutType.TILED:
            layouts = self._layout_tiled(scores, window_width, window_height)
        elif self.strategy == LayoutStrategy.RELATED and relevance_matrix:
            layouts = self._layout_related(scores, relevance_matrix, window_width, window_height)
        else:
            # Auto: choose based on aspect ratio
            aspect = window_width / window_height
            if len(panes) == 2:
                if aspect > 1.5:
                    layouts = self._layout_horizontal(scores, window_width, window_height)
                else:
                    layouts = self._layout_vertical(scores, window_width, window_height)
            else:
                layouts = self._layout_tiled(scores, window_width, window_height)

        return WindowLayout(
            window_width=window_width,
            window_height=window_height,
            panes=layouts,
            strategy=self.strategy
        )

    def get_resize_operations(
        self,
        current_panes: list[PaneData],
        target_layout: WindowLayout
    ) -> list[tuple[str, Optional[int], Optional[int]]]:
        """
        Get resize operations to transform to target layout.

        Returns:
            List of (pane_id, width, height) tuples.
        """
        operations = []
        for pane in current_panes:
            target = target_layout.get_pane(pane.id)
            if target:
                width_change = target.width != pane.width
                height_change = target.height != pane.height
                if width_change or height_change:
                    operations.append((
                        pane.id,
                        target.width if width_change else None,
                        target.height if height_change else None
                    ))
        return operations
