---
name: lint-fix
description: Run all project linters (ruff check, ruff format, mypy, eslint) and auto-fix every violation. Fixes line-length, type annotations, unused vars, and formatting in one pass.
---

# Lint Fix — Full Project Lint & Type Sweep

Run every linter the project uses, collect all violations, and fix them in a single
pass. Handles Python (ruff + mypy) and TypeScript (eslint) together.

## Instructions

### Phase 0 — Run All Linters

Run **all four checks in parallel** and collect their output:

1. `ruff check cachibot/` — lint errors (E501, F841, etc.)
2. `ruff format --check cachibot/` — formatting drift
3. `mypy cachibot/` — type errors (only in `cachibot/`, NOT transitive errors
   from prompture or other installed packages)
4. `cd frontend && npx eslint src/` — TypeScript lint (errors only, warnings are informational)

Parse each tool's output into a list of `{ tool, file, line, code, message }` findings.

**Important:** When parsing mypy output, **discard** any finding whose file path is
outside `cachibot/` (e.g., errors in installed packages like `prompture`). Also
discard `import-not-found` errors for `prompture.*` and `tukuy.*` modules — those are
expected when the editable installs are out of sync and are not CachiBot bugs.

If zero findings remain after filtering, tell the user everything is clean and stop.

### Phase 1 — Auto-Fix What Tools Can

Run the auto-fixers first to knock out the easy ones:

1. `ruff check --fix cachibot/` — auto-fix simple lint issues
2. `ruff format cachibot/` — reformat any drifted files
3. `cd frontend && npx eslint src/ --fix` — auto-fix simple TS issues

### Phase 2 — Fix Remaining Violations

Re-run the linters from Phase 0 to see what remains after auto-fix.

For each remaining finding, apply the appropriate fix strategy:

#### ruff E501 (line too long)

- If the long line is a **string literal** inside a dict/list, wrap it with
  implicit string concatenation using parentheses:
  ```python
  "description": (
      "First part of the string"
      " second part of the string"
  ),
  ```
- If the long line is a **function call or dict literal**, break it into
  multi-line format.
- If the long line is an **import**, use multi-line import with parentheses.
- Never shorten user-facing strings by removing words — prefer wrapping.

#### mypy type-arg (missing generic parameters)

- `dict` → `dict[str, Any]` (or more specific types if obvious from context)
- `list` → `list[str]` (or the appropriate element type)
- `tuple` → fill in the actual element types
- Add missing imports (`from typing import Any`, etc.) as needed.

#### mypy arg-type (incompatible argument types)

- For TypedDict → Pydantic model mismatches, use `Model.model_validate(data)`
  instead of `Model(**data)`.
- For `str` passed where a `Literal[...]` is expected, change the parameter
  type annotation to use the Literal type.
- Read both the call site and the target signature before deciding the fix.

#### eslint no-unused-vars

- If the parameter is required by a callback signature but not used in the body,
  remove it entirely (JS/TS doesn't enforce arity on callbacks).
- If removing it would break the type contract, keep it as `_name` and add an
  eslint-disable comment for that line only.

#### eslint react-hooks/exhaustive-deps

- These are **warnings**, not errors. Do NOT fix them unless the user explicitly
  asked to fix warnings too. Log them in the summary as "skipped warnings."

#### Other violations

- Read the file, understand the context, and apply the minimal fix.
- If a fix would change runtime behavior, flag it in the summary rather than
  applying it silently.

### Phase 3 — Verify

Run all four linters again (same commands as Phase 0). If new violations appear
from the fixes, fix those too (max 2 retry rounds to avoid infinite loops).

### Phase 4 — Summary

Print a concise summary:

```
Lint fix complete.

  ruff check:  N fixed (was N violations)
  ruff format: N files reformatted
  mypy:        N fixed (N filtered as external)
  eslint:      N errors fixed, N warnings skipped

Files modified:
  - path/to/file.py (ruff E501, mypy type-arg)
  - path/to/other.tsx (eslint no-unused-vars)
```

## Important Rules

- **Read before edit** — always read a file before modifying it.
- **Minimal changes** — fix exactly the violation, nothing more. Don't refactor
  surrounding code, add docstrings, or "improve" things.
- **Don't fix warnings** — eslint warnings (react-hooks/exhaustive-deps,
  react-refresh/only-export-components) are informational. Only fix **errors**.
- **Filter external errors** — mypy errors in prompture, tukuy, or other
  installed packages are NOT CachiBot bugs. Discard them.
- **Don't create files** — this is a fix pass. No new files.
- **Don't run tests** — lint fixing doesn't require test execution.
- **Preserve behavior** — every fix must be semantically equivalent. If you're
  unsure a fix is safe, skip it and note it in the summary.
- **Max line length is 100** — this is the ruff config for the project.
