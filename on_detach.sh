#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# AeroWholesale QC — cfgutil detach handler
# Called automatically by cfgutil exec when a device is unplugged.
# ═══════════════════════════════════════════════════════════════

SERVER="http://localhost:5000"
STATION_ID="${QC_STATION_ID:-Station-1}"
LOG="/tmp/aw_qc_attach.log"

echo "$(date) DETACH ecid=$ECID" >> "$LOG"

# Notify station display that device was disconnected
curl -s -X POST "$SERVER/api/station/update" \
    -H "Content-Type: application/json" \
    -d "{\"station_id\": \"$STATION_ID\", \"state\": \"idle\", \"device\": null}" > /dev/null 2>&1
