#!/usr/bin/env bash
#
# Panefit - Shell script wrapper for tmux plugin
#
# Simply invokes the panefit CLI. All settings come from config file.
#

set -e

# Find panefit command
find_panefit() {
    if command -v panefit &> /dev/null; then
        echo "panefit"
    else
        echo ""
    fi
}

PANEFIT=$(find_panefit)

if [ -z "$PANEFIT" ]; then
    tmux display-message "Panefit: Command not found. Run: pip install panefit"
    exit 1
fi

# Run panefit command
case "${1:-reflow}" in
    reflow)
        shift 2>/dev/null || true
        $PANEFIT reflow "$@"
        tmux display-message "Panefit: Reflow complete"
        ;;
    reflow-silent)
        shift 2>/dev/null || true
        $PANEFIT reflow "$@" > /dev/null 2>&1 || true
        ;;
    analyze)
        shift 2>/dev/null || true
        $PANEFIT analyze "$@"
        ;;
    session)
        shift 2>/dev/null || true
        $PANEFIT session "$@"
        ;;
    *)
        echo "Usage: panefit.sh {reflow|reflow-silent|analyze|session}"
        exit 1
        ;;
esac
