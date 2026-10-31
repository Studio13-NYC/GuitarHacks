# Windows MIDI receiver

This helper uses the installed Windows MIDI Services RC4 runtime and Microsoft LOOP transport. Runtime prerequisites: Windows x64, Windows MIDI Services SDK/runtime `1.0.17-rc.4.25`, and .NET 10 runtime. It does not install or repair these prerequisites. The current machine already has them.

Build from the GuitarHacks root:

```powershell
.\tools\windows-midi\build.ps1
```

Building requires .NET SDK 10. The script prefers `tools/windows-midi/.dotnet/dotnet.exe` (local SDK 10.0.403 installed for this work), then the SDK on PATH. On a fresh machine, install the official .NET 10 SDK before building. The build downloads the exact RC4 nupkg from Microsoft's GitHub release into `packages`, then restores with `packages.lock.json` in locked mode. NuGet.org does not serve this pinned RC4 package. SDK/build downloads require internet; capture does not.

`publish` contains the executable and required managed libraries; the project build bundles the whole directory plus `loopback.json`. Keep the configuration with the helper. The .NET runtime and Windows MIDI Services remain machine prerequisites, not bundled installs.

The helper selects the dedicated LOOP pair by transport and saved association GUID, then checks the returned endpoint names. Transient endpoints survive app exit but not service restart. Missing pairs are recreated; incomplete or renamed pairs are reported, not modified. Concurrent creation by two first-launch processes is not tested.

stdin commands: `start`, `stop`, `quit`, one per line. stdout is newline-delimited JSON: `ready` includes endpoint IDs, service clock frequency and timestamp; `midi` includes UInt64 timestamp and raw UInt32 UMP words; start/stop markers share that clock; `error` means recording must be treated as incomplete. MIDI callbacks enqueue to a bounded queue; a writer thread handles stdout. EOF/quit disposes the session. The parent owns and closes only this helper. There is no TCP/WebSocket server.

Tests (dedicated pair only):

```powershell
uv run --frozen --group build python tools/windows-midi/test_live.py
```

The live test uses RtMidi solely as a WinMM sender/second-reader probe, checks actual SDK delivery and timing, and terminates its own helper to exercise partial-take handling. It writes evidence into `build/windows-midi-qa`. Never direct this test at hardware or DAW-control ports.

See `../../JAM-MIDI-PLAN.md` for current verified state, known limitations, candidate use and Guitar Pro import.
