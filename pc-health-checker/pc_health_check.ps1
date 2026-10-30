# PC Health Checker (Windows / PowerShell version)
# -------------------------------------------------
# Same checks as the Python version, but runs natively on Windows with
# nothing to install. Read-only: it never changes any settings.
#
# Run it:
#   powershell -ExecutionPolicy Bypass -File .\pc_health_check.ps1
#   powershell -ExecutionPolicy Bypass -File .\pc_health_check.ps1 -Save
# Or just double-click pc_health_check.bat in the same folder.

param([switch]$Save)

$problems = @()
$lines = @()

function Add-Line($text) {
    $script:lines += $text
    Write-Host $text
}

function GB($bytes) {
    return [math]::Round($bytes / 1GB, 1)
}

$stamp = Get-Date -Format "MMMM dd, yyyy hh:mm tt"
Add-Line "============================================================"
Add-Line "PC HEALTH REPORT -- $env:COMPUTERNAME"
Add-Line "Generated: $stamp"
Add-Line "============================================================"
Add-Line ""

# --- System ---------------------------------------------------------------
$os = Get-CimInstance Win32_OperatingSystem
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
$uptime = (Get-Date) - $os.LastBootUpTime
Add-Line "SYSTEM"
Add-Line "  Computer name : $env:COMPUTERNAME"
Add-Line "  Operating sys : $($os.Caption) ($($os.Version))"
Add-Line "  Architecture  : $($os.OSArchitecture)"
Add-Line "  Processor     : $($cpu.Name.Trim())"
Add-Line "  CPU cores     : $($cpu.NumberOfLogicalProcessors) logical"
Add-Line ("  Uptime        : {0}d {1}h {2}m" -f $uptime.Days, $uptime.Hours, $uptime.Minutes)
Add-Line ""

# --- Memory ---------------------------------------------------------------
$totalKB = $os.TotalVisibleMemorySize
$freeKB = $os.FreePhysicalMemory
$usedPct = [math]::Round(($totalKB - $freeKB) / $totalKB * 100)
if ($usedPct -ge 95) { $status = "FAIL" } elseif ($usedPct -ge 85) { $status = "WARN" } else { $status = "OK" }
if ($status -ne "OK") { $problems += "Memory is $usedPct% used" }
Add-Line "MEMORY"
Add-Line ("  [{0}] RAM: {1} of {2} GB used ({3}%)" -f $status, (GB (($totalKB - $freeKB) * 1KB)), (GB ($totalKB * 1KB)), $usedPct)
Add-Line ""

# --- Disk space -----------------------------------------------------------
Add-Line "DISK SPACE"
Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3" | ForEach-Object {
    $pct = [math]::Round(($_.Size - $_.FreeSpace) / $_.Size * 100)
    if ($pct -ge 95) { $s = "FAIL" } elseif ($pct -ge 85) { $s = "WARN" } else { $s = "OK" }
    if ($s -ne "OK") { $problems += "Drive $($_.DeviceID) is $pct% full" }
    Add-Line ("  [{0}] {1}  {2} of {3} GB used ({4}%), {5} GB free" -f $s, $_.DeviceID, (GB ($_.Size - $_.FreeSpace)), (GB $_.Size), $pct, (GB $_.FreeSpace))
}
Add-Line ""

# --- Battery --------------------------------------------------------------
Add-Line "BATTERY"
$battery = Get-CimInstance Win32_Battery | Select-Object -First 1
if ($null -eq $battery) {
    Add-Line "  [INFO] No battery detected (desktop)."
} else {
    $pct = $battery.EstimatedChargeRemaining
    # BatteryStatus 2 means running on AC power
    $charging = $battery.BatteryStatus -eq 2
    $s = "OK"
    if ($pct -lt 20 -and -not $charging) {
        $s = "WARN"
        $problems += "Battery is low ($pct%) and not charging"
    }
    $state = if ($charging) { "charging" } else { "not charging" }
    Add-Line "  [$s] Battery at $pct% ($state)"
}
Add-Line ""

# --- Network --------------------------------------------------------------
Add-Line "NETWORK"
Add-Line "  Hostname      : $env:COMPUTERNAME"
$ip = [System.Net.Dns]::GetHostAddresses($env:COMPUTERNAME) |
    Where-Object { $_.AddressFamily -eq "InterNetwork" -and $_.IPAddressToString -notlike "169.254*" } |
    Select-Object -First 1
if ($ip) {
    Add-Line "  [OK] Local IP address: $($ip.IPAddressToString)"
} else {
    Add-Line "  [WARN] Could not determine a local IP address"
    $problems += "No local IP address found"
}
if (Test-Connection -ComputerName 8.8.8.8 -Count 1 -Quiet) {
    Add-Line "  [OK] Internet connection is reachable"
} else {
    Add-Line "  [FAIL] Cannot reach the internet"
    $problems += "Internet connection failed"
}
try {
    [System.Net.Dns]::GetHostAddresses("www.google.com") | Out-Null
    Add-Line "  [OK] DNS is resolving names"
} catch {
    Add-Line "  [FAIL] DNS lookups are failing"
    $problems += "DNS lookups are failing"
}
Add-Line ""

# --- Summary --------------------------------------------------------------
Add-Line "SUMMARY"
if ($problems.Count -eq 0) {
    Add-Line "  [OK] This PC looks healthy. No problems found."
} else {
    Add-Line "  $($problems.Count) item(s) need attention:"
    $problems | ForEach-Object { Add-Line "   - $_" }
}

if ($Save) {
    $path = Join-Path $PSScriptRoot "pc-health-report-$env:COMPUTERNAME.txt"
    $lines | Out-File -FilePath $path -Encoding utf8
    Write-Host ""
    Write-Host "Report saved to $path"
}
