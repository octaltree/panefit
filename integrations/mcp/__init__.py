"""
Panefit MCP (Model Context Protocol) Server.

Provides panefit functionality to LLM applications like Claude Code.
"""

from .server import serve, PanefitMCPServer

__all__ = ["serve", "PanefitMCPServer"]
