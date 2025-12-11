# Google Chat Sync

A script to periodically backup and sync Google Chat data (Spaces and Messages).

## Setup

1. Create a project in Google Cloud Console.
2. Enable the "Google Chat API".
3. Configure OAuth consent screen.
4. Create OAuth 2.0 Client ID (Desktop app).
5. Obtain a Refresh Token with the following scopes:
   - `https://www.googleapis.com/auth/chat.spaces.readonly`
   - `https://www.googleapis.com/auth/chat.messages.readonly`
   - `https://www.googleapis.com/auth/chat.memberships.readonly`
6. Set the environment variables:
   - `GCHAT_CLIENT_ID`
   - `GCHAT_CLIENT_SECRET`
   - `GCHAT_REFRESH_TOKEN`

## Usage

```bash
export GCHAT_CLIENT_ID="your_client_id"
export GCHAT_CLIENT_SECRET="your_client_secret"
export GCHAT_REFRESH_TOKEN="your_refresh_token"
python src/sync_gchat.py
```

## Data Structure

- `data/spaces/`: JSON files for each space metadata.
- `data/messages/<space_name>_<space_id>/`:
  - `messages.json`: Raw JSON of messages.
  - `messages.md`: Readable markdown log of messages.
