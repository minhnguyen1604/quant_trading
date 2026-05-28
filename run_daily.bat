@echo off
REM Run daily update: crawl then normalize and store for both Daily and Weekly
REM Place this file in D:\quant_trading and double-click or run from CMD/PowerShell

REM change working dir to the batch file location
cd /d %~dp0

REM prefer venv python if exists
if exist .venv\Scripts\python.exe (
  set "PY=%~dp0.venv\Scripts\python.exe"
) else (
  set "PY=python"
)

echo Starting daily run at %DATE% %TIME% >> "%~dp0daily.log"

echo --- RUNNING DAILY UPDATE --- >> "%~dp0daily.log" 2>&1
"%PY%" scripts\crawl_vnindex.py --outdir data_hose_daily --start 2017-01-01 --hose --refresh --interval 1d >> "%~dp0daily.log" 2>&1
"%PY%" scripts\normalize_and_store.py --indir data_hose_daily --db data_prices.db --table daily_prices >> "%~dp0daily.log" 2>&1

echo --- RUNNING WEEKLY UPDATE --- >> "%~dp0daily.log" 2>&1
"%PY%" scripts\crawl_vnindex.py --outdir data_hose_weekly --start 2017-01-01 --hose --refresh --interval 1wk >> "%~dp0daily.log" 2>&1
"%PY%" scripts\normalize_and_store.py --indir data_hose_weekly --db data_prices.db --table weekly_prices >> "%~dp0daily.log" 2>&1

echo Finished daily run at %DATE% %TIME% >> "%~dp0daily.log"

exit /b 0
