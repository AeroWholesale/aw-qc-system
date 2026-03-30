# AeroWholesale QC System — Operations Guide

## Quick Start

```bash
# First-time setup (run once on a fresh Mac mini)
sudo ./scripts/setup_station.sh Station-1

# Manual start (if not using auto-start)
python3 run.py                    # Start QC server
python3 station_watcher.py        # Start device watcher (separate terminal)
```

Open Safari to **http://localhost:5000/station** for the station display.
Open **http://localhost:5000/** for the dashboard.

---

## Starting and Stopping the Server

### Auto-start (launchd)

After running `setup_station.sh`, the server and watcher start automatically on login.

```bash
# Check if services are running
launchctl list | grep aerowholesale

# Stop services
launchctl unload ~/Library/LaunchAgents/com.aerowholesale.qc.plist
launchctl unload ~/Library/LaunchAgents/com.aerowholesale.watcher.plist

# Start services
launchctl load ~/Library/LaunchAgents/com.aerowholesale.qc.plist
launchctl load ~/Library/LaunchAgents/com.aerowholesale.watcher.plist

# View logs
tail -f /tmp/aw-qc-server.log
tail -f /tmp/aw-qc-watcher.log
```

### Manual start

```bash
cd ~/aw-qc-system

# Terminal 1: QC server
python3 run.py

# Terminal 2: Station watcher
python3 station_watcher.py --station Station-1

# Force polling mode (if Apple Configurator not installed)
python3 station_watcher.py --poll
```

### Health check

```bash
curl http://localhost:5000/health
# Should return: {"ok": true}
```

---

## Adding a New Station

1. **On the new Mac mini**, clone the repo and run setup:

```bash
git clone https://github.com/AeroWholesale/aw-qc-system.git
cd aw-qc-system
sudo ./scripts/setup_station.sh Station-2    # Use a unique ID
```

2. **Set the station ID** — the station watcher uses the `QC_STATION_ID` environment variable or the `--station` flag:

```bash
python3 station_watcher.py --station Station-2
```

3. **For multi-station setups** where stations share a database, set `DATABASE_URL` in `.env` to point to the shared PostgreSQL server:

```env
DATABASE_URL=postgresql://user:pass@192.168.0.100:5432/aw_qc
```

4. Open **http://localhost:5000/station** — the station display will show the station ID in the header.

---

## Running a MacBook Test (Step by Step)

### Method 1: Automatic USB Detection

1. Make sure the QC server and station watcher are running
2. Open the station display in Safari (http://localhost:5000/station)
3. **Plug in the MacBook via USB-C** — the watcher detects it automatically
4. The station display transitions from IDLE → LOADING
5. The diagnostic agent runs and populates auto results
6. Complete the manual inspection checklist on the station display
7. Click **CALCULATE GRADE** — the system grades the device
8. Review the grade, add notes, enter your name
9. Click **CONFIRM & PRINT LABEL** — a label prints and the device is saved
10. Optionally click **WIPE DEVICE** to erase before the next unit

### Method 2: Manual Serial Entry

1. On the station display, type the serial number in the input field
2. Press Enter or click **Start Manual**
3. Skip to step 6 above (no auto diagnostics in manual mode)

### Method 3: Remote Agent (for MacBooks on the network)

1. Get the MacBook's IP address (System Settings → Network)
2. From the Mac mini, run:

```bash
# First register the device
curl -X POST http://localhost:5000/api/devices/detect \
  -H "Content-Type: application/json" \
  -d '{"serial_number":"SERIAL_HERE","device_type":"macbook","model":"MacBook Pro"}'
# Note the device ID from the response

# Deploy and run the agent
./scripts/setup_agent.sh <macbook_ip> <device_id>
```

3. The agent runs 12 diagnostic steps and posts results live to the station display.

---

## Zebra Label Printer

### Setup

1. **Connect** the Zebra GX420d via USB to the Mac mini
2. The printer should appear in **System Settings → Printers & Scanners**
3. If not auto-detected, add it manually:
   - Click **+** → select the Zebra printer → use **Generic** driver → name it `Zebra_GX420d`

### Test Print

```bash
./scripts/test_print.sh
```

This sends a test label to verify the printer is connected.

### Manual ZPL Test

```bash
# Send raw ZPL directly
echo "^XA^FO30,30^CF0,40^FDTEST LABEL^FS^XZ" | lp -d Zebra_GX420d -o raw
```

### Label Specs

- **Size**: 4" x 2" (standard shipping label)
- **DPI**: 406 (GX420d)
- **Content**: Model, barcode (serial), specs, battery, grade, pass/fail, date, tech

### Troubleshooting Printer

| Issue | Fix |
|-------|-----|
| Printer not found | Check USB cable. Run `lpstat -p` to see CUPS printers |
| Blank labels | Calibrate: hold feed button for 3 seconds on power-on |
| Labels misaligned | Adjust label guides, recalibrate |
| CUPS error | Run `cupsctl --debug-logging` then check `/var/log/cups/error_log` |
| Permission denied | Add user to lpadmin group: `sudo dseditgroup -o edit -a $(whoami) -t user lpadmin` |

---

## Troubleshooting

### Server won't start

```bash
# Check if port 5000 is already in use
lsof -i :5000

# Kill existing process
kill $(lsof -ti :5000)

# Check Python dependencies
pip3 install -r requirements.txt

# Check logs
cat /tmp/aw-qc-server.err
```

### Station watcher can't find cfgutil

Apple Configurator must be installed from the Mac App Store. The watcher automatically falls back to polling `system_profiler` if cfgutil isn't available.

```bash
# Verify cfgutil
ls "/Applications/Apple Configurator.app/Contents/MacOS/cfgutil"

# Force polling mode
python3 station_watcher.py --poll
```

### Device not detected via USB

1. Try a different USB-C cable (data cables only, not charge-only)
2. Check if the MacBook appears in `system_profiler SPUSBDataType`
3. On the MacBook, trust the Mac mini when prompted
4. Restart the station watcher

### Station display stuck on LOADING

1. The station waits 8 seconds for real agent data, then simulates
2. If stuck beyond that, the agent may not be posting to the server
3. Check: `curl http://localhost:5000/health`
4. Refresh the station page in Safari

### Database issues

```bash
# Reset the database (WARNING: deletes all data)
rm -f instance/dev.db
python3 -c "
from dotenv import load_dotenv; load_dotenv()
from app import create_app, db
from app.services.test_definitions import seed_defaults
app = create_app()
with app.app_context():
    db.create_all()
    seed_defaults()
    print('Database reset')
"
```

### Wipe fails

- **MDM wipe**: Requires MicroMDM server running and device enrolled. Set `MDM_SERVER_URL` and `MDM_API_KEY` in `.env`.
- **cfgutil wipe**: Requires Apple Configurator and USB connection.
- Both fail: Device may need manual DFU restore via Apple Configurator GUI.

### Mac mini goes to sleep

```bash
# Disable all sleep
sudo pmset -a displaysleep 0 sleep 0 disksleep 0

# Verify settings
pmset -g

# The QC server launchd plist also runs caffeinate
```

---

## API Quick Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/` | GET | Dashboard |
| `/station` | GET | Station display |
| `/api/devices/` | GET | List all devices |
| `/api/devices/stats` | GET | Today's statistics |
| `/api/devices/detect` | POST | Register device by serial |
| `/api/devices/<id>` | PATCH | Update device fields |
| `/api/station/diagnostics` | POST | Post diagnostic step data |
| `/api/station/grade` | POST | Calculate device grade |
| `/api/station/print` | POST | Generate and print label |
| `/api/station/wipe` | POST | Wipe device via MDM/cfgutil |
| `/api/station/update` | POST | Broadcast station state |
| `/api/tests/batch` | POST | Submit batch test results |
| `/api/tests/device/<id>` | GET | Get device test results |

---

## File Layout

```
aw-qc-system/
├── run.py                  # Dev server entry point
├── wsgi.py                 # Production WSGI entry
├── agent.py                # Diagnostic agent (runs on MacBook)
├── station_watcher.py      # USB device detection daemon
├── on_attach.sh            # cfgutil attach handler
├── on_detach.sh            # cfgutil detach handler
├── app/
│   ├── __init__.py         # Flask app factory
│   ├── events.py           # SocketIO events
│   ├── routes/             # API endpoints
│   ├── models/             # SQLAlchemy models
│   ├── services/           # Grader, printer, test defs
│   ├── templates/          # HTML templates
│   └── static/             # CSS, JS
├── mdm/
│   ├── Dockerfile          # MicroMDM container
│   ├── enroll.mobileconfig # MDM enrollment profile
│   ├── ac_prepare.sh       # Apple Configurator prepare
│   ├── wipe.py             # Device wipe module
│   └── com.aerowholesale.*.plist  # launchd service definitions
├── scripts/
│   ├── setup_station.sh    # Full station setup
│   ├── setup_agent.sh      # Deploy agent to MacBook
│   └── test_print.sh       # Printer test
├── config/
│   └── settings.py         # Flask config
└── docs/
    └── OPERATIONS.md       # This file
```
