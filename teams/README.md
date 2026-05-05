# Microsoft Teams Sync

Sync Microsoft Teams channel messages into a Git repository for AI context.

This template uses Microsoft Graph app-only authentication so it can run from
GitHub Actions without a user refresh token. The first version focuses on Teams
and channel messages. 1:1 chats, meeting transcripts, and recordings are not
enabled by default because they require broader permissions and carry higher
privacy or repository-size risk.

## What It Syncs

- Team metadata
- Channel metadata
- Channel messages as daily JSONL files
- Optional message replies when `TEAMS_INCLUDE_REPLIES=true`

## Setup

1. Open the [Azure portal](https://portal.azure.com/) and create an App
   Registration.
2. Copy:
   - Directory (tenant) ID
   - Application (client) ID
3. Create a client secret and copy its value.
4. Add Microsoft Graph application permissions:
   - `Team.ReadBasic.All`
   - `Channel.ReadBasic.All`
   - `ChannelMessage.Read.All`
5. Grant admin consent for the tenant.
6. Configure repository secrets:
   - `TEAMS_TENANT_ID`
   - `TEAMS_CLIENT_ID`
   - `TEAMS_CLIENT_SECRET`
7. Configure optional repository variables:
   - `TEAMS_TEAM_IDS`: comma-separated team IDs. Recommended for least
     privilege and predictable syncs.
   - `TEAMS_CHANNEL_IDS`: comma-separated channel IDs or `team_id/channel_id`
     pairs.
   - `TEAMS_FROM_DAYS`: how many days to look back on each run. Defaults to
     `30`.
   - `TEAMS_INCLUDE_REPLIES`: set to `true` to fetch thread replies for new
     channel messages.

## Usage

Run locally:

```bash
export TEAMS_TENANT_ID="your_tenant_id"
export TEAMS_CLIENT_ID="your_client_id"
export TEAMS_CLIENT_SECRET="your_client_secret"
export TEAMS_TEAM_IDS="team-id-1,team-id-2"
python src/sync_teams.py
```

Or run it from the Actions tab with `workflow_dispatch`.

## Data Structure

- `data/teams/`: team metadata JSON
- `data/channels/<team>/`: channel metadata JSON
- `data/messages/<team>/<channel>/YYYY-MM-DD.jsonl`: channel messages
- `data/state.json`: per-channel cursor and recent message IDs

## Notes

- If `TEAMS_TEAM_IDS` is not set, the script tries to list Teams-backed groups.
  That requires tenant-wide read permissions.
- Start with a small `TEAMS_TEAM_IDS` allowlist and a short `TEAMS_FROM_DAYS`
  window before widening the scope.
- 1:1 chats, meeting transcripts, and recordings should be added as explicit
  opt-in sync targets rather than mixed into the default channel-message sync.
