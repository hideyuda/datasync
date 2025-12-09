# Google Drive Sync (to Markdown)

Exports Google Docs/Slides to Markdown and commits diffs on a schedule.

Output:
- `data/md/*.md` converted markdown
- `data/state.json` last run time

Secrets:
- `GDRIVE_CLIENT_ID`
- `GDRIVE_CLIENT_SECRET`
- `GDRIVE_REFRESH_TOKEN`

Variables:
- `GDRIVE_ROOT_QUERY` optional Drive query filter (e.g., `'trashed = false'`)

Notes:
- Google Docs/Slides exported as HTML then converted to Markdown.
- Google Sheets exported to CSV and converted to Markdown tables (first sheet only).
- Non-Google file types are skipped in this minimal template.

Submodule usage is the same pattern as other sync repos.

