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
2. Stage all relevant changes — be specific with `git add`, don't use `-A` or `.` blindly. Exclude .env files and secrets.
3. Write a commit message:
   - First line: concise summary of WHY (not what), under 72 chars, imperative mood
   - Body: brief explanation if the change isn't obvious
4. Push to origin (create remote branch with -u if needed)
5. Create a PR with `gh pr create`:
   - Title: short, under 70 chars
   - Body: ## Summary (2-3 bullets) + ## Test plan (checklist)
6. Return the PR URL

If $ARGUMENTS is provided, use it as additional context for the commit/PR message.
