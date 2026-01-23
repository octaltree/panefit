#!/usr/bin/env bash
#
# Panefit - Shell script wrapper
#
# Invokes the Python implementation with proper environment setup.
#

set -e

CURRENT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PLUGIN_DIR="$( cd "$CURRENT_DIR/../../.." && pwd )"

# Check for Python
find_python() {
    if command -v python3 &> /dev/null; then
        echo "python3"
    elif command -v python &> /dev/null; then
        echo "python"
    else
        echo ""
    fi
}

PYTHON=$(find_python)

if [ -z "$PYTHON" ]; then
    tmux display-message "Panefit: Python not found. Please install Python 3.8+"
    exit 1
fi

# Export plugin directory for Python to find modules
export PYTHONPATH="$PLUGIN_DIR:$PYTHONPATH"

# Get tmux options and export as environment variables
export_tmux_options() {
    export PANEFIT_LLM_ENABLED=$(tmux show-option -gqv "@panefit-llm-enabled" || echo "false")
    export PANEFIT_LLM_PROVIDER=$(tmux show-option -gqv "@panefit-llm-provider" || echo "auto")
    export PANEFIT_STRATEGY=$(tmux show-option -gqv "@panefit-strategy" || echo "balanced")
    export PANEFIT_LAYOUT_TYPE=$(tmux show-option -gqv "@panefit-layout-type" || echo "auto")
    export PANEFIT_AUTO_REFLOW=$(tmux show-option -gqv "@panefit-auto-reflow" || echo "false")
    export PANEFIT_DEBUG=$(tmux show-option -gqv "@panefit-debug" || echo "false")
}

# Run panefit command
run_panefit() {
    local command="$1"
    shift

    export_tmux_options

    case "$command" in
        reflow)
            $PYTHON -m cli reflow "$@"
            tmux display-message "Panefit: Reflow complete"
            ;;
        reflow-silent)
            $PYTHON -m cli reflow "$@" > /dev/null 2>&1 || true
            ;;
        analyze)
            $PYTHON -m cli analyze "$@"
            ;;
        config)
            $PYTHON -m cli config "$@"
            ;;
        *)
            echo "Usage: panefit.sh {reflow|reflow-silent|analyze|config}"
            exit 1
            ;;
    esac
}

# Main
cd "$PLUGIN_DIR"
run_panefit "$@"
