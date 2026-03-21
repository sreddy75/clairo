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
4. Run tests after each change to verify nothing broke:
   - Python: `cd backend && uv run pytest --tb=short -q`
   - TypeScript: `cd frontend && npm run lint && npx tsc --noEmit`

Rules:
- Only modify files in the changed file list
- Never ADD code — only remove or simplify
- Don't add comments, docstrings, or type annotations that weren't there
- Don't rename variables unless the current name is actively misleading
- If tests fail after a change, revert it
- Three similar lines are better than a premature abstraction
