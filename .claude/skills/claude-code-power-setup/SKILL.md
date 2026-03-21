---
name: claude-code-power-setup
description: >
  Methodology for setting up Claude Code as a power-user development environment on any project.
  Configures CLAUDE.md, permissions, slash commands, hooks, subagents, and MCP servers
  following Boris Cherny's 13-step setup, adapted into a project-portable playbook.
  Use when the user wants to set up Claude Code for a project, asks "how should I configure Claude Code",
  says "apply the power setup", "set up my Claude Code workflow", or wants to port this setup to a new codebase.
  Also use when auditing or improving an existing Claude Code configuration.
  Do NOT use for general coding tasks, feature implementation, or speckit workflows.
---

# Claude Code Power User Setup

A project-adaptable methodology for configuring Claude Code to maximise productivity. Skills, commands, hooks, permissions, and parallel workflow strategies — extracted from Boris Cherny's setup (Claude Code creator) and structured for reuse across any codebase.

Source: Boris Cherny, 13-step setup (X, Jan 2026)

## Core Principle

**Configure once, compound forever.** Every correction added to CLAUDE.md, every slash command for a repeated workflow, every permission pre-allowed — these compound across every session for every team member. The setup cost is hours; the payoff is months.

## When This Applies

- Setting up Claude Code on a new project from scratch
- Auditing an existing Claude Code configuration for gaps
- Porting a working setup from one project to another
- Onboarding a team member to an existing Claude Code workflow
- User asks about parallel sessions, plan mode, slash commands, hooks, or model selection

## Phase 1: Project Setup (One-Time)

### Step 1: CLAUDE.md — The Project Brain

The single highest-leverage configuration. Every session reads it. Mistakes corrected here never recur.

**Minimum viable CLAUDE.md** (start with ~30 lines, grow organically):
1. **Commands** — How to install, typecheck, test, lint, and validate
2. **Architecture** — Key directories, module boundaries, patterns
3. **Code Style** — Non-obvious conventions Claude might violate
4. **Common Mistakes** — Add here every time Claude does something wrong

**Maintenance rule**: See Claude make a mistake -> immediately add it to CLAUDE.md. This is compounding engineering.

Check into git. Whole team contributes. Review monthly to prune stale entries.

### Step 2: Permission Pre-Allowlisting

Pre-allow safe bash commands in `.claude/settings.json` so Claude doesn't prompt for every test run, lint, or git log.

- Add project-specific safe commands (test runners, linters, build tools, git read operations)
- Never add destructive commands (rm -rf, git push --force, docker system prune)
- Don't use `--dangerously-skip-permissions` — use granular allowlisting instead
- Check into git so the team shares permissions

> See `references/project-config-templates.md` for settings.json templates by stack.

### Step 3: Slash Commands for Repeated Workflows

Custom commands in `.claude/commands/` that automate inner-loop workflows.

**Identify your top 3-5 repeated workflows** and create a command for each:
- `/commit-push-pr` — Commit, push, create PR (most common — build this first)
- `/simplify` — Review and simplify recent changes
- `/verify` — Run full validation suite
- `/fix-ci` — Diagnose and fix CI failures
- `/test-this` — Write tests for recent changes

**Key technique**: Use `$(command)` inline bash in command files to pre-compute context (git status, branch, changed files) so the model doesn't waste turns discovering it.

Check into git. Team shares commands.

> See `references/slash-command-templates.md` for ready-to-adapt command files.

### Step 4: Hooks for Automated Quality

Shell commands that run automatically on Claude Code events. Handles the last 10% of formatting/linting without manual intervention.

**Essential hook**: PostToolUse formatter — runs your formatter on every file Claude edits.
- Python: `ruff format $CLAUDE_FILE_PATH && ruff check --fix $CLAUDE_FILE_PATH`
- TypeScript: `npx prettier --write $CLAUDE_FILE_PATH`
- Full-stack: case statement routing by file extension

**Optional hook**: Stop verification — runs validation when Claude thinks it's done. If it fails, Claude sees the failure and keeps working.

Keep hooks fast. If your linter is slow, only format in the hook and lint via slash command.

> See `references/agent-and-hook-templates.md` for hook configurations by stack.

### Step 5: Subagents for Complex Workflows

Specialised agents in `.claude/agents/` for multi-step tasks that benefit from their own context window.

**Think**: "What do I do for almost every PR?" — that's an agent.

Common subagents:
- **code-simplifier** — Reviews and simplifies code after Claude finishes working
- **verify-app** — Detailed end-to-end verification with project-specific steps
- **review-changes** — Pre-review changes before creating a PR

Agents run in parallel, get their own context, and don't pollute your main session.

> See `references/agent-and-hook-templates.md` for subagent templates.

### Step 6: MCP Servers for External Tools

Connect Claude to external services via `.mcp.json` — Slack, databases, monitoring.

Only add MCPs for tools the team uses daily. Use `env:` prefix for tokens (never hardcode). Check `.mcp.json` into git.

Common useful MCPs: Slack (team context), PostgreSQL (query data), Sentry (error investigation).

> See `references/project-config-templates.md` for .mcp.json templates.

## Phase 2: Daily Workflow

### Step 7: Parallel Sessions — The Multiplier

Run 3-5+ Claude sessions simultaneously across terminal tabs and/or claude.ai/code.

**Terminal setup**:
- Number your tabs (1-5)
- Enable system notifications (iTerm2: Preferences > Profiles > Terminal > Notifications)
- Each tab works on an independent task

**Session strategy**:
- Tab 1: Main feature work (plan mode -> auto-accept)
- Tab 2: Bug fix or secondary task
- Tab 3: Tests / verification
- Tab 4: Documentation or refactoring
- Tab 5: Research / exploration

**Web sessions**: Use claude.ai/code for tasks that don't need local files. Hand off with `&`, teleport with `--teleport`. Start sessions from phone (Claude iOS app) for async tasks.

Don't run parallel sessions that modify the same files — they'll conflict.

### Step 8: Plan Mode First

Start most sessions in Plan mode (shift+tab twice). Iterate on the plan until it's right. Then switch to auto-accept (shift+tab) and Claude usually one-shots the implementation.

**A good plan is the single biggest predictor of a good result.**

- Skip plan mode for: quick fixes, slash commands, questions
- Use plan mode for: anything touching 3+ files, new features, architectural changes, anything you'd think about before coding

### Step 9: Model Selection

Default to the strongest available model (currently Opus 4.5/4.6 with thinking). Bigger models require less steering, make fewer mistakes, and handle complex multi-file changes better. The time saved not correcting mistakes compensates for slower generation.

Use fast mode (`/fast`) for simple tasks where speed matters more than reasoning.

### Step 10: Verification — The Quality Multiplier

**The single most important practice for output quality.** Without verification, Claude generates code that looks right. With verification, Claude generates code that works. 2-3x quality difference.

Always give Claude a way to check its own work:
- Backend: run the test suite
- Frontend: typecheck + tests + visual check
- Full-stack: all of the above

**Invest in making your test suite fast and reliable** — this directly improves Claude's output quality.

### Step 11: Long-Running Tasks

For 10+ minute tasks, set up autonomous execution with verification.

**Option A** — Prompt-based: "When done, verify by running [test command]. If it fails, fix and re-verify."

**Option B** — Stop hook (deterministic): Add a Stop hook in settings.json that runs validation automatically when Claude finishes.

**Option C** — Background dontAsk: `claude --permission-mode=dontAsk` in a sandbox. Claude runs without prompts. Only for isolated/sandboxed environments.

## Phase 3: Team Practices

### Step 12: CLAUDE.md as Living Documentation

Whole team contributes to CLAUDE.md, multiple times a week. Every team member catches different Claude mistakes. Sharing corrections means everyone benefits.

**Process**: Claude does something wrong -> fix it -> add a note to CLAUDE.md -> commit.

**During code review**: Tag `@.claude` on PRs (via GitHub Action) to update CLAUDE.md as part of the PR.

### Step 13: Shared Configuration

Check all Claude Code configuration into git:

```
.claude/
  settings.json      # Permissions, hooks
  commands/           # Slash commands
  agents/             # Subagents
.mcp.json             # MCP server configuration
CLAUDE.md             # Project instructions
```

Everyone gets the same commands, permissions, hooks, and MCP servers. Personal preferences go in `~/.claude/settings.json`.

## Quick Start Checklist

When adapting to a new project, do these in order:

```
[ ] 1. Create CLAUDE.md (commands, architecture, code style, common mistakes)
[ ] 2. Configure .claude/settings.json (safe command allowlist)
[ ] 3. Create .claude/commands/commit-push-pr.md
[ ] 4. Add PostToolUse hook for your formatter
[ ] 5. Create .claude/commands/verify.md (test/lint commands)
[ ] 6. Enable terminal notifications for multi-tab workflow
[ ] 7. Start sessions in Plan mode for anything non-trivial
[ ] 8. After week 1: create 2-3 more slash commands for repeated workflows
[ ] 9. After month 1: review CLAUDE.md, consolidate stale entries
[ ] 10. Share entire .claude/ config with team via git
```

## Adaptation Template

Fill in these values when porting to a new project. All reference templates use these as variables.

```yaml
project_name: ""
package_manager: ""              # npm / bun / uv / pip / cargo
typecheck_command: ""             # tsc --noEmit / mypy . / bun run typecheck
test_command_single: ""           # pytest -k "name" / bun run test -- -t "name"
test_command_file: ""             # pytest path/ / bun run test:file -- "glob"
test_command_all: ""              # pytest / bun run test
lint_command_file: ""             # ruff check file / eslint --fix file
lint_command_all: ""              # ruff check . / bun run lint
format_command: ""                # ruff format / prettier --write
full_validation: ""               # ruff check . && pytest / bun run lint && bun run test
dev_server_command: ""            # uvicorn app.main:app --reload / npm run dev
key_directories:
  - ""
common_mistakes:
  - ""
mcp_servers_needed:
  - ""
```

## Reference Files

- `references/project-config-templates.md` — Settings.json (permissions, hooks), .mcp.json, and .gitignore templates by tech stack
- `references/slash-command-templates.md` — Ready-to-adapt command files for common workflows (commit-push-pr, simplify, verify, fix-ci, test-this)
- `references/agent-and-hook-templates.md` — Subagent definitions and hook configurations with per-stack examples

## Source Mapping: Boris's 13 Steps

| # | Boris's Step | Playbook Section | When |
|---|-------------|-----------------|------|
| 1 | 5 parallel terminal Claudes | Step 7 | Day 1 |
| 2 | 5-10 web Claudes + mobile | Step 7 | Week 1 |
| 3 | Opus with thinking | Step 9 | Day 1 |
| 4 | Shared CLAUDE.md | Steps 1 + 12 | Day 1 |
| 5 | @.claude on PRs | Step 12 | Month 1 |
| 6 | Plan mode first | Step 8 | Day 1 |
| 7 | Slash commands | Step 3 | Week 1 |
| 8 | Subagents | Step 5 | Week 2 |
| 9 | PostToolUse formatting hook | Step 4 | Week 1 |
| 10 | Permission pre-allowlisting | Step 2 | Day 1 |
| 11 | MCP servers (Slack, etc.) | Step 6 | Week 2 |
| 12 | Long-running task strategies | Step 11 | Week 2 |
| 13 | Verification feedback loop | Step 10 | Day 1 |
