# Sync SaaS Tools to GitHub for AI Context

Turn Gmail, Google Drive, Google Calendar, Slack, Chatwork, Google Chat,
Notion, and Zoom into a Git-backed AI knowledge base. Each template syncs data
with GitHub Actions, commits readable files, and lets Cursor, Claude Code,
Codex, or another coding agent use those files as local context.

Use this project when you want to sync Slack to GitHub, back up Gmail to
GitHub, convert Google Drive to Markdown, export Google Calendar to Markdown,
save Zoom transcripts, or keep Notion and chat tools available as LLM context
without wiring every AI workflow directly to SaaS APIs.

## Supported Tools

| Tool | Template | Output | Notes |
| --- | --- | --- | --- |
| Gmail | [`gmail`](gmail) | `.eml` files and JSON metadata | Defaults to recent mail unless `GMAIL_FULL_SYNC=true` or `GMAIL_QUERY` is set. |
| Google Drive | [`gdrive`](gdrive) | Markdown | Exports Google Docs, Slides, and Sheets. Non-Google files are skipped. |
| Google Calendar | [`gcal`](gcal) | Daily Markdown summaries | Covers the configured past/future window. |
| Slack | [`slack`](slack) | Daily JSONL logs | Limited to channels the token can read. |
| Chatwork | [`chatwork`](chatwork) | Daily JSONL logs | Can be scoped to specific rooms. |
| Google Chat | [`gchat`](gchat) | Message data files | Requires Google Chat API access and configured spaces. |
| Notion | [`notion`](notion) | JSON and simple Markdown | Saves page/database metadata and properties. |
| Zoom | [`zoom`](zoom) | Recording metadata, Markdown summaries, transcripts | Audio/video download is disabled by default. |

Teams and Limitless are not listed as supported until their templates exist in
this repository.

## Why GitHub for AI Context

1. **Files are portable.** Cursor, Claude Code, Codex, local scripts, and custom
   agents can all read ordinary files.
2. **Git gives you history.** `git log` and diffs show what changed between
   sync runs.
3. **Context stays focused.** Agents can open the exact email, meeting note,
   transcript, or chat log they need instead of loading a large API response.
4. **Sync is decoupled.** GitHub Actions handles scheduled updates in the
   background, so coding workflows do not wait on SaaS APIs.

## Project Shape

Each service directory is a standalone, repo-ready template:

```text
gmail/
  src/sync_gmail.py
  requirements.txt
  .github/workflows/sync.yml
  README.md
```

You can copy one directory into its own private repository, configure secrets,
and run it independently. Your main AI or agent repository can then reference
those data repositories as Git submodules.

## Quick Start

1. Choose a service template such as [`gmail`](gmail), [`slack`](slack), or
   [`zoom`](zoom).
2. Create a private GitHub repository for that service data.
3. Copy the template contents into that repository.
4. Configure the required GitHub Actions secrets and variables.
5. Run the workflow manually from the Actions tab with `workflow_dispatch`.
6. Add the data repository to your main project as a submodule.

```bash
git submodule add https://github.com/<user>/gmail data/gmail
git submodule add https://github.com/<user>/gdrive data/gdrive
git submodule add https://github.com/<user>/gcal data/gcal
git submodule add https://github.com/<user>/slack data/slack
git submodule add https://github.com/<user>/chatwork data/chatwork
git submodule add https://github.com/<user>/gchat data/gchat
git submodule add https://github.com/<user>/notion data/notion
git submodule add https://github.com/<user>/zoom data/zoom
```

Fetch the latest synced data from your main repository:

```bash
git submodule update --remote --merge
```

## Google OAuth Setup

Gmail, Google Drive, and Google Calendar can share one OAuth refresh token when
you request all required scopes.

1. Open the [Google Cloud Console](https://console.cloud.google.com/).
2. Create or select a project.
3. Enable the Gmail API, Google Drive API, and Google Calendar API.
4. Configure the OAuth consent screen. In testing mode, add your own email as a
   test user.
5. Create an OAuth Client ID with application type `Desktop App`.
6. Copy the client ID and client secret.

Generate a refresh token with [`scripts/generate_refresh_token.py`](scripts/generate_refresh_token.py):

```bash
pip install google-auth-oauthlib
python scripts/generate_refresh_token.py
```

Use the printed `REFRESH_TOKEN` in the Google service repositories.

## Service Setup

Each service README contains the exact secrets, variables, scopes, and output
paths for that template:

- [Gmail setup](gmail/README.md)
- [Google Drive setup](gdrive/README.md)
- [Google Calendar setup](gcal/README.md)
- [Slack setup](slack/README.md)
- [Chatwork setup](chatwork/README.md)
- [Google Chat setup](gchat/README.md)
- [Notion setup](notion/README.md)
- [Zoom setup](zoom/README.md)

Common behavior:

- Missing secrets are treated as a skip where possible, not as a hard failure.
- Initial backfills can be large. Start with a narrow query or short lookback
  window, run manually, then widen the scope.
- Scheduled workflows commit only when files changed.

## Privacy and Repository Size

Synced email, documents, chat logs, calendars, recordings, and transcripts can
contain sensitive data. Use private repositories, restrict token scopes, and be
careful before enabling large file downloads such as Zoom audio or video.

Git is excellent for text history, but it is not ideal for large binary
archives. Prefer Markdown, JSON, JSONL, `.eml`, and transcript files for an AI
knowledge base.

## Local Development

Install test dependencies and run the unit tests:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest
```

The current tests focus on API-free sync helpers so they can run without SaaS
credentials.