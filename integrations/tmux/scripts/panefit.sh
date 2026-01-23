#!/usr/bin/env bash
#
# Panefit tmux integration
#
# Calls Python library directly (no CLI dependency)
#

# Use absolute paths (symlink-resolved)
PYTHON="/Users/takumiyagi/workspace/hoge/ve/bin/python"
REFLOW_SCRIPT="/Users/takumiyagi/workspace/new/panefit/integrations/tmux/reflow.py"

if [ ! -x "$PYTHON" ]; then
    tmux display-message "Panefit: Python not found at $PYTHON"
    exit 1
fi

if [ ! -f "$REFLOW_SCRIPT" ]; then
    tmux display-message "Panefit: reflow.py not found at $REFLOW_SCRIPT"
    exit 1
fi

# Export tmux options as environment variables
export_tmux_options() {
    local val
    val=$(tmux show-option -gqv "@panefit-llm-enabled" 2>/dev/null || echo "")
    [ -n "$val" ] && export PANEFIT_LLM_ENABLED="$val"

    val=$(tmux show-option -gqv "@panefit-strategy" 2>/dev/null || echo "")
    [ -n "$val" ] && export PANEFIT_STRATEGY="$val"
}

cmd_reflow() {
    export_tmux_options
    local result
    result=$("$PYTHON" "$REFLOW_SCRIPT" reflow "$@" 2>&1)
    if [ -n "$result" ]; then
        tmux display-message "Panefit: $result"
    else
        tmux display-message "Panefit: layout applied"
    fi
}

cmd_dry_run() {
    export_tmux_options
    local result
    result=$("$PYTHON" "$REFLOW_SCRIPT" dry-run "$@" 2>&1)
    if [ -n "$result" ]; then
        tmux display-message "Panefit: $result"
    else
        tmux display-message "Panefit: no changes needed"
    fi
}

cmd_session_analyze() {
    export_tmux_options
    local result
    result=$("$PYTHON" "$REFLOW_SCRIPT" session-analyze "$@" 2>&1)
    if [ -n "$result" ]; then
        tmux display-message "Panefit: $result"
    else
        tmux display-message "Panefit: session analyzed"
    fi
}

cmd_session_optimize() {
    export_tmux_options
    local result
    result=$("$PYTHON" "$REFLOW_SCRIPT" session-optimize "$@" 2>&1) || true
    tmux display-message "Panefit: $result" 2>/dev/null || echo "Panefit: $result"
}

cmd_session_park() {
    export_tmux_options
    local result
    result=$("$PYTHON" "$REFLOW_SCRIPT" session-park "$@" 2>&1) || true
    tmux display-message "Panefit: $result" 2>/dev/null || echo "Panefit: $result"
}

# Entry point
case "${1:-reflow}" in
    reflow)
        shift 2>/dev/null || true
        cmd_reflow "$@"
        ;;
    dry-run)
        shift 2>/dev/null || true
        cmd_dry_run "$@"
        ;;
    session-analyze)
        shift 2>/dev/null || true
        cmd_session_analyze "$@"
        ;;
    session-optimize)
        shift 2>/dev/null || true
        cmd_session_optimize "$@"
        ;;
    session-park)
        shift 2>/dev/null || true
        cmd_session_park "$@"
        ;;
    *)
        echo "Usage: panefit.sh {reflow|dry-run|session-analyze|session-optimize|session-park}"
        exit 1
        ;;
esac
