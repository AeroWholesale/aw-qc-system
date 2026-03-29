#!/bin/bash
# ═══════════════════════════════════════════════
# AeroWholesale QC — Apple Configurator Prepare
# Runs when a MacBook is plugged in via USB-C
# ═══════════════════════════════════════════════

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVER_URL="${QC_SERVER_URL:-http://localhost:5000}"
PROFILE_PATH="${SCRIPT_DIR}/enroll.mobileconfig"

echo "[AW-QC] Waiting for USB device..."

# Get the connected device ECID (waits for device)
ECID=$(cfgutil --format JSON list 2>/dev/null | python3 -c "
import sys, json
devices = json.load(sys.stdin)
if devices:
    print(list(devices.keys())[0])
" 2>/dev/null)

if [ -z "$ECID" ]; then
    echo "[AW-QC] ERROR: No device detected via cfgutil"
    exit 1
fi

echo "[AW-QC] Device detected: ECID=${ECID}"

# Get serial number
SERIAL=$(cfgutil --ecid "$ECID" get serialNumber 2>/dev/null || echo "UNKNOWN")
echo "[AW-QC] Serial: ${SERIAL}"

# Prepare the device: name it, supervise, apply DEP profile
echo "[AW-QC] Running cfgutil prepare..."
cfgutil --ecid "$ECID" prepare \
    -n "AW-QC" \
    --supervise \
    --dep-profile "$PROFILE_PATH"

echo "[AW-QC] Prepare complete. Registering with QC server..."

# Post serial number to the QC server to register the device
RESPONSE=$(curl -s -X POST "${SERVER_URL}/api/devices/detect" \
    -H "Content-Type: application/json" \
    -d "{\"serial_number\": \"${SERIAL}\", \"device_type\": \"macbook\", \"model\": \"MacBook (USB detect)\", \"station_id\": \"Station-1\"}")

DEVICE_ID=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('device', {}).get('id', ''))" 2>/dev/null || echo "")

echo "[AW-QC] Registered device_id=${DEVICE_ID}"

# Trigger station display loading state via SocketIO
python3 -c "
import json, urllib.request
data = json.dumps({
    'station_id': 'Station-1',
    'state': 'loading',
    'device': {'id': '${DEVICE_ID}', 'serial_number': '${SERIAL}', 'model': 'MacBook (USB detect)'}
}).encode()
req = urllib.request.Request('${SERVER_URL}/api/station/update', data=data, headers={'Content-Type': 'application/json'})
urllib.request.urlopen(req)
" 2>/dev/null && echo "[AW-QC] Station notified — loading state" || echo "[AW-QC] WARNING: Could not notify station"

echo "[AW-QC] Done. Device is ready for diagnostics."
