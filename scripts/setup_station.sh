#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# AeroWholesale QC — Station Setup
# Sets up a fresh Mac mini as a QC station.
# Run as the aeroserver user or with sudo.
#
# Usage:
#   sudo ./scripts/setup_station.sh [station_id]
#
# Example:
#   sudo ./scripts/setup_station.sh Station-1
# ═══════════════════════════════════════════════════════════════

set -euo pipefail

STATION_ID="${1:-Station-1}"
QC_DIR="$(cd "$(dirname "$0")/.." && pwd)"
USER_HOME=$(eval echo "~${SUDO_USER:-$(whoami)}")
LAUNCH_AGENTS_DIR="$USER_HOME/Library/LaunchAgents"

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║   AEROWHOLESALE QC — STATION SETUP           ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
echo "  Station ID:   $STATION_ID"
echo "  QC Directory: $QC_DIR"
echo "  User:         ${SUDO_USER:-$(whoami)}"
echo ""

# ── 1. Install Python dependencies ──
echo "  [1/7] Installing Python dependencies..."
pip3 install -r "$QC_DIR/requirements.txt" --break-system-packages 2>/dev/null \
    || pip3 install -r "$QC_DIR/requirements.txt" 2>/dev/null \
    || pip3 install --user -r "$QC_DIR/requirements.txt"
echo "        ✓ Dependencies installed"
echo ""

# ── 2. Set up the database ──
echo "  [2/7] Setting up database..."
cd "$QC_DIR"
python3 -c "
from dotenv import load_dotenv
load_dotenv()
from app import create_app, db
from app.services.test_definitions import seed_defaults
app = create_app()
with app.app_context():
    db.create_all()
    seed_defaults()
    print('        ✓ Database created and seeded')
"
echo ""

# ── 3. Create .env if missing ──
if [ ! -f "$QC_DIR/.env" ]; then
    echo "  [3/7] Creating .env file..."
    cp "$QC_DIR/.env.example" "$QC_DIR/.env" 2>/dev/null || cat > "$QC_DIR/.env" << 'ENVEOF'
FLASK_ENV=production
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
DATABASE_URL=sqlite:///qc.db
ENVEOF
    echo "        ✓ .env created"
else
    echo "  [3/7] .env already exists ✓"
fi
echo ""

# ── 4. Install launchd plists for auto-start ──
echo "  [4/7] Installing launchd services..."
mkdir -p "$LAUNCH_AGENTS_DIR"

# Update plists with actual paths and station ID
sed "s|/Users/aeroserver/aw-qc-system|$QC_DIR|g" "$QC_DIR/mdm/com.aerowholesale.qc.plist" \
    | sed "s|<string>aeroserver</string>|<string>${SUDO_USER:-$(whoami)}</string>|g" \
    > "$LAUNCH_AGENTS_DIR/com.aerowholesale.qc.plist"

sed "s|/Users/aeroserver/aw-qc-system|$QC_DIR|g" "$QC_DIR/mdm/com.aerowholesale.watcher.plist" \
    | sed "s|<string>aeroserver</string>|<string>${SUDO_USER:-$(whoami)}</string>|g" \
    | sed "s|<string>Station-1</string>|<string>${STATION_ID}</string>|g" \
    > "$LAUNCH_AGENTS_DIR/com.aerowholesale.watcher.plist"

# Load the services
launchctl unload "$LAUNCH_AGENTS_DIR/com.aerowholesale.qc.plist" 2>/dev/null || true
launchctl unload "$LAUNCH_AGENTS_DIR/com.aerowholesale.watcher.plist" 2>/dev/null || true
launchctl load "$LAUNCH_AGENTS_DIR/com.aerowholesale.qc.plist"
launchctl load "$LAUNCH_AGENTS_DIR/com.aerowholesale.watcher.plist"
echo "        ✓ QC server service installed (com.aerowholesale.qc)"
echo "        ✓ Station watcher service installed (com.aerowholesale.watcher)"
echo ""

# ── 5. Disable sleep ──
echo "  [5/7] Disabling sleep..."
sudo pmset -a displaysleep 0 2>/dev/null || true
sudo pmset -a sleep 0 2>/dev/null || true
sudo pmset -a disksleep 0 2>/dev/null || true
sudo pmset -a powernap 0 2>/dev/null || true
sudo pmset -a autopoweroff 0 2>/dev/null || true
echo "        ✓ Sleep disabled (display, disk, system)"
echo ""

# ── 6. Set up Safari to open station on login ──
echo "  [6/7] Configuring station display auto-open..."
STATION_URL="http://localhost:5000/station"

# Create a login item that opens Safari to station page
LOGIN_APP_DIR="$USER_HOME/Applications"
mkdir -p "$LOGIN_APP_DIR"
cat > "/tmp/open-qc-station.applescript" << ASEOF
tell application "Safari"
    activate
    delay 3
    open location "$STATION_URL"
    delay 1
    tell application "System Events"
        keystroke "f" using {command down, control down}
    end tell
end tell
ASEOF
osacompile -o "$LOGIN_APP_DIR/OpenQCStation.app" "/tmp/open-qc-station.applescript" 2>/dev/null || true
rm -f "/tmp/open-qc-station.applescript"

# Add to login items via osascript
osascript -e "
tell application \"System Events\"
    try
        delete login item \"OpenQCStation\"
    end try
    make login item at end with properties {path:\"$LOGIN_APP_DIR/OpenQCStation.app\", hidden:false}
end tell
" 2>/dev/null || echo "        Note: Could not add login item automatically. Add manually in System Settings > Login Items."
echo "        ✓ Station display will open in Safari on login"
echo ""

# ── 7. Make scripts executable ──
echo "  [7/7] Setting permissions..."
chmod +x "$QC_DIR/scripts/"*.sh
chmod +x "$QC_DIR/on_attach.sh"
chmod +x "$QC_DIR/on_detach.sh"
chmod +x "$QC_DIR/mdm/ac_prepare.sh"
echo "        ✓ Scripts are executable"
echo ""

# ── Done ──
echo "╔══════════════════════════════════════════════╗"
echo "║         SETUP COMPLETE                        ║"
echo "╠══════════════════════════════════════════════╣"
echo "║                                              ║"
echo "║  QC Server:  http://localhost:5000            ║"
echo "║  Dashboard:  http://localhost:5000/            ║"
echo "║  Station:    http://localhost:5000/station     ║"
echo "║                                              ║"
echo "║  Services will auto-start on login.           ║"
echo "║  Logs: /tmp/aw-qc-server.log                  ║"
echo "║        /tmp/aw-qc-watcher.log                 ║"
echo "║                                              ║"
echo "║  Station ID: $STATION_ID                      ║"
echo "║                                              ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
