@echo off
cd /d "C:\IT\praca"

echo [1/3] Pobieranie danych (dlt: entsoe + pse)...
"C:\IT\praca\.venv\Scripts\python.exe" "C:\IT\praca\pipeline\run_pipeline.py"
if %errorlevel% neq 0 exit /b %errorlevel%

echo [2/3] Budowanie modeli (dbt)...
cd /d "C:\IT\praca\dbt"
"C:\IT\praca\.venv\Scripts\dbt.exe" run --profiles-dir .
if %errorlevel% neq 0 exit /b %errorlevel%

echo [3/3] Synchronizacja kanonicznych tabel do MotherDuck...
cd /d "C:\IT\praca"
"C:\IT\praca\.venv\Scripts\python.exe" "C:\IT\praca\pipeline\sync_motherduck.py"
if %errorlevel% neq 0 exit /b %errorlevel%
