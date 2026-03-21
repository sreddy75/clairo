Review the current changes as if you were a senior code reviewer.

Context:
- Current branch: $(git branch --show-current)
- Changed files: $(git diff --name-only main...HEAD 2>/dev/null || git diff --name-only)
- Full diff: $(git diff main...HEAD --stat 2>/dev/null || git diff --stat)

Review for:
1. **Correctness**: Logic errors, off-by-one, null/None handling, async/await mistakes
2. **Security**: SQL injection, XSS, secrets in code, missing tenant_id in queries, OWASP top 10
3. **Performance**: N+1 queries, unnecessary loops, missing pagination, blocking I/O in async paths
4. **Clairo patterns**: Repository pattern used, domain exceptions (not HTTPException in services), Pydantic schemas for validation, tenant isolation
5. **Testing**: Are the changes tested? Any obvious untested paths?
6. **Consistency**: Does it follow CLAUDE.md conventions and existing module patterns?

Output format:
- **MUST FIX**: Issues that should be fixed before merging (with specific suggestions)
- **SHOULD FIX**: Improvements that aren't blocking but would improve quality
- **NITPICK**: Minor style preferences (only mention if truly worth changing)
- **LOOKS GOOD**: Things that are well done (brief acknowledgement)

If $ARGUMENTS is provided, it's the PR number to review: `gh pr diff $ARGUMENTS`
