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

## Install

```bash
pip install panefit
```

## Usage

### tmux: One Key

Add to `~/.tmux.conf`:

```tmux
run-shell /path/to/panefit/integrations/tmux/panefit.tmux
```

Press `prefix + R`. Done.

### CLI: One Command

```bash
panefit reflow
```

### Library: A Few Lines

```python
from panefit import Analyzer, LayoutCalculator, PaneData

panes = [
    PaneData(id="1", content="def main():\n    print('hello')", width=80, height=24),
    PaneData(id="2", content="$ _", width=80, height=24),
]

analyzer = Analyzer()
results = analyzer.analyze_panes(panes)

calc = LayoutCalculator()
layout = calc.calculate(panes, results, window_width=200, window_height=50)
# Pane 1: 124x50, Pane 2: 76x50
```

### Claude Code: MCP Server

```json
{
  "mcpServers": {
    "panefit": {
      "command": "panefit",
      "args": ["mcp-server"]
    }
  }
}
```

Then ask Claude: *"Optimize my terminal layout"*

## How It Works

Panefit scores each pane based on:

| Metric | What it measures |
|--------|-----------------|
| **Entropy** | Information density |
| **Surprisal** | Unpredictability (interesting content) |
| **Activity** | Recent commands, shell prompts |
| **Keywords** | Code patterns, tech terms |

Higher scores = more screen space.

## Strategies

```bash
panefit reflow --strategy balanced   # (default) Mix of all factors
panefit reflow --strategy importance # Content-focused
panefit reflow --strategy activity   # Favor active panes
panefit reflow --strategy entropy    # Information density
```

## LLM Enhancement

For semantic analysis:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
panefit reflow --llm
```

Supports OpenAI, Anthropic, and local Ollama.

## Requirements

- Python 3.8+
- tmux 2.6+ (for tmux integration)

## Links

- [Development Guide](CLAUDE.md) - API details, extending, algorithms
- [Issues](https://github.com/username/panefit/issues)

## License

MIT
