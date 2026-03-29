#!/usr/bin/env python3
"""
AeroWholesale QC Station Watcher
Runs 24/7 on the QC Mac mini. Detects MacBooks plugged in via USB-C.

Primary mode:  cfgutil exec (Apple Configurator) — event-driven, instant
Fallback mode: polling system_profiler every 3 seconds

When a device is detected:
  1. Reads serial number via cfgutil
  2. Creates/finds device record on the QC server
  3. Triggers the station display to start the LOADING state

Usage:
    python3 station_watcher.py                    # default Station-1
    python3 station_watcher.py --station Station-3
    python3 station_watcher.py --poll              # force polling mode
    QC_STATION_ID=Station-2 python3 station_watcher.py
"""

import subprocess
import json
import os
import sys
import time
import signal
import argparse

CFGUTIL = "/Applications/Apple Configurator.app/Contents/MacOS/cfgutil"
SERVER = "http://localhost:5000"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ATTACH_SCRIPT = os.path.join(SCRIPT_DIR, "on_attach.sh")
DETACH_SCRIPT = os.path.join(SCRIPT_DIR, "on_detach.sh")


def has_cfgutil():
    return os.path.isfile(CFGUTIL)


def run_cfgutil_exec(station_id):
    """
    Run cfgutil exec — blocks forever, calls on_attach.sh / on_detach.sh
    when devices are plugged in or out. This is the primary mode.
    """
    env = os.environ.copy()
    env["QC_STATION_ID"] = station_id

    print(f"  Mode:       cfgutil exec (event-driven)")
    print(f"  Attach:     {ATTACH_SCRIPT}")
    print(f"  Detach:     {DETACH_SCRIPT}")
    print(f"  Log:        /tmp/aw_qc_attach.log")
    print()
    print("  Waiting for USB device connections...")
    print()

    proc = subprocess.Popen(
        [CFGUTIL, "exec", "-a", ATTACH_SCRIPT, "-d", DETACH_SCRIPT],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    # Forward cfgutil output to terminal
    try:
        for line in proc.stdout:
            line = line.strip()
            if line:
                print(f"  [cfgutil] {line}")
    except KeyboardInterrupt:
        proc.terminate()
        raise

    return proc.wait()


def run_polling_mode(station_id):
    """
    Fallback: poll system_profiler for USB devices every 3 seconds.
    Used when cfgutil is not available.
    """
    import re

    print(f"  Mode:       Polling (system_profiler, every 3s)")
    print()
    print("  Waiting for USB device connections...")
    print()

    last_serial = None

    while True:
        try:
            r = subprocess.run(
                ["system_profiler", "SPUSBDataType", "-json"],
                capture_output=True, text=True, timeout=15,
            )
            if r.returncode != 0:
                time.sleep(3)
                continue

            data = json.loads(r.stdout)
            serial = None
            model = None

            # Walk USB tree looking for Apple devices
            def walk_usb(items):
                nonlocal serial, model
                for item in items:
                    name = item.get("_name", "").lower()
                    vendor = item.get("manufacturer", "").lower()
                    if "apple" in vendor or "mac" in name:
                        s = item.get("serial_num", "")
                        if s and len(s) > 8:
                            serial = s
                            model = item.get("_name", "Unknown Mac")
                    # Recurse into child items
                    if "_items" in item:
                        walk_usb(item["_items"])

            for bus in data.get("SPUSBDataType", []):
                if "_items" in bus:
                    walk_usb(bus["_items"])

            if serial and serial != last_serial:
                print(f"  Detected: {model} ({serial})")
                last_serial = serial

                # Register with server
                try:
                    import urllib.request
                    payload = json.dumps({
                        "serial_number": serial,
                        "device_type": "macbook",
                        "model": model or "Unknown Mac",
                        "station_id": station_id,
                    }).encode()
                    req = urllib.request.Request(
                        f"{SERVER}/api/devices/detect",
                        data=payload,
                        headers={"Content-Type": "application/json"},
                    )
                    resp = urllib.request.urlopen(req, timeout=5)
                    result = json.loads(resp.read())
                    device = result.get("device", {})
                    device_id = device.get("id")
                    print(f"  Device ID: {device_id}")

                    if device_id:
                        # Mark as testing
                        patch_data = json.dumps({
                            "status": "testing",
                            "station_id": station_id,
                        }).encode()
                        req2 = urllib.request.Request(
                            f"{SERVER}/api/devices/{device_id}",
                            data=patch_data,
                            headers={"Content-Type": "application/json"},
                            method="PATCH",
                        )
                        urllib.request.urlopen(req2, timeout=5)

                        # Notify station display
                        update_data = json.dumps({
                            "station_id": station_id,
                            "state": "loading",
                            "device": device,
                        }).encode()
                        req3 = urllib.request.Request(
                            f"{SERVER}/api/station/update",
                            data=update_data,
                            headers={"Content-Type": "application/json"},
                        )
                        urllib.request.urlopen(req3, timeout=5)
                        print(f"  Station display notified — LOADING")
                except Exception as e:
                    print(f"  Server error: {e}")

            elif not serial and last_serial:
                print(f"  Device disconnected")
                last_serial = None
                try:
                    import urllib.request
                    update_data = json.dumps({
                        "station_id": station_id,
                        "state": "idle",
                        "device": None,
                    }).encode()
                    req = urllib.request.Request(
                        f"{SERVER}/api/station/update",
                        data=update_data,
                        headers={"Content-Type": "application/json"},
                    )
                    urllib.request.urlopen(req, timeout=5)
                except Exception:
                    pass

        except json.JSONDecodeError:
            pass
        except KeyboardInterrupt:
            raise

        time.sleep(3)


def main():
    parser = argparse.ArgumentParser(description="AeroWholesale QC Station Watcher")
    parser.add_argument("--station", default=os.environ.get("QC_STATION_ID", "Station-1"),
                        help="Station ID (default: Station-1)")
    parser.add_argument("--poll", action="store_true",
                        help="Force polling mode (skip cfgutil)")
    args = parser.parse_args()

    station_id = args.station

    print()
    print("╔══════════════════════════════════════════════╗")
    print("║   AEROWHOLESALE QC STATION WATCHER          ║")
    print("╚══════════════════════════════════════════════╝")
    print()
    print(f"  Station:    {station_id}")
    print(f"  Server:     {SERVER}")
    print(f"  cfgutil:    {'Found ✓' if has_cfgutil() else 'Not found ✗'}")
    print()

    # Verify server is reachable
    try:
        import urllib.request
        r = urllib.request.urlopen(f"{SERVER}/health", timeout=5)
        print(f"  Server:     Connected ✓")
    except Exception as e:
        print(f"  Server:     UNREACHABLE ✗ ({e})")
        print("  Start the QC server first: python run.py")
        sys.exit(1)

    print()

    try:
        if has_cfgutil() and not args.poll:
            run_cfgutil_exec(station_id)
        else:
            if not args.poll:
                print("  cfgutil not available, using polling mode")
                print()
            run_polling_mode(station_id)
    except KeyboardInterrupt:
        print("\n  Watcher stopped.")


if __name__ == "__main__":
    main()
