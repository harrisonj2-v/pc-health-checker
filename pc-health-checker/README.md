# PC Health Checker

A quick health check you can run on any computer. It prints a plain-language
report — system info, memory, disk space, battery, and network — with each
item marked `[OK]`, `[WARN]`, or `[FAIL]`, plus a summary of anything that
needs attention.

It is **read-only**: it never changes settings, needs **no admin rights**,
and installs nothing.

## Which file do I run?

| Computer | File | How |
|---|---|---|
| Windows (no Python needed) | `pc_health_check.bat` | Double-click it. The report opens in a window and is also saved as a text file next to the script. |
| Windows (from a terminal) | `pc_health_check.ps1` | `powershell -ExecutionPolicy Bypass -File .\pc_health_check.ps1` |
| Mac / Linux / any PC with Python 3 | `pc_health_check.py` | `python3 pc_health_check.py` — add `--save` to also save the report as a text file next to the script. |

Tip: copy the folder to a USB drive and you can run it on any machine you
work on — exactly how you'd use it on a help desk shift.

## What it checks

- **System** — computer name, OS and version, processor, core count, uptime
- **Memory** — RAM used vs. total, flagged at 85% (warn) and 95% (fail)
- **Disk space** — every drive, flagged at 85% full (warn) and 95% (fail)
- **Battery** — charge level and whether it's charging (laptops only)
- **Network** — local IP address, internet reachability, DNS resolution

## How it works

- The Python version uses only the standard library (`platform`, `shutil`,
  `os`, plus small per-OS reads like `/proc/meminfo` on Linux and Windows
  system calls through `ctypes`), so the same one file runs on Windows,
  macOS, and Linux.
- The PowerShell version asks Windows directly through CIM
  (`Win32_OperatingSystem`, `Win32_LogicalDisk`, `Win32_Battery`) and uses
  `Test-Connection` and DNS lookups for the network checks.
- Both versions use the same thresholds and the same report layout, so a
  report looks the same no matter which one produced it.
