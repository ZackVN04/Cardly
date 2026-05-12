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

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **Cardly** (1239 symbols, 2090 relationships, 11 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/Cardly/context` | Codebase overview, check index freshness |
| `gitnexus://repo/Cardly/clusters` | All functional areas |
| `gitnexus://repo/Cardly/processes` | All execution flows |
| `gitnexus://repo/Cardly/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
