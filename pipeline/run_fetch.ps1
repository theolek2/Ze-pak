# Sciaganie surowych CSV w tle (log: logs/fetch_csv.log).
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $here
& (Join-Path $root ".venv\Scripts\python.exe") (Join-Path $root "pipeline\fetch_csv.py") --years 2025 2026 --workers 6 >> (Join-Path $root "logs\fetch_csv.log") 2>&1
