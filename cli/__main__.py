#!/usr/bin/env python3
"""
Panefit CLI - Content-aware intelligent pane layout.

Usage:
    panefit reflow [--strategy=<s>] [--dry-run] [--json]
    panefit analyze [--json]
    panefit session [analyze|optimize|consolidate|park] [options]
    panefit mcp-server [--port=<p>]
    panefit config [show|init|path|set]
    panefit --version
    panefit --help
"""

import argparse
import json
import sys

from panefit import (
    Analyzer,
    LayoutCalculator,
    SessionOptimizer,
    __version__,
    load_config,
    save_config,
    get_config_path,
    PanefitConfig,
)
from panefit.providers import TmuxProvider
from panefit.llm import LLMManager


def get_llm_manager(config: PanefitConfig) -> LLMManager:
    """Create LLMManager from config."""
    llm_cfg = config.llm
    return LLMManager(
        ollama_model=llm_cfg.ollama_model if llm_cfg.provider in ("auto", "ollama") else None,
        preferred_provider=llm_cfg.provider if llm_cfg.provider != "auto" else None,
    )


def cmd_reflow(args, config: PanefitConfig):
    """Reflow panes based on content analysis."""
    try:
        provider = TmuxProvider(history_lines=config.tmux.history_lines)
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

        # LLM enhancement (from config or CLI flag)
        use_llm = args.llm or config.llm.enabled
        if use_llm:
            llm = get_llm_manager(config)
            if llm.is_available():
                blend = config.llm.blend_ratio
                for pane in panes:
                    llm_result = llm.analyze_content(pane.content)
                    if llm_result:
                        analysis = analyses[pane.id]
                        analysis.importance_score = (
                            (1 - blend) * analysis.importance_score +
                            blend * llm_result.importance_score
                        )
                        analysis.interestingness_score = (
                            (1 - blend) * analysis.interestingness_score +
                            blend * llm_result.interestingness_score
                        )

        # Calculate layout
        width, height = provider.get_window_size()
        strategy = args.strategy or config.layout.strategy
        calc = LayoutCalculator(
            strategy=strategy,
            min_width=config.layout.min_width,
            min_height=config.layout.min_height,
        )
        layout = calc.calculate(panes, analyses, width, height)

        # Apply
        if not args.dry_run:
            provider.apply_layout(layout)

        # Output
        result = {
            "status": "applied" if not args.dry_run else "calculated",
            "strategy": strategy,
            "llm_enabled": use_llm,
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
            print(f"Status: {result['status']} (strategy: {strategy})")
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


def cmd_analyze(args, config: PanefitConfig):
    """Analyze panes without changing layout."""
    try:
        provider = TmuxProvider(history_lines=config.tmux.history_lines)
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


def cmd_mcp_server(args, config: PanefitConfig):
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


def cmd_session(args, config: PanefitConfig):
    """Session-wide optimization (cross-window)."""
    if not config.session.enabled:
        print("Session optimization is disabled in config", file=sys.stderr)
        return 1

    try:
        optimizer = SessionOptimizer(
            relevance_threshold=config.session.relevance_threshold,
            importance_threshold=config.session.importance_threshold,
        )
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
            window_name = args.window_name or config.session.park_window_name
            result = optimizer.park_inactive(
                window_name=window_name,
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


def cmd_config(args, config: PanefitConfig):
    """Configuration management."""
    config_path = get_config_path()

    if args.config_action == "path":
        print(config_path)

    elif args.config_action == "show":
        print(json.dumps(config.to_dict(), indent=2))

    elif args.config_action == "init":
        if config_path.exists() and not args.force:
            print(f"Config already exists: {config_path}")
            print("Use --force to overwrite")
        else:
            save_config(PanefitConfig(), config_path)
            print(f"Created: {config_path}")

    elif args.config_action == "set":
        if not args.key or args.value is None:
            print("Usage: panefit config set --key <key> --value <value>")
            print("Examples:")
            print("  panefit config set --key llm.enabled --value true")
            print("  panefit config set --key layout.strategy --value importance")
            return 1

        # Parse key path (e.g., "llm.enabled")
        parts = args.key.split(".")
        if len(parts) != 2:
            print("Key must be in format: section.field (e.g., llm.enabled)")
            return 1

        section, field = parts
        data = config.to_dict()

        if section not in data:
            print(f"Unknown section: {section}")
            return 1
        if field not in data[section]:
            print(f"Unknown field: {field} in section {section}")
            return 1

        # Parse value
        value = args.value
        if value.lower() == "true":
            value = True
        elif value.lower() == "false":
            value = False
        elif value.isdigit():
            value = int(value)
        else:
            try:
                value = float(value)
            except ValueError:
                pass  # Keep as string

        data[section][field] = value
        new_config = PanefitConfig.from_dict(data)
        save_config(new_config, config_path)
        print(f"Set {args.key} = {value}")

    else:
        print("Usage: panefit config [show|init|path|set]")

    return 0


def main():
    """CLI entry point."""
    # Load config first
    config = load_config()

    parser = argparse.ArgumentParser(
        prog="panefit",
        description="Content-aware intelligent pane layout"
    )
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command")

    # reflow
    p_reflow = subparsers.add_parser("reflow", help="Reflow panes based on content")
    p_reflow.add_argument("-s", "--strategy", help="Layout strategy (overrides config)")
    p_reflow.add_argument("-n", "--dry-run", action="store_true", help="Don't apply changes")
    p_reflow.add_argument("-j", "--json", action="store_true", help="JSON output")
    p_reflow.add_argument("--llm", action="store_true", help="Use LLM analysis (overrides config)")

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
    p_config = subparsers.add_parser("config", help="Configuration management")
    p_config.add_argument("config_action", nargs="?", default="show",
                          choices=["show", "init", "path", "set"])
    p_config.add_argument("--key", help="Config key (e.g., llm.enabled)")
    p_config.add_argument("--value", help="Config value")
    p_config.add_argument("--force", action="store_true", help="Force overwrite")

    args = parser.parse_args()

    if args.command == "reflow":
        return cmd_reflow(args, config)
    elif args.command == "analyze":
        return cmd_analyze(args, config)
    elif args.command == "session":
        return cmd_session(args, config)
    elif args.command == "mcp-server":
        return cmd_mcp_server(args, config)
    elif args.command == "config":
        return cmd_config(args, config)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
