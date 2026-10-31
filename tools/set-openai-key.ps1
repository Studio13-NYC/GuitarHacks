#requires -Version 7.0
<#
Prompts securely; never accepts a key on the command line or prints it.
Local: ignored env file. Azure: production SWA backend app settings only.
Requires an existing SWA; this script does not provision or deploy an app.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$EnvFile,
    [ValidateSet('Local','Azure','Both')][string]$Target = 'Local',
    [string]$AzureResourceId,
    [switch]$UseSavedKey
)
$ErrorActionPreference = 'Stop'
$VerbosePreference = 'SilentlyContinue'
$DebugPreference = 'SilentlyContinue'
$workspace = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$secretPath = [IO.Path]::GetFullPath($EnvFile, $workspace)
$keyText = $token = $settings = $headers = $secureKey = $null
$temporaryPath = $null
$localSaved = $false

try {
    if (-not $secretPath.StartsWith($workspace + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Choose an ignored env file inside the GuitarHacks workspace.'
    }
    $parent = Split-Path $secretPath
    if (-not (Test-Path -LiteralPath $parent -PathType Container)) { throw 'The env file directory does not exist.' }
    $probe = $secretPath
    while ($probe -and $probe.Length -ge $workspace.Length) {
        if ((Test-Path -LiteralPath $probe) -and ((Get-Item -LiteralPath $probe -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Symlink/reparse-point destinations are not supported.' }
        $probe = Split-Path $probe
    }
    & git -C $workspace check-ignore --quiet -- $secretPath
    if ($LASTEXITCODE -ne 0) { throw 'The env file must be ignored by Git before storing a key.' }
    $uri = $null
    if ($Target -ne 'Local') {
        if ($AzureResourceId -notmatch '^/subscriptions/([0-9a-fA-F-]{36})/resourceGroups/([^/]+)/providers/Microsoft\.Web/staticSites/([^/]+)$') {
            throw 'Supply the exact existing SWA AzureResourceId for Azure or Both.'
        }
        $subscription = $Matches[1]
        $token = (& az account get-access-token --subscription $subscription --resource 'https://management.azure.com/' --query accessToken -o tsv --only-show-errors 2>$null)
        if ($LASTEXITCODE -ne 0 -or -not $token) { throw 'Azure CLI sign-in is required for the target subscription.' }
        $headers = @{ Authorization = 'Bearer ' + $token }
        $uri = 'https://management.azure.com' + $AzureResourceId
        $resource = Invoke-RestMethod -Method Get -Uri ($uri + '?api-version=2025-05-01') -Headers $headers
        if ($resource.type -ne 'Microsoft.Web/staticSites') { throw 'The destination is not an Azure Static Web App.' }
        $current = Invoke-RestMethod -Method Post -Uri ($uri + '/listAppSettings?api-version=2025-05-01') -Headers $headers
        $settings = @{}
        foreach ($property in $current.properties.PSObject.Properties) { $settings[$property.Name] = $property.Value }
        Write-Host ('Azure production backend: ' + $AzureResourceId)
    }
    if ($Target -ne 'Azure') { Write-Host ('Local destination: ' + $secretPath) }
    if ((Read-Host 'Type YES to configure these destinations') -cne 'YES') { Write-Host 'Cancelled. Nothing changed.'; return }
    if ($UseSavedKey) {
        if (-not (Test-Path -LiteralPath $secretPath -PathType Leaf)) { throw 'The saved env file does not exist.' }
        $match = [regex]::Match([IO.File]::ReadAllText($secretPath), '(?m)^\s*(?:export\s+)?OPENAI_API_KEY\s*=\s*([^\r\n]+)')
        $keyText = $match.Groups[1].Value.Trim().Trim('"').Trim("'")
    } else {
        $secureKey = Read-Host 'Paste the OpenAI API key (hidden)' -AsSecureString
        $keyText = [Net.NetworkCredential]::new('', $secureKey).Password.Trim()
    }
    if ($keyText -notmatch '^sk-[A-Za-z0-9_-]{16,}$') { throw 'This does not look like an OpenAI API key; nothing was saved.' }
    if ($Target -ne 'Azure') {
        $existing = if (Test-Path -LiteralPath $secretPath) { [IO.File]::ReadAllText($secretPath) } else { '' }
        $updated = [regex]::Replace($existing, '(?m)^\s*(?:export\s+)?OPENAI_API_KEY\s*=[^\r\n]*(?:\r?\n|$)', '')
        $updated = $updated.TrimEnd() + [Environment]::NewLine + 'OPENAI_API_KEY=' + $keyText + [Environment]::NewLine
        $temporaryPath = Join-Path $parent ('.env.staging-' + [guid]::NewGuid().ToString('N'))
        [IO.File]::WriteAllText($temporaryPath, '')
        $acl = [Security.AccessControl.FileSecurity]::new()
        $sid = [Security.Principal.WindowsIdentity]::GetCurrent().User
        $acl.SetOwner($sid); $acl.SetAccessRuleProtection($true, $false)
        $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($sid, 'FullControl', 'Allow'))
        Set-Acl -LiteralPath $temporaryPath -AclObject $acl
        [IO.File]::WriteAllText($temporaryPath, $updated, [Text.UTF8Encoding]::new($false))
        [IO.File]::Move($temporaryPath, $secretPath, $true)
        $temporaryPath = $null; $localSaved = $true
        Write-Host 'Local OPENAI_API_KEY saved. Value not displayed.'
    }
    if ($Target -ne 'Local') {
        $settings['OPENAI_API_KEY'] = $keyText
        $body = @{ properties = $settings } | ConvertTo-Json -Depth 8 -Compress
        $null = Invoke-RestMethod -Method Put -Uri ($uri + '/config/appsettings?api-version=2025-05-01') -Headers $headers -ContentType 'application/json' -Body $body
        $check = Invoke-RestMethod -Method Post -Uri ($uri + '/listAppSettings?api-version=2025-05-01') -Headers $headers
        if ($check.properties.OPENAI_API_KEY -cne $keyText) { throw 'Azure verification failed.' }
        foreach ($name in $settings.Keys) {
            if ($check.properties.$name -cne $settings[$name]) { throw 'An Azure setting did not match after the update.' }
        }
        Write-Host 'Production OPENAI_API_KEY saved and verified; existing app settings preserved.'
    }
} catch {
    # Do not echo HTTP error bodies, exception objects, request headers, or secret-bearing values.
    Write-Host 'Setup did not complete. No credential values were printed.' -ForegroundColor Red
    if ($localSaved) { Write-Host 'The local key was saved, but production setup did not finish.' }
    else { Write-Host 'Check the destination path, Git ignore rules, key format, and Azure resource/sign-in if applicable.' }
    exit 1
} finally {
    if ($temporaryPath -and (Test-Path -LiteralPath $temporaryPath)) { Remove-Item -LiteralPath $temporaryPath -Force }
    if ($secureKey) { $secureKey.Dispose() }
    $keyText = $token = $settings = $headers = $body = $current = $check = $updated = $existing = $match = $null
}
