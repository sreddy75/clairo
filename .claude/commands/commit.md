# Commit Changes

Commit the current changes with a well-crafted message.

Context (pre-computed):
- Current branch: $(git branch --show-current)
- Git status: $(git status --short)
- Staged diff: $(git diff --cached --stat)
- Unstaged diff: $(git diff --stat)
- Recent commits: $(git log --oneline -5)

## Process:

1. Review all staged and unstaged changes to understand what was accomplished
2. Decide whether changes should be one commit or multiple logical commits
3. Stage relevant files specifically (never use `git add -A` or `.` — exclude .env, credentials, large binaries)
4. Write a commit message:
   - First line: concise summary in imperative mood, under 72 chars, focus on WHY not WHAT
   - Body: brief explanation if the change isn't obvious
   - Commits should be authored solely by the user — no co-author lines
5. Create the commit(s)
6. Show the result with `git log --oneline -n 3`

If $ARGUMENTS is provided, use it as context for the commit message.

## Rules:
- Group related changes together
- Keep commits focused and atomic
- Do not add Co-Authored-By or Claude attribution lines
