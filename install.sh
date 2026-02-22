#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_DIR="$HOME/.config/managebac-notifier"
PYTHON_PATH="$(which python)"
LABEL_PREFIX="com.$(whoami).managebac"

echo "=== ManageBac Notifier Setup ==="

# 1. Create config directory
echo "Creating config directory..."
mkdir -p "$CONFIG_DIR/logs"

# 2. Copy example config if not exists
if [ ! -f "$CONFIG_DIR/config.yaml" ]; then
    cp "$SCRIPT_DIR/config.example.yaml" "$CONFIG_DIR/config.yaml"
    chmod 600 "$CONFIG_DIR/config.yaml"
    echo "Created $CONFIG_DIR/config.yaml — please edit with your credentials!"
else
    echo "Config already exists at $CONFIG_DIR/config.yaml"
fi

# 3. Install Python dependencies
echo "Installing Python dependencies..."
pip install -r "$SCRIPT_DIR/requirements.txt"

# 4. Install launchd plists (substitute paths)
echo "Installing launchd agents..."
for template in "$SCRIPT_DIR"/launchd/*.plist; do
    plist_name=$(basename "$template" .plist)
    # Replace example label with user-specific label
    actual_name="${plist_name/com.example/com.$(whoami)}"
    dst="$HOME/Library/LaunchAgents/$actual_name.plist"

    if launchctl list | grep -q "$actual_name" 2>/dev/null; then
        launchctl bootout "gui/$(id -u)/$actual_name" 2>/dev/null || true
    fi

    sed -e "s|/Users/YOUR_USERNAME|$HOME|g" \
        -e "s|com.example.|com.$(whoami).|g" \
        "$template" > "$dst"

    launchctl bootstrap "gui/$(id -u)" "$dst"
    echo "  Installed: $actual_name"
done

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "  1. Edit $CONFIG_DIR/config.yaml with your ManageBac credentials"
echo "  2. Run: python $SCRIPT_DIR/managebac_notifier.py explore"
echo "  3. Run: python $SCRIPT_DIR/managebac_notifier.py run --dry-run"
echo ""
echo "The notifier will run daily at 18:00."
