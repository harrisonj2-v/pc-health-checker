#!/usr/bin/env python3
"""
PC Health Checker
-----------------
Runs a quick health check on the computer it is launched on and prints a
plain-language report: system info, memory, disk space, battery, and
network, each marked OK, WARN, or FAIL.

Works on Windows, macOS, and Linux. Python 3 standard library only --
nothing to install, no admin rights needed, and it only reads system
information (it never changes any settings).

Usage:
    python3 pc_health_check.py            # print the report
    python3 pc_health_check.py --save     # also save it to a .txt file
"""

import os
import platform
import shutil
import socket
import subprocess
import sys
from datetime import datetime, timedelta

OK, WARN, FAIL, INFO = "OK", "WARN", "FAIL", "INFO"


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def gb(num_bytes):
    return num_bytes / (1024 ** 3)


def tag(status):
    return f"[{status}]"


def run_quiet(command):
    """Run a command and return its stdout, or '' if anything goes wrong."""
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip()
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# System information
# ---------------------------------------------------------------------------

def cpu_model():
    system = platform.system()
    if system == "Windows":
        return os.environ.get("PROCESSOR_IDENTIFIER", "") or platform.processor()
    if system == "Linux":
        try:
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if line.lower().startswith("model name"):
                        return line.split(":", 1)[1].strip()
        except OSError:
            pass
        return platform.processor() or platform.machine()
    if system == "Darwin":
        return run_quiet(["sysctl", "-n", "machdep.cpu.brand_string"]) \
            or platform.processor()
    return platform.processor() or platform.machine()


def uptime():
    """Best-effort system uptime as a timedelta, or None if unknown."""
    system = platform.system()
    try:
        if system == "Windows":
            import ctypes
            millis = ctypes.windll.kernel32.GetTickCount64()
            return timedelta(milliseconds=int(millis))
        if system == "Linux":
            with open("/proc/uptime") as f:
                return timedelta(seconds=float(f.read().split()[0]))
        if system == "Darwin":
            out = run_quiet(["sysctl", "-n", "kern.boottime"])
            # looks like: { sec = 1699900000, usec = 0 } ...
            sec = int(out.split("sec =")[1].split(",")[0].strip())
            return datetime.now() - datetime.fromtimestamp(sec)
    except Exception:
        return None
    return None


def system_info(lines):
    lines.append("SYSTEM")
    lines.append(f"  Computer name : {platform.node() or 'unknown'}")
    lines.append(f"  Operating sys : {platform.system()} {platform.release()} "
                 f"({platform.version()})")
    lines.append(f"  Architecture  : {platform.machine()}")
    model = cpu_model()
    if model:
        lines.append(f"  Processor     : {model}")
    lines.append(f"  CPU cores     : {os.cpu_count() or 'unknown'} logical")
    up = uptime()
    if up is not None:
        days = up.days
        hours, rem = divmod(up.seconds, 3600)
        minutes = rem // 60
        text = f"{days}d {hours}h {minutes}m" if days else f"{hours}h {minutes}m"
        lines.append(f"  Uptime        : {text}")
    try:
        load1 = os.getloadavg()[0]
        lines.append(f"  Load (1 min)  : {load1:.2f}")
    except (AttributeError, OSError):
        pass  # getloadavg is Unix-only
    lines.append("")


# ---------------------------------------------------------------------------
# Memory
# ---------------------------------------------------------------------------

def memory_info():
    """Return (total_bytes, available_bytes) or (None, None)."""
    system = platform.system()
    try:
        if system == "Windows":
            import ctypes

            class MemoryStatus(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            status = MemoryStatus()
            status.dwLength = ctypes.sizeof(MemoryStatus)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
            return status.ullTotalPhys, status.ullAvailPhys
        if system == "Linux":
            values = {}
            with open("/proc/meminfo") as f:
                for line in f:
                    key, _, rest = line.partition(":")
                    values[key.strip()] = int(rest.split()[0]) * 1024
            return values["MemTotal"], values["MemAvailable"]
        if system == "Darwin":
            total = int(run_quiet(["sysctl", "-n", "hw.memsize"]))
            vm = run_quiet(["vm_stat"])
            page_size = 4096
            free_pages = 0
            for line in vm.splitlines():
                if "page size of" in line:
                    page_size = int(line.split("page size of")[1].split()[0])
                if line.startswith("Pages free"):
                    free_pages = int(line.split(":")[1].strip().rstrip("."))
            return total, free_pages * page_size
    except Exception:
        return None, None
    return None, None


def memory_check(lines, problems):
    total, available = memory_info()
    lines.append("MEMORY")
    if total is None:
        lines.append(f"  {tag(INFO)} Could not read memory information.")
    else:
        used = total - available
        pct = used / total * 100
        if pct >= 95:
            status = FAIL
        elif pct >= 85:
            status = WARN
        else:
            status = OK
        if status != OK:
            problems.append(f"Memory is {pct:.0f}% used")
        lines.append(f"  {tag(status)} RAM: {gb(used):.1f} of {gb(total):.1f} GB "
                     f"used ({pct:.0f}%)")
    lines.append("")


# ---------------------------------------------------------------------------
# Disk space
# ---------------------------------------------------------------------------

def drives_to_check():
    if platform.system() == "Windows":
        import string
        drives = []
        for letter in string.ascii_uppercase:
            root = f"{letter}:\\"
            if os.path.exists(root):
                drives.append(root)
        return drives
    return ["/"]


def disk_checks(lines, problems):
    lines.append("DISK SPACE")
    for drive in drives_to_check():
        try:
            usage = shutil.disk_usage(drive)
        except OSError:
            continue
        pct = usage.used / usage.total * 100
        if pct >= 95:
            status = FAIL
        elif pct >= 85:
            status = WARN
        else:
            status = OK
        if status != OK:
            problems.append(f"Drive {drive} is {pct:.0f}% full")
        lines.append(
            f"  {tag(status)} {drive}  {gb(usage.used):.1f} of "
            f"{gb(usage.total):.1f} GB used ({pct:.0f}%), "
            f"{gb(usage.free):.1f} GB free"
        )
    lines.append("")


# ---------------------------------------------------------------------------
# Battery (laptops)
# ---------------------------------------------------------------------------

def battery_info():
    """Return (percent, charging) or None when there is no battery."""
    system = platform.system()
    try:
        if system == "Windows":
            import ctypes

            class PowerStatus(ctypes.Structure):
                _fields_ = [
                    ("ACLineStatus", ctypes.c_byte),
                    ("BatteryFlag", ctypes.c_byte),
                    ("BatteryLifePercent", ctypes.c_byte),
                    ("SystemStatusFlag", ctypes.c_byte),
                    ("BatteryLifeTime", ctypes.c_ulong),
                    ("BatteryFullLifeTime", ctypes.c_ulong),
                ]

            status = PowerStatus()
            ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status))
            if status.BatteryFlag == 128:  # no system battery
                return None
            return status.BatteryLifePercent, status.ACLineStatus == 1
        if system == "Linux":
            base = "/sys/class/power_supply"
            for name in sorted(os.listdir(base)):
                if name.startswith("BAT"):
                    with open(os.path.join(base, name, "capacity")) as f:
                        percent = int(f.read().strip())
                    with open(os.path.join(base, name, "status")) as f:
                        state = f.read().strip()
                    return percent, state in ("Charging", "Full")
            return None
        if system == "Darwin":
            out = run_quiet(["pmset", "-g", "batt"])
            if "InternalBattery" not in out:
                return None
            # looks like: ... 85%; discharging; ...
            part = out.split("InternalBattery")[1]
            percent = int(part.split("%")[0].strip().split()[-1])
            return percent, "charging" in part.lower() and \
                "discharging" not in part.lower()
    except Exception:
        return None
    return None


def battery_check(lines, problems):
    info = battery_info()
    lines.append("BATTERY")
    if info is None:
        lines.append(f"  {tag(INFO)} No battery detected (desktop or "
                     f"battery not readable).")
    else:
        percent, charging = info
        status = OK
        if percent < 20 and not charging:
            status = WARN
            problems.append(f"Battery is low ({percent}%) and not charging")
        state = "charging" if charging else "not charging"
        lines.append(f"  {tag(status)} Battery at {percent}% ({state})")
    lines.append("")


# ---------------------------------------------------------------------------
# Network
# ---------------------------------------------------------------------------

def network_checks(lines, problems):
    lines.append("NETWORK")
    hostname = socket.gethostname()
    lines.append(f"  Hostname      : {hostname}")

    local_ip = None
    try:
        # A UDP "connect" sends nothing; it just reveals the local address
        # the machine would use to reach the internet.
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(3)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
    except OSError:
        pass
    if local_ip:
        lines.append(f"  {tag(OK)} Local IP address: {local_ip}")
    else:
        lines.append(f"  {tag(WARN)} Could not determine a local IP address")
        problems.append("No local IP address found")

    internet = False
    try:
        with socket.create_connection(("8.8.8.8", 53), timeout=3):
            internet = True
    except OSError:
        internet = False
    if internet:
        lines.append(f"  {tag(OK)} Internet connection is reachable")
    else:
        lines.append(f"  {tag(FAIL)} Cannot reach the internet")
        problems.append("Internet connection failed")

    try:
        socket.gethostbyname("www.google.com")
        lines.append(f"  {tag(OK)} DNS is resolving names")
    except OSError:
        lines.append(f"  {tag(FAIL)} DNS lookups are failing")
        problems.append("DNS lookups are failing")
    lines.append("")


# ---------------------------------------------------------------------------
# Report assembly
# ---------------------------------------------------------------------------

def build_report():
    lines = []
    problems = []
    stamp = datetime.now().strftime("%B %d, %Y %I:%M %p")
    lines.append("=" * 60)
    lines.append(f"PC HEALTH REPORT -- {platform.node() or 'this computer'}")
    lines.append(f"Generated: {stamp}")
    lines.append("=" * 60)
    lines.append("")

    system_info(lines)
    memory_check(lines, problems)
    disk_checks(lines, problems)
    battery_check(lines, problems)
    network_checks(lines, problems)

    lines.append("SUMMARY")
    if not problems:
        lines.append(f"  {tag(OK)} This PC looks healthy. No problems found.")
    else:
        lines.append(f"  {len(problems)} item(s) need attention:")
        for problem in problems:
            lines.append(f"   - {problem}")
    return "\n".join(lines)


def main(argv=None):
    save = "--save" in (argv if argv is not None else sys.argv[1:])
    report = build_report()
    print(report)
    if save:
        name = f"pc-health-report-{platform.node() or 'pc'}.txt".replace(" ", "-")
        folder = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(folder, name)
        with open(path, "w") as f:
            f.write(report + "\n")
        print(f"\nReport saved to {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
