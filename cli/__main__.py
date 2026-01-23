#!/usr/bin/env python3
"""
Panefit CLI - Content-aware intelligent pane layout.

Pure computation: receives pane data, returns layout calculation.

Usage:
    panefit calculate [--strategy=<s>] [--json] < input.json
    panefit analyze [--json] < input.json
    panefit config [show|init|path|set]
    panefit --version
    panefit --help

Input format (JSON):
    {
        "window": {"width": 200, "height": 50},
        "panes": [
            {"id": "1", "content": "...", "width": 80, "height": 24, "active": true},
            {"id": "2", "content": "...", "width": 80, "height": 24}
        ]
    }
"""

import argparse
import json
import sys

from panefit import (
    Analyzer,
    LayoutCalculator,
    PaneData,
    __version__,
    load_config,
    save_config,
    get_config_path,
    PanefitConfig,
)
from panefit.llm import LLMManager


def read_input() -> dict:
    """Read JSON input from stdin."""
    try:
        return json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON input: {e}", file=sys.stderr)
        sys.exit(1)


def get_llm_manager(config: PanefitConfig) -> LLMManager:
    """Create LLMManager from config."""
    llm_cfg = config.llm
    return LLMManager(
        ollama_model=llm_cfg.ollama_model if llm_cfg.provider in ("auto", "ollama") else None,
        preferred_provider=llm_cfg.provider if llm_cfg.provider != "auto" else None,
    )


def input_to_panes(data: dict) -> list[PaneData]:
    """Convert input JSON to PaneData list."""
    panes = []
    for p in data.get("panes", []):
        panes.append(PaneData(
            id=str(p.get("id", "")),
            content=p.get("content", ""),
            width=p.get("width", 80),
            height=p.get("height", 24),
            x=p.get("x", 0),
            y=p.get("y", 0),
            active=p.get("active", False),
            title=p.get("title", ""),
            command=p.get("command", ""),
        ))
    return panes


def cmd_calculate(args, config: PanefitConfig):
    """Calculate layout from input panes."""
    data = read_input()

    window = data.get("window", {})
    window_width = window.get("width", 200)
    window_height = window.get("height", 50)

    panes = input_to_panes(data)
    if not panes:
        print(json.dumps({"error": "No panes provided"}))
        return 1

    # Analyze
    analyzer = Analyzer()
    analyses = analyzer.analyze_panes(panes)

    # LLM enhancement
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
    strategy = args.strategy or config.layout.strategy
    calc = LayoutCalculator(
        strategy=strategy,
        min_width=config.layout.min_width,
        min_height=config.layout.min_height,
    )
    layout = calc.calculate(panes, analyses, window_width, window_height)

    # Output
    result = {
        "window": {"width": window_width, "height": window_height},
        "strategy": strategy,
        "panes": []
    }

    for pane in panes:
        analysis = analyses[pane.id]
        pane_layout = layout.get_pane(pane.id)
        result["panes"].append({
            "id": pane.id,
            "importance": round(analysis.importance_score, 3),
            "interestingness": round(analysis.interestingness_score, 3),
            "layout": {
                "x": pane_layout.x if pane_layout else 0,
                "y": pane_layout.y if pane_layout else 0,
                "width": pane_layout.width if pane_layout else pane.width,
                "height": pane_layout.height if pane_layout else pane.height,
            }
        })

    print(json.dumps(result, indent=2 if not args.compact else None))
    return 0


def cmd_analyze(args, config: PanefitConfig):
    """Analyze panes without calculating layout."""
    data = read_input()

    panes = input_to_panes(data)
    if not panes:
        print(json.dumps({"error": "No panes provided"}))
        return 1

    analyzer = Analyzer()
    results = analyzer.analyze_panes(panes)

    output = {"panes": []}
    for pane in panes:
        analysis = results[pane.id]
        output["panes"].append({
            "id": pane.id,
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

    print(json.dumps(output, indent=2 if not args.compact else None))
    return 0


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
                pass

        data[section][field] = value
        new_config = PanefitConfig.from_dict(data)
        save_config(new_config, config_path)
        print(f"Set {args.key} = {value}")

    else:
        print("Usage: panefit config [show|init|path|set]")

    return 0


def main():
    """CLI entry point."""
    config = load_config()

    parser = argparse.ArgumentParser(
        prog="panefit",
        description="Content-aware intelligent pane layout calculator"
    )
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command")

    # calculate
    p_calc = subparsers.add_parser("calculate", help="Calculate layout from JSON input")
    p_calc.add_argument("-s", "--strategy", help="Layout strategy")
    p_calc.add_argument("--llm", action="store_true", help="Use LLM analysis")
    p_calc.add_argument("-c", "--compact", action="store_true", help="Compact JSON output")

    # analyze
    p_analyze = subparsers.add_parser("analyze", help="Analyze panes from JSON input")
    p_analyze.add_argument("-c", "--compact", action="store_true", help="Compact JSON output")

    # config
    p_config = subparsers.add_parser("config", help="Configuration management")
    p_config.add_argument("config_action", nargs="?", default="show",
                          choices=["show", "init", "path", "set"])
    p_config.add_argument("--key", help="Config key (e.g., llm.enabled)")
    p_config.add_argument("--value", help="Config value")
    p_config.add_argument("--force", action="store_true", help="Force overwrite")

    args = parser.parse_args()

    if args.command == "calculate":
        return cmd_calculate(args, config)
    elif args.command == "analyze":
        return cmd_analyze(args, config)
    elif args.command == "config":
        return cmd_config(args, config)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
