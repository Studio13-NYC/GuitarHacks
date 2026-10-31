param([string]$DriveLetter = 'D', [int]$Minutes = 30)
$ErrorActionPreference = 'Continue'
# Save on C: so evidence survives loss of the project drive. Read-only diagnostics.
$destination = Join-Path $env:LOCALAPPDATA ('GuitarHacks\diagnostics\drive-' + $DriveLetter + '-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $destination -Force | Out-Null
[pscustomobject]@{Captured=(Get-Date).ToString('o');Drive=$DriveLetter;Accessible=(Test-Path ($DriveLetter+':\'))} |
    ConvertTo-Json | Set-Content (Join-Path $destination 'snapshot.json')
Get-Disk | Select-Object Number,FriendlyName,SerialNumber,OperationalStatus,HealthStatus,IsOffline,Size |
    ConvertTo-Json -Depth 4 | Set-Content (Join-Path $destination 'disks.json')
Get-Volume | Select-Object DriveLetter,FileSystemLabel,OperationalStatus,HealthStatus,Size,SizeRemaining |
    ConvertTo-Json -Depth 4 | Set-Content (Join-Path $destination 'volumes.json')
Get-WinEvent -FilterHashtable @{LogName='System';StartTime=(Get-Date).AddMinutes(-$Minutes)} -ErrorAction SilentlyContinue |
    Where-Object {$_.ProviderName -match 'disk|stor|Ntfs|Kernel-PnP|WHEA'} |
    Select-Object TimeCreated,ProviderName,Id,LevelDisplayName,Message |
    ConvertTo-Json -Depth 5 | Set-Content (Join-Path $destination 'storage-events.json')
$destination
