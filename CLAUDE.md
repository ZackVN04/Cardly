# Cardly — Claude Code Instructions

## Project
FastAPI + Motor (async MongoDB) backend. Python 3.11. Pydantic v2.
Collections: users, contacts, events, tags, business_card_scans, enrichment_results, digital_cards, contact_activity_logs.

## Skill Workflow

### Automatic (run without being asked)
- After editing any `.py` file → run `/review-code`
- After writing or modifying test files → run `/python-testing` to check coverage gaps
- Before any auth-related code (JWT, password, tokens) → run `/security`

### On-demand (user invokes manually)
- `/debug` — quick diagnosis of a runtime error
- `/systematic-debugging` — structured root-cause analysis for hard bugs
- `/test` — run existing test suite or fix failing tests
- `/coverage` — check test coverage after implementing a module
- `/explain` — explain unfamiliar code (useful when reading teammate's work)
- `/commit` — generate a conventional commit message
- `/claude-mem` — recall context from previous sessions

## Code Style
- No comments unless the WHY is non-obvious
- No docstrings
- Async all the way (Motor is async — never use sync pymongo calls)
- Pydantic v2 patterns: `model_validator`, `field_validator`, not v1 `@validator`
- ObjectId → PyObjectId custom type (already in src/core/models.py)

## Testing Rules
- `asyncio_mode = "auto"` is set — all async tests work without decorator
- Use `async_client` fixture (defined in tests/conftest.py) — it calls connect_db() + create_indexes()
- Do NOT mock MongoDB — integration tests hit real Atlas
- Test file naming: `tests/<module>/test_<feature>.py`

## Build Order (internship plan)
W3 done (core, database, main). Next:
1. activity/service.py
2. tags/ (router + service)
3. events/ (router + service)
4. contacts/ (router + service)
5. auth/ (router + service)
6. scans/, enrichment/, cards/, uploads/
