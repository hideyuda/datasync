# Claude Code Instructions

This repository contains standalone Python 3.11 templates for syncing SaaS data
to GitHub for AI context.

Project conventions:

- Service directories are named by service only, for example `gmail`, `gdrive`,
  `slack`, `notion`, and `zoom`.
- Preserve each service as a copyable GitHub Actions template with its own
  `src/`, `requirements.txt`, `.github/workflows/sync.yml`, and `README.md`.
- Do not commit secrets, OAuth tokens, generated `data/` output, or `.env`
  files.
- Missing credentials should skip sync work gracefully where possible.
- Keep tests API-free by default. Use `python -m pytest` from the repository
  root.
- When updating documentation, list only implemented integrations as supported.
