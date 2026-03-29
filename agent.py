#!/usr/bin/env python3
"""
AeroWholesale QC Diagnostic Agent
Runs on the MacBook being tested. Collects all hardware diagnostics
and posts results in real time to the QC station server.

Usage:
    python3 agent.py <server_ip> <device_id> [station_id]

Examples:
    python3 agent.py 192.168.1.50 42
    python3 agent.py 192.168.1.50 42 Station-3
    python3 agent.py localhost 42

The server URL is built as http://<server_ip>:5000
Results are posted step-by-step so the station display updates live.
A JSON backup is saved to ~/Desktop/qc_<serial>_<timestamp>.json
"""

import subprocess
import json
import os
import sys
import time
import re
import plistlib
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

# ═══════════════════════════════════════════════════════════════
#  CONFIG
# ═══════════════════════════════════════════════════════════════

SERVER = None       # set from argv
DEVICE_ID = None    # set from argv
STATION_ID = None   # set from argv or default

# Accumulated results — every step adds to this, and the full dict
# is sent each time so the station display always has the latest.
ALL_DATA = {}


# ═══════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════

def run(cmd, timeout=15):
    """Run a shell command, return stdout string. Never throws."""
    try:
        r = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        return r.stdout.strip()
    except Exception:
        return ""


def run_plist(cmd, timeout=15):
    """Run a command that outputs plist XML, return parsed dict/list."""
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, timeout=timeout)
        if r.returncode == 0 and r.stdout:
            return plistlib.loads(r.stdout)
    except Exception:
        pass
    return None


def post_step(step_name, data):
    """Post diagnostic step to the QC server. Updates ALL_DATA first."""
    ALL_DATA.update(data)
    payload = json.dumps({
        "device_id": DEVICE_ID,
        "step": step_name,
        "station_id": STATION_ID,
        "data": ALL_DATA,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{SERVER}/api/station/diagnostics",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        print(f"    ⚠ POST failed: {e}")


def fmt(label, value, width=22):
    """Format a key-value line for terminal output."""
    return f"    {label:<{width}} {value}"


# ═══════════════════════════════════════════════════════════════
#  DIAGNOSTIC STEPS
# ═══════════════════════════════════════════════════════════════

def step_hardware():
    """Model, chip, serial, RAM, cores."""
    d = {}
    sp = run_plist("system_profiler SPHardwareDataType -xml")
    if sp:
        hw = sp[0].get("_items", [{}])[0]
        d["model"] = hw.get("machine_name", "Unknown Mac")
        d["model_id"] = hw.get("machine_model", "")
        d["serial"] = hw.get("serial_number", run("ioreg -l | grep IOPlatformSerialNumber | awk '{print $4}' | tr -d '\"'"))
        d["chip"] = hw.get("chip_type", hw.get("cpu_type", ""))
        d["cores"] = str(hw.get("number_processors", ""))
        # RAM — Apple Silicon reports as "X GB"
        ram_raw = hw.get("physical_memory", "")
        d["ram"] = ram_raw.replace(" ", "") if ram_raw else ""
    else:
        # Fallback
        d["model"] = run("sysctl -n hw.model") or "Unknown"
        d["serial"] = run("ioreg -l | grep IOPlatformSerialNumber | awk '{print $4}' | tr -d '\"'")
        d["chip"] = run("sysctl -n machdep.cpu.brand_string")
        mem_bytes = run("sysctl -n hw.memsize")
        if mem_bytes:
            d["ram"] = f"{int(mem_bytes) // (1024**3)}GB"

    print(fmt("Model", d.get("model", "?")))
    print(fmt("Model ID", d.get("model_id", "?")))
    print(fmt("Serial", d.get("serial", "?")))
    print(fmt("Chip", d.get("chip", "?")))
    print(fmt("RAM", d.get("ram", "?")))
    return d


def step_system():
    """macOS version, uptime, storage size."""
    d = {}

    # macOS
    prod = run("sw_vers -productName")
    ver = run("sw_vers -productVersion")
    build = run("sw_vers -buildVersion")
    d["macos"] = f"{prod} {ver}" if prod else ver
    d["macos_build"] = build

    # Uptime
    boot_raw = run("sysctl -n kern.boottime")
    if boot_raw:
        m = re.search(r'sec\s*=\s*(\d+)', boot_raw)
        if m:
            boot_ts = int(m.group(1))
            uptime_secs = int(time.time()) - boot_ts
            days = uptime_secs // 86400
            hours = (uptime_secs % 86400) // 3600
            mins = (uptime_secs % 3600) // 60
            d["uptime"] = f"{days}d {hours}h {mins}m"
            d["uptime_seconds"] = uptime_secs

    # Storage — get the main APFS container size
    diskutil = run("diskutil info / 2>/dev/null")
    if diskutil:
        total_m = re.search(r'Disk Size.*?(\d+[\.,]?\d*)\s*(GB|TB)', diskutil)
        free_m = re.search(r'Container Free Space.*?(\d+[\.,]?\d*)\s*(GB|TB)', diskutil)
        if not free_m:
            free_m = re.search(r'Volume Free Space.*?(\d+[\.,]?\d*)\s*(GB|TB)', diskutil)
        if total_m:
            raw = float(total_m.group(1).replace(",", "."))
            unit = total_m.group(2)
            if unit == "TB":
                gb = raw * 1000
            else:
                gb = raw
            # Map to standard size
            for std in [128, 256, 512, 1000, 2000, 4000, 8000]:
                if gb <= std * 1.1:
                    d["storage"] = f"{std}GB" if std < 1000 else f"{std // 1000}TB"
                    break
            else:
                d["storage"] = f"{int(gb)}GB"
        if free_m:
            d["storage_free"] = f"{free_m.group(1)} {free_m.group(2)}"

    print(fmt("macOS", d.get("macos", "?")))
    print(fmt("Build", d.get("macos_build", "?")))
    print(fmt("Uptime", d.get("uptime", "?")))
    print(fmt("Storage", d.get("storage", "?")))
    print(fmt("Free Space", d.get("storage_free", "?")))
    return d


def step_battery():
    """Battery health %, cycle count, max/design capacity mAh, charging."""
    d = {}
    raw = run("ioreg -rc AppleSmartBattery")
    if not raw:
        print("    No battery data (desktop Mac?)")
        return d

    def extract(key):
        m = re.search(rf'"{key}"\s*=\s*(\w+)', raw)
        return m.group(1) if m else None

    max_cap = extract("MaxCapacity")
    design_cap = extract("DesignCapacity")
    cycle = extract("CycleCount")
    charging = extract("IsCharging")
    fully_charged = extract("FullyCharged")
    connected = extract("ExternalConnected")

    if max_cap and design_cap and int(design_cap) > 0:
        max_mah = int(max_cap)
        design_mah = int(design_cap)
        health = min(round(max_mah / design_mah * 100), 100)
        d["battery_health"] = health
        d["battery_max_mah"] = max_mah
        d["battery_design_mah"] = design_mah

    if cycle:
        d["cycle_count"] = int(cycle)

    if charging:
        d["charging"] = charging == "Yes"
    if fully_charged:
        d["fully_charged"] = fully_charged == "Yes"
    if connected:
        d["charger_connected"] = connected == "Yes"

    # Charge percentage
    cur_cap = extract("CurrentCapacity")
    if cur_cap and max_cap:
        d["charge_percent"] = min(round(int(cur_cap) / int(max_cap) * 100), 100)

    health_str = f"{d.get('battery_health', '?')}%"
    if d.get("battery_health", 100) < 80:
        health_str += " ⚠ LOW"
    print(fmt("Battery Health", health_str))
    print(fmt("Cycle Count", d.get("cycle_count", "?")))
    print(fmt("Max Capacity", f"{d.get('battery_max_mah', '?')} mAh"))
    print(fmt("Design Capacity", f"{d.get('battery_design_mah', '?')} mAh"))
    print(fmt("Charge", f"{d.get('charge_percent', '?')}%"))
    print(fmt("Charging", "Yes" if d.get("charging") else "No"))
    return d


def step_smart():
    """SMART disk status."""
    d = {}
    info = run("diskutil info disk0 2>/dev/null")
    if info:
        m = re.search(r'SMART Status:\s*(.+)', info)
        if m:
            d["smart_status"] = m.group(1).strip()

    if not d.get("smart_status"):
        # Try NVMe
        nvme = run("system_profiler SPNVMeDataType 2>/dev/null")
        if nvme:
            m = re.search(r'S\.M\.A\.R\.T\.\s*status:\s*(\S+)', nvme, re.IGNORECASE)
            if m:
                d["smart_status"] = m.group(1)

    if not d.get("smart_status"):
        d["smart_status"] = "Unknown"

    status = d["smart_status"]
    indicator = "✓" if status.lower() == "verified" else "✗ FAILING" if "fail" in status.lower() else "?"
    print(fmt("SMART Status", f"{status} {indicator}"))
    return d


def step_display():
    """Display resolution, type, all connected displays."""
    d = {}
    d["displays"] = []

    sp = run_plist("system_profiler SPDisplaysDataType -xml")
    if sp:
        for gpu in sp[0].get("_items", []):
            gpu_name = gpu.get("_name", "")
            for disp in gpu.get("spdisplays_ndrvs", []):
                info = {
                    "name": disp.get("_name", ""),
                    "resolution": disp.get("_spdisplays_resolution", ""),
                    "pixel_resolution": disp.get("_spdisplays_pixels", ""),
                    "type": disp.get("spdisplays_display_type", ""),
                    "gpu": gpu_name,
                    "mirror": disp.get("spdisplays_mirror", ""),
                    "retina": "Retina" in disp.get("_name", "") or "Retina" in disp.get("spdisplays_retina", ""),
                }
                d["displays"].append(info)

    if d["displays"]:
        d["display_count"] = len(d["displays"])
        main = d["displays"][0]
        d["display_resolution"] = main.get("resolution", "")
        d["display_type"] = main.get("type", "")
        for disp in d["displays"]:
            print(fmt("Display", f"{disp['name']} — {disp['resolution']}"))
    else:
        print("    No display info found")

    return d


def step_memory():
    """Memory pressure percentage."""
    d = {}
    vm = run("vm_stat")
    if not vm:
        print("    Could not read vm_stat")
        return d

    page_size = 16384
    pages = {}
    for line in vm.split("\n"):
        if "page size" in line.lower():
            m = re.search(r'(\d+)', line)
            if m:
                page_size = int(m.group(1))
        for key in ("free", "active", "inactive", "speculative", "wired"):
            if f"Pages {key}" in line:
                m = re.search(r'(\d+)', line.split(":")[1])
                if m:
                    pages[key] = int(m.group(1))

    total = sum(pages.values()) if pages else 0
    if total > 0:
        used = pages.get("active", 0) + pages.get("wired", 0)
        pressure = round(used / total * 100)
        d["mem_pressure"] = pressure
        d["mem_used_gb"] = round(used * page_size / (1024**3), 1)
        d["mem_total_pages"] = total
        print(fmt("Memory Pressure", f"{pressure}%"))
        print(fmt("Memory Used", f"{d['mem_used_gb']} GB"))
    else:
        print("    Could not parse memory stats")

    return d


def step_wifi():
    """WiFi hardware detection and current network."""
    d = {}

    airport = run(
        "/System/Library/PrivateFrameworks/Apple80211.framework"
        "/Versions/Current/Resources/airport -I 2>/dev/null"
    )
    if airport and "AirPort: Off" not in airport and "ERROR" not in airport:
        d["wifi"] = True
        ssid_m = re.search(r'\bSSID:\s*(.+)', airport)
        if ssid_m:
            d["wifi_ssid"] = ssid_m.group(1).strip()
        rssi_m = re.search(r'agrCtlRSSI:\s*(-?\d+)', airport)
        if rssi_m:
            d["wifi_rssi"] = int(rssi_m.group(1))
        channel_m = re.search(r'channel:\s*(\S+)', airport)
        if channel_m:
            d["wifi_channel"] = channel_m.group(1)
    else:
        # Fallback: check interface exists
        ifaces = run("networksetup -listallhardwareports 2>/dev/null")
        d["wifi"] = "Wi-Fi" in ifaces

    status = "Detected ✓" if d["wifi"] else "Not found ✗"
    print(fmt("WiFi", status))
    if d.get("wifi_ssid"):
        print(fmt("  Network", d["wifi_ssid"]))
    if d.get("wifi_rssi"):
        print(fmt("  Signal (RSSI)", f"{d['wifi_rssi']} dBm"))
    return d


def step_bluetooth():
    """Bluetooth hardware detection."""
    d = {}
    bt = run("system_profiler SPBluetoothDataType 2>/dev/null")
    if bt and "Bluetooth" in bt:
        d["bluetooth"] = True
        # Firmware
        fw_m = re.search(r'Firmware Version:\s*(.+)', bt)
        if fw_m:
            d["bluetooth_firmware"] = fw_m.group(1).strip()
        # Check power state
        if "State: On" in bt or "Powered: Yes" in bt:
            d["bluetooth_on"] = True
        else:
            d["bluetooth_on"] = False
    else:
        d["bluetooth"] = False

    status = "Detected ✓" if d["bluetooth"] else "Not found ✗"
    on = " (On)" if d.get("bluetooth_on") else " (Off)" if d.get("bluetooth") else ""
    print(fmt("Bluetooth", status + on))
    return d


def step_camera():
    """FaceTime camera detection."""
    d = {}
    sp = run_plist("system_profiler SPCameraDataType -xml")
    if sp:
        cams = sp[0].get("_items", [])
        d["camera"] = len(cams) > 0
        d["cameras"] = []
        for cam in cams:
            name = cam.get("_name", "Camera")
            d["cameras"].append(name)
    else:
        cam_text = run("system_profiler SPCameraDataType 2>/dev/null")
        d["camera"] = "FaceTime" in cam_text or "Camera" in cam_text
        d["cameras"] = []

    if d["camera"]:
        for name in d.get("cameras", ["FaceTime Camera"]):
            print(fmt("Camera", f"{name} ✓"))
    else:
        print(fmt("Camera", "Not found ✗"))
    return d


def step_audio():
    """Audio input/output device detection."""
    d = {}
    d["audio_outputs"] = []
    d["audio_inputs"] = []

    sp = run_plist("system_profiler SPAudioDataType -xml")
    if sp:
        for section in sp[0].get("_items", []):
            for dev in section.get("_items", []):
                name = dev.get("_name", "")
                # Determine type from available keys
                is_output = (
                    "coreaudio_device_output" in dev
                    or "speaker" in name.lower()
                    or "output" in name.lower()
                    or "headphone" in name.lower()
                )
                is_input = (
                    "coreaudio_device_input" in dev
                    or "microphone" in name.lower()
                    or "input" in name.lower()
                )
                if is_output:
                    d["audio_outputs"].append(name)
                if is_input:
                    d["audio_inputs"].append(name)
    else:
        audio_text = run("system_profiler SPAudioDataType 2>/dev/null")
        if "Speaker" in audio_text or "Output" in audio_text:
            d["audio_outputs"] = ["Built-in Speaker"]
        if "Microphone" in audio_text or "Input" in audio_text:
            d["audio_inputs"] = ["Built-in Microphone"]

    d["speakers"] = len(d["audio_outputs"]) > 0
    d["microphone"] = len(d["audio_inputs"]) > 0

    for name in d["audio_outputs"]:
        print(fmt("Audio Output", f"{name} ✓"))
    for name in d["audio_inputs"]:
        print(fmt("Audio Input", f"{name} ✓"))
    if not d["audio_outputs"] and not d["audio_inputs"]:
        print(fmt("Audio", "No devices found ✗"))
    return d


def step_security():
    """iCloud lock, MDM enrollment, FileVault, SIP."""
    d = {}

    # ── iCloud / Find My Mac ──
    # fmm-mobileme-token in NVRAM indicates Find My is enabled
    fmm = run("nvram -p 2>/dev/null | grep fmm-mobileme-token")
    d["icloud_locked"] = bool(fmm)

    # Also check activation lock via system_profiler if available
    if not d["icloud_locked"]:
        sp_hw = run("system_profiler SPHardwareDataType 2>/dev/null")
        if "Activation Lock Status" in sp_hw:
            d["icloud_locked"] = "Enabled" in sp_hw.split("Activation Lock Status")[1][:50]

    # ── MDM ──
    profiles = run("profiles status -type enrollment 2>/dev/null")
    if profiles:
        d["mdm_enrolled"] = "Yes" in profiles and "MDM" in profiles
    else:
        # Fallback: check for any configuration profiles
        prof_list = run("profiles list -all 2>/dev/null")
        d["mdm_enrolled"] = bool(prof_list and "com." in prof_list)

    # ── FileVault ──
    fv = run("fdesetup status 2>/dev/null")
    if "On" in fv:
        d["filevault"] = "On"
    elif "Off" in fv:
        d["filevault"] = "Off"
    else:
        d["filevault"] = "Unknown"

    # ── SIP (System Integrity Protection) ──
    sip = run("csrutil status 2>/dev/null")
    if "enabled" in sip.lower():
        d["sip"] = "Enabled"
    elif "disabled" in sip.lower():
        d["sip"] = "Disabled"
    else:
        d["sip"] = "Unknown"

    icloud_str = "LOCKED ✗" if d["icloud_locked"] else "OFF ✓"
    mdm_str = "Enrolled ✗" if d["mdm_enrolled"] else "Clean ✓"
    print(fmt("iCloud Lock", icloud_str))
    print(fmt("MDM", mdm_str))
    print(fmt("FileVault", d["filevault"]))
    print(fmt("SIP", d["sip"]))
    return d


def step_speeds():
    """Disk read/write speed benchmark (256MB test file)."""
    d = {}
    test_file = "/tmp/aw_qc_speedtest"
    block_count = 256  # 256 x 1MB = 256MB

    def parse_dd_speed(output):
        """Parse dd output to get MB/s."""
        # macOS dd outputs: "268435456 bytes transferred in 0.054178 secs (4953438869 bytes/sec)"
        m = re.search(r'(\d+) bytes transferred in ([\d.]+) secs', output)
        if m:
            total_bytes = int(m.group(1))
            seconds = float(m.group(2))
            if seconds > 0:
                return round(total_bytes / seconds / 1_000_000)
        # Alternative format: "XXX MB/s"
        m2 = re.search(r'([\d.]+)\s*([GMK]?B)/s', output, re.IGNORECASE)
        if m2:
            speed = float(m2.group(1))
            unit = m2.group(2).upper()
            if unit == "GB":
                return round(speed * 1000)
            elif unit == "KB":
                return round(speed / 1000)
            return round(speed)
        return None

    # Write test
    print("    Testing write speed (256MB)...")
    write_out = run(
        f"dd if=/dev/zero of={test_file} bs=1048576 count={block_count} 2>&1",
        timeout=60
    )
    write_speed = parse_dd_speed(write_out)
    if write_speed:
        d["disk_write"] = write_speed
        print(fmt("Disk Write", f"{write_speed:,} MB/s"))
    else:
        print(fmt("Disk Write", "Could not measure"))

    # Purge disk cache for accurate read test
    run("purge 2>/dev/null", timeout=10)
    time.sleep(0.5)

    # Read test
    print("    Testing read speed (256MB)...")
    read_out = run(
        f"dd if={test_file} of=/dev/null bs=1048576 2>&1",
        timeout=60
    )
    read_speed = parse_dd_speed(read_out)
    if read_speed:
        d["disk_read"] = read_speed
        print(fmt("Disk Read", f"{read_speed:,} MB/s"))
    else:
        print(fmt("Disk Read", "Could not measure"))

    # Cleanup
    run(f"rm -f {test_file}")
    return d


# ═══════════════════════════════════════════════════════════════
#  STEP REGISTRY
# ═══════════════════════════════════════════════════════════════

STEPS = [
    ("hardware",  step_hardware,  "Hardware Info"),
    ("battery",   step_battery,   "Battery"),
    ("system",    step_system,    "System / Storage"),
    ("smart",     step_smart,     "SMART Status"),
    ("display",   step_display,   "Display"),
    ("memory",    step_memory,    "Memory"),
    ("wifi",      step_wifi,      "WiFi"),
    ("bluetooth", step_bluetooth, "Bluetooth"),
    ("camera",    step_camera,    "Camera"),
    ("audio",     step_audio,     "Audio"),
    ("security",  step_security,  "Security"),
    ("speeds",    step_speeds,    "Disk Speed"),
]


# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════

def save_backup():
    """Save results to ~/Desktop as JSON backup."""
    serial = ALL_DATA.get("serial", "unknown")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"qc_{serial}_{ts}.json"
    desktop = Path.home() / "Desktop"
    if not desktop.exists():
        desktop = Path.home()
    filepath = desktop / filename
    with open(filepath, "w") as f:
        json.dump({
            "device_id": DEVICE_ID,
            "station_id": STATION_ID,
            "timestamp": datetime.now().isoformat(),
            "diagnostics": ALL_DATA,
        }, f, indent=2, default=str)
    return filepath


def main():
    global SERVER, DEVICE_ID, STATION_ID

    if len(sys.argv) < 3:
        print("AeroWholesale QC Diagnostic Agent")
        print()
        print("Usage:  python3 agent.py <server_ip> <device_id> [station_id]")
        print()
        print("  server_ip    IP of the QC Mac mini (e.g. 192.168.1.50 or localhost)")
        print("  device_id    Device ID from the QC system")
        print("  station_id   Optional station identifier (default: Station-1)")
        print()
        print("Example:")
        print("  python3 agent.py 192.168.1.50 42 Station-3")
        sys.exit(1)

    server_ip = sys.argv[1]
    DEVICE_ID = int(sys.argv[2])
    STATION_ID = sys.argv[3] if len(sys.argv) > 3 else "Station-1"

    # Build server URL — add http:// if not present
    if server_ip.startswith("http"):
        SERVER = server_ip.rstrip("/")
    else:
        SERVER = f"http://{server_ip}:5000"

    print()
    print("╔══════════════════════════════════════════════╗")
    print("║   AEROWHOLESALE QC DIAGNOSTIC AGENT         ║")
    print("╚══════════════════════════════════════════════╝")
    print()
    print(f"  Server:     {SERVER}")
    print(f"  Device ID:  {DEVICE_ID}")
    print(f"  Station:    {STATION_ID}")
    print()

    # Verify server is reachable
    try:
        r = urllib.request.urlopen(f"{SERVER}/health", timeout=5)
        if r.status == 200:
            print("  Server:     Connected ✓")
        else:
            print(f"  Server:     Responded with {r.status} ⚠")
    except Exception as e:
        print(f"  Server:     UNREACHABLE ✗ ({e})")
        print("  Continuing anyway — results will be saved locally.")

    print()
    print(f"  Running {len(STEPS)} diagnostic steps...")
    print("  " + "─" * 44)
    print()

    t_start = time.time()

    for i, (step_id, step_fn, step_label) in enumerate(STEPS, 1):
        header = f"  [{i:2}/{len(STEPS)}] {step_label}"
        print(header)
        t0 = time.time()

        try:
            result = step_fn()
        except Exception as e:
            result = {}
            print(f"    ERROR: {e}")

        elapsed = time.time() - t0
        print(f"    ── {elapsed:.1f}s")
        print()

        # Post to server
        post_step(step_id, result)

    total_time = time.time() - t_start

    # Save local backup
    backup_path = save_backup()

    print("  " + "─" * 44)
    print(f"  Done in {total_time:.1f}s")
    print(f"  Backup saved: {backup_path}")
    print()

    # Print summary
    print("  ┌─ SUMMARY ─────────────────────────────────┐")
    serial = ALL_DATA.get("serial", "?")
    model = ALL_DATA.get("model", "?")
    bat = ALL_DATA.get("battery_health", "?")
    cyc = ALL_DATA.get("cycle_count", "?")
    smart = ALL_DATA.get("smart_status", "?")
    icloud = "LOCKED" if ALL_DATA.get("icloud_locked") else "Clean"
    mdm = "Enrolled" if ALL_DATA.get("mdm_enrolled") else "Clean"
    print(f"  │  {model}")
    print(f"  │  Serial: {serial}")
    print(f"  │  Battery: {bat}% · {cyc} cycles")
    print(f"  │  SMART: {smart}")
    print(f"  │  iCloud: {icloud}  MDM: {mdm}")
    print(f"  │  {ALL_DATA.get('ram', '?')} · {ALL_DATA.get('storage', '?')}")
    if ALL_DATA.get("disk_read"):
        print(f"  │  Disk: {ALL_DATA['disk_read']:,} MB/s read · {ALL_DATA.get('disk_write', '?'):,} MB/s write")
    print(f"  └──────────────────────────────────────────┘")
    print()


if __name__ == "__main__":
    main()
