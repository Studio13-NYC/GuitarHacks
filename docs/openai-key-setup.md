# OpenAI key setup

The helper `tools/set-openai-key.ps1` uses PowerShell 7 and a hidden key prompt. Keys are never command-line arguments. It can save an ignored local env file and/or set `OPENAI_API_KEY` in an existing Azure Static Web App's **production backend** app settings. It does not create the SWA, deploy an API, or inject secrets into browser JavaScript. Existing Azure settings are retained and compared after the update.

Run only after choosing the destinations. Example local command from the repository root:

```powershell
pwsh -NoProfile -File .\tools\set-openai-key.ps1 -EnvFile .env.local -Target Local
```

For both, add `-Target Both -AzureResourceId '<existing SWA resource ID>'` instead of `-Target Local`. After saving locally, `-Target Azure -UseSavedKey` can configure production without asking for the key again. Azure CLI must be signed into the resource's subscription. The helper confirms destinations before prompting and never prints values. Do not run it under shell tracing/debug output.

The native development app reads `.env.local` from the repository root, or the file explicitly selected by `GUITARHACKS_OPENAI_ENV`. The installed `FretboardFiend/release` app reads the same repository-root file. Optional `GUITARHACKS_COACH_MODEL` defaults to `gpt-5.4-mini`. The browser never reads this file. Local files are private to the current Windows account and ignored by Git.

Current status (October 31, 2026): the user approved `.env.local` and entered the new key into the hidden PowerShell prompt. Local and Azure key values match (compared in memory, never printed). Azure target: `swa-guitarhacks` in `rg-guitarhacks`, subscription `cb1dcd8d-3035-46f5-838e-855b58fbd27a`. A real desktop GPT review using `gpt-5.4-mini` succeeded. `COACH_ALLOWED_USERS=github:nickknyc` restricts the hosted review to the owner's GitHub sign-in; credentials are never included in frontend code. The initial static UI was deployed by Azure's generated GitHub workflow; the new API deployment is still pending at this writing.

Azure API references: [backend application settings](https://learn.microsoft.com/en-us/azure/static-web-apps/application-settings), [read existing settings](https://learn.microsoft.com/en-us/rest/api/appservice/static-sites/list-static-site-app-settings?view=rest-appservice-2025-05-01), [update settings](https://learn.microsoft.com/en-us/rest/api/appservice/static-sites/create-or-update-static-site-app-settings?view=rest-appservice-2025-05-01).
