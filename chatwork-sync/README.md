# Chatwork Sync

Fetches rooms and messages from Chatwork via the Chatwork API and writes them as local files for AI context.

Output:
- `data/rooms/<room_name>_<room_id>.json`
- `data/chatwork/<room_name>_<room_id>/YYYY-MM-DD.jsonl`
- `data/state.json` last message ID per room

## Setup

1. Create or copy your Chatwork API token from Chatwork.
2. Set the token in the `CHATWORK_API_TOKEN` environment variable.
3. Optional: set `CHATWORK_ROOM_IDS` to a comma-separated room ID list if you only want specific rooms.

## Usage

```bash
export CHATWORK_API_TOKEN="your_api_token"
# Optional:
export CHATWORK_ROOM_IDS="12345,67890"
python src/sync_chatwork.py
```

## Notes

Chatwork's messages API returns the messages available from the standard endpoint, not a fully paginated historical export. This sync keeps `data/state.json` and only writes messages newer than the last stored `message_id`, so scheduled runs avoid duplicating data.
