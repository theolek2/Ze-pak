# Backfill ENTSO-E 2025-2026 (3 instrumenty bez historii) + dbt + sync do MotherDuck.
# Uruchomienie w tle: Start-Process powershell -ArgumentList '-NoProfile','-File',"<repo>\pipeline\run_backfill.ps1"
# Log: logs/backfill_2025_2026.log
$ErrorActionPreference = "Continue"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $here
$log = Join-Path $root "logs\backfill_2025_2026.log"
New-Item -ItemType Directory -Path (Join-Path $root "logs") -Force | Out-Null

function Msg($text) {
    $line = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $text"
    Write-Host $line
    Add-Content -Path $log -Value $line
}

function Step($label, $cmd, $cwd) {
    Msg "START $label"
    $outLog = Join-Path $root "logs\backfill_2025_2026.$label.out.log"
    $errLog = Join-Path $root "logs\backfill_2025_2026.$label.err.log"
    try {
        $p = Start-Process -FilePath $cmd[0] -ArgumentList $cmd[1..($cmd.Count - 1)] `
            -WorkingDirectory $cwd -Wait -PassThru -NoNewWindow `
            -RedirectStandardOutput $outLog -RedirectStandardError $errLog
        $rc = $p.ExitCode
    } catch {
        Msg "[$label] START-PROCESS FAIL: $($_.Exception.Message)"
        $rc = 99
    }
    if (Test-Path $outLog) {
        Get-Content $outLog -Tail 6 | ForEach-Object { Msg "[$label|out] $_" }
    }
    if (Test-Path $errLog) {
        Get-Content $errLog -Tail 6 | ForEach-Object { Msg "[$label|err] $_" }
    }
    Msg "KONIEC $label rc=$rc"
    return $rc
}

# Token do sync (z rejestru User lub z biezacego srodowiska)
if (-not $env:MOTHERDUCK_TOKEN) {
    $env:MOTHERDUCK_TOKEN = [Environment]::GetEnvironmentVariable("MOTHERDUCK_TOKEN", "User")
}

$py = Join-Path $root ".venv\Scripts\python.exe"
$rc = Step "dlt-backfill" @($py, "pipeline\run_pipeline.py", "--entsoe-only",
    "--entsoe-instruments", "imbalance_prices", "generation_forecasts", "aggregated_generation",
    "--entsoe-years", "2025", "2026", "--entsoe-force") $root
if ($rc -ne 0) { Msg "[BACKFILL] dlt fail rc=$rc - STOP"; exit $rc }

$dbt = Join-Path $root ".venv\Scripts\dbt.exe"
$rc = Step "dbt" @($dbt, "run", "--profiles-dir", ".") (Join-Path $root "dbt")
if ($rc -ne 0) { Msg "[BACKFILL] dbt fail rc=$rc - STOP"; exit $rc }

$rc = Step "sync" @($py, "pipeline\sync_motherduck.py") $root
Msg "[BACKFILL] DONE rc=$rc"
exit $rc
