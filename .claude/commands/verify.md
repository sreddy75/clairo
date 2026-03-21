Verify the Clairo application works correctly after recent changes.

Context:
- Changed files: $(git diff --name-only HEAD~1 2>/dev/null || git diff --name-only)

Steps:
1. Backend lint: `cd backend && uv run ruff check .`
   - If it fails, fix lint errors and re-run
2. Backend tests: `cd backend && uv run pytest --tb=short -q`
   - If tests fail, analyse the failure
   - If related to recent changes, fix and re-run
   - If pre-existing failure, report it but don't attempt to fix
3. Frontend lint: `cd frontend && npm run lint`
   - If it fails, fix lint errors and re-run
4. Frontend typecheck: `cd frontend && npx tsc --noEmit`
   - If it fails, fix type errors and re-run
5. Report final status:
   - PASS: All checks green
   - FAIL: Which checks failed and why (with details)

If $ARGUMENTS is provided, only verify the specified area ("backend", "frontend", or a specific module path).
