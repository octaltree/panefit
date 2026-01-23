# Panefit

> Your terminal panes, perfectly sized. Automatically.

```
Before                              After
┌──────────┬──────────┐            ┌────────────────┬─────┐
│ editor   │ logs     │            │ editor         │logs │
│ (active) │ (idle)   │   ──►      │ (important!)   │     │
│          │          │            │                │     │
├──────────┼──────────┤            ├────────────────┼─────┤
│ shell    │ htop     │            │ shell (active) │htop │
└──────────┴──────────┘            └────────────────┴─────┘
     Equal sizes                    Content-aware sizes
```

**Panefit** analyzes what's in your panes and gives more space to what matters.

## Why Panefit?

- **Smart sizing** - Active code editor? Gets more space. Idle logs? Shrinks automatically.
- **Zero config** - Works out of the box. Press one key.
- **Multiple interfaces** - Library, CLI, tmux plugin, or MCP server.
- **AI-ready** - Optional LLM integration for semantic analysis.

## Quick Start

```bash
pip install panefit
panefit reflow          # That's it
```

## Interfaces

**tmux** - Add to `~/.tmux.conf`, press `prefix + R`
```tmux
run-shell /path/to/panefit/integrations/tmux/panefit.tmux
```

**CLI** - Direct command
```bash
panefit reflow --strategy balanced
```

**Library** - Programmatic control
```python
from panefit import Analyzer, LayoutCalculator, PaneData

panes = [PaneData(id="1", content="vim...", width=80, height=24)]
results = Analyzer().analyze_panes(panes)
layout = LayoutCalculator().calculate(panes, results, 200, 50)
```

**MCP Server** - For Claude Code
```json
{"mcpServers": {"panefit": {"command": "panefit", "args": ["mcp-server"]}}}
```

## How It Works

Panefit scores each pane by entropy (information density), surprisal (unpredictability), activity (recent commands), and code patterns. Higher scores get more screen space.

## Configuration

**Zero-config by default.** Just run `panefit reflow`.

Want to customize? You can:

```bash
# CLI flags
panefit reflow --strategy importance --llm

# Environment variables
export PANEFIT_STRATEGY=activity

# Config file
panefit config init     # Creates config file
panefit config show     # View current settings
```

Strategies: `balanced` (default), `importance`, `activity`, `entropy`, `related`

See [CLAUDE.md](CLAUDE.md) for full configuration options and API details.

## Requirements

- Python 3.8+
- tmux 2.6+ (for tmux integration)

## Links

- [Development Guide](CLAUDE.md) - API details, extending, algorithms
- [Issues](https://github.com/username/panefit/issues)

## License

MIT
