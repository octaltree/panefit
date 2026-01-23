#!/usr/bin/env bash
#
# Panefit tmux integration
#

PYTHON="/Users/takumiyagi/workspace/hoge/ve/bin/python"
REFLOW_SCRIPT="/Users/takumiyagi/workspace/new/panefit/integrations/tmux/reflow.py"

[ ! -x "$PYTHON" ] && { tmux display-message "Panefit: Python not found"; exit 1; }
[ ! -f "$REFLOW_SCRIPT" ] && { tmux display-message "Panefit: reflow.py not found"; exit 1; }

cmd_reflow() {
    local result
    result=$("$PYTHON" "$REFLOW_SCRIPT" reflow 2>&1)
    tmux set-option -g display-time 5000
    tmux display-message "Panefit: $result"
}

cmd_dry_run() {
    local result
    result=$("$PYTHON" "$REFLOW_SCRIPT" dry-run 2>&1)
    tmux set-option -g display-time 5000
    tmux display-message "Panefit: $result"
}

cmd_session_analyze() {
    local result
    result=$("$PYTHON" "$REFLOW_SCRIPT" session-analyze 2>&1)
    tmux set-option -g display-time 5000
    tmux display-message "Panefit: $result"
}

case "${1:-reflow}" in
    reflow) cmd_reflow ;;
    dry-run) cmd_dry_run ;;
    session-analyze) cmd_session_analyze ;;
    *) echo "Usage: panefit.sh {reflow|dry-run|session-analyze}"; exit 1 ;;
esac
