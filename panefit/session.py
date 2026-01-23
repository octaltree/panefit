"""
Session-wide optimization for Panefit.

Provides cross-window pane organization based on content analysis.
Groups related panes together and optimizes layout across all windows.
"""

from dataclasses import dataclass, field
from typing import Optional

from .types import PaneData, AnalysisResult, RelevanceResult
from .analyzer import Analyzer
from .providers.base import Provider


@dataclass
class WindowGroup:
    """A group of related panes that should be in the same window."""

    name: str
    pane_ids: list[str] = field(default_factory=list)
    topic: str = ""
    importance: float = 0.0


@dataclass
class SessionLayout:
    """Proposed layout for entire session."""

    groups: list[WindowGroup] = field(default_factory=list)
    orphan_panes: list[str] = field(default_factory=list)  # Panes that don't fit any group
    changes: list[dict] = field(default_factory=list)  # List of moves to make


class SessionOptimizer:
    """
    Optimizes pane arrangement across terminal session.

    Features:
    - Groups related panes into same window
    - Moves low-importance panes to "parking" window
    - Consolidates scattered context

    Note: Requires a provider with cross-window support (e.g., TmuxProvider).
    """

    def __init__(
        self,
        provider: Provider,
        analyzer: Optional[Analyzer] = None,
        relevance_threshold: float = 0.3,
        importance_threshold: float = 0.2
    ):
        """
        Initialize optimizer.

        Args:
            provider: Provider instance with cross-window support.
            analyzer: Analyzer instance.
            relevance_threshold: Min relevance score to group panes.
            importance_threshold: Panes below this may be parked.
        """
        self.provider = provider
        self.analyzer = analyzer or Analyzer()
        self.relevance_threshold = relevance_threshold
        self.importance_threshold = importance_threshold

    def analyze_session(self) -> dict:
        """
        Analyze all panes in session.

        Returns:
            Dict with panes, analyses, relevance matrix, and grouping suggestions.
        """
        if not self.provider.is_available():
            return {"error": "Provider not available"}

        # Get all panes across all windows
        all_panes = self.provider.get_all_panes()
        if not all_panes:
            return {"error": "No panes found"}

        # Analyze each pane
        analyses = self.analyzer.analyze_panes(all_panes)

        # Build relevance matrix
        relevance_matrix = self.analyzer.build_relevance_matrix(all_panes)

        # Group panes by window
        windows = {}
        for pane in all_panes:
            window_id = pane.title.split(":")[0] if ":" in pane.title else "unknown"
            if window_id not in windows:
                windows[window_id] = []
            windows[window_id].append(pane.id)

        # Find suggested groups based on relevance
        groups = self._suggest_groups(all_panes, analyses, relevance_matrix)

        return {
            "pane_count": len(all_panes),
            "window_count": len(windows),
            "windows": windows,
            "panes": [
                {
                    "id": p.id,
                    "command": p.command,
                    "window": p.title.split(":")[0] if ":" in p.title else "unknown",
                    "importance": round(analyses[p.id].importance_score, 3),
                    "activity": round(analyses[p.id].recent_activity_score, 3),
                }
                for p in all_panes
            ],
            "suggested_groups": [
                {
                    "name": g.name,
                    "panes": g.pane_ids,
                    "topic": g.topic,
                    "importance": round(g.importance, 3)
                }
                for g in groups
            ]
        }

    def _suggest_groups(
        self,
        panes: list[PaneData],
        analyses: dict[str, AnalysisResult],
        relevance_matrix: dict[tuple[str, str], RelevanceResult]
    ) -> list[WindowGroup]:
        """Suggest pane groupings based on relevance."""
        groups = []
        assigned = set()

        # Sort panes by importance
        sorted_panes = sorted(
            panes,
            key=lambda p: analyses[p.id].importance_score,
            reverse=True
        )

        for pane in sorted_panes:
            if pane.id in assigned:
                continue

            # Start new group with this pane
            group = WindowGroup(
                name=f"group_{len(groups) + 1}",
                pane_ids=[pane.id],
                topic=pane.command,
                importance=analyses[pane.id].importance_score
            )
            assigned.add(pane.id)

            # Find related panes
            for other in panes:
                if other.id in assigned:
                    continue

                # Check relevance
                rel = relevance_matrix.get((pane.id, other.id))
                if rel and rel.combined_score >= self.relevance_threshold:
                    group.pane_ids.append(other.id)
                    assigned.add(other.id)
                    if rel.shared_keywords:
                        group.topic = rel.shared_keywords[0]

            if len(group.pane_ids) > 1:
                groups.append(group)

        # Handle remaining panes
        remaining = [p.id for p in panes if p.id not in assigned]
        if remaining:
            groups.append(WindowGroup(
                name="misc",
                pane_ids=remaining,
                topic="miscellaneous",
                importance=0.0
            ))

        return groups

    def calculate_moves(
        self,
        target_layout: SessionLayout,
        dry_run: bool = True
    ) -> list[dict]:
        """
        Calculate moves needed to achieve target layout.

        Args:
            target_layout: Desired session layout.
            dry_run: If True, only calculate; don't execute.

        Returns:
            List of move operations.
        """
        all_panes = self.provider.get_all_panes()

        # Build current window mapping
        current_windows = {}
        for pane in all_panes:
            window_id = pane.title.split(":")[0] if ":" in pane.title else "unknown"
            current_windows[pane.id] = window_id

        moves = []

        for group in target_layout.groups:
            if len(group.pane_ids) < 2:
                continue

            # Find which window has most panes from this group
            window_counts = {}
            for pane_id in group.pane_ids:
                win = current_windows.get(pane_id, "unknown")
                window_counts[win] = window_counts.get(win, 0) + 1

            target_window = max(window_counts, key=window_counts.get)

            # Move panes that aren't in target window
            for pane_id in group.pane_ids:
                current_win = current_windows.get(pane_id, "unknown")
                if current_win != target_window:
                    moves.append({
                        "action": "move",
                        "pane": pane_id,
                        "from": current_win,
                        "to": target_window,
                        "group": group.name
                    })

        return moves

    def optimize(
        self,
        dry_run: bool = True,
        park_low_importance: bool = False
    ) -> dict:
        """
        Optimize session layout.

        Args:
            dry_run: If True, only calculate; don't execute.
            park_low_importance: Move low-importance panes to separate window.

        Returns:
            Dict with analysis and applied/proposed changes.
        """
        analysis = self.analyze_session()
        if "error" in analysis:
            return analysis

        # Build layout from suggestions
        groups = []
        for sg in analysis["suggested_groups"]:
            groups.append(WindowGroup(
                name=sg["name"],
                pane_ids=sg["panes"],
                topic=sg["topic"],
                importance=sg["importance"]
            ))

        layout = SessionLayout(groups=groups)
        moves = self.calculate_moves(layout, dry_run=True)

        result = {
            "status": "calculated" if dry_run else "applied",
            "analysis": analysis,
            "proposed_moves": moves,
            "move_count": len(moves)
        }

        if not dry_run and moves:
            applied = []
            for move in moves:
                success = self.provider.move_pane(
                    move["pane"],
                    move["to"],
                    vertical=True
                )
                applied.append({**move, "success": success})
            result["applied_moves"] = applied
            result["status"] = "applied"

        return result

    def consolidate_related(self, pane_id: str, dry_run: bool = True) -> dict:
        """
        Move all panes related to given pane into same window.

        Args:
            pane_id: Reference pane.
            dry_run: If True, only calculate.

        Returns:
            Dict with moves.
        """
        all_panes = self.provider.get_all_panes()
        analyses = self.analyzer.analyze_panes(all_panes)
        relevance_matrix = self.analyzer.build_relevance_matrix(all_panes)

        # Find related panes
        related = [pane_id]
        for pane in all_panes:
            if pane.id == pane_id:
                continue
            rel = relevance_matrix.get((pane_id, pane.id))
            if rel and rel.combined_score >= self.relevance_threshold:
                related.append(pane.id)

        if len(related) <= 1:
            return {"status": "no_related_panes", "related": related}

        # Find current window of reference pane
        target_window = None
        for pane in all_panes:
            if pane.id == pane_id:
                target_window = pane.title.split(":")[0] if ":" in pane.title else None
                break

        if not target_window:
            return {"error": "Could not determine target window"}

        # Calculate moves
        moves = []
        for pid in related:
            if pid == pane_id:
                continue
            for pane in all_panes:
                if pane.id == pid:
                    current_window = pane.title.split(":")[0] if ":" in pane.title else None
                    if current_window and current_window != target_window:
                        moves.append({
                            "action": "move",
                            "pane": pid,
                            "from": current_window,
                            "to": target_window
                        })
                    break

        result = {
            "status": "calculated" if dry_run else "applied",
            "reference_pane": pane_id,
            "related_panes": related,
            "target_window": target_window,
            "moves": moves
        }

        if not dry_run:
            for move in moves:
                success = self.provider.move_pane(move["pane"], move["to"])
                move["success"] = success

        return result

    def park_inactive(self, window_name: str = "parked", dry_run: bool = True) -> dict:
        """
        Move low-importance/inactive panes to a parking window.

        Args:
            window_name: Name for parking window.
            dry_run: If True, only calculate.

        Returns:
            Dict with moves.
        """
        all_panes = self.provider.get_all_panes()
        analyses = self.analyzer.analyze_panes(all_panes)

        # Find low-importance panes
        to_park = []
        for pane in all_panes:
            analysis = analyses[pane.id]
            if (analysis.importance_score < self.importance_threshold and
                analysis.recent_activity_score < 0.2):
                to_park.append({
                    "id": pane.id,
                    "command": pane.command,
                    "importance": analysis.importance_score
                })

        if not to_park:
            return {"status": "nothing_to_park", "threshold": self.importance_threshold}

        result = {
            "status": "calculated" if dry_run else "applied",
            "to_park": to_park,
            "window_name": window_name
        }

        if not dry_run and to_park:
            # Break first pane to create parking window
            first = to_park[0]
            new_window = self.provider.break_pane(first["id"], window_name)

            if new_window:
                # Move remaining panes to parking window
                for pane in to_park[1:]:
                    self.provider.move_pane(pane["id"], new_window)

                result["parking_window"] = new_window

        return result
