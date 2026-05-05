# Agent Instructions

This project provides standalone sync templates that turn SaaS data into files
for Cursor, Claude Code, Codex, and other AI agents.

Use these rules when editing the repository:

- Treat each service directory as an independent template repository.
- Keep service directory names in `[service]` format, such as `gmail`, `gcal`,
  `chatwork`, `gchat`, and `zoom`.
- Keep generated sync output under each service's `data/` directory out of
  source changes unless explicitly requested.
- Never add secrets, credentials, tokens, or real customer data.
- Prefer focused unit tests around deterministic helper behavior before adding
  integration tests.
- Run `python -m pytest` after test or sync-helper changes.
- Update the root `README.md` and the relevant service `README.md` when changing
  setup requirements, output formats, or supported tools.
