# GuitarHacks web release

The SWA workflow publishes `chord_painter` and the `api` backend to `swa-guitarhacks` in `rg-guitarhacks` on pushes to `main`.

- `/`: web Home (`home.html`).
- `/practice`: shared Chord Painter (`index.html`); native Qt continues loading the file directly.
- `/explorer.html`: shared Explorer.
- `/index.html`: redirect to `/practice` for existing links.
- `/api/practice-review`: authenticated GPT review with the server's explicit account allowlist. Keys stay in server settings.

Home, Painter and Explorer link to the Windows release, the public GuitarHacks repository and Studio13's public repositories. Desktop-only cards are disabled with visible explanations. No browser microphone permission is requested by this release. The original separately managed `sites/chord-painter` checkout is not deployed by this workflow.

## Storage

The direct-file path retains serialized automatic writes and external-edit/deletion protection. Session mode and imported JSON use memory only, without localStorage or IndexedDB writes. Export requests a JSON download; the UI does not claim that the browser completed saving it. A fresh session starts empty. Browsers without direct file pickers can enter session mode or import JSON instead of being blocked at startup. The optional migration of older browser results remains available with the direct file picker.

The service worker caches application assets and public pages only. It does not cache API requests or practice data. Cache version v18 includes the Home/practice split. An already-open old page may need reloading after its worker updates.

## Verification

`node --test test_explorer.cjs test_painter.cjs test_painter_career.cjs test_practice_file.cjs api/review.test.cjs` — 34 checks passed.

`.venv\Scripts\python.exe -m unittest test_explorer_view test_painter_quiz test_painter_listening` — 24 checks passed in Qt WebEngine.

Real Edge checks used the same route mapping as `staticwebapp.config.json`: Home links and disabled tools, Explorer shape filtering, missing file-picker support, one-question round, JSON export and reimport, fresh-session reset, absence of a hidden session copy and offline Home/practice. Evidence: `output/playwright/web-release-home.png`, `output/playwright/web-release-imported.png`. These tests use synthetic practice data. Signed-in hosted GPT review and live guitar/voice accuracy are not established by these checks.

Before making the repository public, 192 historical blobs were scanned for OpenAI/GitHub token patterns, private key headers and Azure storage keys; no matches were found. This is a bounded automated scan, not a guarantee that all sensitive information has been identified. Personal recordings, saved data, environments, model weights and `.env` files are excluded by `.gitignore`.

Windows release build: `powershell -NoProfile -ExecutionPolicy Bypass -File .\build.ps1 -OutputDirectory build\public-release`. The release ZIP contains the new executable, public setup documentation and third-party notices, without the existing installation's data. Publication and deployment verification are recorded in CHORD-PAINTER-QA.md.
