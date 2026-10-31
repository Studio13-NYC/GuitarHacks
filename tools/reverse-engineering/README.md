# Local REA native-analysis prerequisites

Installed 2026-10-28 with user authorization. Portable installs; no system PATH, global JAVA_HOME, drivers, or file associations changed.

- Ghidra 12.1.4: `ghidra_12.1.4_PUBLIC`
- Full Temurin JDK 21.0.12.1+1: `jdk-21.0.12.1+1` (java and javac verified)
- Ghidra archive SHA256: ddac49f903da9d5bac833e5cc79395098b9c33cfd3279be5f31bd00387d2d4db
- JDK archive SHA256: f9d6e191ab098c0d416e7d588a24420a8621cd2f4720dab2459b8b7b2d2d8b4e

Official sources: https://github.com/NationalSecurityAgency/ghidra/releases/tag/Ghidra_12.1.4_build and https://api.adoptium.net/v3/assets/latest/21/hotspot?architecture=x64&image_type=jdk&os=windows&vendor=eclipse . Hashes matched release metadata before extraction.

Codex configuration `C:\Users\NickKatsivelos\.codex\config.toml` has only an added `env` entry in `[mcp_servers.rea]` for GHIDRA_INSTALL_DIR and JAVA_HOME pointing here. Backup: `C:\Users\NickKatsivelos\.codex\config.toml.before-ghidra-20261028-120302.bak`. Existing connected MCP process must reconnect to inherit these variables; CLI use works immediately with process-scoped variables.

```powershell
$env:GHIDRA_INSTALL_DIR='D:\Studio13\Lab\Music\GuitarHacks\tools\reverse-engineering\ghidra_12.1.4_PUBLIC'
$env:JAVA_HOME='D:\Studio13\Lab\Music\GuitarHacks\tools\reverse-engineering\jdk-21.0.12.1+1'
& 'C:\Program Files\nodejs\node.exe' 'D:\Studio13\Lab\Code\REA\runtime\node_modules\rea-agents\scripts\rea.mjs' providers --format json
```
