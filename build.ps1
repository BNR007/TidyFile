$ErrorActionPreference = 'Stop'
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$excludes = @('--exclude-module','PySide6.QtWebEngineCore','--exclude-module','PySide6.QtWebEngineWidgets','--exclude-module','PySide6.QtMultimedia','--exclude-module','PySide6.QtNetwork')
$assets = @('--add-data','assets;assets')
$icon = @('--icon','assets\tidy.ico')
& $python -m PyInstaller --noconfirm --clean --onefile --windowed --name Tidy @excludes @assets @icon app.py
if ($LASTEXITCODE -ne 0) { throw 'Single-file build failed.' }
& $python -m PyInstaller --noconfirm --clean --onedir --windowed --name Tidy-Light @excludes @assets @icon app.py
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed.' }
