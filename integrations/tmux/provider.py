"""
tmux provider for Panefit.

Implements pane management for tmux terminal multiplexer.
"""

import subprocess
import re
from typing import Optional

from panefit.providers.base import Provider
from panefit.types import (
    PaneData,
    WindowLayout,
    PaneLayout,
    LayoutPlan,
    LayoutStep,
    LayoutOperation,
)


class TmuxProvider(Provider):
    """Provider for tmux terminal multiplexer."""

    @property
    def name(self) -> str:
        return "tmux"

    def __init__(self, history_lines: int = 100):
        """
        Initialize tmux provider.

        Args:
            history_lines: Number of history lines to capture.
        """
        self.history_lines = history_lines

    def _run_tmux(self, *args: str) -> str:
        """Run tmux command and return output."""
        result = subprocess.run(
            ["tmux", *args],
            capture_output=True,
            text=True
        )
        return result.stdout.strip()

    def is_available(self) -> bool:
        """Check if tmux is available and we're in a session."""
        try:
            result = subprocess.run(
                ["tmux", "display-message", "-p", "#{session_name}"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0 and bool(result.stdout.strip())
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def get_panes(self, window_id: Optional[str] = None) -> list[PaneData]:
        """Get all panes with content."""
        format_str = "#{pane_id}|#{pane_width}|#{pane_height}|#{pane_top}|#{pane_left}|#{pane_active}|#{pane_title}|#{pane_current_command}"

        args = ["list-panes"]
        if window_id:
            args.extend(["-t", window_id])
        args.extend(["-F", format_str])

        output = self._run_tmux(*args)
        panes = []

        for line in output.split("\n"):
            if not line:
                continue
            parts = line.split("|")
            if len(parts) >= 8:
                pane_id = parts[0]
                content = self._capture_content(pane_id)

                panes.append(PaneData(
                    id=pane_id,
                    content=content,
                    width=int(parts[1]),
                    height=int(parts[2]),
                    y=int(parts[3]),
                    x=int(parts[4]),
                    active=parts[5] == "1",
                    title=parts[6],
                    command=parts[7]
                ))

        return panes

    def _capture_content(self, pane_id: str) -> str:
        """Capture pane content."""
        content = self._run_tmux(
            "capture-pane",
            "-t", pane_id,
            "-p",
            "-S", f"-{self.history_lines}"
        )
        # Strip ANSI escape sequences
        content = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', content)
        return content

    def get_window_size(self, window_id: Optional[str] = None) -> tuple[int, int]:
        """Get window dimensions."""
        args = ["display-message"]
        if window_id:
            args.extend(["-t", window_id])
        args.extend(["-p", "#{window_width}|#{window_height}"])

        output = self._run_tmux(*args)
        width, height = output.split("|")
        return int(width), int(height)

    def apply_layout(self, layout: WindowLayout, window_id: Optional[str] = None) -> bool:
        """
        Apply layout using swap operations and resizing.

        1. Calculate swap operations to reorder panes by importance
        2. Apply swaps to move panes to ideal positions
        3. Resize panes to target sizes
        """
        try:
            # Plan the transformation
            plan = self.plan_layout(layout, window_id)

            # Execute the plan
            return self.execute_plan(plan)
        except Exception:
            return False

    def plan_layout(self, layout: WindowLayout, window_id: Optional[str] = None) -> LayoutPlan:
        """
        Plan the operations needed to transform current layout to target.

        Algorithm:
        1. Get current pane positions (sorted by position in tree)
        2. Sort target panes by their calculated positions (importance order)
        3. Match positions: pane at position[i] should go to target position[i]
        4. Generate swaps to achieve the target ordering
        """
        plan = LayoutPlan(target=layout)

        # Get current panes with their positions
        current_panes = self.get_panes(window_id)
        if not current_panes:
            return plan

        # Sort current panes by position (top-left to bottom-right)
        # This represents the order in tmux's binary tree
        current_sorted = sorted(current_panes, key=lambda p: (p.y, p.x))
        current_order = [p.id for p in current_sorted]

        # Sort target panes by position (top-left to bottom-right)
        # Larger/more important panes should be at top-left
        target_sorted = sorted(layout.panes, key=lambda p: (p.y, p.x))
        target_order = [p.id for p in target_sorted]

        # Calculate swaps needed to transform current_order -> target_order
        # Use a simple algorithm: for each position, if wrong pane is there, swap it
        working_order = current_order.copy()

        for i, target_id in enumerate(target_order):
            if i >= len(working_order):
                break

            current_id = working_order[i]
            if current_id != target_id:
                # Find where target_id currently is
                try:
                    j = working_order.index(target_id)
                    # Swap positions i and j
                    working_order[i], working_order[j] = working_order[j], working_order[i]

                    plan.steps.append(LayoutStep(
                        operation=LayoutOperation.SWAP,
                        pane_id=current_id,
                        target_id=target_id
                    ))
                except ValueError:
                    # target_id not in current window, skip
                    continue

        # Add resize steps for all panes
        for pane_layout in layout.panes:
            plan.steps.append(LayoutStep(
                operation=LayoutOperation.RESIZE,
                pane_id=pane_layout.id,
                width=pane_layout.width,
                height=pane_layout.height
            ))

        return plan

    def execute_plan(self, plan: LayoutPlan) -> bool:
        """Execute a layout transformation plan."""
        success = True

        # Execute swaps first
        for step in plan.steps:
            if step.operation == LayoutOperation.SWAP:
                if not self.swap_panes(step.pane_id, step.target_id):
                    success = False

        # Get current pane dimensions after swaps
        current_panes = {p.id: p for p in self.get_panes()}

        # Execute resizes (sorted by y desc to resize from bottom up)
        resize_steps = [s for s in plan.steps if s.operation == LayoutOperation.RESIZE]
        # Sort by target y position descending (bottom first)
        target_positions = {p.id: p.y for p in plan.target.panes}
        resize_steps.sort(key=lambda s: target_positions.get(s.pane_id, 0), reverse=True)

        for step in resize_steps:
            current = current_panes.get(step.pane_id)
            # Only resize if dimension actually changed
            new_width = step.width if current and step.width != current.width else None
            new_height = step.height if current and step.height != current.height else None
            if new_width or new_height:
                if not self.resize_pane(step.pane_id, new_width, new_height):
                    success = False

        # Handle joins
        for step in plan.steps:
            if step.operation == LayoutOperation.JOIN:
                direction = "-v" if step.vertical else "-h"
                try:
                    self._run_tmux("join-pane", direction, "-s", step.pane_id, "-t", step.target_id)
                except Exception:
                    success = False

        return success

    def _build_layout_string(self, layout: WindowLayout) -> str:
        """
        Build tmux layout string from WindowLayout.

        tmux layout format: {width}x{height},{x},{y}[,pane_id | {nested}]
        """
        w, h = layout.window_width, layout.window_height

        if len(layout.panes) == 0:
            return f"{w}x{h},0,0"

        if len(layout.panes) == 1:
            p = layout.panes[0]
            pane_num = p.id.replace("%", "")
            return f"{w}x{h},0,0,{pane_num}"

        # Build nested layout structure
        pane_strs = []
        for p in layout.panes:
            pane_num = p.id.replace("%", "")
            pane_strs.append(f"{p.width}x{p.height},{p.x},{p.y},{pane_num}")

        # Determine layout orientation based on pane positions
        # Check if horizontal (side by side) or vertical (stacked)
        xs = [p.x for p in layout.panes]
        ys = [p.y for p in layout.panes]

        if len(set(ys)) == 1:
            # All same y = horizontal layout
            inner = ",".join(pane_strs)
            return f"{w}x{h},0,0{{{inner}}}"
        elif len(set(xs)) == 1:
            # All same x = vertical layout
            inner = ",".join(pane_strs)
            return f"{w}x{h},0,0{{{inner}}}"
        else:
            # Mixed/tiled layout - use checksum format
            checksum = self._calculate_layout_checksum(pane_strs)
            inner = ",".join(pane_strs)
            return f"{checksum},{w}x{h},0,0{{{inner}}}"

    def _calculate_layout_checksum(self, pane_strs: list[str]) -> str:
        """Calculate tmux layout checksum."""
        layout_str = ",".join(pane_strs)
        csum = 0
        for c in layout_str:
            csum = (csum >> 1) + ((csum & 1) << 15)
            csum += ord(c)
            csum &= 0xffff
        return f"{csum:04x}"

    def resize_pane(
        self,
        pane_id: str,
        width: Optional[int] = None,
        height: Optional[int] = None
    ) -> bool:
        """Resize a pane."""
        try:
            if width is not None:
                self._run_tmux("resize-pane", "-t", pane_id, "-x", str(width))
            if height is not None:
                self._run_tmux("resize-pane", "-t", pane_id, "-y", str(height))
            return True
        except Exception:
            return False

    def swap_panes(self, pane_id_1: str, pane_id_2: str) -> bool:
        """Swap two panes."""
        try:
            self._run_tmux("swap-pane", "-s", pane_id_1, "-t", pane_id_2)
            return True
        except Exception:
            return False

    def select_pane(self, pane_id: str) -> bool:
        """Select a pane."""
        try:
            self._run_tmux("select-pane", "-t", pane_id)
            return True
        except Exception:
            return False

    def get_current_session(self) -> str:
        """Get current session name."""
        return self._run_tmux("display-message", "-p", "#{session_name}")

    def get_current_window(self) -> str:
        """Get current window ID."""
        return self._run_tmux("display-message", "-p", "#{window_id}")

    # ========== Cross-window operations ==========

    def list_windows(self, session: Optional[str] = None) -> list[dict]:
        """
        List all windows in session.

        Returns:
            List of dicts with window_id, window_name, window_active, pane_count.
        """
        format_str = "#{window_id}|#{window_name}|#{window_active}|#{window_panes}"
        args = ["list-windows"]
        if session:
            args.extend(["-t", session])
        args.extend(["-F", format_str])

        output = self._run_tmux(*args)
        windows = []
        for line in output.split("\n"):
            if not line:
                continue
            parts = line.split("|")
            if len(parts) >= 4:
                windows.append({
                    "window_id": parts[0],
                    "window_name": parts[1],
                    "active": parts[2] == "1",
                    "pane_count": int(parts[3])
                })
        return windows

    def get_all_panes(self, session: Optional[str] = None) -> list[PaneData]:
        """
        Get all panes across all windows in session.

        Args:
            session: Session name. If None, uses current session.

        Returns:
            List of PaneData with window_id in title field.
        """
        format_str = "#{pane_id}|#{window_id}|#{pane_width}|#{pane_height}|#{pane_top}|#{pane_left}|#{pane_active}|#{pane_title}|#{pane_current_command}"
        args = ["list-panes", "-s"]  # -s for all panes in session
        if session:
            args.extend(["-t", session])
        args.extend(["-F", format_str])

        output = self._run_tmux(*args)
        panes = []

        for line in output.split("\n"):
            if not line:
                continue
            parts = line.split("|")
            if len(parts) >= 9:
                pane_id = parts[0]
                window_id = parts[1]
                content = self._capture_content(pane_id)

                panes.append(PaneData(
                    id=pane_id,
                    content=content,
                    width=int(parts[2]),
                    height=int(parts[3]),
                    y=int(parts[4]),
                    x=int(parts[5]),
                    active=parts[6] == "1",
                    title=f"{window_id}:{parts[7]}",  # Include window_id
                    command=parts[8]
                ))

        return panes

    def move_pane(
        self,
        source_pane: str,
        target_window: str,
        vertical: bool = True
    ) -> bool:
        """
        Move pane to another window.

        Args:
            source_pane: Source pane ID (e.g., "%0").
            target_window: Target window (e.g., ":1" or "@2").
            vertical: Split direction in target.

        Returns:
            True if successful.
        """
        try:
            direction = "-v" if vertical else "-h"
            self._run_tmux("join-pane", direction, "-s", source_pane, "-t", target_window)
            return True
        except Exception:
            return False

    def break_pane(self, pane_id: str, window_name: Optional[str] = None) -> Optional[str]:
        """
        Break pane out to a new window.

        Args:
            pane_id: Pane to break out.
            window_name: Optional name for new window.

        Returns:
            New window ID, or None on failure.
        """
        try:
            args = ["break-pane", "-s", pane_id, "-P", "-F", "#{window_id}"]
            if window_name:
                args.extend(["-n", window_name])
            result = self._run_tmux(*args)
            return result if result else None
        except Exception:
            return None

    def join_pane(
        self,
        source_pane: str,
        target_pane: str,
        vertical: bool = True,
        before: bool = False
    ) -> bool:
        """
        Join source pane to target pane's window.

        Args:
            source_pane: Pane to move (e.g., "%5" or ":2.0").
            target_pane: Target pane (source joins next to this).
            vertical: True for vertical split, False for horizontal.
            before: True to place before target, False for after.

        Returns:
            True if successful.
        """
        try:
            args = ["join-pane"]
            args.append("-v" if vertical else "-h")
            if before:
                args.append("-b")
            args.extend(["-s", source_pane, "-t", target_pane])
            self._run_tmux(*args)
            return True
        except Exception:
            return False

    def swap_panes_cross_window(self, pane1: str, pane2: str) -> bool:
        """
        Swap two panes, even across different windows.

        Args:
            pane1: First pane (e.g., ":1.0").
            pane2: Second pane (e.g., ":2.1").

        Returns:
            True if successful.
        """
        try:
            self._run_tmux("swap-pane", "-s", pane1, "-t", pane2)
            return True
        except Exception:
            return False

    def link_window(self, source_window: str, target_session: str) -> bool:
        """
        Link a window to another session.

        Args:
            source_window: Window to link.
            target_session: Target session name.

        Returns:
            True if successful.
        """
        try:
            self._run_tmux("link-window", "-s", source_window, "-t", target_session)
            return True
        except Exception:
            return False
