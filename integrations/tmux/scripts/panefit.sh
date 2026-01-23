#!/usr/bin/env bash
#
# Panefit tmux integration
#
# Workflow:
#   1. Get pane data from tmux
#   2. Send to panefit CLI for calculation
#   3. Apply result to tmux
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

# Export tmux options as environment variables for panefit config override
export_tmux_options() {
    local val
    val=$(tmux show-option -gqv "@panefit-llm-enabled" 2>/dev/null || echo "")
    [ -n "$val" ] && export PANEFIT_LLM_ENABLED="$val"

    val=$(tmux show-option -gqv "@panefit-strategy" 2>/dev/null || echo "")
    [ -n "$val" ] && export PANEFIT_STRATEGY="$val"
}

# Get pane data as JSON
get_panes_json() {
    local window_width window_height
    window_width=$(tmux display-message -p '#{window_width}')
    window_height=$(tmux display-message -p '#{window_height}')

    echo "{"
    echo "  \"window\": {\"width\": $window_width, \"height\": $window_height},"
    echo "  \"panes\": ["

    local first=true
    while IFS='|' read -r pane_id width height top left active command; do
        [ -z "$pane_id" ] && continue

        # Capture pane content
        local content
        content=$(tmux capture-pane -t "$pane_id" -p -S -100 2>/dev/null | sed 's/\\/\\\\/g; s/"/\\"/g; s/\t/\\t/g' | tr '\n' '\\' | sed 's/\\/\\n/g')

        [ "$first" = "true" ] && first=false || echo ","

        echo "    {"
        echo "      \"id\": \"$pane_id\","
        echo "      \"content\": \"$content\","
        echo "      \"width\": $width,"
        echo "      \"height\": $height,"
        echo "      \"x\": $left,"
        echo "      \"y\": $top,"
        echo "      \"active\": $([ "$active" = "1" ] && echo "true" || echo "false"),"
        echo "      \"command\": \"$command\""
        echo -n "    }"
    done < <(tmux list-panes -F '#{pane_id}|#{pane_width}|#{pane_height}|#{pane_top}|#{pane_left}|#{pane_active}|#{pane_current_command}')

    echo ""
    echo "  ]"
    echo "}"
}

# Apply layout result to tmux
apply_layout() {
    local result="$1"

    # Parse JSON and apply each pane's layout
    # Using simple parsing since we control the output format
    echo "$result" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for p in data.get('panes', []):
    layout = p.get('layout', {})
    pane_id = p.get('id', '')
    width = layout.get('width')
    height = layout.get('height')
    if pane_id and width and height:
        print(f'{pane_id}|{width}|{height}')
" | while IFS='|' read -r pane_id width height; do
        [ -z "$pane_id" ] && continue
        tmux resize-pane -t "$pane_id" -x "$width" -y "$height" 2>/dev/null || true
    done
}

# Main commands
cmd_reflow() {
    export_tmux_options

    local input result
    input=$(get_panes_json)
    result=$(echo "$input" | $PANEFIT calculate --compact "$@")

    if echo "$result" | grep -q '"error"'; then
        tmux display-message "Panefit: $(echo "$result" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("error","Unknown error"))')"
        return 1
    fi

    apply_layout "$result"
    tmux display-message "Panefit: Reflow complete"
}

cmd_analyze() {
    export_tmux_options

    local input
    input=$(get_panes_json)
    echo "$input" | $PANEFIT analyze "$@"
}

# Entry point
case "${1:-reflow}" in
    reflow)
        shift 2>/dev/null || true
        cmd_reflow "$@"
        ;;
    reflow-silent)
        shift 2>/dev/null || true
        cmd_reflow "$@" > /dev/null 2>&1 || true
        ;;
    analyze)
        shift 2>/dev/null || true
        cmd_analyze "$@"
        ;;
    *)
        echo "Usage: panefit.sh {reflow|reflow-silent|analyze}"
        exit 1
        ;;
esac
