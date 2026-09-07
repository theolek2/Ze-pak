@echo off
cd /d "C:\IT\praca"

echo [1/2] Pobieranie danych (dlt)...
"C:\IT\praca\.venv\Scripts\python.exe" "C:\IT\praca\pipeline\run_pipeline.py"

echo [2/2] Budowanie modeli (dbt)...
cd /d "C:\IT\praca\dbt"
"C:\IT\praca\.venv\Scripts\dbt.exe" run --profiles-dir .
