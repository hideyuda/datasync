# Data Sync Templates

This directory contains standalone, repo-ready templates for scheduled sync:
- `gmail-data/` Gmail messages as `.eml` + metadata
- `gdrive-data/` Google Drive → Markdown (Docs/Slides/Sheets)
- `gcal-data/` Google Calendar ±3 months → daily Markdown
- `slack-data/` Slack channels → per-day JSONL

How to use:
1) Move each folder into its own GitHub repository (or initialize and push from here).
2) Add the required Secrets/Variables for each repo (see each `README.md`).
3) The included GitHub Actions will run on a schedule and auto-commit diffs.
4) In your main Agent repo, add each data repo as a Git submodule, e.g.:
   - `git submodule add https://github.com/<<your user or org name>>/gmail-sync data/gmail-sync`
   - `git submodule add https://github.com/<<your user or org name>>/gdrive-sync data/gdrive-sync`
   - `git submodule add https://github.com/<<your user or org name>>/gcal-sync data/gcal-sync`
   - `git submodule add https://github.com/<<your user or org name>>/slack-sync data/slack-sync`

Notes:
- These templates skip gracefully if secrets are missing, avoiding failing runs.
- Initial backfills can be large; consider running manually first (`workflow_dispatch`) and/or limiting queries.
- For privacy/security, ensure repos are private if they contain sensitive content.

