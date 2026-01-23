"""
Panefit MCP Server implementation.

Exposes panefit functionality via Model Context Protocol for use with
Claude Code and other MCP-compatible applications.
"""

import json
import sys
from typing import Any, Optional

from panefit import (
    Analyzer, LayoutCalculator, PaneData,
    LayoutStrategy, LayoutType
)
from panefit.providers import TmuxProvider, GenericProvider


class PanefitMCPServer:
    """MCP Server for Panefit."""

    def __init__(self):
        self.analyzer = Analyzer()
        self._tmux_provider = None

    @property
    def tmux(self) -> Optional[TmuxProvider]:
        """Lazy-load tmux provider."""
        if self._tmux_provider is None:
            provider = TmuxProvider()
            if provider.is_available():
                self._tmux_provider = provider
        return self._tmux_provider

    def get_tools(self) -> list[dict]:
        """Return list of available MCP tools."""
        return [
            {
                "name": "panefit_analyze",
                "description": "Analyze pane contents and return importance/interestingness metrics. Can analyze tmux panes automatically or accept custom pane data.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "panes": {
                            "type": "array",
                            "description": "Optional: Custom pane data. If not provided, reads from tmux.",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "string"},
                                    "content": {"type": "string"},
                                },
                                "required": ["id", "content"]
                            }
                        }
                    }
                }
            },
            {
                "name": "panefit_calculate_layout",
                "description": "Calculate optimal pane layout based on content analysis.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "panes": {
                            "type": "array",
                            "description": "Pane data with content",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "string"},
                                    "content": {"type": "string"},
                                    "width": {"type": "integer"},
                                    "height": {"type": "integer"},
                                },
                                "required": ["id", "content"]
                            }
                        },
                        "window_width": {"type": "integer", "default": 200},
                        "window_height": {"type": "integer", "default": 50},
                        "strategy": {
                            "type": "string",
                            "enum": ["importance", "entropy", "activity", "balanced", "related"],
                            "default": "balanced"
                        },
                        "layout_type": {
                            "type": "string",
                            "enum": ["auto", "horizontal", "vertical", "tiled"],
                            "default": "auto"
                        }
                    },
                    "required": ["panes"]
                }
            },
            {
                "name": "panefit_reflow",
                "description": "Analyze tmux panes and apply optimal layout. Only works when running in tmux.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "strategy": {
                            "type": "string",
                            "enum": ["importance", "entropy", "activity", "balanced", "related"],
                            "default": "balanced"
                        },
                        "dry_run": {
                            "type": "boolean",
                            "description": "If true, calculate but don't apply layout",
                            "default": False
                        }
                    }
                }
            },
            {
                "name": "panefit_get_strategies",
                "description": "Get list of available layout strategies with descriptions.",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            }
        ]

    def handle_tool_call(self, name: str, arguments: dict) -> dict:
        """Handle a tool call."""
        try:
            if name == "panefit_analyze":
                return self._tool_analyze(arguments)
            elif name == "panefit_calculate_layout":
                return self._tool_calculate_layout(arguments)
            elif name == "panefit_reflow":
                return self._tool_reflow(arguments)
            elif name == "panefit_get_strategies":
                return self._tool_get_strategies()
            else:
                return {"error": f"Unknown tool: {name}"}
        except Exception as e:
            return {"error": str(e)}

    def _tool_analyze(self, args: dict) -> dict:
        """Analyze pane contents."""
        if "panes" in args and args["panes"]:
            panes = [
                PaneData(
                    id=p["id"],
                    content=p["content"],
                    width=p.get("width", 80),
                    height=p.get("height", 24)
                )
                for p in args["panes"]
            ]
        elif self.tmux:
            panes = self.tmux.get_panes()
        else:
            return {"error": "No panes provided and tmux not available"}

        results = self.analyzer.analyze_panes(panes)

        return {
            "panes": [
                {
                    "id": pane.id,
                    "command": pane.command,
                    "active": pane.active,
                    "metrics": {
                        "importance": round(results[pane.id].importance_score, 3),
                        "interestingness": round(results[pane.id].interestingness_score, 3),
                        "entropy": round(results[pane.id].char_entropy, 3),
                        "activity": round(results[pane.id].recent_activity_score, 3),
                        "word_count": results[pane.id].word_count,
                    }
                }
                for pane in panes
            ]
        }

    def _tool_calculate_layout(self, args: dict) -> dict:
        """Calculate optimal layout."""
        panes = [
            PaneData(
                id=p["id"],
                content=p["content"],
                width=p.get("width", 80),
                height=p.get("height", 24)
            )
            for p in args["panes"]
        ]

        results = self.analyzer.analyze_panes(panes)

        calc = LayoutCalculator(
            strategy=args.get("strategy", "balanced"),
            min_width=20,
            min_height=5
        )

        layout = calc.calculate(
            panes=panes,
            analyses=results,
            window_width=args.get("window_width", 200),
            window_height=args.get("window_height", 50),
            layout_type=args.get("layout_type", "auto")
        )

        return {
            "window": {
                "width": layout.window_width,
                "height": layout.window_height
            },
            "strategy": layout.strategy.value,
            "panes": [
                {
                    "id": p.id,
                    "x": p.x,
                    "y": p.y,
                    "width": p.width,
                    "height": p.height,
                    "area_ratio": round(p.area / (layout.window_width * layout.window_height), 3)
                }
                for p in layout.panes
            ]
        }

    def _tool_reflow(self, args: dict) -> dict:
        """Reflow tmux panes."""
        if not self.tmux:
            return {"error": "Not running in tmux session"}

        panes = self.tmux.get_panes()
        if len(panes) < 2:
            return {"status": "skipped", "message": "Need at least 2 panes"}

        results = self.analyzer.analyze_panes(panes)
        width, height = self.tmux.get_window_size()

        calc = LayoutCalculator(strategy=args.get("strategy", "balanced"))
        layout = calc.calculate(panes, results, width, height)

        if not args.get("dry_run", False):
            self.tmux.apply_layout(layout)

        return {
            "status": "applied" if not args.get("dry_run") else "calculated",
            "panes": [
                {
                    "id": p.id,
                    "importance": round(results[p.id].importance_score, 3),
                    "new_size": f"{layout.get_pane(p.id).width}x{layout.get_pane(p.id).height}"
                    if layout.get_pane(p.id) else "unchanged"
                }
                for p in panes
            ]
        }

    def _tool_get_strategies(self) -> dict:
        """Get available strategies."""
        return {
            "strategies": [
                {
                    "name": "balanced",
                    "description": "Weighted combination: 40% importance, 30% interestingness, 30% activity"
                },
                {
                    "name": "importance",
                    "description": "Focus on content amount, code keywords, vocabulary richness"
                },
                {
                    "name": "entropy",
                    "description": "Information density - higher entropy content gets more space"
                },
                {
                    "name": "activity",
                    "description": "Recent activity - shell prompts, running commands"
                },
                {
                    "name": "related",
                    "description": "Groups related panes together based on shared topics"
                }
            ]
        }


def serve(port: int = 0):
    """
    Start MCP server.

    Args:
        port: Port number. 0 for stdio transport.
    """
    server = PanefitMCPServer()

    if port == 0:
        # Stdio transport
        _serve_stdio(server)
    else:
        # HTTP transport (simplified)
        _serve_http(server, port)


def _serve_stdio(server: PanefitMCPServer):
    """Serve via stdio (JSON-RPC over stdin/stdout)."""
    sys.stderr.write("Panefit MCP Server started (stdio)\n")

    for line in sys.stdin:
        try:
            request = json.loads(line)
            response = _handle_request(server, request)
            print(json.dumps(response), flush=True)
        except json.JSONDecodeError:
            print(json.dumps({"error": "Invalid JSON"}), flush=True)
        except Exception as e:
            print(json.dumps({"error": str(e)}), flush=True)


def _serve_http(server: PanefitMCPServer, port: int):
    """Serve via HTTP."""
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import json

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode()

            try:
                request = json.loads(body)
                response = _handle_request(server, request)
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())

        def log_message(self, format, *args):
            sys.stderr.write(f"[MCP] {args[0]}\n")

    httpd = HTTPServer(('localhost', port), Handler)
    sys.stderr.write(f"Panefit MCP Server started on port {port}\n")
    httpd.serve_forever()


def _handle_request(server: PanefitMCPServer, request: dict) -> dict:
    """Handle MCP request."""
    method = request.get("method", "")
    params = request.get("params", {})
    request_id = request.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "panefit",
                    "version": "0.1.0"
                }
            }
        }

    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": server.get_tools()
            }
        }

    elif method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})
        result = server.handle_tool_call(tool_name, tool_args)
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(result, indent=2)
                    }
                ]
            }
        }

    else:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": -32601,
                "message": f"Method not found: {method}"
            }
        }


if __name__ == "__main__":
    serve()
