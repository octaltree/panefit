#!/usr/bin/env python3
"""
Panefit tmux reflow command.

Uses the panefit library directly (no CLI).
"""

import sys
import os

# Add parent directories to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from panefit import Analyzer, LayoutCalculator, load_config, LayoutOperation, SessionOptimizer
from panefit.llm import LLMManager
from integrations.tmux import TmuxProvider


def reflow(dry_run: bool = False, strategy: str = None) -> dict:
    """
    Analyze and reflow tmux panes in current window.

    Args:
        dry_run: If True, calculate but don't apply.
        strategy: Layout strategy override.

    Returns:
        Dict with before/after info.
    """
    provider = TmuxProvider()

    if not provider.is_available():
        return {"error": "Not in tmux session"}

    config = load_config()
    panes = provider.get_panes()
    if len(panes) < 2:
        return {"status": "skipped", "message": "Need 2+ panes"}

    # Analyze and calculate
    before = {p.id: (p.width, p.height) for p in panes}
    analyzer = Analyzer()
    analyses = analyzer.analyze_panes(panes)

    width, height = provider.get_window_size()
    calc = LayoutCalculator(
        strategy=strategy or config.layout.strategy,
        min_width=config.layout.min_width,
        min_height=config.layout.min_height,
    )
    layout = calc.calculate(panes, analyses, width, height)

    # Plan and execute
    plan = provider.plan_layout(layout)

    if not dry_run:
        provider.execute_plan(plan)

    # Collect results
    results = []
    for pane in panes:
        pane_layout = layout.get_pane(pane.id)
        if pane_layout:
            results.append({
                "id": pane.id,
                "before": f"{before[pane.id][0]}x{before[pane.id][1]}",
                "after": f"{pane_layout.width}x{pane_layout.height}@({pane_layout.x},{pane_layout.y})",
            })

    return {
        "status": "dry_run" if dry_run else "applied",
        "panes": results,
    }


def session_analyze() -> dict:
    """Analyze all panes across all windows."""
    provider = TmuxProvider()

    if not provider.is_available():
        return {"error": "Not in tmux session"}

    config = load_config()
    optimizer = SessionOptimizer(
        provider=provider,
        relevance_threshold=config.session.relevance_threshold,
        importance_threshold=config.session.importance_threshold
    )

    return optimizer.analyze_session()


def session_optimize(dry_run: bool = True) -> dict:
    """Optimize pane arrangement across windows."""
    provider = TmuxProvider()

    if not provider.is_available():
        return {"error": "Not in tmux session"}

    config = load_config()
    optimizer = SessionOptimizer(
        provider=provider,
        relevance_threshold=config.session.relevance_threshold,
        importance_threshold=config.session.importance_threshold
    )

    return optimizer.optimize(dry_run=dry_run)


def session_park(dry_run: bool = True) -> dict:
    """Park low-importance panes to a separate window."""
    provider = TmuxProvider()

    if not provider.is_available():
        return {"error": "Not in tmux session"}

    config = load_config()
    optimizer = SessionOptimizer(
        provider=provider,
        relevance_threshold=config.session.relevance_threshold,
        importance_threshold=config.session.importance_threshold
    )

    return optimizer.park_inactive(
        window_name=config.session.park_window_name,
        dry_run=dry_run
    )


def format_result(result: dict, command: str = "reflow") -> str:
    """Format result for tmux display-message."""
    if "error" in result:
        return f"Error: {result['error']}"

    if result.get("status") == "skipped":
        return result.get("message", "Skipped")

    if command == "session-analyze":
        return f"{result.get('pane_count', 0)} panes in {result.get('window_count', 0)} windows, {len(result.get('suggested_groups', []))} groups"

    if command in ("session-optimize", "session-park"):
        moves = result.get("proposed_moves", result.get("to_park", []))
        prefix = "[dry-run] " if result.get("status") in ("calculated", "dry_run") else ""
        if not moves:
            return f"{prefix}No changes needed"
        return f"{prefix}{len(moves)} moves proposed"

    # reflow/dry-run
    panes = result.get("panes", [])
    prefix = "[dry-run] " if result.get("status") == "dry_run" else ""

    parts = [f"{p['id']}: {p['before']} -> {p['after']}" for p in panes]
    return f"{prefix}{' | '.join(parts)}" if parts else f"{prefix}No changes"


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Panefit tmux reflow")
    parser.add_argument("command",
                       choices=["reflow", "dry-run", "session-analyze", "session-optimize", "session-park"],
                       default="reflow", nargs="?")
    parser.add_argument("-s", "--strategy", help="Layout strategy")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress output")
    parser.add_argument("--apply", action="store_true", help="Apply changes (for session commands)")

    args = parser.parse_args()

    if args.command == "reflow":
        result = reflow(dry_run=False, strategy=args.strategy)
    elif args.command == "dry-run":
        result = reflow(dry_run=True, strategy=args.strategy)
    elif args.command == "session-analyze":
        result = session_analyze()
    elif args.command == "session-optimize":
        result = session_optimize(dry_run=not args.apply)
    elif args.command == "session-park":
        result = session_park(dry_run=not args.apply)
    else:
        result = {"error": f"Unknown command: {args.command}"}

    if not args.quiet:
        print(format_result(result, args.command))

    return 0 if "error" not in result else 1


if __name__ == "__main__":
    sys.exit(main())
