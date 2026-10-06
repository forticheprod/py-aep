# Run one render-matrix JSX in After Effects 2026 headless, relaunching after
# a crash or a hang (the JSX skips the label a previous run died on).
#   pwsh scripts/render_matrix/run.ps1 -Dir <out dir> -Script render_C.jsx
param(
    [Parameter(Mandatory = $true)][string]$Dir,
    [Parameter(Mandatory = $true)][string]$Script,
    [int]$HangSeconds = 150
)
$ae = "C:\Program Files\Adobe\Adobe After Effects 2026\Support Files\AfterFX.com"
$jsx = Join-Path $Dir $Script
$log = Join-Path $Dir "$Script`_log.txt"
if (Test-Path $log) { Remove-Item -LiteralPath $log }
for ($run = 1; $run -le 25; $run++) {
    $start = Get-Date
    Start-Process -FilePath $ae -ArgumentList @("-noui", "-ro", $jsx) -WindowStyle Hidden
    $state = "?"
    $lastChange = Get-Date
    $lastLen = -1
    while ($true) {
        Start-Sleep 3
        if (Test-Path $log) {
            $len = (Get-Item $log).Length
            if ($len -ne $lastLen) { $lastLen = $len; $lastChange = Get-Date }
            if ((Get-Content $log -Tail 1) -eq "DONE") { $state = "DONE"; break }
        }
        if (Get-Process -Name AdobeCrashReport -ErrorAction SilentlyContinue | Where-Object { $_.StartTime -gt $start }) { $state = "CRASH"; break }
        if (((Get-Date) - $lastChange).TotalSeconds -gt $HangSeconds) { $state = "HANG"; break }
    }
    "run $run => $state"
    Start-Sleep 3
    # Only the processes this run started.
    Get-Process -Name AfterFX*, AdobeCrashReport -ErrorAction SilentlyContinue |
        Where-Object { $_.StartTime -gt $start } |
        Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep 3
    if ($state -eq "DONE") { break }
}
Get-Content $log | Where-Object { $_ -match "^(ERR|SKIPCRASH|NOITEM|CANNOT)" }
