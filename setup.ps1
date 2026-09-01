$ErrorActionPreference = 'Stop'

if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 -m venv (Join-Path $PSScriptRoot '.venv')
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    & python -m venv (Join-Path $PSScriptRoot '.venv')
} else {
    throw 'Python 3 is required. Install it from python.org, then run this script again.'
}

$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
& $python -m pip install --upgrade pip
& $python -m pip install -r (Join-Path $PSScriptRoot 'requirements.txt')
Write-Host 'Tidy is ready. Run .\run.ps1 to start it.'

