# Auto-Sync Slack, Chatwork, Gmail, Drive, Calendar, and Zoom to GitHub for Better AI Context

Dump data from Gmail, Drive, Calendar, Slack, Chatwork, and Zoom into a Git repository first → Use that repo as a "Local Knowledge Base" for Cursor or your AI Agent.

This directory contains standalone, repo-ready templates for scheduled sync:

  * **Gmail:** Saves almost all emails as `.eml` files + JSON metadata.
  * **Google Drive:** Converts Docs, Slides, and Sheets into Markdown.
  * **Google Calendar:** Exports schedules (past 3 months to future 3 months) as daily Markdown summaries.
  * **Slack:** Dumps logs from joined channels into daily JSONL files.
  * **Chatwork:** Dumps room messages into daily JSONL files via the Chatwork API.
  * **Zoom:** Saves Cloud Recording metadata and transcripts for AI-readable meeting context.

Run these as **separate GitHub repositories** and use **GitHub Actions** to periodically check for diffs and auto-commit them. 

Main AI/Agent repository just references them as **Git Submodules**.

Notes:
- These templates skip gracefully if secrets are missing, avoiding failing runs.
- Initial backfills can be large; consider running manually first (`workflow_dispatch`) and/or limiting queries.
- For privacy/security, ensure repos are private if they contain sensitive content.

Here is a translation that captures the vibe of a modern tech blog post (like something you’d see on Dev.to or Medium). I’ve adjusted the phrasing to sound like a real developer talking to peers, avoiding stiff "AI-translation" language while keeping the technical details precise.

### Why this approach rocks

1.  **Files are reusable:** Whether it's Cursor, VS Code, or a custom Agent, they all just read standard files. No proprietary API handling needed.
2.  **Diffs = History:** You can use `git log` to see exactly what changed yesterday or what happened on a specific date.
3.  **Smarter Context:** instead of dumping a massive API response into the LLM, you just open the specific file you need. It’s way cheaper and more accurate.
4.  **Stability:** The sync happens in the background via GitHub Actions. If it fails, it just retries later. You don't have to wait for an API call while you're trying to code.

-----

### Setup Guide

Here is how to set it up for yourself.

#### 1\. Google Setup (Gmail / Drive / Calendar)

**1-1. GCP Project & APIs**

  * Go to the [Google Cloud Console](https://console.cloud.google.com/).
  * Create a project (or select an existing one).
  * Go to **APIs & Services \> Library** and enable:
      * Gmail API
      * Google Drive API
      * Google Calendar API

**1-2. OAuth Consent Screen**

  * **User Type:** External (or Internal if you have a Workspace org).
  * Fill in the app name/email.
  * **Important:** If in "Testing" mode, add your own email as a Test User. Move to Production when you're ready for stable use.

**1-3. Create Credentials**

  * **Credentials \> Create Credentials \> OAuth Client ID**.
  * App type: **Desktop App**.
  * **Save the Client ID and Client Secret.**

#### 2\. Generate a Single Refresh Token

You don't need separate tokens for each service. I use one token with scopes for all three.

1.  **Install dependencies:**

    ```bash
    pip install google-auth-oauthlib
    # or
    uv add google-auth-oauthlib
    ```

2.  **Update the script:**
    In the repo (`scripts/generate_refresh_token.py`), replace `YOUR_CLIENT_ID` and `YOUR_CLIENT_SECRET` with your own.

    ```python
    from google_auth_oauthlib.flow import InstalledAppFlow

    SCOPES = [
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
        "https://www.googleapis.com/auth/calendar.readonly",
    ]

    client_config = {
        "installed": {
            "client_id": "YOUR_CLIENT_ID",
            "client_secret": "YOUR_CLIENT_SECRET",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }

    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")
    print("REFRESH_TOKEN=", creds.refresh_token)
    ```

3.  **Run it:**

    ```bash
    python scripts/generate_refresh_token.py
    ```

    Login via the browser window that pops up.

4.  **Save the Token:** copy the `REFRESH_TOKEN` printed in your terminal. You will use this for all Google services.

#### 3\. Repository Configuration

Configure the Secrets/Env vars in each of your sync repos (`gmail-sync`, `gdrive-sync`, etc.).

**3-1. Gmail (`gmail-sync`)**

  * `GMAIL_CLIENT_ID`
  * `GMAIL_CLIENT_SECRET`
  * `GMAIL_REFRESH_TOKEN` (The one you just generated)
  * `GMAIL_USER_EMAIL` (e.g., `you@example.com`)
  * *Optional:* `GMAIL_QUERY` (e.g., `newer_than:90d` to keep the initial sync manageable).

**3-2. Drive & Calendar**

  * Use the same Client ID/Secret/Refresh Token logic as above.
  * For variables, just change the prefix (e.g., `GDRIVE_CLIENT_ID`, `GCAL_CLIENT_ID`).

**3-4. Slack (`slack-sync`)**

  * Create an app at [api.slack.com/apps](https://api.slack.com/apps).
  * **OAuth & Permissions \> Bot Token Scopes**:
      * `channels:read`
      * `groups:read`
      * `channels:history`
      * `groups:history`
  * **Install to Workspace** and copy the **Bot User OAuth Token** (`xoxb-...`).
  * Set this as `SLACK_BOT_TOKEN` in your repo secrets.

**3-5. Chatwork (`chatwork-sync`)**

  * Create or copy your Chatwork API token.
  * Set it as `CHATWORK_API_TOKEN` in your repo secrets.
  * *Optional:* Set `CHATWORK_ROOM_IDS` as a repository variable with comma-separated room IDs to sync only specific rooms.

**3-6. Zoom (`zoom-sync`)**

  * Create a Server-to-Server OAuth app in the [Zoom App Marketplace](https://marketplace.zoom.us/).
  * Add cloud recording read scopes. If you do not set `ZOOM_USER_IDS`, also add user read/list scopes so the script can discover active account users.
  * Set these repository secrets:
      * `ZOOM_ACCOUNT_ID`
      * `ZOOM_CLIENT_ID`
      * `ZOOM_CLIENT_SECRET`
  * *Optional:* Set `ZOOM_USER_IDS` as a repository variable with comma-separated user IDs or emails.
  * *Optional:* Set `ZOOM_FROM_DAYS` to control the lookback window. Defaults to `30`.
  * *Optional:* Set `ZOOM_DOWNLOAD_RECORDINGS=true` only if you want to store audio/video files in Git. Transcripts are downloaded by default.

#### 4\. The First Run

Go to the **Actions** tab in each repo and manually trigger the workflow.
*Tip: For Gmail, start with a narrow query (like 90 days) to test it out. If it works, widen the scope.*
After this, the `cron` schedule will handle it automatically.

#### 5\. Integrate as Submodules

Finally, link these data repos to your main Agent or Project repo:

```bash
git submodule add https://github.com/<user>/gmail-sync  data/gmail-sync
git submodule add https://github.com/<user>/gdrive-sync data/gdrive-sync
git submodule add https://github.com/<user>/gcal-sync   data/gcal-sync
git submodule add https://github.com/<user>/slack-sync  data/slack-sync
git submodule add https://github.com/<user>/chatwork-sync data/chatwork-sync
git submodule add https://github.com/<user>/zoom-sync data/zoom-sync
```

To fetch new data, just run:

```bash
git submodule update --remote --merge
```