# Gmail Sync (GitHub Actions)

Pulls Gmail messages into this repository and commits diffs on a schedule.

Output:
- `data/eml/*.eml` RFC822 messages
- `data/index/*.json` message metadata
- `data/state.json` incremental cursor

Secrets (Repository → Settings → Secrets and variables → Actions):
- `GMAIL_CLIENT_ID`
- `GMAIL_CLIENT_SECRET`
- `GMAIL_REFRESH_TOKEN` (offline access)
- `GMAIL_USER_EMAIL` (e.g., your.email@example.com)

Optional Variables (Actions → Variables):
- `GMAIL_QUERY` e.g., `-category:promotions -category:social`
- `GMAIL_FULL_SYNC` set to `true` for initial full backfill

Submodule usage:
1) Create this repo on GitHub and push.
2) In your main repo:  
   `git submodule add https://github.com/you/gmail-sync vendors/gmail`
3) Commit and pull updates as needed:  
   `git submodule update --remote vendors/gmail`

