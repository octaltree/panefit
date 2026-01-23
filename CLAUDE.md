# Panefit Development Guide

## Project Structure

```
panefit/
├── panefit/              # Core library (Python package)
│   ├── __init__.py       # Public API exports
│   ├── types.py          # Type definitions (PaneData, AnalysisResult, etc.)
│   ├── analyzer.py       # Content analysis (entropy, surprisal, activity)
│   ├── layout.py         # Layout calculation algorithms
│   ├── providers/        # Terminal multiplexer providers
│   │   ├── base.py       # Abstract Provider interface
│   │   ├── tmux.py       # tmux implementation
│   │   └── generic.py    # Generic/programmatic provider
│   └── llm/              # Optional LLM integration
│       ├── base.py       # LLMProvider interface
│       └── manager.py    # Multi-provider manager
├── cli/                  # CLI application
│   └── __main__.py       # Entry point (panefit command)
├── integrations/
│   ├── tmux/             # tmux plugin
│   │   ├── panefit.tmux  # Plugin entry point
│   │   └── scripts/      # Shell wrappers
│   └── mcp/              # MCP server for Claude Code
│       └── server.py     # JSON-RPC server
├── pyproject.toml        # Package configuration
└── README.md
```

## Core Concepts

### Content Analysis

`panefit.Analyzer` analyzes pane content using:

1. **Shannon Entropy**: Information density at character/word level
2. **Surprisal**: N-gram based unpredictability (how "surprising" the text is)
3. **Activity Detection**: Regex patterns for shell prompts, commands
4. **Code Keyword Ratio**: Presence of programming keywords

Scores are normalized to 0-1 range and combined into:
- `importance_score`: Overall importance (content amount, activity, diversity)
- `interestingness_score`: Semantic interestingness (entropy, surprisal)

### Layout Calculation

`panefit.LayoutCalculator` supports strategies:

| Strategy | Description |
|----------|-------------|
| `balanced` | 40% importance + 30% interestingness + 30% activity |
| `importance` | Pure importance score |
| `entropy` | Pure interestingness (entropy-based) |
| `activity` | Pure recent activity |
| `related` | Groups related panes together |

Layout types: `auto`, `horizontal`, `vertical`, `tiled`

### Providers

Providers abstract terminal multiplexer interaction:

```python
class Provider(ABC):
    def get_panes(self) -> list[PaneData]: ...
    def get_window_size(self) -> tuple[int, int]: ...
    def apply_layout(self, layout: WindowLayout) -> bool: ...
    def resize_pane(self, pane_id, width, height) -> bool: ...
```

- `TmuxProvider`: Interacts with tmux via subprocess
- `GenericProvider`: In-memory, for library usage

## API Usage

### Basic Library Usage

```python
from panefit import Analyzer, LayoutCalculator, PaneData

# Create panes
panes = [
    PaneData(id="1", content="vim editing...", width=80, height=24, active=True),
    PaneData(id="2", content="npm run build...", width=80, height=24),
]

# Analyze
analyzer = Analyzer()
results = analyzer.analyze_panes(panes)

# Calculate layout
calc = LayoutCalculator(strategy="balanced")
layout = calc.calculate(panes, results, window_width=200, window_height=50)

for p in layout.panes:
    print(f"{p.id}: {p.width}x{p.height} at ({p.x},{p.y})")
```

### With tmux Provider

```python
from panefit import Analyzer, LayoutCalculator
from panefit.providers import TmuxProvider

provider = TmuxProvider()
if provider.is_available():
    panes = provider.get_panes()
    width, height = provider.get_window_size()

    analyzer = Analyzer()
    results = analyzer.analyze_panes(panes)

    calc = LayoutCalculator()
    layout = calc.calculate(panes, results, width, height)
    provider.apply_layout(layout)
```

### With LLM Enhancement

```python
from panefit import Analyzer
from panefit.llm import LLMManager

llm = LLMManager(preferred_provider="anthropic")
analyzer = Analyzer()

for pane in panes:
    result = analyzer.analyze_pane(pane)

    if llm.is_available():
        llm_result = llm.analyze_content(pane.content)
        # Blend scores
        result.importance_score = 0.6 * result.importance_score + 0.4 * llm_result.importance_score
```

## MCP Server

The MCP server exposes panefit to Claude Code and other MCP clients.

### Tools Provided

| Tool | Description |
|------|-------------|
| `panefit_analyze` | Analyze pane contents |
| `panefit_calculate_layout` | Calculate optimal layout |
| `panefit_reflow` | Analyze + apply (tmux only) |
| `panefit_get_strategies` | List available strategies |

### Configuration for Claude Code

Add to MCP settings:

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

## tmux Plugin

### Installation

```bash
# In ~/.tmux.conf
run-shell /path/to/panefit/integrations/tmux/panefit.tmux
```

### Options

```tmux
set -g @panefit-key "R"              # Keybinding
set -g @panefit-strategy "balanced"  # Layout strategy
set -g @panefit-llm-enabled "false"  # LLM analysis
set -g @panefit-auto-reflow "false"  # Auto-reflow on focus
```

## Development

### Setup

```bash
git clone https://github.com/username/panefit.git
cd panefit
pip install -e ".[dev]"
```

### Testing

```bash
pytest
pytest --cov=panefit
```

### Type Checking

```bash
mypy panefit
```

### Code Style

```bash
ruff check .
ruff format .
```

## Algorithm Details

### Entropy Calculation

```python
H = -Σ p(x) * log₂(p(x))
```

Character-level entropy ranges 0-5+ (English text typically 4-5).

### Surprisal (N-gram)

Uses trigram model to calculate average surprisal:

```python
Surprisal(word|context) = -log₂ P(word|context)
```

Higher surprisal = more unpredictable content.

### Importance Score Formula

```
importance = 0.2 * content_amount
           + 0.2 * activity_score
           + 0.15 * unique_word_ratio
           + 0.15 * code_keyword_ratio
           + 0.15 * recent_change_score
           + 0.15 * entropy_normalized
```

### Layout Calculation

1. Calculate scores per pane
2. Normalize to sum = 1
3. Allocate space proportionally (respecting min dimensions)
4. Main pane uses golden ratio (φ = 1.618) for tiled layout

## Extending

### Custom Provider

```python
from panefit.providers import Provider
from panefit import PaneData, WindowLayout

class MyProvider(Provider):
    @property
    def name(self) -> str:
        return "my-provider"

    def is_available(self) -> bool:
        return True

    def get_panes(self, window_id=None) -> list[PaneData]:
        # Return your panes
        ...

    def get_window_size(self, window_id=None) -> tuple[int, int]:
        return (200, 50)

    def apply_layout(self, layout: WindowLayout, window_id=None) -> bool:
        # Apply layout to your system
        ...

    def resize_pane(self, pane_id, width=None, height=None) -> bool:
        ...
```

### Custom LLM Provider

```python
from panefit.llm import LLMProvider, LLMAnalysisResult

class MyLLMProvider(LLMProvider):
    @property
    def name(self) -> str:
        return "my-llm"

    def is_available(self) -> bool:
        return True

    def analyze_content(self, content, context=None) -> LLMAnalysisResult:
        # Call your LLM
        return LLMAnalysisResult(
            importance_score=0.7,
            interestingness_score=0.6,
            summary="...",
            topics=["python", "development"],
            predicted_activity="high"
        )
```

## Cross-Window Operations (Optional)

Panefit supports cross-window pane management via `SessionOptimizer`.

### CLI Commands

```bash
# Analyze entire session
panefit session analyze

# Optimize: group related panes into same windows
panefit session optimize --dry-run
panefit session optimize

# Consolidate: move all related panes to same window as reference pane
panefit session consolidate --pane %5

# Park: move low-importance panes to a parking window
panefit session park --window-name archived
```

### SessionOptimizer API

```python
from panefit import SessionOptimizer

optimizer = SessionOptimizer(
    relevance_threshold=0.3,   # Min relevance to group panes
    importance_threshold=0.2   # Below this = candidate for parking
)

# Analyze all panes across all windows
analysis = optimizer.analyze_session()
# Returns: pane_count, window_count, windows, panes, suggested_groups

# Optimize: calculate and apply moves
result = optimizer.optimize(dry_run=False)

# Consolidate related panes around a reference pane
result = optimizer.consolidate_related("%5", dry_run=False)

# Park inactive panes
result = optimizer.park_inactive(window_name="parked", dry_run=False)
```

### TmuxProvider Cross-Window Methods

```python
from panefit.providers import TmuxProvider

provider = TmuxProvider()

# List all windows in session
windows = provider.list_windows()

# Get all panes across all windows
all_panes = provider.get_all_panes()

# Move pane to another window
provider.move_pane(source_pane="%5", target_window=":2")

# Break pane out to new window
new_window = provider.break_pane(pane_id="%3", window_name="new-window")

# Join pane to another pane's window
provider.join_pane(source_pane=":1.0", target_pane=":2.0", vertical=True)

# Swap panes across windows
provider.swap_panes_cross_window(":1.0", ":2.1")
```

### Grouping Algorithm

1. Sort panes by importance (descending)
2. For each unassigned pane:
   - Create new group with this pane
   - Find all panes with relevance >= threshold
   - Add to group
3. Remaining panes go to "misc" group
4. Calculate moves to consolidate each group into single window
