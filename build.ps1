param([string]$OutputDirectory = 'FretboardFiend\release')
$ErrorActionPreference = 'Stop'
$buildOriginalPath = $env:PATH
$buildUv = (Get-Command uv -CommandType Application).Source
Push-Location $PSScriptRoot
try {
    $buildOutput = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot $OutputDirectory))
    New-Item -ItemType Directory -Path $buildOutput -Force | Out-Null
    & "$PSScriptRoot\tools\windows-midi\build.ps1"
    $buildPythonHome = & $buildUv run --frozen python -c 'import sys; print(sys.base_prefix)'
    if ($LASTEXITCODE -ne 0) { throw 'Could not locate the project Python runtime.' }
    # Dependency scanning must not collect incompatible ICU/API-set DLLs from
    # unrelated tools (e.g. Poppler/libheif) in the caller's inherited PATH.
    $env:PATH = @((Join-Path $PSScriptRoot '.venv\Scripts'), $buildPythonHome,
        (Split-Path $buildUv), "$env:SystemRoot\System32", "$env:SystemRoot") -join ';'
    if (Test-Path -LiteralPath (Join-Path $buildOutput 'GuitarHacks.exe')) {
        $backupFolder = Join-Path $PSScriptRoot ('backups\' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
        New-Item -ItemType Directory -Path $backupFolder -Force | Out-Null
        Copy-Item -LiteralPath (Join-Path $buildOutput 'GuitarHacks.exe') -Destination $backupFolder
    }
    & $buildUv run --frozen python FretboardFiend\tools\build_icon.py
    if ($LASTEXITCODE -ne 0) { throw 'Icon build failed.' }
    & $buildUv run --frozen --group build python -m PyInstaller --clean --noconfirm --onefile --windowed --noupx --name GuitarHacks --icon "$PSScriptRoot\FretboardFiend\assets\guitarhacks.ico" --version-file "$PSScriptRoot\FretboardFiend\assets\windows-version.txt" --distpath "$buildOutput" --workpath build\pyinstaller --specpath build --add-data "$PSScriptRoot\FretboardFiend\lessons;bundled_lessons" --add-data "$PSScriptRoot\FretboardFiend\assets\guitarhacks.ico;assets" --add-data "$PSScriptRoot\chord_painter;chord_painter" --add-data "$PSScriptRoot\api\coach-contract.json;api" --add-data "$PSScriptRoot\tools\windows-midi\publish;windows-midi" --collect-binaries _sounddevice_data --hidden-import win32com.client.dynamic --hidden-import pythoncom --hidden-import pywintypes app.py
    if ($LASTEXITCODE -ne 0) { throw 'Executable build failed.' }
    Copy-Item -LiteralPath '.\README.md', '.\LESSONS.md', '.\CHORD-PAINTER.md', '.\UNIFIED-UI-QA.md', '.\JAM-MIDI-PLAN.md', '.\DETECTION-HELP-QA.md' -Destination $buildOutput
    $playbackLicenses = Join-Path $buildOutput 'playback-licenses'
    New-Item -ItemType Directory -Path $playbackLicenses -Force | Out-Null
    Copy-Item -LiteralPath '.\StemSlicer\playback\FluidR3Mono_License.md', '.\StemSlicer\playback\TinySoundFont-LICENSE.txt', '.\StemSlicer\playback\TinySoundFont-NOTICE.txt' -Destination $playbackLicenses
    Compress-Archive -Path '.\chord_painter\*' -DestinationPath (Join-Path $buildOutput 'ChordPainter-offline-web.zip') -Force
    Get-Item -LiteralPath (Join-Path $buildOutput 'GuitarHacks.exe') | Select-Object FullName,Length,LastWriteTime
} finally {
    $env:PATH = $buildOriginalPath
    Pop-Location
}

