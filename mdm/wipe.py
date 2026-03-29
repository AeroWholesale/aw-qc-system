"""
AeroWholesale QC — Device Wipe Module
Sends EraseDevice MDM command via MicroMDM API, falls back to cfgutil erase.
"""

import os
import json
import subprocess
import urllib.request
import urllib.error


MDM_SERVER_URL = os.environ.get("MDM_SERVER_URL", "https://mdm.aerowholesale.com")
MDM_API_KEY = os.environ.get("MDM_API_KEY", "")


def wipe_via_mdm(device_udid):
    """Send EraseDevice command through MicroMDM API."""
    url = f"{MDM_SERVER_URL}/v1/commands"
    payload = json.dumps({
        "udid": device_udid,
        "request_type": "EraseDevice",
    }).encode()

    req = urllib.request.Request(url, data=payload, method="POST", headers={
        "Content-Type": "application/json",
        "Authorization": f"Basic {MDM_API_KEY}",
    })

    try:
        resp = urllib.request.urlopen(req, timeout=30)
        data = json.loads(resp.read())
        return {"ok": True, "method": "mdm", "response": data}
    except (urllib.error.URLError, urllib.error.HTTPError) as e:
        return {"ok": False, "method": "mdm", "error": str(e)}


def wipe_via_cfgutil(ecid=None):
    """Fallback: erase device using Apple Configurator cfgutil."""
    cmd = ["cfgutil"]
    if ecid:
        cmd += ["--ecid", ecid]
    cmd.append("erase")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if result.returncode == 0:
            return {"ok": True, "method": "cfgutil", "output": result.stdout}
        else:
            return {"ok": False, "method": "cfgutil", "error": result.stderr}
    except subprocess.TimeoutExpired:
        return {"ok": False, "method": "cfgutil", "error": "Erase timed out after 180s"}
    except FileNotFoundError:
        return {"ok": False, "method": "cfgutil", "error": "cfgutil not found"}


def wipe_device(device_udid=None, ecid=None):
    """Attempt MDM wipe first, fall back to cfgutil erase."""
    if device_udid:
        result = wipe_via_mdm(device_udid)
        if result["ok"]:
            return result

    # Fallback to cfgutil
    return wipe_via_cfgutil(ecid=ecid)


if __name__ == "__main__":
    import sys
    udid = sys.argv[1] if len(sys.argv) > 1 else None
    ecid = sys.argv[2] if len(sys.argv) > 2 else None
    result = wipe_device(device_udid=udid, ecid=ecid)
    print(json.dumps(result, indent=2))
