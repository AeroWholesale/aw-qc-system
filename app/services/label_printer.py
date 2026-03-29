import subprocess
import os


def generate_zpl(data):
    """
    Generate ZPL for a 4x2 label on Zebra GX420D (406 DPI).

    data keys:
      model, serial, ram, storage, color, battery_health,
      cycle_count, grade, passed, fail_reason, date, station, tech
    """
    model = data.get("model", "MacBook")
    serial = data.get("serial", "UNKNOWN")
    ram = data.get("ram", "")
    storage = data.get("storage", "")
    color = data.get("color", "")
    battery = data.get("battery_health", "")
    cycles = data.get("cycle_count", "")
    grade = data.get("grade", "")
    passed = data.get("passed", True)
    fail_reason = data.get("fail_reason", "")
    date = data.get("date", "")
    station = data.get("station", "")
    tech = data.get("tech", "")

    status = "PASS" if passed else "FAIL"
    specs_line = " · ".join(filter(None, [ram, storage, color]))
    battery_line = f"Battery: {battery}% · {cycles} cycles" if battery else ""

    zpl = f"""^XA
^CF0,24
^FO30,20^FDAEROWHOLESALE LLC^FS

^CF0,30
^FO30,55^FD{model}^FS

^BY2,2,80
^FO30,100^BC,,Y,N,N^FD{serial}^FS

^CF0,20
^FO30,200^FD{specs_line}^FS

^CF0,20
^FO30,228^FD{battery_line}^FS

^CF0,60
^FO540,55^FD{grade}^FS

^CF0,36
^FO540,120^FD{status}^FS
"""

    if not passed and fail_reason:
        zpl += f"""^CF0,18
^FO540,160^FD{fail_reason[:30]}^FS
"""

    zpl += f"""^CF0,16
^FO30,262^FD{date}  Stn:{station}  Tech:{tech}^FS
^XZ"""

    return zpl


def print_label(zpl):
    """
    Send ZPL to Zebra GX420D printer.
    Tries direct USB device first, then falls back to CUPS lp command.
    """
    # Try direct USB paths
    usb_paths = [
        "/dev/usb/lp0",
        "/dev/usblp0",
    ]
    for path in usb_paths:
        if os.path.exists(path):
            try:
                with open(path, "wb") as printer:
                    printer.write(zpl.encode("utf-8"))
                return {"success": True, "method": "usb_direct", "path": path}
            except (PermissionError, OSError) as e:
                continue

    # Fall back to CUPS
    try:
        result = subprocess.run(
            ["lp", "-d", "Zebra_GX420d", "-o", "raw"],
            input=zpl.encode("utf-8"),
            capture_output=True,
            timeout=10,
        )
        if result.returncode == 0:
            return {"success": True, "method": "cups"}

        # Try without specifying printer name (use default)
        result = subprocess.run(
            ["lp", "-o", "raw"],
            input=zpl.encode("utf-8"),
            capture_output=True,
            timeout=10,
        )
        if result.returncode == 0:
            return {"success": True, "method": "cups_default"}

        return {"success": False, "error": f"CUPS error: {result.stderr.decode()}"}
    except FileNotFoundError:
        return {"success": False, "error": "No printer found. Check USB connection."}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Printer timeout"}
