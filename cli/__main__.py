#!/usr/bin/env python3
"""
Panefit CLI - Content-aware intelligent pane layout.

Usage:
    panefit reflow [--strategy=<s>] [--dry-run] [--json]
    panefit analyze [--json]
    panefit mcp-server [--port=<p>]
    panefit config [show|init|path]
    panefit --version
    panefit --help
"""

import argparse
import json
import sys
from typing import Optional

from panefit import Analyzer, LayoutCalculator, SessionOptimizer, __version__
from panefit.providers import TmuxProvider
from panefit.llm import LLMManager


def cmd_reflow(args):
    """Reflow panes based on content analysis."""
    try:
        provider = TmuxProvider()
        if not provider.is_available():
            print("Error: Not in a tmux session", file=sys.stderr)
            return 1

        panes = provider.get_panes()
        if len(panes) < 2:
            result = {"status": "skipped", "message": "Need at least 2 panes"}
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                print(f"Skipped: {result['message']}")
            return 0

        # Analyze
        analyzer = Analyzer()
        analyses = analyzer.analyze_panes(panes)

        # LLM enhancement if enabled
        if args.llm:
            llm = LLMManager()
            if llm.is_available():
                for pane in panes:
                    llm_result = llm.analyze_content(pane.content)
                    if llm_result:
                        analysis = analyses[pane.id]
                        analysis.importance_score = (
                            0.6 * analysis.importance_score +
                            0.4 * llm_result.importance_score
                        )
                        analysis.interestingness_score = (
                            0.6 * analysis.interestingness_score +
                            0.4 * llm_result.interestingness_score
                        )

        # Calculate layout
        width, height = provider.get_window_size()
        calc = LayoutCalculator(strategy=args.strategy or "balanced")
        layout = calc.calculate(panes, analyses, width, height)

        # Apply
        if not args.dry_run:
            provider.apply_layout(layout)

        # Output
        result = {
            "status": "applied" if not args.dry_run else "calculated",
            "window": {"width": width, "height": height},
            "panes": []
        }

        for pane in panes:
            analysis = analyses[pane.id]
            pane_layout = layout.get_pane(pane.id)
            result["panes"].append({
                "id": pane.id,
                "command": pane.command,
                "importance": round(analysis.importance_score, 3),
                "interestingness": round(analysis.interestingness_score, 3),
                "layout": {
                    "width": pane_layout.width if pane_layout else pane.width,
                    "height": pane_layout.height if pane_layout else pane.height,
                }
            })

        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"Status: {result['status']}")
            for p in result["panes"]:
                print(f"  {p['id']}: importance={p['importance']:.2f}, "
                      f"size={p['layout']['width']}x{p['layout']['height']}")

        return 0

    except Exception as e:
        if args.json:
            print(json.dumps({"status": "error", "message": str(e)}))
        else:
            print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_analyze(args):
    """Analyze panes without changing layout."""
    try:
        provider = TmuxProvider()
        if not provider.is_available():
            print("Error: Not in a tmux session", file=sys.stderr)
            return 1

        panes = provider.get_panes()
        analyzer = Analyzer()
        results = analyzer.analyze_panes(panes)

        output = {"panes": []}
        for pane in panes:
            analysis = results[pane.id]
            output["panes"].append({
                "id": pane.id,
                "command": pane.command,
                "active": pane.active,
                "metrics": {
                    "importance": round(analysis.importance_score, 3),
                    "interestingness": round(analysis.interestingness_score, 3),
                    "char_entropy": round(analysis.char_entropy, 3),
                    "word_entropy": round(analysis.word_entropy, 3),
                    "surprisal": round(analysis.surprisal_score, 3),
                    "activity": round(analysis.recent_activity_score, 3),
                    "word_count": analysis.word_count,
                    "line_count": analysis.line_count,
                }
            })

        if args.json:
            print(json.dumps(output, indent=2))
        else:
            for p in output["panes"]:
                print(f"\nPane {p['id']} ({p['command']})")
                print(f"  Active: {p['active']}")
                m = p["metrics"]
                print(f"  Importance: {m['importance']:.3f}")
                print(f"  Interestingness: {m['interestingness']:.3f}")
                print(f"  Entropy: {m['char_entropy']:.3f}")
                print(f"  Activity: {m['activity']:.3f}")
                print(f"  Words: {m['word_count']}, Lines: {m['line_count']}")

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_mcp_server(args):
    """Start MCP server."""
    try:
        from panefit.integrations.mcp import serve
        serve(port=args.port)
        return 0
    except ImportError:
        print("MCP server module not found", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_session(args):
    """Session-wide optimization (cross-window)."""
    try:
        optimizer = SessionOptimizer()
        if not optimizer.provider.is_available():
            print("Error: Not in a tmux session", file=sys.stderr)
            return 1

        if args.session_action == "analyze":
            result = optimizer.analyze_session()

        elif args.session_action == "optimize":
            result = optimizer.optimize(dry_run=args.dry_run)

        elif args.session_action == "consolidate":
            if not args.pane:
                print("Error: --pane required for consolidate", file=sys.stderr)
                return 1
            result = optimizer.consolidate_related(args.pane, dry_run=args.dry_run)

        elif args.session_action == "park":
            result = optimizer.park_inactive(
                window_name=args.window_name or "parked",
                dry_run=args.dry_run
            )

        else:
            result = optimizer.analyze_session()

        if args.json:
            print(json.dumps(result, indent=2))
        else:
            if "error" in result:
                print(f"Error: {result['error']}")
                return 1

            if args.session_action == "analyze":
                print(f"Session: {result['pane_count']} panes in {result['window_count']} windows")
                print("\nPanes:")
                for p in result["panes"]:
                    print(f"  {p['id']} ({p['command']}): importance={p['importance']:.2f}")
                print("\nSuggested groups:")
                for g in result["suggested_groups"]:
                    print(f"  {g['name']}: {', '.join(g['panes'])} ({g['topic']})")

            elif "proposed_moves" in result:
                print(f"Status: {result['status']}")
                print(f"Proposed moves: {result['move_count']}")
                for move in result.get("proposed_moves", []):
                    print(f"  {move['pane']}: {move['from']} -> {move['to']}")

            elif "moves" in result:
                print(f"Status: {result['status']}")
                print(f"Reference: {result.get('reference_pane', 'N/A')}")
                print(f"Related: {', '.join(result.get('related_panes', []))}")
                for move in result.get("moves", []):
                    status = " (done)" if move.get("success") else ""
                    print(f"  {move['pane']}: {move['from']} -> {move['to']}{status}")

            elif "to_park" in result:
                print(f"Status: {result['status']}")
                print(f"To park: {len(result.get('to_park', []))} panes")
                for p in result.get("to_park", []):
                    print(f"  {p['id']} ({p['command']}): importance={p['importance']:.2f}")

        return 0

    except Exception as e:
        if args.json:
            print(json.dumps({"error": str(e)}))
        else:
            print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_config(args):
    """Configuration management."""
    import os
    from pathlib import Path

    config_path = Path(os.environ.get("XDG_CONFIG_HOME", "~/.config")).expanduser() / "panefit" / "config.json"

    if args.config_action == "path":
        print(config_path)
    elif args.config_action == "show":
        if config_path.exists():
            print(config_path.read_text())
        else:
            print("{}")
    elif args.config_action == "init":
        if config_path.exists():
            print(f"Config already exists: {config_path}")
        else:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text(json.dumps({
                "llm": {"enabled": False, "provider": "auto"},
                "layout": {"strategy": "balanced", "min_width": 20, "min_height": 5},
            }, indent=2))
            print(f"Created: {config_path}")
    else:
        print("Usage: panefit config [show|init|path]")

    return 0


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="panefit",
        description="Content-aware intelligent pane layout"
    )
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command")

    # reflow
    p_reflow = subparsers.add_parser("reflow", help="Reflow panes based on content")
    p_reflow.add_argument("-s", "--strategy", help="Layout strategy")
    p_reflow.add_argument("-n", "--dry-run", action="store_true", help="Don't apply changes")
    p_reflow.add_argument("-j", "--json", action="store_true", help="JSON output")
    p_reflow.add_argument("--llm", action="store_true", help="Use LLM analysis")

    # analyze
    p_analyze = subparsers.add_parser("analyze", help="Analyze panes")
    p_analyze.add_argument("-j", "--json", action="store_true", help="JSON output")

    # mcp-server
    p_mcp = subparsers.add_parser("mcp-server", help="Start MCP server")
    p_mcp.add_argument("-p", "--port", type=int, default=0, help="Port (0 for stdio)")

    # session (cross-window optimization)
    p_session = subparsers.add_parser("session", help="Cross-window session optimization")
    p_session.add_argument("session_action", nargs="?", default="analyze",
                           choices=["analyze", "optimize", "consolidate", "park"],
                           help="Action: analyze, optimize, consolidate, park")
    p_session.add_argument("-n", "--dry-run", action="store_true", help="Don't apply changes")
    p_session.add_argument("-j", "--json", action="store_true", help="JSON output")
    p_session.add_argument("--pane", help="Reference pane ID (for consolidate)")
    p_session.add_argument("--window-name", help="Window name (for park)")

    # config
    p_config = subparsers.add_parser("config", help="Configuration")
    p_config.add_argument("config_action", nargs="?", default="show",
                          choices=["show", "init", "path"])

    args = parser.parse_args()

    if args.command == "reflow":
        return cmd_reflow(args)
    elif args.command == "analyze":
        return cmd_analyze(args)
    elif args.command == "session":
        return cmd_session(args)
    elif args.command == "mcp-server":
        return cmd_mcp_server(args)
    elif args.command == "config":
        return cmd_config(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
