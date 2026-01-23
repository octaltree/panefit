"""
Base provider interface for Panefit.

Defines the abstract interface that all providers must implement.
"""

from abc import ABC, abstractmethod
from typing import Optional

from ..types import PaneData, WindowLayout


class Provider(ABC):
    """Abstract base class for pane providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this provider is available in current environment."""
        pass

    @abstractmethod
    def get_panes(self, window_id: Optional[str] = None) -> list[PaneData]:
        """
        Get all panes with their content.

        Args:
            window_id: Optional window/session identifier.

        Returns:
            List of PaneData objects.
        """
        pass

    @abstractmethod
    def get_window_size(self, window_id: Optional[str] = None) -> tuple[int, int]:
        """
        Get window dimensions.

        Args:
            window_id: Optional window identifier.

        Returns:
            Tuple of (width, height).
        """
        pass

    @abstractmethod
    def apply_layout(self, layout: WindowLayout, window_id: Optional[str] = None) -> bool:
        """
        Apply a calculated layout.

        Args:
            layout: WindowLayout to apply.
            window_id: Optional window identifier.

        Returns:
            True if successful.
        """
        pass

    @abstractmethod
    def resize_pane(
        self,
        pane_id: str,
        width: Optional[int] = None,
        height: Optional[int] = None
    ) -> bool:
        """
        Resize a specific pane.

        Args:
            pane_id: Pane identifier.
            width: New width (None to keep current).
            height: New height (None to keep current).

        Returns:
            True if successful.
        """
        pass

    def swap_panes(self, pane_id_1: str, pane_id_2: str) -> bool:
        """
        Swap two panes.

        Args:
            pane_id_1: First pane ID.
            pane_id_2: Second pane ID.

        Returns:
            True if successful.
        """
        raise NotImplementedError("Swap not supported by this provider")

    def select_pane(self, pane_id: str) -> bool:
        """
        Select/focus a pane.

        Args:
            pane_id: Pane to select.

        Returns:
            True if successful.
        """
        raise NotImplementedError("Select not supported by this provider")
