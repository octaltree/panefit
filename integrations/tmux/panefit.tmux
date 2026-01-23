#!/usr/bin/env bash
#
# Panefit - Content-aware intelligent pane layout for tmux
#
# tmux plugin entry point
#

CURRENT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SCRIPTS_DIR="$CURRENT_DIR/scripts"

# Default options
default_key="R"
default_auto_reflow="false"
default_auto_reflow_interval="5"
default_llm_enabled="false"
default_strategy="balanced"
default_layout_type="auto"

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

# Set tmux option
set_tmux_option() {
    local option="$1"
    local value="$2"
    tmux set-option -g "$option" "$value"
}

# Initialize options with defaults if not set
init_options() {
    local key
    key=$(get_tmux_option "@panefit-key" "$default_key")
    set_tmux_option "@panefit-key" "$key"

    local auto_reflow
    auto_reflow=$(get_tmux_option "@panefit-auto-reflow" "$default_auto_reflow")
    set_tmux_option "@panefit-auto-reflow" "$auto_reflow"

    local interval
    interval=$(get_tmux_option "@panefit-auto-reflow-interval" "$default_auto_reflow_interval")
    set_tmux_option "@panefit-auto-reflow-interval" "$interval"

    local llm_enabled
    llm_enabled=$(get_tmux_option "@panefit-llm-enabled" "$default_llm_enabled")
    set_tmux_option "@panefit-llm-enabled" "$llm_enabled"

    local strategy
    strategy=$(get_tmux_option "@panefit-strategy" "$default_strategy")
    set_tmux_option "@panefit-strategy" "$strategy"

    local layout_type
    layout_type=$(get_tmux_option "@panefit-layout-type" "$default_layout_type")
    set_tmux_option "@panefit-layout-type" "$layout_type"
}

# Set up key binding
setup_keybinding() {
    local key
    key=$(get_tmux_option "@panefit-key" "$default_key")
    tmux bind-key "$key" run-shell "$SCRIPTS_DIR/panefit.sh reflow"
}

# Set up auto-reflow hook (optional)
setup_auto_reflow() {
    local auto_reflow
    auto_reflow=$(get_tmux_option "@panefit-auto-reflow" "$default_auto_reflow")

    if [ "$auto_reflow" = "true" ]; then
        # Hook into pane-focus-in for auto-reflow
        tmux set-hook -g pane-focus-in "run-shell -b '$SCRIPTS_DIR/panefit.sh reflow-silent'"
    fi
}

# Main initialization
main() {
    init_options
    setup_keybinding
    setup_auto_reflow
}

main
