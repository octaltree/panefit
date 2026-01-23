#!/usr/bin/env python3
"""
Panefit tmux reflow command.

Uses the panefit library directly (no CLI).
"""

import sys
import os

# Add parent directories to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from panefit import Analyzer, LayoutCalculator, SessionOptimizer, load_config, LayoutOperation
from panefit.llm import LLMManager
from integrations.tmux import TmuxProvider


def reflow(dry_run: bool = False, strategy: str = None) -> dict:
    """
    Analyze and reflow tmux panes.

    Args:
        dry_run: If True, calculate but don't apply.
        strategy: Layout strategy override.

    Returns:
        Dict with before/after info.
    """
    provider = TmuxProvider()

    if not provider.is_available():
        return {"error": "Not in tmux session"}

    panes = provider.get_panes()
    if len(panes) < 2:
        return {"status": "skipped", "message": "Need at least 2 panes"}

    # Load config
    config = load_config()

    # Get before sizes
    before = {p.id: (p.width, p.height) for p in panes}

    # Analyze
    analyzer = Analyzer()
    analyses = analyzer.analyze_panes(panes)

    # LLM enhancement if enabled
    if config.llm.enabled:
        llm = LLMManager(
            gemini_key=config.llm.gemini_api_key if hasattr(config.llm, 'gemini_api_key') else None,
            preferred_provider=config.llm.provider if config.llm.provider != "auto" else None,
        )
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
    calc = LayoutCalculator(
        strategy=strategy or config.layout.strategy,
        min_width=config.layout.min_width,
        min_height=config.layout.min_height,
    )
    layout = calc.calculate(panes, analyses, width, height)

    # Get after sizes and positions
    after = {}
    for pane_layout in layout.panes:
        after[pane_layout.id] = {
            "width": pane_layout.width,
            "height": pane_layout.height,
            "x": pane_layout.x,
            "y": pane_layout.y,
        }

    # Plan the transformation
    plan = provider.plan_layout(layout)

    result = {
        "status": "dry_run" if dry_run else "applied",
        "panes": [],
        "operations": [],
    }

    for pane in panes:
        pane_info = {
            "id": pane.id,
            "before": f"{before[pane.id][0]}x{before[pane.id][1]}",
            "after": f"{after[pane.id]['width']}x{after[pane.id]['height']}@({after[pane.id]['x']},{after[pane.id]['y']})",
            "importance": round(analyses[pane.id].importance_score, 3),
        }
        result["panes"].append(pane_info)

    # Include operations in result
    for step in plan.steps:
        if step.operation == LayoutOperation.SWAP:
            result["operations"].append(f"swap({step.pane_id},{step.target_id})")
        elif step.operation == LayoutOperation.RESIZE:
            result["operations"].append(f"resize({step.pane_id},{step.width}x{step.height})")

    # Apply if not dry run
    if not dry_run:
        provider.execute_plan(plan)

    return result


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
    ops = result.get("operations", [])
    swap_count = len([o for o in ops if o.startswith("swap")])

    parts = []
    for p in result.get("panes", []):
        parts.append(f"{p['id']}: {p['before']} -> {p['after']}")

    prefix = "[dry-run] " if result.get("status") == "dry_run" else ""
    op_info = f" ({swap_count} swaps)" if swap_count > 0 else ""
    return f"{prefix}{' | '.join(parts)}{op_info}"


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
