#!/usr/bin/env bash
#
# Panefit - Content-aware intelligent pane layout for tmux
#
# tmux plugin entry point
#
# Options (set in .tmux.conf):
#   @panefit-key         - Keybinding for reflow (default: R)
#   @panefit-auto-reflow - Auto-reflow on pane focus (default: false)
#
# All other settings are managed via: panefit config
#

CURRENT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SCRIPTS_DIR="$CURRENT_DIR/scripts"

# Default options
default_key="T"
default_auto_reflow="false"

# Get tmux option or default
get_tmux_option() {
    local option="$1"
    local default_value="$2"
    local option_value
    option_value=$(tmux show-option -gqv "$option")
    if [ -z "$option_value" ]; then
        echo "$default_value"
    else
        echo "$option_value"
    fi
}

# Set up key bindings
setup_keybinding() {
    local key
    key=$(get_tmux_option "@panefit-key" "$default_key")

    # Current window reflow
    tmux bind-key "$key" run-shell "$SCRIPTS_DIR/panefit.sh reflow"
    tmux bind-key "X" run-shell "$SCRIPTS_DIR/panefit.sh dry-run"

    # Cross-window session commands
    tmux bind-key "Q" run-shell "$SCRIPTS_DIR/panefit.sh session-analyze"
}

# Set up auto-reflow hook (optional)
setup_auto_reflow() {
    local auto_reflow
    auto_reflow=$(get_tmux_option "@panefit-auto-reflow" "$default_auto_reflow")

    if [ "$auto_reflow" = "true" ]; then
        tmux set-hook -g pane-focus-in "run-shell -b '$SCRIPTS_DIR/panefit.sh reflow-silent'"
    fi
}

# Main initialization
main() {
    setup_keybinding
    setup_auto_reflow
}

main
