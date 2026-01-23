"""
tmux provider for Panefit.

Implements pane management for tmux terminal multiplexer.
"""

import subprocess
import re
from typing import Optional

from .base import Provider
from ..types import PaneData, WindowLayout


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
        """Apply layout by resizing panes."""
        try:
            for pane_layout in layout.panes:
                self.resize_pane(
                    pane_layout.id,
                    pane_layout.width,
                    pane_layout.height
                )
            return True
        except Exception:
            return False

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
