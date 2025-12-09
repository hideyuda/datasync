# Slack Sync (all joined channels)

Fetches messages from all channels the bot/user can access and writes per-day JSONL.

Output:
- `data/slack/<channel_name>/YYYY-MM-DD.jsonl`
- `data/state.json` last per-channel timestamp

Secret:
- `SLACK_BOT_TOKEN` (with scopes: `channels:history`, `groups:history`, `channels:read`, `groups:read`)


