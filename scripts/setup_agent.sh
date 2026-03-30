#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# AeroWholesale QC — Agent Installer
# Copies agent.py to a MacBook and runs it.
# Run FROM the Mac mini, pass the MacBook's IP as argument.
#
# Usage:
#   ./scripts/setup_agent.sh <macbook_ip> <device_id> [station_id]
#
# Example:
#   ./scripts/setup_agent.sh 192.168.0.42 15
#   ./scripts/setup_agent.sh 192.168.0.42 15 Station-2
# ═══════════════════════════════════════════════════════════════

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
QC_DIR="$(dirname "$SCRIPT_DIR")"
AGENT_PATH="$QC_DIR/agent.py"

if [ $# -lt 2 ]; then
    echo "AeroWholesale QC — Agent Installer"
    echo ""
    echo "Usage:  $0 <macbook_ip> <device_id> [station_id]"
    echo ""
    echo "  macbook_ip   IP address of the MacBook being tested"
    echo "  device_id    Device ID from the QC system"
    echo "  station_id   Optional station ID (default: Station-1)"
    echo ""
    echo "This script will:"
    echo "  1. Copy agent.py to the MacBook's /tmp/"
    echo "  2. Run the diagnostic agent remotely"
    echo "  3. Stream results back to this QC station"
    exit 1
fi

MACBOOK_IP="$1"
DEVICE_ID="$2"
STATION_ID="${3:-Station-1}"

# Get this Mac mini's IP for the agent to call back
SERVER_IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "localhost")

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║   AEROWHOLESALE QC — AGENT DEPLOY            ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
echo "  MacBook IP:   $MACBOOK_IP"
echo "  Device ID:    $DEVICE_ID"
echo "  Station:      $STATION_ID"
echo "  Server IP:    $SERVER_IP"
echo ""

# Copy agent.py to MacBook
echo "  [1/2] Copying agent.py to MacBook..."
scp -o ConnectTimeout=5 -o StrictHostKeyChecking=no \
    "$AGENT_PATH" "${MACBOOK_IP}:/tmp/aw_qc_agent.py"
echo "  Copied ✓"

# Run agent on MacBook
echo "  [2/2] Running diagnostics on MacBook..."
echo ""
ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no \
    "$MACBOOK_IP" "python3 /tmp/aw_qc_agent.py $SERVER_IP $DEVICE_ID $STATION_ID"

echo ""
echo "  Agent complete ✓"
