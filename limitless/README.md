# Limitless Sync

Sync Limitless Pendant lifelogs into a Git repository for AI context.

This template uses the Limitless Developer API with an API key. The current
Limitless API supports Pendant recordings/lifelogs, not web or desktop meeting
data. Audio downloads are disabled by default so the repository stays focused on
portable text files.

## What It Syncs

- Lifelog metadata as JSON
- Lifelog Markdown
- Optional structured `contents` as JSONL
- Optional Ogg Opus audio files when explicitly enabled

## Setup

1. Open Limitless Developer settings in the Limitless web or desktop app.
2. Create an API key.
3. Configure repository secrets:
   - `LIMITLESS_API_KEY`
4. Configure optional repository variables:
   - `LIMITLESS_FROM_DAYS`: how many days to look back on each run. Defaults to
     `30`.
   - `LIMITLESS_TIMEZONE`: IANA timezone used for API date filtering. Defaults
     to `UTC`.
   - `LIMITLESS_INCLUDE_CONTENTS`: set to `false` to skip structured contents.
     Defaults to `true`.
   - `LIMITLESS_INCLUDE_AUDIO`: set to `true` to download audio files. Defaults
     to `false`.

## Usage

Run locally:

```bash
export LIMITLESS_API_KEY="your_api_key"
export LIMITLESS_TIMEZONE="UTC"
python src/sync_limitless.py
```

Or run it from the Actions tab with `workflow_dispatch`.

## Data Structure

- `data/lifelogs/YYYY-MM-DD/`: lifelog JSON and Markdown files
- `data/contents/YYYY-MM-DD/`: structured contents as JSONL
- `data/audio/YYYY-MM-DD/`: optional Ogg Opus audio downloads
- `data/state.json`: processed lifelog IDs and last sync window

## Notes

- The scheduled sync uses `start` / `end` date filtering plus cursor pagination.
  It does not use search because search pagination is limited.
- Existing lifelog JSON and Markdown files are overwritten at the same path, so
  updated titles or summaries can be refreshed without duplicate files.
- Audio can contain sensitive conversations and can grow the repository quickly.
  Enable `LIMITLESS_INCLUDE_AUDIO` only in a private repository where that trade
  off is acceptable.
