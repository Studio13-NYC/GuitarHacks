# OpenAI model routing

Updated 31 October 2026.

Requested policy: lower tier **`gpt-6.1-terra` / high**, upper tier **`gpt-6-astra` / medium**.

Desktop and web practice reviews default to GPT-6.1 Terra/high. `GUITARHACKS_COACH_MODEL` remains the model override; Astra uses medium. Existing structured output and 3,000-token review bounds remain.

These are repository changes on `codex/openai-model-tiers-20261031`. This document does not certify a deployed service. Existing host environment variables take precedence over model defaults; reconcile the listed overrides when merging/deploying. No API key is added, rotated, or committed.

Official compatibility reference: https://developers.openai.com/api/docs/guides/latest-model

## Validation

`node --test api/review.test.cjs`: 4 passed. Existing GuitarHacks virtualenv: `python -m unittest test_painter_coach`: 3 passed.

Changed Python/JavaScript files passed syntax checks; `git diff --check` passed. Two small synthetic Responses API checks with an existing Studio13 project key returned completed, valid JSON for Terra/high and Astra/medium. These establish model access for that key, not full application quality or every deployment credential.
