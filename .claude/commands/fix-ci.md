The CI pipeline is failing. Diagnose the issue and fix it.

Context:
- Current branch: $(git branch --show-current)
- Recent commits: $(git log --oneline -5)
- Changed files vs main: $(git diff --name-only main...HEAD 2>/dev/null || git diff --name-only main)

Steps:
1. Check CI status: `gh pr checks` or `gh run list --limit 3`
2. Get failure logs: `gh run view --log-failed` (for the latest failed run)
3. Analyse the failure:
   - Test failure? Read the test and the code it tests
   - Lint/format error? Run locally: `cd backend && uv run ruff check .` or `cd frontend && npm run lint`
   - Type error? Run locally: `cd frontend && npx tsc --noEmit`
   - Build error? Check dependencies and imports
   - Migration error? Check alembic history: `cd backend && uv run alembic history`
4. Fix the root cause (not the symptom)
5. Verify locally: `cd backend && uv run ruff check . && uv run pytest && cd ../frontend && npm run lint`
6. Commit the fix with a clear message referencing what CI check was failing

If $ARGUMENTS is provided, it contains the PR number or run ID to check.
