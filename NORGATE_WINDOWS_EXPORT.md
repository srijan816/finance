# Norgate Windows Export Setup

This is the clean path now that Windows is running in Parallels.

## 1. Install Norgate Data Updater in Windows

Open Windows Chrome and go to:

https://norgatedata.com/downloads.php

Download and install **Norgate Data Updater**. Norgate’s own docs say NDU is a Windows app, installs by default under `C:\Program Files\Norgate Data Updater`, stores the local database under `C:\ProgramData\Norgate Data`, and must stay running for updates.

Sign in inside NDU using your trial account, then run the first update. The first historical download can take a while.

## 2. Copy the Quant Lab export scripts to Windows

From this Mac repo, copy these two files to a Windows folder, for example your Windows Desktop:

- `scripts/norgate_windows_export.py`
- `scripts/setup_norgate_windows.ps1`

If Parallels shared folders are enabled, you may be able to reach the Mac files from Windows Explorer under a path like `\\Mac\Home\Volumes\SrijanExt\Users\Srijan\work\quant-lab\scripts`.

If that is annoying, just drag the two files into Windows.

## 3. Run PowerShell

Open Windows PowerShell in the folder where you copied the scripts.

If script execution is blocked, run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Then run:

```powershell
.\setup_norgate_windows.ps1
```

That script will:

- install Python if Windows does not already have it,
- install `pandas` and `norgatedata`,
- check whether NDU is running,
- write available database and watchlist names,
- export a small test set: `AAPL,MSFT,NVDA`.

The default export folder is:

```text
C:\Users\<you>\Desktop\quant_lab_norgate_export
```

## 4. Inspect available database names

After the setup script runs, open:

```text
C:\Users\<you>\Desktop\quant_lab_norgate_export\metadata\available_databases.csv
```

Use the exact database names shown there. Common examples from Norgate docs include:

- `US Equities`
- `US Equities Delisted`
- `AU Equities`
- `US Indices`
- `World Indices`

Canadian and Australian exact delisted database names should be taken from your file, not guessed.

## 5. Export larger datasets

Start with metadata only:

```powershell
py -3 .\norgate_windows_export.py --out "$env:USERPROFILE\Desktop\quant_lab_norgate_export" --databases "US Equities,US Equities Delisted,AU Equities" --skip-prices
```

Then do a limited test:

```powershell
py -3 .\norgate_windows_export.py --out "$env:USERPROFILE\Desktop\quant_lab_norgate_export" --databases "US Equities,US Equities Delisted,AU Equities" --start 1990-01-01 --limit 25
```

Then, only after the test works, do the broad export:

```powershell
py -3 .\norgate_windows_export.py --out "$env:USERPROFILE\Desktop\quant_lab_norgate_export" --databases "US Equities,US Equities Delisted,AU Equities" --start 1990-01-01
```

This may take a long time and create many CSV files. That is expected.

For S&P 500 constituent history, use:

```powershell
py -3 .\norgate_windows_export.py --out "$env:USERPROFILE\Desktop\quant_lab_norgate_export_sp500" --databases "US Equities,US Equities Delisted" --index "S&P 500" --start 1990-01-01
```

Historical index constituents require the right Norgate subscription level.

## 6. Import back on the Mac

Copy the `quant_lab_norgate_export` folder back to the Mac. Then run:

```bash
quant norgate import-ascii --path /path/to/quant_lab_norgate_export/prices
quant norgate import-metadata --path /path/to/quant_lab_norgate_export
quant norgate status
```

Then switch Quant Lab to Norgate:

```bash
export QUANT_DATA_SOURCE=norgate
quant web
```

## 7. Keep the limitation visible

Norgate ASCII price files are useful, but not enough by themselves for full research-grade claims. The research-grade upgrade comes when `quant norgate status` shows imported security-master rows, delisted securities, and constituent metadata.
