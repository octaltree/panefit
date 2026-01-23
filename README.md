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

## Configuration

Works without any config (zero-config). Optionally customize via config file.

**Priority** (highest to lowest):
1. CLI arguments (`--strategy`)
2. Environment variables (`PANEFIT_STRATEGY`)
3. Config file
4. Defaults

### Config File Location

```
Linux:   ~/.config/panefit/config.json
macOS:   ~/Library/Application Support/panefit/config.json
Windows: %APPDATA%\panefit\config.json
```

```bash
panefit config path       # Show config file path
panefit config path --dir # Show config directory
panefit config init       # Create default config
panefit config show       # Show current settings
```

### Config Schema

```json
{
  "layout": {
    "strategy": "balanced",
    "layout_type": "auto",
    "min_width": 20,
    "min_height": 5
  },
  "llm": {
    "enabled": false,
    "provider": "auto",
    "blend_ratio": 0.4,
    "ollama_model": "llama3.2",
    "ollama_host": "http://localhost:11434",
    "openai_model": "gpt-4o-mini",
    "anthropic_model": "claude-3-haiku-20240307"
  },
  "session": {
    "enabled": true,
    "relevance_threshold": 0.3,
    "importance_threshold": 0.2,
    "auto_park": false,
    "park_window_name": "parked"
  }
}
```

| Section | Key | Values | Description |
|---------|-----|--------|-------------|
| `layout` | `strategy` | `balanced`, `importance`, `entropy`, `activity`, `related` | Layout algorithm |
| | `layout_type` | `auto`, `horizontal`, `vertical`, `tiled` | Pane arrangement |
| | `min_width` | int | Minimum pane width |
| | `min_height` | int | Minimum pane height |
| `llm` | `enabled` | bool | Enable LLM analysis |
| | `provider` | `auto`, `openai`, `anthropic`, `ollama` | LLM provider |
| | `blend_ratio` | 0.0-1.0 | LLM weight when blending scores |
| `session` | `enabled` | bool | Enable cross-window operations |
| | `relevance_threshold` | 0.0-1.0 | Min relevance to group panes |
| | `importance_threshold` | 0.0-1.0 | Below this = candidate for parking |

### Environment Variables

```bash
PANEFIT_STRATEGY=importance
PANEFIT_LAYOUT_TYPE=tiled
PANEFIT_LLM_ENABLED=true
PANEFIT_LLM_PROVIDER=ollama
```

## Requirements

- Python 3.8+
- tmux 2.6+ (for tmux integration)

## Links

- [Development Guide](CLAUDE.md) - API details, extending, algorithms
- [Issues](https://github.com/username/panefit/issues)

## License

MIT
