# Slash Command Templates

Ready-to-adapt command files for `.claude/commands/`. Each file becomes a `/command-name` slash command.

## How Commands Work

- Files live in `.claude/commands/` as markdown
- Filename becomes the command: `commit-push-pr.md` -> `/commit-push-pr`
- `$ARGUMENTS` is replaced with whatever the user types after the command
- `$(command)` runs inline bash to pre-compute context (avoids model turns)
- Check into git so the team shares them

## Command: commit-push-pr

**File**: `.claude/commands/commit-push-pr.md`

The most-used command. Boris uses it dozens of times per day.

```markdown
Commit all current changes, push to remote, and create a pull request.

Context (pre-computed):
- Current branch: $(git branch --show-current)
- Git status: $(git status --short)
- Staged changes: $(git diff --cached --stat)
- Unstaged changes: $(git diff --stat)
- Recent commits on this branch: $(git log --oneline -10)
- Base branch: $(git rev-parse --abbrev-ref HEAD@{upstream} 2>/dev/null || echo "main")

Steps:
1. Review all staged and unstaged changes to understand what was done
2. Stage all relevant changes (be specific — don't use `git add -A` blindly, exclude .env or sensitive files)
3. Write a commit message:
   - First line: concise summary of WHY (not what), under 72 chars
   - Body: brief explanation if the change isn't obvious
   - End with: Co-Authored-By: Claude <noreply@anthropic.com>
4. Push to origin (create remote branch with -u if needed)
5. Create a PR with `gh pr create`:
   - Title: short, under 70 chars
   - Body: ## Summary (2-3 bullets) + ## Test plan (checklist)
6. Return the PR URL

If $ARGUMENTS is provided, use it as additional context for the commit message.
```

## Command: simplify

**File**: `.claude/commands/simplify.md`

Run after Claude finishes a task to clean up the result.

```markdown
Review the code I just changed and simplify it without changing behaviour.

Context:
- Changed files: $(git diff --name-only HEAD~1 2>/dev/null || git diff --name-only)
- Diff summary: $(git diff --stat HEAD~1 2>/dev/null || git diff --stat)

For each changed file:
1. Read the full file to understand context
2. Look for:
   - Unnecessary abstractions (helpers/utils used only once)
   - Over-engineering (error handling for impossible cases, premature config)
   - Dead code or unused imports
   - Overly verbose patterns that can be simplified
   - Duplicated logic that could be a simple shared line (but don't over-abstract)
3. Simplify what you find
4. Run tests after each change to verify nothing broke: [test_command_all]

Rules:
- Only modify files in the changed file list
- Never ADD code — only remove or simplify
- Don't add comments, docstrings, or type annotations that weren't there
- Don't rename variables unless the current name is actively misleading
- If tests fail after a change, revert it
- Three similar lines are better than a premature abstraction
```

## Command: verify

**File**: `.claude/commands/verify.md`

Run the full validation suite and fix any issues.

```markdown
Verify the application works correctly after recent changes.

Context:
- Changed files: $(git diff --name-only HEAD~1 2>/dev/null || git diff --name-only)

Steps:
1. Run typecheck: [typecheck_command]
   - If it fails, fix the type errors and re-run
2. Run linter: [lint_command_all]
   - If it fails, fix lint errors and re-run
3. Run test suite: [test_command_all]
   - If tests fail, analyse the failure
   - If related to recent changes, fix and re-run
   - If pre-existing failure, report it but don't attempt to fix
4. Report final status:
   - PASS: All checks green
   - FAIL: Which checks failed and why (with details)

If $ARGUMENTS is provided, only verify the specified area (e.g., "backend", "frontend", "module-name").
```

## Command: fix-ci

**File**: `.claude/commands/fix-ci.md`

Diagnose and fix CI failures.

```markdown
The CI pipeline is failing. Diagnose the issue and fix it.

Context:
- Current branch: $(git branch --show-current)
- Recent commits: $(git log --oneline -5)
- Changed files vs base: $(git diff --name-only main...HEAD 2>/dev/null || git diff --name-only main)

Steps:
1. Check CI status: `gh pr checks` or `gh run list --limit 3`
2. Get failure logs: `gh run view --log-failed` (for the latest failed run)
3. Analyse the failure:
   - Is it a test failure? Read the test and the code it tests
   - Is it a lint/format error? Run the linter locally
   - Is it a type error? Run the typecheck locally
   - Is it a build error? Check dependencies and imports
4. Fix the root cause (not the symptom)
5. Verify locally: [full_validation]
6. Commit the fix with a clear message referencing what CI check was failing

If $ARGUMENTS is provided, it contains the PR number or run ID to check.
```

## Command: test-this

**File**: `.claude/commands/test-this.md`

Write tests for recent changes.

```markdown
Write tests for the code I just changed.

Context:
- Changed files: $(git diff --name-only HEAD~1 2>/dev/null || git diff --name-only)
- Diff: $(git diff HEAD~1 2>/dev/null || git diff)

Steps:
1. Read each changed file and understand what was added/modified
2. For each significant change, write tests that verify:
   - Happy path: the feature works as intended
   - Edge cases: empty input, null values, boundary conditions
   - Error cases: invalid input, missing dependencies, failure modes
3. Follow existing test patterns in the project:
   - Find a nearby test file for the same module
   - Match the testing framework, assertion style, and fixture patterns
4. Run the tests to verify they pass: [test_command_all]
5. If a test fails, fix either the test or the code (determine which is wrong)

Rules:
- Put tests next to existing tests for the same module
- Follow the project's test naming conventions
- Don't over-test — focus on behaviour, not implementation details
- Mock external dependencies (APIs, databases) but not internal logic
```

## Command: review

**File**: `.claude/commands/review.md`

Review changes before creating a PR.

```markdown
Review the current changes as if you were a senior code reviewer.

Context:
- Current branch: $(git branch --show-current)
- Changed files: $(git diff --name-only main...HEAD 2>/dev/null || git diff --name-only)
- Full diff: $(git diff main...HEAD --stat 2>/dev/null || git diff --stat)

Review for:
1. **Correctness**: Does the code do what it's supposed to? Any logic errors?
2. **Security**: SQL injection, XSS, command injection, secrets in code, OWASP top 10
3. **Performance**: N+1 queries, unnecessary loops, missing indexes, large payloads
4. **Maintainability**: Clear naming, reasonable complexity, no magic numbers
5. **Testing**: Are the changes tested? Any obvious untested paths?
6. **Consistency**: Does it follow the project's patterns and CLAUDE.md conventions?

Output format:
- MUST FIX: Issues that should be fixed before merging (with specific suggestions)
- SHOULD FIX: Improvements that aren't blocking but would improve quality
- NITPICK: Minor style preferences (only mention if truly worth changing)
- LOOKS GOOD: Things that are well done (brief acknowledgement)

If $ARGUMENTS is provided, it's the PR number to review: `gh pr diff $ARGUMENTS`
```

## Command: meeting-prep

**File**: `.claude/commands/meeting-prep.md`

Project-specific. Example for a client-facing platform.

```markdown
Generate a meeting preparation briefing.

Context:
$ARGUMENTS

Steps:
1. Gather all relevant data about the subject from the codebase and any available data sources
2. Summarise the current state: what's working, what's pending, what's blocked
3. Identify 2-3 discussion points or decisions needed
4. Note any risks or timeline concerns
5. Format as a concise briefing (max 1 page)

Output format:
## Meeting Briefing: [Subject]
### Current Status
[2-3 bullet points]
### Discussion Points
[2-3 numbered items with context]
### Risks / Blockers
[If any]
### Suggested Next Steps
[2-3 actionable items]
```

## Design Principles for Commands

1. **Pre-compute context** with `$(command)` — don't make the model run git commands to discover info you can provide upfront
2. **Be specific about steps** — numbered steps with concrete actions
3. **Include the verification step** — commands should check their own work
4. **Handle $ARGUMENTS** — let users pass extra context
5. **Reference project commands** — use `[test_command_all]` placeholders so each project adapts the command to their stack
6. **One job per command** — don't combine commit + test + deploy. Keep them composable
