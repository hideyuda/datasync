# Notion Sync

A script to periodically backup and sync Notion data.

## Setup

1. Create an integration in Notion: [https://www.notion.so/my-integrations](https://www.notion.so/my-integrations)
2. Get the "Internal Integration Token" for the integration.
3. Select "Add connections" from the "..." menu of the Notion page or database you want to sync, and add the created integration.
4. Set the token in the `NOTION_API_KEY` environment variable.

## Usage

```bash
export NOTION_API_KEY="your_secret_token"
python src/sync_notion.py
```

## Data Structure

- `data/pages/`: JSON and Markdown files for each page
- `data/databases/`: JSON files for each database
