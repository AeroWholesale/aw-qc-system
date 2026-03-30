#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# AeroWholesale QC — Test Print
# Sends a test label to the Zebra printer to verify connectivity.
#
# Usage:
#   ./scripts/test_print.sh
# ═══════════════════════════════════════════════════════════════

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
QC_DIR="$(dirname "$SCRIPT_DIR")"

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║   AEROWHOLESALE QC — PRINTER TEST            ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# Check CUPS printers
echo "  Checking printers..."
if command -v lpstat &>/dev/null; then
    PRINTERS=$(lpstat -p 2>/dev/null || true)
    if [ -n "$PRINTERS" ]; then
        echo "$PRINTERS" | sed 's/^/    /'
    else
        echo "    No CUPS printers found"
    fi
else
    echo "    lpstat not available"
fi
echo ""

# Run test print via Python
cd "$QC_DIR"
python3 -c "
from app.services.label_printer import generate_zpl, print_label, test_print
result = test_print()
if result['success']:
    print('  Test label sent ✓')
    print(f'  Method: {result[\"method\"]}')
else:
    print(f'  Print failed ✗')
    print(f'  Error: {result[\"error\"]}')
    print()
    print('  Troubleshooting:')
    print('    1. Is the Zebra printer plugged in via USB?')
    print('    2. Is it powered on and has labels loaded?')
    print('    3. Run: lpstat -p  to check CUPS printer list')
    print('    4. Run: system_profiler SPUSBDataType | grep -i zebra')
"

echo ""
