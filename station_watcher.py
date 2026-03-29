#!/usr/bin/env python3
"""
Station Watcher — runs 24/7 on the QC Mac mini.
Detects MacBooks plugged in via USB-C using Apple Configurator's cfgutil,
then notifies the local Flask server to start the QC process.
"""

import subprocess
import json
import time
import sys
import requests

SERVER = "http://localhost:5000"
POLL_INTERVAL = 3  # seconds between checks


def get_station_id():
    """Read station ID from config or hostname."""
    import socket
    return f"Station-{socket.gethostname().split('.')[0]}"


def detect_with_cfgutil():
    """Use cfgutil to detect connected Apple devices."""
    try:
        result = subprocess.run(
            ["cfgutil", "--format", "JSON", "list"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return None

        data = json.loads(result.stdout)
        devices = data.get("Output", {})
        if not devices:
            return None

        # Return first detected device
        for ecid, info in devices.items():
            return {
                "serial_number": info.get("serialNumber", ""),
                "model": info.get("marketingName", info.get("deviceType", "Unknown Mac")),
                "device_type": "macbook",
                "ecid": ecid,
            }
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return None
    return None


def detect_with_system_profiler():
    """Fallback: use system_profiler to detect USB-connected Macs in Target Disk/DFU mode."""
    try:
        result = subprocess.run(
            ["system_profiler", "SPUSBDataType", "-json"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            return None

        data = json.loads(result.stdout)
        usb_items = data.get("SPUSBDataType", [])

        for bus in usb_items:
            for item in bus.get("_items", []):
                name = item.get("_name", "").lower()
                if "apple" in name or "mac" in name:
                    serial = item.get("serial_num", "")
                    if serial:
                        return {
                            "serial_number": serial,
                            "model": item.get("_name", "Unknown Mac"),
                            "device_type": "macbook",
                        }
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return None
    return None


def notify_server(device_info, station_id):
    """Post detected device to the local QC server."""
    device_info["station_id"] = station_id
    try:
        resp = requests.post(
            f"{SERVER}/api/devices/detect",
            json=device_info,
            timeout=5,
        )
        data = resp.json()
        if data.get("existing"):
            print(f"  Device already in system: {data['warning']}")
        else:
            print(f"  Registered: {data['device']['serial_number']}")
        return data.get("device", {}).get("id")
    except requests.RequestException as e:
        print(f"  Server error: {e}")
        return None


def main():
    station_id = get_station_id()
    print(f"Station Watcher started — {station_id}")
    print(f"Server: {SERVER}")
    print(f"Polling every {POLL_INTERVAL}s for USB devices...")
    print()

    last_serial = None
    has_cfgutil = True

    while True:
        device = None

        if has_cfgutil:
            device = detect_with_cfgutil()
            if device is None and has_cfgutil:
                # Check once if cfgutil exists
                try:
                    subprocess.run(["which", "cfgutil"], capture_output=True, check=True)
                except subprocess.CalledProcessError:
                    print("cfgutil not found — falling back to system_profiler")
                    has_cfgutil = False

        if device is None:
            device = detect_with_system_profiler()

        if device and device.get("serial_number"):
            serial = device["serial_number"]
            if serial != last_serial:
                print(f"Detected: {device['model']} ({serial})")
                device_id = notify_server(device, station_id)
                if device_id:
                    last_serial = serial
        else:
            if last_serial is not None:
                print("Device disconnected")
                last_serial = None

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
