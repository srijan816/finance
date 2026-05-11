# Quant Lab Windows setup helper for Norgate exports.
#
# Run this in Windows PowerShell after installing/logging into Norgate Data
# Updater. It installs Python dependencies, checks that the Norgate Python
# package can see NDU, and creates a small test export.

param(
  [string]$ExportRoot = "$env:USERPROFILE\Desktop\quant_lab_norgate_export",
  [string]$Symbols = "AAPL,MSFT,NVDA",
  [string]$Start = "1990-01-01"
)

$ErrorActionPreference = "Stop"

Write-Host "Quant Lab Norgate Windows setup" -ForegroundColor Cyan
Write-Host "Export folder: $ExportRoot"

function Ensure-Python {
  $python = Get-Command py -ErrorAction SilentlyContinue
  if ($python) {
    return "py -3"
  }

  $pythonExe = Get-Command python -ErrorAction SilentlyContinue
  if ($pythonExe) {
    return "python"
  }

  $winget = Get-Command winget -ErrorAction SilentlyContinue
  if (-not $winget) {
    throw "Python was not found and winget is unavailable. Install Python 3.11+ from https://www.python.org/downloads/windows/ and rerun this script."
  }

  Write-Host "Installing Python via winget..." -ForegroundColor Yellow
  winget install --id Python.Python.3.11 -e --source winget
  return "py -3"
}

$pythonCmd = Ensure-Python
Write-Host "Using Python command: $pythonCmd"

Write-Host "Installing Python packages..." -ForegroundColor Yellow
Invoke-Expression "$pythonCmd -m pip install --upgrade pip"
Invoke-Expression "$pythonCmd -m pip install pandas norgatedata"

Write-Host "Checking Norgate Data Updater status..." -ForegroundColor Yellow
$statusCode = @"
import norgatedata
print("NDU running:", norgatedata.status())
print("Databases:")
for item in norgatedata.databases():
    print(" -", item)
"@
$statusCode | Set-Content -Encoding UTF8 "$env:TEMP\norgate_status_check.py"
Invoke-Expression "$pythonCmd $env:TEMP\norgate_status_check.py"

Write-Host "Writing available database/watchlist names..." -ForegroundColor Yellow
Invoke-Expression "$pythonCmd .\norgate_windows_export.py --out `"$ExportRoot`" --list-only"

Write-Host "Running a small test export..." -ForegroundColor Yellow
Invoke-Expression "$pythonCmd .\norgate_windows_export.py --symbols `"$Symbols`" --out `"$ExportRoot`" --start $Start --limit 3"

Write-Host ""
Write-Host "Done." -ForegroundColor Green
Write-Host "Copy this folder back to the Mac:"
Write-Host "  $ExportRoot"
Write-Host ""
Write-Host "Then on the Mac run:"
Write-Host "  quant norgate import-ascii --path /path/to/quant_lab_norgate_export/prices"
Write-Host "  quant norgate import-metadata --path /path/to/quant_lab_norgate_export"
