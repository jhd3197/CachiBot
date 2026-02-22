---
name: code-review
description: Run a full-codebase audit of CachiBot using 8 parallel review agents (DRY, Security, API, Data, Frontend, Tests, State, Observability). Each agent reports findings with file paths and line numbers, compiled into a dated report.
---

# Code Review — 8-Agent Sweep

Run a full-codebase audit of CachiBot using 8 parallel review agents. Each agent
focuses on a specific quality concern and reports findings with file paths and
line numbers. Results are compiled into a single dated report.

## Instructions

1. Note today's date for the report header.
2. Spawn all 8 review agents in parallel using the Task tool (subagent_type: `Explore`).
   Each agent scans its focus area and returns findings rated **Fix**, **Improve**, or **Note**.
3. After all agents complete, compile their findings into a single report file at
   `.reviews/YYYY-MM-DD-review.md` (create the `.reviews/` directory if it doesn't exist).
4. Print a summary to the user with totals per severity.

## Agent Definitions

### 1. Tina — The DRY Enforcer

**Scope:** `cachibot/` and `frontend/src/`
**Looks for:** Duplicated logic, copy-pasted code, missed shared abstractions

- Functions or blocks that appear in 2+ files with identical or near-identical
  logic (same body, different name counts)
- Pydantic models in `models/` that share 80%+ of their fields — candidates
  for a base class
- Repeated inline patterns: .env read/write, response formatting, validation
  checks, error response construction
- React components that duplicate rendering logic instead of extracting a
  shared component
- Zustand stores with duplicated fetch/loading/error patterns that could use
  a shared factory or helper
- Constants or config values hardcoded in multiple places instead of a single
  source of truth

### 2. Marcus — The Security Auditor

**Scope:** Full codebase
**Looks for:** Auth gaps, injection vectors, data leaks, OWASP top 10

- Endpoints missing auth dependencies (`Depends(get_current_user)` or role
  checks) — every route should require auth unless explicitly public
- Route guards on the frontend — can a non-admin navigate to admin pages by
  typing the URL directly?
- Injection risks in any string interpolation touching .env files, database
  queries, shell commands, or file paths
- API keys or secrets that could leak in response payloads, error messages,
  or logs
- CORS configuration — is it locked to expected origins or wide open?
- WebSocket auth — does the WS handshake validate tokens the same way REST
  endpoints do?
- Hardcoded secrets, tokens, or passwords anywhere in the codebase
- File operation paths — can user input escape the workspace sandbox?

### 3. Priya — The API Consistency Reviewer

**Scope:** `cachibot/api/routes/`
**Looks for:** Inconsistent endpoint patterns, missing validation, API design issues

- Inconsistent response shapes — do all endpoints follow the same success/error
  response pattern?
- Missing input validation — are request bodies validated with Pydantic models,
  or do some endpoints accept raw dicts?
- HTTP status code correctness — 200 vs 201 for creation, 404 vs 400 for bad
  input, proper use of 403 vs 401
- Missing or inconsistent error handling — do all endpoints catch expected
  failures and return structured error responses?
- Endpoint naming conventions — RESTful consistency across all routers
- Missing `response_model` declarations on endpoints that return data
- Deprecated endpoints still active without migration path or warnings

### 4. Carlos — The Data Layer Inspector

**Scope:** `cachibot/storage/` and any database-touching code
**Looks for:** Database issues, unsafe queries, missing error handling in storage

- Raw SQL without parameterized queries (SQL injection risk)
- Missing error handling around database operations — are connection failures,
  constraint violations, and timeouts caught?
- Transactions that should be atomic but aren't wrapped properly
- Missing indexes on columns used in WHERE/ORDER BY clauses
- Schema inconsistencies between what the code expects and what migrations create
- Repository methods that duplicate query logic instead of composing
- Connection pool or lifecycle issues — are connections properly closed on error
  paths?

### 5. Zoe — The Frontend Quality Checker

**Scope:** `frontend/src/`
**Looks for:** Component issues, accessibility, React anti-patterns

- Components that are too large (>200 lines) and should be split
- Missing error boundaries — what happens when a component throws?
- Accessibility gaps — missing aria labels, keyboard navigation, focus
  management in modals/dialogs
- Hardcoded strings that should be in constants or i18n
- Inline styles that should be in CSS/Tailwind classes
- Props being drilled through 3+ levels instead of using context or stores
- useEffect with missing or incorrect dependency arrays
- Components re-rendering unnecessarily — missing memo, unstable references
  in deps

### 6. Derek — The Test Coverage Analyst

**Scope:** `tests/` and full codebase
**Looks for:** Missing tests, weak assertions, untested paths

- Which endpoints in `api/routes/` have zero test coverage?
- Which utility functions and service methods lack unit tests?
- Are error paths tested, or only happy paths?
- Do integration tests exist for critical flows (auth, chat, WebSocket)?
- Are there tests that assert on implementation details instead of behavior
  (brittle tests)?
- Frontend: are there any component or store tests? What's missing?
- Are test fixtures/factories available, or does every test build its own
  data from scratch?

### 7. Luna — The State & Integration Reviewer

**Scope:** `frontend/src/stores/`, `frontend/src/api/`
**Looks for:** State management issues, frontend-backend contract mismatches

- Zustand stores with stale state bugs — data fetched but never refreshed,
  or refreshed too aggressively
- API client methods that don't handle errors consistently — some throw,
  some return null, some swallow
- Type mismatches between frontend TypeScript interfaces and backend Pydantic
  models — fields that exist on one side but not the other
- localStorage persistence of sensitive data (tokens, keys, admin state)
- WebSocket reconnection logic — does the client recover from disconnects
  gracefully?
- Race conditions — multiple concurrent requests updating the same store slice
- Loading/error states that are missing or inconsistent across views

### 8. Oscar — The Observability Reviewer

**Scope:** Full codebase
**Looks for:** Silent failures, missing logs, poor error messages, bare excepts

- Bare `except Exception` or `except:` blocks that swallow errors silently —
  every catch should log or re-raise
- Important operations with no logging at all (user creation, config changes,
  provider key updates)
- Log messages that are too vague to be useful ("error occurred" with no
  context)
- Error responses that expose internal details (tracebacks, file paths, SQL)
  to the client
- Missing `logger = logging.getLogger(...)` in modules that should have one
- Inconsistent log levels — warnings that should be errors, debug that should
  be info
- Health check gaps — what breaks silently with no way to detect it?

## Report Format

After all agents finish, write `.reviews/YYYY-MM-DD-review.md` with this structure:

```markdown
# CachiBot Code Review — YYYY-MM-DD

**Reviewers:** Tina, Marcus, Priya, Carlos, Zoe, Derek, Luna, Oscar
**Scope:** cachibot/, frontend/src/, desktop/

## Summary

| Severity | Count |
|----------|-------|
| Fix      | N     |
| Improve  | N     |
| Note     | N     |

## Tina — DRY

### Fix
- `path/to/file.py:42` — Description

### Improve
- `path/to/file.ts:108` — Description

### Note
- `path/to/file.py:15` — Description

## Marcus — Security

(same structure)

... (all 8 agents)

## Previous Reviews

(Link to or diff against the last review file in .reviews/ if one exists,
noting which prior findings were fixed and which are still open.)
```

## Severity Definitions

- **Fix** — Real bug, security issue, or maintenance risk. Should be fixed now.
- **Improve** — Worth doing, not urgent. Better patterns, cleaner code.
- **Note** — Awareness item. No action needed yet, but worth knowing about.
