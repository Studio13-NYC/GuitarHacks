# ChordLab hosting

Current publication: October 27, 2026, ChordLab module chooser and browser listening exercises. Public access and the home-screen launch fix are retained.

- URL: https://guitarhacks-chord-painter.nickknyc.chatgpt.site
- Audience: public, as requested October 27; no ChatGPT sign-in is required.
- Project: `appgprj_6ade8fa6c9d88191a599fb01d819f3eb`
- Checkout: `D:\Studio13\Lab\Music\GuitarHacks\sites\chord-painter`
- Manifest: `.openai\hosting.json`; static directory: `dist`.
- Pushed source: `36d19652f606e25ba6cb8e51578a71119905d3fc`
- Saved version: `appgprj_6ade8fa6c9d88191a599fb01d819f3eb~appgver_8de4f391f5248191aa375b10d223e004` (version 6)
- Successful deployment: `appgdep_6ae13a902f74819181bcb9b8caf65071`
- Archive: `D:\Studio13\Lab\Music\GuitarHacks\build\chordlab-listen.tar.gz`

Reuse this project identity and public audience for updates. The hosted checkout owns ChordLab's shell and listening code. Shared Painter changes originate in the parent's `chord_painter` folder, but must be applied selectively: copying that whole folder over hosted `dist` would remove the web modules. Preserve the web navigation hook, manifest and service worker. Obtain a fresh Sites source credential at update time; no credentials are stored here. Use the Sites skill's source workflow, push the exact source, then save/deploy that commit and matching archive. Bump `sw.js` cache version when application assets change.

No progress data was uploaded. Phone progress stays in local browser storage; desktop progress stays in its existing local files. Desktop and phone do not sync. Android installation instructions are in `CHORD-PAINTER.md`. The user confirmed Chrome loads the app but their installed icon failed. The same cached-launch failure was reproduced and repaired in desktop Chrome; the repaired Android icon awaits user confirmation.

Chord Painter retains Reset round, 1–100 questions per round, scores, fret scrolling and completed-round storage. Listen & Play adds microphone calibration, four 12-card note modes, Find everywhere, pause/resume, and separate local results. Tests: 16 Node tests plus actual-browser generated-audio journeys, permission failures and cache launch checks; details in `sites\chord-painter\QA.md`. Live-guitar/physical-Android accuracy is not yet verified.

Service-worker cache: `chord-painter-v10`. New icons launch at `/`; existing `/index.html` icons receive the canonical cached ChordLab page. The manifest retains its original app identity, with the display name changed to ChordLab. Existing browsers may show their old cached Painter page once while fetching the update; refresh after it loads. A browser may retain the old icon label until its manifest updates. Desktop assets remain on their prior Painter version; no Windows rebuild was performed.
