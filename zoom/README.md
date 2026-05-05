# Zoom Sync

Sync Zoom Cloud Recording metadata and transcripts into a Git repository.

This template is designed for scheduled GitHub Actions runs. It skips gracefully
when secrets are missing, and it avoids downloading large audio/video files by
default so the repository stays manageable.

## What It Syncs

- Meeting and recording metadata as JSON
- A compact Markdown summary for each meeting
- Transcript files (`TRANSCRIPT`, usually `.vtt`)
- Optional non-transcript recording files when explicitly enabled

## Setup

1. Create a Zoom Server-to-Server OAuth app in the
   [Zoom App Marketplace](https://marketplace.zoom.us/).
2. Copy the app credentials:
   - Account ID
   - Client ID
   - Client Secret
3. Add scopes for reading cloud recordings. If you do not set `ZOOM_USER_IDS`,
   also add the user read/list scope so the script can discover account users.
4. Configure repository secrets:
   - `ZOOM_ACCOUNT_ID`
   - `ZOOM_CLIENT_ID`
   - `ZOOM_CLIENT_SECRET`
5. Configure optional repository variables:
   - `ZOOM_USER_IDS`: comma-separated Zoom user IDs or emails. Recommended for
     least privilege and predictable syncs.
   - `ZOOM_FROM_DAYS`: how many days to look back on each run. Defaults to `30`.
   - `ZOOM_DOWNLOAD_RECORDINGS`: set to `true` to download non-transcript files
     such as audio/video. Defaults to `false`.

## Usage

Run locally:

```bash
export ZOOM_ACCOUNT_ID="your_account_id"
export ZOOM_CLIENT_ID="your_client_id"
export ZOOM_CLIENT_SECRET="your_client_secret"
export ZOOM_USER_IDS="you@example.com"
python src/sync_zoom.py
```

Or run it from the Actions tab with `workflow_dispatch`.

## Data Structure

- `data/meetings/YYYY-MM-DD/`: meeting metadata JSON and Markdown summaries
- `data/transcripts/YYYY-MM-DD/`: transcript files
- `data/recording_files/YYYY-MM-DD/`: optional non-transcript downloads
- `data/state.json`: sync state and processed recording file IDs

## Notes

- Zoom recording APIs limit date ranges, so the script splits long lookbacks
  into 30-day windows.
- Transcript files are downloaded by default because they are usually small and
  useful for AI context.
- Audio/video downloads are disabled by default. Enable them only if this repo
  is private and you are comfortable with Git repository growth.
