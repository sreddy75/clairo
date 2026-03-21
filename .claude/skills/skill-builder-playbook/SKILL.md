---
name: skill-builder-playbook
description: >
  Methodology for designing and building project-specific Claude Code skills.
  Analyzes a codebase's development workflow, identifies where skills add value,
  and produces skills that enhance existing processes rather than requiring manual triggers.
  Use when the user wants to create skills for a project, asks "what skills should I build",
  or says "build skills for this codebase". Also use when porting this methodology to a new project.
  Do NOT use for general coding tasks unrelated to skill creation.
---

# Project-Specific Skill Builder Playbook

A structured methodology for designing Claude Code skills that enhance an existing development workflow. Skills built this way integrate with how you already work — they don't create new workflows you have to remember.

## The Core Principle

**Don't build skills as manual triggers. Build them as knowledge layers that make your existing workflow smarter.**

Most skill guides assume users will type trigger phrases like "create an email campaign" or "analyze support tickets." In practice, developers work through higher-level workflows (spec systems, CI/CD, feature branches) and rarely type skill-specific commands. Skills must plug into the workflow that already exists.

## Phase 1: Discover the Development Workflow

Before designing any skills, understand how features actually get built in this project.

### Step 1.1: Map the Feature Development Pipeline

Answer these questions by reading project docs (CLAUDE.md, README, command definitions, CI configs):

```
1. How does a feature go from idea to code?
   - Is there a spec/design phase? What artifacts does it produce?
   - Is there a task generation phase? How are tasks structured?
   - How does implementation happen? Manual coding? Guided by tasks?

2. What automation already exists?
   - Custom commands (slash commands, scripts)
   - CI/CD pipelines
   - Code generators, scaffolding tools
   - Linters, formatters, build checks

3. Where are the decision points?
   - What triggers research into the existing codebase?
   - Where does domain knowledge get injected?
   - What gates exist before proceeding (reviews, checklists, builds)?

4. What gets repeated every feature?
   - Same files touched (interfaces, DI registration, configs)
   - Same patterns followed (API endpoint → service → repository)
   - Same gotchas hit (framework quirks, legacy traps, platform issues)
```

### Step 1.2: Identify the Workflow Phases

Map the phases where Claude participates. For each phase, note:
- **Input**: What does Claude read/receive?
- **Output**: What does Claude produce?
- **Knowledge needed**: What does Claude have to discover or know?
- **Time spent**: How much of Claude's effort goes to research vs. execution?

Example phase map:
```
Phase: Specification
  Input: User's feature description
  Output: Structured spec document
  Knowledge: Domain model, edge case patterns, quality standards
  Time: 40% research (what entities exist, what patterns apply), 60% writing

Phase: Implementation Planning
  Input: Spec document
  Output: Architecture plan, file list, data model
  Knowledge: Codebase patterns, architectural rules, existing implementations
  Time: 60% research (reading existing code to find patterns), 40% planning

Phase: Task Execution
  Input: Task list with file paths
  Output: Working code
  Knowledge: Code templates, framework patterns, integration choreography
  Time: 30% research (reading referenced patterns), 70% coding

Phase: Verification
  Input: Completed implementation
  Output: Verification report
  Knowledge: Build commands, container setup, health checks, test scenarios
  Time: 50% figuring out how to verify, 50% actually verifying
```

### Step 1.3: Find the Knowledge Bottlenecks

For each phase, ask: **"What does Claude re-discover every time?"**

Signs of a knowledge bottleneck:
- Claude reads the same source files across multiple features
- The same "gotcha" appears in project docs as a learned rule
- Research agents are dispatched to find the same patterns
- Tasks reference the same file:line patterns for "follow this existing implementation"

These bottlenecks are your skill candidates.

## Phase 2: Design the Skill Set

### Step 2.1: Categorize Candidates

Map each bottleneck to a skill category:

| Category | What It Provides | When It Triggers | Example |
|----------|-----------------|------------------|---------|
| **Recipe** | Step-by-step integration patterns with code templates | During planning and implementation of features that use the pattern | "ezy-ai-recipe": 3-tier AI integration choreography |
| **Domain Knowledge** | Entity models, business rules, edge case libraries | During specification and clarification | "speckit-enhance": legal domain model + recurring edge cases |
| **Verification** | Post-implementation checklists, build/test/deploy commands | After implementation completes | "speckit-verify": compilation + Docker + health checks |
| **Constitution Guard** | Architectural rules with pass/fail examples | During planning and implementation | Correct implementations for each coding rule |

### Step 2.2: Prioritize by Research-Time Savings

Rank candidates by: **How much research time does Claude spend re-discovering this knowledge per feature?**

High priority:
- Pattern used in 3+ past features and will be used again
- Requires reading 5+ source files to piece together
- Has documented "gotchas" or learned rules associated with it

Medium priority:
- Fills a gap in the workflow (e.g., no verification step exists)
- Domain knowledge that reduces clarification rounds

Low priority (skip or fold into CLAUDE.md):
- Simple commands or short patterns already in CLAUDE.md
- Knowledge needed only once (single-feature patterns)
- Anything the existing automation handles well

### Step 2.3: Design Each Skill's Scope

For each skill, define:

```
Name: [kebab-case, descriptive]
Trigger: [When should Claude load this? Be specific about workflow phases and keywords]
Anti-trigger: [When should Claude NOT load this? Prevent false matches]

SKILL.md covers:
  - Overview (when this applies, which workflow phases)
  - Implementation checklist (which files to touch, in what order)
  - Critical traps (things that break if forgotten)
  - Pointers to reference files

references/ covers:
  - Detailed code patterns (actual method signatures, templates)
  - Domain knowledge (entity models, enums, terminology)
  - Checklists and troubleshooting
```

**Rule of thumb**: SKILL.md should be readable in 30 seconds and give Claude enough to start. References are pulled only when Claude needs the details.

## Phase 3: Extract Patterns from the Codebase

For each skill, dispatch research to extract the exact patterns. Don't write skills from memory — extract from actual code.

### Step 3.1: Pattern Extraction Approach

For **Recipe skills** (integration patterns):
```
1. Find 2-3 completed features that used this pattern
2. For each feature, trace the data flow across all tiers:
   - What files were created/modified?
   - What's the exact method signature at each tier?
   - How does data transform between tiers?
3. Identify the invariants (what's ALWAYS the same):
   - URL construction pattern
   - Auth mechanism
   - Error handling format
   - Serialization conventions
4. Identify the variants (what changes per feature):
   - Request/response schemas
   - Business logic
   - Model/config selection
5. Create a template that preserves invariants and parameterizes variants
```

For **Domain Knowledge skills** (specs, edge cases):
```
1. Read ALL past specs/design docs in the project
2. Extract recurring patterns across specs:
   - Common entity references
   - Repeated edge case categories
   - Quality patterns (what makes a good spec here)
3. Build a domain model reference from actual entities (not documentation)
4. Build an edge case library organized by category, not by feature
5. Extract terminology and domain-specific conventions
```

For **Verification skills** (post-implementation):
```
1. Map every build/test/deploy command in the project
2. Document which commands apply to which tiers
3. Identify the gap between "code compiles" and "feature works"
4. Create a structured verification flow that fills that gap
5. Include troubleshooting for common failures
```

### Step 3.2: What to Include vs. Exclude

**Include in skill references:**
- Exact method signatures and code templates
- File paths relative to project root
- Concrete examples from past features
- Decision trees for choosing between variants
- Troubleshooting for known failure modes

**Exclude from skill references:**
- Full source file contents (reference by path + line number instead)
- Implementation details that change frequently (use patterns not snapshots)
- Anything already well-covered by CLAUDE.md or the project constitution

## Phase 4: Build the Skills

### Step 4.1: File Structure

```
.claude/skills/
└── your-skill-name/
    ├── SKILL.md              # Required: frontmatter + overview + checklist + traps
    └── references/           # Optional: detailed knowledge files
        ├── pattern-a.md
        ├── pattern-b.md
        └── domain-ref.md
```

### Step 4.2: SKILL.md Template

```markdown
---
name: your-skill-name
description: >
  [One sentence: what this skill provides.]
  [One sentence: what workflow phases it applies to.]
  Use when [specific trigger conditions — be precise].
  Do NOT use for [anti-triggers — prevent false matches].
---

# [Skill Title]

[2-3 sentences: what this skill is and why it exists.]

## When This Applies

[Bullet list of specific scenarios where this skill adds value]

## [Core Content — varies by skill type]

For Recipe skills: Architecture overview → Implementation checklist → Critical traps
For Domain skills: Quality bar → Domain concepts → Reference pointers
For Verification skills: Step-by-step verification flow → Troubleshooting

## Reference Files

[Pointers to references/ files with one-line descriptions]
```

### Step 4.3: Description Quality

The description is the most important line — it determines whether Claude loads the skill.

**Good descriptions:**
- Name specific workflow phases: "Use during /speckit.plan when researching..."
- Name specific entities/concepts: "...features that involve cases, steps, facts, evidence..."
- Include anti-triggers: "Do NOT use for infrastructure or CI/CD tasks"

**Bad descriptions:**
- "Helps with development" (too vague, triggers on everything)
- "Database integration skill" (no workflow context, no triggers)

### Step 4.4: Reference File Guidelines

Each reference file should be:
- **Self-contained**: Readable without other files
- **Pattern-focused**: Show the template, not just one example
- **Annotated**: Include "why" alongside "what" (e.g., "camelCase because the ezy-ai Zod schemas expect it")
- **Keyed to file locations**: Always include relative paths so Claude can verify against current code

## Phase 5: Validate the Skills

### Test 1: Trigger Accuracy
Start a fresh session. Describe a feature that should trigger each skill. Verify:
- The skill loads when it should
- The skill does NOT load for unrelated features
- If it loads too broadly, tighten the anti-triggers

### Test 2: Knowledge Completeness
Run through a feature implementation with the skills loaded. Note:
- Did Claude still need to dispatch research agents for the pattern?
- Did Claude reference the skill's templates, or re-read source files?
- Were there gaps in the skill's knowledge that caused errors?

### Test 3: Workflow Integration
Use the skills through your actual development pipeline (spec → plan → implement → verify). Check:
- Skills trigger at the right phases
- Skills don't conflict with existing automation (constitution, commands)
- The combination of skills + existing workflow is faster than before

## Maintenance

Skills are code — they get stale. Update when:
- A new feature reveals a pattern variant not covered by the recipe
- An entity or enum changes (update the domain model reference)
- A "gotcha" is discovered that should be in the traps section
- The development workflow changes (new commands, new CI steps)

**Don't update skills for:**
- One-off exceptions (keep the skill focused on the common case)
- Temporary workarounds (these belong in CLAUDE.md learned rules)
