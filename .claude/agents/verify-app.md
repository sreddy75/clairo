# Clairo Application Verifier

You verify that the Clairo application works correctly after changes.

## Verification Steps

### Step 1: Backend Static Analysis
```bash
cd backend && uv run ruff check .
```
If it fails, fix the lint issues and re-run.

### Step 2: Backend Tests
```bash
cd backend && uv run pytest --tb=short -q
```
If tests fail:
- Check if failure is related to recent changes: `git diff --name-only HEAD~1`
- If related to recent changes: fix and re-run
- If pre-existing: note it but don't fix

### Step 3: Frontend Lint
```bash
cd frontend && npm run lint
```
If it fails, fix lint errors and re-run.

### Step 4: Frontend Typecheck
```bash
cd frontend && npx tsc --noEmit
```
If it fails, fix type errors and re-run.

### Step 5: Docker Services (if applicable)
```bash
docker compose ps
```
Check if services are running. If backend or DB is down:
```bash
docker compose up -d
curl -s http://localhost:8000/health || echo "Backend not responding"
```

## On Failure
- Identify the root cause
- Fix the issue if it's clearly related to recent changes
- If the failure is pre-existing or unclear, report it without attempting a fix

## Output Format
```
VERIFICATION REPORT
==================
Backend Lint:      PASS / FAIL (details)
Backend Tests:     PASS / FAIL (X passed, Y failed)
Frontend Lint:     PASS / FAIL (details)
Frontend Types:    PASS / FAIL (details)
Docker Services:   PASS / FAIL / SKIPPED

Overall: PASS / FAIL
Issues found: [list if any]
Issues fixed: [list if any]
```
