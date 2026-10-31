$ErrorActionPreference = 'Stop'
$neuralRoot = Split-Path $PSScriptRoot
$cmake = Join-Path $neuralRoot 'tools\.build-venv\Scripts\cmake.exe'
$ninja = Join-Path $neuralRoot 'tools\.build-venv\Scripts\ninja.exe'
$sdk = Join-Path $neuralRoot 'tools\VulkanSDK'
$vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
$vs = & $vswhere -latest -property installationPath
if (!(Test-Path $cmake) -or !(Test-Path "$sdk\Bin\glslc.exe")) { throw 'Install the local CMake/Ninja tools and Vulkan SDK first; see README.md.' }
Import-Module (Join-Path $vs 'Common7\Tools\Microsoft.VisualStudio.DevShell.dll')
Enter-VsDevShell -VsInstallPath $vs -SkipAutomaticLocation -DevCmdArguments '-arch=x64 -host_arch=x64' | Out-Null
$env:VULKAN_SDK = $sdk
$env:CC = 'cl'
$env:CXX = 'cl'
$env:PATH = (Split-Path $cmake) + ';' + $env:PATH
& $cmake -S $PSScriptRoot -B "$PSScriptRoot\build" -G Ninja "-DCMAKE_MAKE_PROGRAM=$ninja" -DCMAKE_BUILD_TYPE=Release -DMUSCRIPTOR_VULKAN=ON "-DCMAKE_RUNTIME_OUTPUT_DIRECTORY=$PSScriptRoot/build/Release"
if ($LASTEXITCODE -ne 0) { throw 'Transcription engine configuration failed' }
& $cmake --build "$PSScriptRoot\build" --parallel 8
if ($LASTEXITCODE -ne 0) { throw 'Transcription engine build failed' }
