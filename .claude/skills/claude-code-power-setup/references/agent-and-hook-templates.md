# Subagent and Hook Templates

Ready-to-adapt templates for `.claude/agents/` and hook configurations.

## Subagents

### Code Simplifier

**File**: `.claude/agents/code-simplifier.md`

```markdown
# Code Simplifier

You review recently changed code and simplify it without changing behaviour.

## Rules
- Only modify files changed in the last commit: check `git diff --name-only HEAD~1`
- Never ADD code — only remove or simplify
- Don't add comments, docstrings, or type hints that weren't there
- Don't rename things unless the current name is actively misleading
- Run tests after every change to verify nothing breaks
- If tests fail, revert the change immediately
- Three similar lines are better than a premature abstraction

## Process
1. Get changed files: `git diff --name-only HEAD~1`
2. For each file, read it fully and identify:
   - Single-use abstractions that can be inlined
   - Over-engineered error handling for impossible cases
   - Unnecessary intermediate variables
   - Verbose patterns with simpler equivalents
   - Dead code or unused imports
3. Make one simplification at a time
4. Run tests after each: [test_command_all]
5. If tests pass, move to next simplification
6. If tests fail, `git checkout -- [file]` and skip that change
7. Report: what you simplified, what you skipped (and why)
```

### Application Verifier

**File**: `.claude/agents/verify-app.md`

```markdown
# Application Verifier

You verify that the application works correctly after changes.

## Verification Steps

### Step 1: Static Analysis
- Typecheck: [typecheck_command]
- Lint: [lint_command_all]
- If either fails, fix the issue and re-run

### Step 2: Test Suite
- Run all tests: [test_command_all]
- If tests fail:
  - Check if failure is related to recent changes (git diff HEAD~1)
  - If related: fix and re-run
  - If pre-existing: note it but don't fix

### Step 3: Build Verification
- Build the project: [build_command]
- Verify no build warnings that indicate real issues

### Step 4: Runtime Verification (if applicable)
- Start dev server: [dev_server_command]
- Verify health endpoint responds: curl localhost:[port]/health
- Verify key API endpoints respond with expected status codes
- Stop the server

## Output Format
```
VERIFICATION REPORT
==================
Static Analysis:  PASS / FAIL (details)
Test Suite:       PASS / FAIL (X passed, Y failed)
Build:            PASS / FAIL (details)
Runtime:          PASS / FAIL / SKIPPED (details)

Overall: PASS / FAIL
Issues found: [list if any]
Issues fixed: [list if any]
```
```

### Change Reviewer

**File**: `.claude/agents/review-changes.md`

```markdown
# Change Reviewer

You review code changes before they become a PR, acting as a senior reviewer.

## What to Review
Get the changes: `git diff main...HEAD` (or `git diff` if on main)

## Review Checklist

### Correctness
- [ ] Logic errors, off-by-one, null/undefined handling
- [ ] Edge cases: empty inputs, max values, concurrent access
- [ ] Error handling: are errors caught and handled appropriately?

### Security
- [ ] No secrets, API keys, or credentials in code
- [ ] Input validation at system boundaries
- [ ] No SQL injection, XSS, command injection vectors
- [ ] Authentication/authorization checks present where needed

### Performance
- [ ] No N+1 query patterns
- [ ] No unnecessary loops or redundant computations
- [ ] Appropriate use of pagination for list endpoints
- [ ] No blocking I/O in async code paths

### Consistency
- [ ] Follows project patterns (check CLAUDE.md)
- [ ] Naming conventions match existing code
- [ ] Error handling pattern matches existing modules
- [ ] Test patterns match existing test files

## Output
For each issue found:
- File + line number
- Severity: MUST FIX / SHOULD FIX / NITPICK
- Description of the issue
- Suggested fix (code snippet if applicable)

End with: Overall assessment (ready to merge / needs changes)
```

### Test Writer

**File**: `.claude/agents/test-writer.md`

```markdown
# Test Writer

You write tests for recently changed code, following the project's existing test patterns.

## Process
1. Get changed files: `git diff --name-only HEAD~1`
2. For each changed file, find its existing test file (or the nearest test file in the same module)
3. Read the existing tests to understand:
   - Testing framework and assertion style
   - Fixture/factory patterns
   - Mocking conventions
   - File naming and organisation
4. For each significant change, write tests covering:
   - Happy path (the feature works as intended)
   - Edge cases (empty, null, boundary values)
   - Error cases (invalid input, service failures)
5. Run all tests: [test_command_all]
6. Fix any failures in your new tests

## Rules
- Match the existing test style exactly — don't introduce new patterns
- One test function per behaviour, not per line of code
- Test behaviour, not implementation (don't assert internal method calls)
- Mock external dependencies (APIs, databases), not internal logic
- Use descriptive test names that explain WHAT is being tested and WHAT is expected
- Don't test framework behaviour (e.g., don't test that FastAPI returns 422 for bad types)
```

## Hook Configurations

### PostToolUse: Auto-Format on Edit

Runs your formatter every time Claude edits or writes a file.

#### Python (ruff)
```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "command": "ruff format \"$CLAUDE_FILE_PATH\" 2>/dev/null; ruff check --fix \"$CLAUDE_FILE_PATH\" 2>/dev/null || true"
      }
    ]
  }
}
```

#### TypeScript (prettier)
```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "command": "npx prettier --write \"$CLAUDE_FILE_PATH\" 2>/dev/null || true"
      }
    ]
  }
}
```

#### TypeScript (prettier + eslint)
```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "command": "npx prettier --write \"$CLAUDE_FILE_PATH\" 2>/dev/null && npx eslint --fix \"$CLAUDE_FILE_PATH\" 2>/dev/null || true"
      }
    ]
  }
}
```

#### Full-Stack (Python + TypeScript)
```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "command": "case \"$CLAUDE_FILE_PATH\" in *.py) ruff format \"$CLAUDE_FILE_PATH\" 2>/dev/null; ruff check --fix \"$CLAUDE_FILE_PATH\" 2>/dev/null || true ;; *.ts|*.tsx|*.js|*.jsx) npx prettier --write \"$CLAUDE_FILE_PATH\" 2>/dev/null || true ;; esac"
      }
    ]
  }
}
```

#### Rust (rustfmt)
```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "command": "rustfmt \"$CLAUDE_FILE_PATH\" 2>/dev/null || true"
      }
    ]
  }
}
```

#### Go (gofmt)
```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "command": "gofmt -w \"$CLAUDE_FILE_PATH\" 2>/dev/null || true"
      }
    ]
  }
}
```

### Stop Hook: Verification on Completion

Runs validation every time Claude finishes. Use judiciously — this adds time to every session end.

```json
{
  "hooks": {
    "Stop": [
      {
        "command": "[full_validation_command]"
      }
    ]
  }
}
```

**Tip**: Only enable Stop hooks during implementation sessions. For quick Q&A sessions, the overhead isn't worth it. You can toggle by using a separate settings file or enabling/disabling in `.claude/settings.json` as needed.

### PreCommit Hook: Gate Commits

Runs before any commit Claude makes.

```json
{
  "hooks": {
    "PreCommit": [
      {
        "command": "[lint_command_all] && [test_command_all]"
      }
    ]
  }
}
```

**Warning**: If your test suite is slow (>30s), this will block every commit. Consider running only the linter in PreCommit and tests in a separate verification step.

## Hook Design Principles

1. **Keep hooks fast** — they run on every matching event. Target <5s for PostToolUse, <30s for Stop
2. **Use `|| true`** to prevent hooks from blocking Claude on non-critical warnings
3. **Quote `$CLAUDE_FILE_PATH`** — file paths may contain spaces
4. **Redirect stderr** with `2>/dev/null` for formatters that are noisy on files they can't process (e.g., prettier on non-JS files)
5. **Use case statements** for full-stack projects to route by file extension
6. **Test hooks locally** before committing — a broken hook blocks all Claude sessions

## Combining Hooks with Subagents

For maximum quality, use hooks for fast automated checks and subagents for deeper analysis:

```
PostToolUse hook: Format code (fast, automatic, every edit)
Stop hook: Run linter + tests (medium, automatic, every session end)
code-simplifier agent: Simplify after feature complete (slow, manual trigger)
verify-app agent: Full verification (slow, manual trigger)
review-changes agent: Pre-PR review (medium, manual trigger)
```

This creates a quality pipeline:
1. Every edit is auto-formatted (hook)
2. Every session end is auto-validated (hook)
3. Every feature completion is simplified (agent, triggered by user)
4. Every PR is pre-reviewed (agent, triggered by user)
