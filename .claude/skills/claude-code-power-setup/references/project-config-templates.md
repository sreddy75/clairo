# Project Configuration Templates

Ready-to-adapt templates for `.claude/settings.json` and `.mcp.json`. Replace `[bracketed]` values with your project's adaptation template values.

## .claude/settings.json

### Python Project (FastAPI / Django)

```json
{
  "permissions": {
    "allow": [
      "Bash(uv run pytest*)",
      "Bash(uv run ruff*)",
      "Bash(uv run mypy*)",
      "Bash(uv run alembic*)",
      "Bash(uv sync*)",
      "Bash(python -m pytest*)",
      "Bash(git status*)",
      "Bash(git log*)",
      "Bash(git diff*)",
      "Bash(git branch*)",
      "Bash(gh pr *)",
      "Bash(gh issue *)",
      "Bash(docker compose*)"
    ],
    "deny": []
  },
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "command": "ruff format $CLAUDE_FILE_PATH 2>/dev/null; ruff check --fix $CLAUDE_FILE_PATH 2>/dev/null || true"
      }
    ]
  }
}
```

### TypeScript Project (Next.js / Node)

```json
{
  "permissions": {
    "allow": [
      "Bash(npm run *)",
      "Bash(npx *)",
      "Bash(bun run *)",
      "Bash(node *)",
      "Bash(tsc *)",
      "Bash(git status*)",
      "Bash(git log*)",
      "Bash(git diff*)",
      "Bash(git branch*)",
      "Bash(gh pr *)",
      "Bash(gh issue *)"
    ],
    "deny": []
  },
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "command": "npx prettier --write $CLAUDE_FILE_PATH 2>/dev/null || true"
      }
    ]
  }
}
```

### Full-Stack (Python Backend + TypeScript Frontend)

```json
{
  "permissions": {
    "allow": [
      "Bash(uv run *)",
      "Bash(npm run *)",
      "Bash(npx *)",
      "Bash(pytest*)",
      "Bash(ruff *)",
      "Bash(alembic *)",
      "Bash(git status*)",
      "Bash(git log*)",
      "Bash(git diff*)",
      "Bash(git branch*)",
      "Bash(gh pr *)",
      "Bash(gh issue *)",
      "Bash(docker compose*)",
      "Bash(celery *)"
    ],
    "deny": []
  },
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

### Rust Project

```json
{
  "permissions": {
    "allow": [
      "Bash(cargo build*)",
      "Bash(cargo test*)",
      "Bash(cargo check*)",
      "Bash(cargo clippy*)",
      "Bash(cargo fmt*)",
      "Bash(cargo run*)",
      "Bash(git status*)",
      "Bash(git log*)",
      "Bash(git diff*)",
      "Bash(git branch*)",
      "Bash(gh pr *)",
      "Bash(gh issue *)"
    ],
    "deny": []
  },
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "command": "rustfmt $CLAUDE_FILE_PATH 2>/dev/null || true"
      }
    ]
  }
}
```

### Go Project

```json
{
  "permissions": {
    "allow": [
      "Bash(go build*)",
      "Bash(go test*)",
      "Bash(go vet*)",
      "Bash(go run*)",
      "Bash(golangci-lint*)",
      "Bash(git status*)",
      "Bash(git log*)",
      "Bash(git diff*)",
      "Bash(git branch*)",
      "Bash(gh pr *)",
      "Bash(gh issue *)"
    ],
    "deny": []
  },
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "command": "gofmt -w $CLAUDE_FILE_PATH 2>/dev/null || true"
      }
    ]
  }
}
```

## Permission Design Principles

1. **Allowlist safe read/build/test commands** — things you'd type yourself without thinking
2. **Never allowlist destructive commands** — `rm`, `git push --force`, `docker system prune`, `DROP TABLE`
3. **Use glob patterns** — `Bash(pytest*)` covers `pytest`, `pytest -k "name"`, `pytest path/`
4. **Include git read operations** — status, log, diff, branch are always safe
5. **Include gh CLI** — PR and issue operations are common and safe
6. **Team shares via git** — everyone gets the same allowlist

## Stop Hook (Verification on Completion)

Add this to automatically verify Claude's work when it finishes:

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

Examples:
```json
// Python
"command": "cd backend && uv run ruff check . && uv run pytest --tb=short -q"

// TypeScript
"command": "npm run typecheck && npm run lint && npm run test"

// Full-stack
"command": "cd backend && uv run ruff check . && uv run pytest -q && cd ../frontend && npm run lint && npm run test"
```

**Warning**: Stop hooks run every time Claude finishes, including for simple questions. Keep them fast (<30s) or only enable them for implementation sessions.

## .mcp.json Templates

### Slack Integration

```json
{
  "mcpServers": {
    "slack": {
      "command": "npx",
      "args": ["-y", "@anthropic/mcp-slack"],
      "env": {
        "SLACK_BOT_TOKEN": "env:SLACK_BOT_TOKEN",
        "SLACK_TEAM_ID": "env:SLACK_TEAM_ID"
      }
    }
  }
}
```

### PostgreSQL Integration

```json
{
  "mcpServers": {
    "postgres": {
      "command": "npx",
      "args": ["-y", "@anthropic/mcp-postgres", "env:DATABASE_URL"]
    }
  }
}
```

### Sentry Integration

```json
{
  "mcpServers": {
    "sentry": {
      "command": "npx",
      "args": ["-y", "@anthropic/mcp-sentry"],
      "env": {
        "SENTRY_AUTH_TOKEN": "env:SENTRY_AUTH_TOKEN",
        "SENTRY_ORG": "env:SENTRY_ORG"
      }
    }
  }
}
```

### Combined (Full-Stack with Slack + DB + Monitoring)

```json
{
  "mcpServers": {
    "slack": {
      "command": "npx",
      "args": ["-y", "@anthropic/mcp-slack"],
      "env": {
        "SLACK_BOT_TOKEN": "env:SLACK_BOT_TOKEN",
        "SLACK_TEAM_ID": "env:SLACK_TEAM_ID"
      }
    },
    "postgres": {
      "command": "npx",
      "args": ["-y", "@anthropic/mcp-postgres", "env:DATABASE_URL"]
    },
    "sentry": {
      "command": "npx",
      "args": ["-y", "@anthropic/mcp-sentry"],
      "env": {
        "SENTRY_AUTH_TOKEN": "env:SENTRY_AUTH_TOKEN",
        "SENTRY_ORG": "env:SENTRY_ORG"
      }
    }
  }
}
```

### MCP Design Principles

1. **Use `env:` prefix** for all secrets — tokens never go in the config file
2. **Check .mcp.json into git** — team shares the server configuration
3. **Each person sets their own env vars** — in shell profile or .env.local
4. **Only add MCPs you use daily** — each server adds startup overhead
5. **Test MCPs work before sharing** — broken MCPs produce confusing errors

## .gitignore Additions

Add these to your `.gitignore` to keep user-specific settings out of git:

```gitignore
# Claude Code user-specific
.claude/settings.local.json
```
