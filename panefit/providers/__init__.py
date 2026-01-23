"""
Panefit providers.

Providers abstract the interaction with different terminal multiplexers
and environments.

Note: Terminal-specific providers (e.g., TmuxProvider) are in integrations/.
"""

from .base import Provider
from .generic import GenericProvider

__all__ = ["Provider", "GenericProvider"]
