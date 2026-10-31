$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    $env:DOTNET_CLI_TELEMETRY_OPTOUT = '1'
    $env:DOTNET_SKIP_FIRST_TIME_EXPERIENCE = '1'
    $midiDotnet = Join-Path $PSScriptRoot '.dotnet\dotnet.exe'
    if (!(Test-Path -LiteralPath $midiDotnet)) { $midiDotnet = (Get-Command dotnet -ErrorAction Stop).Source }
    $midiVersion = & $midiDotnet --version
    if ([int]($midiVersion.Split('.')[0]) -lt 10) { throw 'Build prerequisite: .NET SDK 10 or later. See tools/windows-midi/README.md.' }
    $midiPackage = 'Microsoft.Windows.Devices.Midi2.1.0.17-rc.4.25.nupkg'
    New-Item -ItemType Directory -Path packages -Force | Out-Null
    if (!(Test-Path -LiteralPath "packages\$midiPackage")) {
        Invoke-WebRequest "https://github.com/microsoft/MIDI/releases/download/rc-4/$midiPackage" -OutFile "packages\$midiPackage"
    }
    & $midiDotnet restore GuitarHacks.Midi.csproj -r win-x64 --locked-mode
    if ($LASTEXITCODE -ne 0) { throw 'MIDI helper restore failed.' }
    & $midiDotnet publish GuitarHacks.Midi.csproj -c Release -r win-x64 --self-contained false --no-restore -o publish
    if ($LASTEXITCODE -ne 0) { throw 'MIDI helper build failed.' }
    Copy-Item -LiteralPath loopback.json -Destination publish\loopback.json
} finally { Pop-Location }
