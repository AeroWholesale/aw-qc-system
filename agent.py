#!/usr/bin/env python3
"""
AeroWholesale QC Agent — runs on the MacBook being tested.
Collects hardware diagnostics and posts results to the QC station server.

Usage:
    python3 agent.py <server_url> <device_id>
    python3 agent.py http://192.168.1.50:5000 42

The agent runs through 12 diagnostic steps, posting each result
to the server in real time. The station display updates as each
step completes.
"""

import subprocess
import json
import sys
import time
import re
import plistlib


def run_cmd(cmd, timeout=15):
    """Run a shell command and return stdout."""
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except (subprocess.TimeoutExpired, Exception):
        return ""


def run_plist_cmd(cmd, timeout=15):
    """Run a command that outputs plist XML and parse it."""
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, timeout=timeout)
        if r.returncode == 0 and r.stdout:
            return plistlib.loads(r.stdout)
    except Exception:
        pass
    return {}


def post_step(server, device_id, step, data):
    """Post a diagnostic step result to the QC server."""
    import urllib.request
    payload = json.dumps({
        "device_id": device_id,
        "step": step,
        "data": data,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{server}/api/station/diagnostics",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        print(f"  [!] Failed to post {step}: {e}")


# ═══════════════════════════════════════════
#  DIAGNOSTIC STEPS
# ═══════════════════════════════════════════

def diag_hardware():
    """Step 1: Basic hardware info — model, serial, RAM, storage, macOS."""
    data = {}

    # Model and serial from system_profiler
    sp = run_plist_cmd("system_profiler SPHardwareDataType -xml")
    if sp:
        items = sp[0].get("_items", [{}])
        hw = items[0] if items else {}
        data["model"] = hw.get("machine_name", "")
        data["model_id"] = hw.get("machine_model", "")
        data["serial"] = hw.get("serial_number", "")
        data["chip"] = hw.get("chip_type", hw.get("cpu_type", ""))

        # RAM
        ram_raw = hw.get("physical_memory", "")
        data["ram"] = ram_raw

        # Cores
        cores = hw.get("number_processors", "")
        data["cores"] = str(cores)

    # Storage
    diskutil = run_cmd("diskutil info -all / 2>/dev/null | grep 'Disk Size'")
    if diskutil:
        match = re.search(r'(\d+\.?\d*)\s*(GB|TB)', diskutil)
        if match:
            size = float(match.group(1))
            unit = match.group(2)
            if unit == "TB":
                data["storage"] = f"{size} TB"
            else:
                # Round to nearest standard size
                std = [128, 256, 512, 1024, 2048]
                closest = min(std, key=lambda x: abs(x - size))
                data["storage"] = f"{closest}GB" if closest < 1024 else f"{closest // 1024}TB"

    # Fallback storage from diskutil list
    if not data.get("storage"):
        apfs = run_cmd("diskutil apfs list 2>/dev/null | grep 'Capacity' | head -1")
        if apfs:
            match = re.search(r'(\d+\.?\d*)\s*(GB|TB)', apfs)
            if match:
                data["storage"] = f"{match.group(1)} {match.group(2)}"

    # macOS version
    sw = run_cmd("sw_vers -productName") + " " + run_cmd("sw_vers -productVersion")
    data["macos"] = sw.strip()

    # Color (from model identifier if possible)
    data["color"] = ""

    return data


def diag_battery():
    """Step 2: Battery health and cycle count."""
    data = {}

    # ioreg battery info
    bat_raw = run_cmd("ioreg -rc AppleSmartBattery")
    if bat_raw:
        # Max capacity
        max_cap = re.search(r'"MaxCapacity"\s*=\s*(\d+)', bat_raw)
        design_cap = re.search(r'"DesignCapacity"\s*=\s*(\d+)', bat_raw)
        cycle = re.search(r'"CycleCount"\s*=\s*(\d+)', bat_raw)

        if max_cap and design_cap:
            health = round(int(max_cap.group(1)) / int(design_cap.group(1)) * 100)
            data["battery_health"] = min(health, 100)

        if cycle:
            data["cycle_count"] = int(cycle.group(1))

        # Charging state
        charging = re.search(r'"IsCharging"\s*=\s*(Yes|No)', bat_raw)
        data["charging"] = charging.group(1) == "Yes" if charging else False

    # Fallback: system_profiler
    if "battery_health" not in data:
        sp = run_plist_cmd("system_profiler SPPowerDataType -xml")
        if sp:
            items = sp[0].get("_items", [{}])
            for item in items:
                health_info = item.get("sppower_battery_health_info", {})
                if health_info:
                    condition = health_info.get("sppower_battery_health", "")
                    data["battery_condition"] = condition
                    cycle = health_info.get("sppower_battery_cycle_count", 0)
                    data["cycle_count"] = cycle
                    max_cap = health_info.get("sppower_battery_max_capacity", 0)
                    if isinstance(max_cap, str) and "%" in max_cap:
                        data["battery_health"] = int(max_cap.replace("%", ""))
                    elif isinstance(max_cap, int):
                        data["battery_health"] = max_cap

    return data


def diag_storage():
    """Step 3: Storage details."""
    data = {}

    # APFS container info
    container = run_cmd("diskutil apfs list 2>/dev/null")
    if container:
        total = re.search(r'Capacity.*?(\d+\.?\d*)\s*(GB|TB)', container)
        free = re.search(r'Free.*?(\d+\.?\d*)\s*(GB|TB)', container)
        if total:
            data["disk_total"] = f"{total.group(1)} {total.group(2)}"
        if free:
            data["disk_free"] = f"{free.group(1)} {free.group(2)}"

    return data


def diag_smart():
    """Step 4: SMART disk status."""
    data = {}

    smart = run_cmd("diskutil info disk0 2>/dev/null | grep 'SMART Status'")
    if smart:
        status = smart.split(":")[-1].strip()
        data["smart_status"] = status  # "Verified" = good
    else:
        # Try alternate
        smart2 = run_cmd("system_profiler SPNVMeDataType 2>/dev/null | grep -i 'smart' | head -1")
        if smart2:
            data["smart_status"] = smart2.split(":")[-1].strip()
        else:
            data["smart_status"] = "Unknown"

    return data


def diag_display():
    """Step 5: Display info."""
    data = {}

    sp = run_plist_cmd("system_profiler SPDisplaysDataType -xml")
    if sp:
        items = sp[0].get("_items", [{}])
        for item in items:
            displays = item.get("spdisplays_ndrvs", [])
            for d in displays:
                res = d.get("_spdisplays_resolution", "")
                data["display_resolution"] = res
                data["display_name"] = d.get("_name", "")
                data["display_type"] = d.get("spdisplays_display_type", "")

    return data


def diag_memory():
    """Step 6: Memory pressure and usage."""
    data = {}

    # Memory pressure via vm_stat
    vm = run_cmd("vm_stat")
    if vm:
        pages_free = 0
        pages_active = 0
        pages_inactive = 0
        pages_wired = 0
        page_size = 16384  # Apple Silicon default

        for line in vm.split("\n"):
            if "page size" in line.lower():
                m = re.search(r'(\d+)', line)
                if m:
                    page_size = int(m.group(1))
            if "Pages free" in line:
                m = re.search(r'(\d+)', line.split(":")[1])
                if m: pages_free = int(m.group(1))
            if "Pages active" in line:
                m = re.search(r'(\d+)', line.split(":")[1])
                if m: pages_active = int(m.group(1))
            if "Pages inactive" in line:
                m = re.search(r'(\d+)', line.split(":")[1])
                if m: pages_inactive = int(m.group(1))
            if "Pages wired" in line:
                m = re.search(r'(\d+)', line.split(":")[1])
                if m: pages_wired = int(m.group(1))

        total = pages_free + pages_active + pages_inactive + pages_wired
        if total > 0:
            used = pages_active + pages_wired
            pressure = round(used / total * 100)
            data["mem_pressure"] = pressure

    return data


def diag_wifi():
    """Step 7: WiFi detection."""
    data = {}

    # Check for WiFi hardware
    airport = run_cmd("/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport -I 2>/dev/null")
    if airport and "AirPort" not in airport:
        data["wifi"] = True
        ssid = re.search(r'SSID:\s*(.+)', airport)
        if ssid:
            data["wifi_ssid"] = ssid.group(1).strip()
    else:
        # Fallback
        sp = run_plist_cmd("system_profiler SPNetworkDataType -xml")
        if sp:
            for item in sp[0].get("_items", []):
                if "Wi-Fi" in item.get("_name", "") or "wi-fi" in item.get("type", "").lower():
                    data["wifi"] = True
                    break

    if "wifi" not in data:
        iface = run_cmd("networksetup -listallhardwareports 2>/dev/null | grep -A1 Wi-Fi | grep Device")
        data["wifi"] = bool(iface)

    return data


def diag_bluetooth():
    """Step 8: Bluetooth detection."""
    data = {}

    bt = run_cmd("system_profiler SPBluetoothDataType 2>/dev/null")
    if bt:
        data["bluetooth"] = "Bluetooth" in bt
        # Check if powered on
        if "State: On" in bt or "Powered: Yes" in bt:
            data["bluetooth_on"] = True
    else:
        data["bluetooth"] = False

    return data


def diag_camera():
    """Step 9: Camera detection."""
    data = {}

    sp = run_plist_cmd("system_profiler SPCameraDataType -xml")
    if sp:
        items = sp[0].get("_items", [])
        data["camera"] = len(items) > 0
        if items:
            data["camera_name"] = items[0].get("_name", "FaceTime Camera")
    else:
        # Fallback
        cam = run_cmd("system_profiler SPCameraDataType 2>/dev/null")
        data["camera"] = "FaceTime" in cam or "Camera" in cam

    return data


def diag_audio():
    """Step 10: Audio device detection."""
    data = {}

    sp = run_plist_cmd("system_profiler SPAudioDataType -xml")
    if sp:
        items = sp[0].get("_items", [])
        outputs = []
        inputs = []
        for item in items:
            for dev in item.get("_items", []):
                name = dev.get("_name", "")
                if "output" in str(dev.get("coreaudio_output_source", "")).lower() or "speaker" in name.lower():
                    outputs.append(name)
                if "input" in str(dev.get("coreaudio_input_source", "")).lower() or "microphone" in name.lower():
                    inputs.append(name)
        data["speakers"] = len(outputs) > 0
        data["microphone"] = len(inputs) > 0
    else:
        audio = run_cmd("system_profiler SPAudioDataType 2>/dev/null")
        data["speakers"] = "Speaker" in audio or "Output" in audio
        data["microphone"] = "Microphone" in audio or "Input" in audio

    return data


def diag_security():
    """Step 11: Security checks — iCloud lock, MDM, FileVault, SIP."""
    data = {}

    # Activation Lock (Requires MDM or cfgutil to check reliably)
    # Check profiles for MDM
    profiles = run_cmd("profiles status -type enrollment 2>/dev/null")
    if profiles:
        data["mdm_enrolled"] = "MDM enrollment" in profiles and "No" not in profiles
    else:
        # Fallback: check for any configuration profiles
        prof_list = run_cmd("profiles list 2>/dev/null")
        data["mdm_enrolled"] = bool(prof_list and "attribute" in prof_list.lower())

    # iCloud — check if Find My Mac is enabled (indicator of iCloud lock)
    fmm = run_cmd("nvram -p 2>/dev/null | grep fmm-mobileme-token")
    data["icloud_locked"] = bool(fmm)

    # FileVault
    fv = run_cmd("fdesetup status 2>/dev/null")
    if "On" in fv:
        data["filevault"] = "On"
    elif "Off" in fv:
        data["filevault"] = "Off"
    else:
        data["filevault"] = "Unknown"

    # SIP (System Integrity Protection)
    sip = run_cmd("csrutil status 2>/dev/null")
    if "enabled" in sip.lower():
        data["sip"] = "Enabled"
    elif "disabled" in sip.lower():
        data["sip"] = "Disabled"
    else:
        data["sip"] = "Unknown"

    return data


def diag_speeds():
    """Step 12: Disk read/write speed test."""
    data = {}

    # Write speed test (256MB)
    write_out = run_cmd(
        "dd if=/dev/zero of=/tmp/qc_speed_test bs=1048576 count=256 2>&1 | tail -1",
        timeout=30,
    )
    if write_out:
        # Parse: "256+0 records out ... bytes/sec" or "bytes transferred ... bytes/sec"
        match = re.search(r'(\d+\.?\d*)\s*(bytes|MB|GB)/sec', write_out, re.IGNORECASE)
        if match:
            speed = float(match.group(1))
            unit = match.group(2).upper()
            if unit == "BYTES":
                speed = round(speed / 1_000_000)
            elif unit == "GB":
                speed = round(speed * 1000)
            else:
                speed = round(speed)
            data["disk_write"] = speed

    # Read speed test
    run_cmd("purge 2>/dev/null", timeout=5)  # Clear disk cache
    read_out = run_cmd(
        "dd if=/tmp/qc_speed_test of=/dev/null bs=1048576 2>&1 | tail -1",
        timeout=30,
    )
    if read_out:
        match = re.search(r'(\d+\.?\d*)\s*(bytes|MB|GB)/sec', read_out, re.IGNORECASE)
        if match:
            speed = float(match.group(1))
            unit = match.group(2).upper()
            if unit == "BYTES":
                speed = round(speed / 1_000_000)
            elif unit == "GB":
                speed = round(speed * 1000)
            else:
                speed = round(speed)
            data["disk_read"] = speed

    # Cleanup
    run_cmd("rm -f /tmp/qc_speed_test")

    return data


# ═══════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════

STEPS = [
    ("hardware", diag_hardware),
    ("battery", diag_battery),
    ("storage", diag_storage),
    ("smart", diag_smart),
    ("display", diag_display),
    ("memory", diag_memory),
    ("wifi", diag_wifi),
    ("bluetooth", diag_bluetooth),
    ("camera", diag_camera),
    ("audio", diag_audio),
    ("security", diag_security),
    ("speeds", diag_speeds),
]


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 agent.py <server_url> <device_id>")
        print("Example: python3 agent.py http://192.168.1.50:5000 42")
        sys.exit(1)

    server = sys.argv[1].rstrip("/")
    device_id = int(sys.argv[2])

    print(f"AeroWholesale QC Agent")
    print(f"Server: {server}")
    print(f"Device ID: {device_id}")
    print(f"Running {len(STEPS)} diagnostic steps...\n")

    all_data = {}
    for step_name, step_fn in STEPS:
        print(f"  [{step_name}] ", end="", flush=True)
        t0 = time.time()
        try:
            result = step_fn()
            all_data.update(result)
            elapsed = time.time() - t0
            print(f"done ({elapsed:.1f}s) — {result}")
        except Exception as e:
            print(f"error: {e}")
            result = {}

        post_step(server, device_id, step_name, all_data)

    print(f"\nAll diagnostics complete.")
    print(f"Summary:")
    for k, v in sorted(all_data.items()):
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
