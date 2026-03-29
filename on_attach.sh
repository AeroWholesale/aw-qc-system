#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# AeroWholesale QC — cfgutil attach handler
# Called automatically by cfgutil exec when a device is plugged in.
#
# Environment variables set by cfgutil:
#   ECID, UDID, deviceName, deviceType, buildVersion,
#   firmwareVersion, locationID
# ═══════════════════════════════════════════════════════════════

CFGUTIL="/Applications/Apple Configurator.app/Contents/MacOS/cfgutil"
SERVER="http://localhost:5000"
STATION_ID="${QC_STATION_ID:-Station-1}"
LOG="/tmp/aw_qc_attach.log"

echo "$(date) ATTACH ecid=$ECID type=$deviceType name=$deviceName" >> "$LOG"

# Get serial number and additional properties from cfgutil
SERIAL=$("$CFGUTIL" -e "$ECID" get serialNumber --format JSON 2>/dev/null | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    # cfgutil JSON output: {\"Output\": {\"ECID\": {\"serialNumber\": \"XXX\"}}}
    output = data.get('Output', {})
    for ecid_key, props in output.items():
        if isinstance(props, dict):
            print(props.get('serialNumber', ''))
            break
        else:
            print(props)
            break
except:
    pass
" 2>/dev/null)

# Fallback: try plain text output
if [ -z "$SERIAL" ]; then
    SERIAL=$("$CFGUTIL" -e "$ECID" get serialNumber 2>/dev/null | grep -v "^$" | tail -1 | awk '{print $NF}')
fi

if [ -z "$SERIAL" ]; then
    echo "$(date) ERROR: Could not read serial number for ECID=$ECID" >> "$LOG"
    exit 1
fi

# Map deviceType to friendly model name
MODEL="$deviceName"
if [ -z "$MODEL" ] || [ "$MODEL" = "(null)" ]; then
    MODEL="$deviceType"
fi

echo "$(date) Serial=$SERIAL Model=$MODEL ECID=$ECID" >> "$LOG"

# Post to QC server
RESPONSE=$(curl -s -X POST "$SERVER/api/devices/detect" \
    -H "Content-Type: application/json" \
    -d "{
        \"serial_number\": \"$SERIAL\",
        \"device_type\": \"macbook\",
        \"model\": \"$MODEL\",
        \"station_id\": \"$STATION_ID\"
    }" 2>/dev/null)

echo "$(date) Server response: $RESPONSE" >> "$LOG"

# Extract device ID and set status to testing
DEVICE_ID=$(echo "$RESPONSE" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('device', {}).get('id', ''))
except:
    pass
" 2>/dev/null)

if [ -n "$DEVICE_ID" ]; then
    # Mark as testing
    curl -s -X PATCH "$SERVER/api/devices/$DEVICE_ID" \
        -H "Content-Type: application/json" \
        -d "{\"status\": \"testing\", \"station_id\": \"$STATION_ID\"}" > /dev/null 2>&1

    # Broadcast to station display to start loading
    curl -s -X POST "$SERVER/api/station/update" \
        -H "Content-Type: application/json" \
        -d "{
            \"station_id\": \"$STATION_ID\",
            \"state\": \"loading\",
            \"device\": {
                \"id\": $DEVICE_ID,
                \"serial_number\": \"$SERIAL\",
                \"model\": \"$MODEL\",
                \"device_type\": \"macbook\"
            }
        }" > /dev/null 2>&1

    echo "$(date) Device $DEVICE_ID registered and station notified" >> "$LOG"
fi
