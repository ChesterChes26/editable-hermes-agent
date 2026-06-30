# Quick wake-config and S3 diagnostic script
# Usage: powershell -ExecutionPolicy Bypass -File check-wake-config.ps1

Write-Host "=== Wake-Armed Devices ==="
powercfg /devicequery wake_armed

Write-Host ""
Write-Host "=== Last Wake Source ==="
powercfg /lastwake

Write-Host ""
Write-Host "=== Ethernet Wake-on-LAN Settings ==="
$adapters = Get-NetAdapter | Where-Object { $_.InterfaceDescription -match "Ethernet|以太" }
foreach ($adapter in $adapters) {
    Write-Host "--- $($adapter.Name) ($($adapter.InterfaceDescription)) ---"
    $props = Get-NetAdapterAdvancedProperty -Name $adapter.Name -ErrorAction SilentlyContinue
    foreach ($p in $props) {
        if ($p.RegistryKeyword -match "Wake|WoL|PME|Pattern|Magic|EEE|Energy|Power") {
            Write-Host "  $($p.DisplayName) = $($p.DisplayValue)"
        }
    }
}

Write-Host ""
Write-Host "=== Sleep Timeout Settings ==="
powercfg /query SCHEME_CURRENT SUB_SLEEP | Select-String -Pattern "电源使用方案|备用|超时|休眠|允许"

Write-Host ""
Write-Host "=== S3 Resume Stats (last 20 transisions) ==="
Get-WinEvent -LogName System -MaxEvents 1000 | Where-Object { $_.Id -eq 131 } | Select-Object -First 20 | ForEach-Object {
    $msg = $_.Message
    Write-Host $_.TimeCreated $msg
}

Write-Host ""
Write-Host "=== Recent NTP Errors ==="
$ntpErrors = Get-WinEvent -LogName System -MaxEvents 500 | Where-Object { $_.Id -eq 37 -and $_.TimeCreated -gt (Get-Date).AddHours(-24) }
if ($ntpErrors) {
    Write-Host "Found $($ntpErrors.Count) NTP errors in last 24h"
} else {
    Write-Host "No NTP errors in last 24h"
}

Write-Host ""
Write-Host "=== Memory Pressure ==="
$os = Get-CimInstance Win32_OperatingSystem
$tp = [math]::Round($os.TotalVisibleMemorySize/1MB,1)
$fp = [math]::Round($os.FreePhysicalMemory/1MB,1)
Write-Host "Physical: ${tp} MB total, ${fp} MB free, $([math]::Round($tp-$fp,1)) MB used"
$mc = Get-Process -Name "Memory Compression" -ErrorAction SilentlyContinue
if ($mc) {
    Write-Host "Memory Compression: $([math]::Round($mc.WorkingSet64/1MB,1)) MB WorkingSet"
}
$pf = Get-CimInstance Win32_PageFileUsage
foreach ($p in $pf) {
    Write-Host "Pagefile: $($p.AllocatedBaseSize)MB alloc, $($p.CurrentUsage)MB used, $($p.PeakUsage)MB peak"
}

Write-Host ""
Write-Host "=== Uptime ==="
$boot = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime
$uptime = (Get-Date) - $boot
Write-Host "Uptime: $($uptime.Days) days $($uptime.Hours) hours (booted $boot)"
