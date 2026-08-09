# Double-click to start JobHunt workspace (Windows).
# Keeps the window open, starts the server, and opens the browser.

$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "Python not found. Install from https://www.python.org/downloads/ (tick 'Add to PATH')."
    Read-Host "Press Enter to exit"; exit 1
}

python -c "import jobhunt" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing jobhunt-os (one-time)..."
    python -m pip install --quiet -e .
}

Write-Host "Starting JobHunt workspace at http://127.0.0.1:8020/ ..."
python -m jobhunt serve