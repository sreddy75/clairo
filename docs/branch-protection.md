# Branch Protection Rules

This document describes the recommended branch protection settings for the Clairo repository.

## Protected Branches

### `main` Branch (Production)

**Settings**:

| Setting | Value | Description |
|---------|-------|-------------|
| Require pull request reviews | Yes | At least 1 approval required |
| Dismiss stale reviews | Yes | New commits invalidate approvals |
| Require status checks | Yes | CI must pass before merge |
| Require branches up to date | Yes | Branch must be current with main |
| Include administrators | Yes | Rules apply to everyone |
| Restrict force pushes | Yes | Prevent history rewriting |
| Restrict deletions | Yes | Prevent accidental deletion |

**Required Status Checks**:
- `CI Success` - Aggregate check for all CI jobs
- `backend-test` - Backend pytest suite
- `backend-lint` - Ruff and MyPy checks
- `frontend-lint` - ESLint checks
- `frontend-build` - Next.js build verification

### `develop` Branch (Staging)

**Settings**:

| Setting | Value | Description |
|---------|-------|-------------|
| Require pull request reviews | Optional | Recommended for larger teams |
| Require status checks | Yes | CI must pass |
| Require branches up to date | No | Allow parallel development |

**Required Status Checks**:
- `CI Success` - Aggregate check for all CI jobs

## How to Configure

### Via GitHub Web UI

1. Go to **Settings** > **Branches**
2. Click **Add branch protection rule**
3. Enter branch name pattern: `main`
4. Enable the settings listed above
5. Click **Create**

### Via GitHub CLI

```bash
# Configure main branch protection
gh api repos/{owner}/{repo}/branches/main/protection \
  -X PUT \
  -H "Accept: application/vnd.github+json" \
  -f required_status_checks='{"strict":true,"contexts":["CI Success"]}' \
  -f enforce_admins=true \
  -f required_pull_request_reviews='{"dismiss_stale_reviews":true,"require_code_owner_reviews":false,"required_approving_review_count":1}' \
  -f restrictions=null \
  -f allow_force_pushes=false \
  -f allow_deletions=false
```

## Workflow Integration

The CI workflow (`ci.yml`) creates a `ci-success` job that aggregates all check results. This single job can be used in branch protection rules instead of listing each individual check.

```yaml
# In branch protection, only this check is required:
required_status_checks:
  contexts:
    - "CI Success"
```

This approach allows adding or modifying CI jobs without updating branch protection rules.

## Bypassing Protection (Emergency)

In rare emergencies, repository administrators can bypass protection:

1. Go to the protected branch settings
2. Temporarily disable "Include administrators"
3. Make the emergency fix
4. Re-enable "Include administrators"
5. Document the bypass in the PR/issue

**Warning**: Only use for genuine emergencies. All bypasses should be documented.
