# Round review and career history

Implemented in source, 2026-10-31. Native Chord Painter and the Azure Static Web App bundle; see CHORD-PAINTER-QA.md for build/deployment status.

- Keep local scoring authoritative. Save explicit round IDs and all-time compact round summaries by game and chord type; retries update the same round. Keep the existing last-300 detailed attempt history and lifetime totals.
- Never guess legacy round boundaries. Earlier results remain in totals and are disclosed separately from the chronological chart.
- Review completed rounds before starting the next: identify weak types from recent results, accept per-type more/normal/less preferences and free text, show why the next plan contains each type.
- GPT interprets comments and summaries with the configured OpenAI key. Only comments and practice summaries are sent as model input, never guitar audio, file paths or credentials. Requests are asynchronous, bounded, and explicitly initiated with Analyze comments. Scores and history cannot be changed by the response. The native backend reads the ignored root `.env.local`; Azure uses server-only app settings and an authenticated allowed-user list.
- Suggestions adjust weights within bounds; all selected chord types retain a nonzero practice weight. Build the actual next question queue before starting; show type counts without giving away the question order in Guess.
- Career chart: chord types on rows, rounds chronologically left to right, separate Guess/Paint views. Green: all clean successes; yellow: at least half the tries succeeded but some misses/retries; red: fewer than half succeeded; gray: untested. Cells include text counts and accessible details.
- Preserve prior installed Retry work. Use the existing embedded Qt and JS, local atomic JSON storage, and build.ps1. Verify real embedded UI and installed package, then request permission before restarting the user's app.
- Browser storage is a chosen local JSON file, opened each visit in desktop Chrome/Edge and saved automatically. No persistent browser data or file handle is retained. Legacy browser data has an explicit migration path. Native Windows keeps its existing JSON path. Deletion or external edits stop saves instead of restoring stale in-memory history. Close the app and delete the file to reset. This affects Chord Painter practice only, not Flashcards or audio exports.
