"""
Generic provider for Panefit.

A provider that works with manually provided pane data.
Useful for library usage and custom integrations.
"""

from typing import Optional, Callable

from .base import Provider
from ..types import PaneData, WindowLayout


class GenericProvider(Provider):
    """
    Generic provider for custom integrations.

    This provider doesn't interact with any specific terminal multiplexer.
    Instead, it works with pane data provided programmatically.
    """

    @property
    def name(self) -> str:
        return "generic"

    def __init__(
        self,
        panes: Optional[list[PaneData]] = None,
        window_width: int = 200,
        window_height: int = 50,
        on_layout_applied: Optional[Callable[[WindowLayout], None]] = None,
        on_pane_resized: Optional[Callable[[str, int, int], None]] = None
    ):
        """
        Initialize generic provider.

        Args:
            panes: Initial pane data.
            window_width: Window width.
            window_height: Window height.
            on_layout_applied: Callback when layout is applied.
            on_pane_resized: Callback when pane is resized.
        """
        self._panes = panes or []
        self._window_width = window_width
        self._window_height = window_height
        self._on_layout_applied = on_layout_applied
        self._on_pane_resized = on_pane_resized

    def is_available(self) -> bool:
        """Always available."""
        return True

    def set_panes(self, panes: list[PaneData]) -> None:
        """Set pane data."""
        self._panes = panes

    def set_window_size(self, width: int, height: int) -> None:
        """Set window dimensions."""
        self._window_width = width
        self._window_height = height

    def get_panes(self, window_id: Optional[str] = None) -> list[PaneData]:
        """Get stored panes."""
        return self._panes

    def get_window_size(self, window_id: Optional[str] = None) -> tuple[int, int]:
        """Get window dimensions."""
        return self._window_width, self._window_height

    def apply_layout(self, layout: WindowLayout, window_id: Optional[str] = None) -> bool:
        """Apply layout (updates internal state and calls callback)."""
        # Update internal pane data
        for pane_layout in layout.panes:
            for pane in self._panes:
                if pane.id == pane_layout.id:
                    pane.x = pane_layout.x
                    pane.y = pane_layout.y
                    pane.width = pane_layout.width
                    pane.height = pane_layout.height
                    break

        if self._on_layout_applied:
            self._on_layout_applied(layout)

        return True

    def resize_pane(
        self,
        pane_id: str,
        width: Optional[int] = None,
        height: Optional[int] = None
    ) -> bool:
        """Resize a pane (updates internal state)."""
        for pane in self._panes:
            if pane.id == pane_id:
                if width is not None:
                    pane.width = width
                if height is not None:
                    pane.height = height

                if self._on_pane_resized:
                    self._on_pane_resized(
                        pane_id,
                        width or pane.width,
                        height or pane.height
                    )
                return True
        return False

    def add_pane(self, pane: PaneData) -> None:
        """Add a pane."""
        self._panes.append(pane)

    def remove_pane(self, pane_id: str) -> bool:
        """Remove a pane."""
        for i, pane in enumerate(self._panes):
            if pane.id == pane_id:
                self._panes.pop(i)
                return True
        return False

    def update_content(self, pane_id: str, content: str) -> bool:
        """Update pane content."""
        for pane in self._panes:
            if pane.id == pane_id:
                pane.content = content
                return True
        return False
