# Worked Example: EzyLegal Skill Design

This documents the exact process used to design and build 3 project-specific skills for the EzyLegal platform. Use it as a reference when applying the playbook to a new project.

## Step 1: Workflow Discovery

### What we found

EzyLegal uses a **speckit pipeline** — a multi-phase spec-driven workflow:

```
/speckit.specify  →  spec.md (pure requirements, no tech)
/speckit.clarify  →  updated spec.md (ambiguities resolved)
/speckit.plan     →  plan.md + research.md + data-model.md + contracts/ + quickstart.md
/speckit.tasks    →  tasks.md (ordered, numbered, with file paths)
/speckit.implement →  working code (tasks executed phase-by-phase)
```

Plus a **constitution** (605 lines, 19 architectural principles) that gates the plan phase.

### Key insight: Skills must enhance speckit, not bypass it

Initial skill ideas were manual triggers ("add AI feature", "create endpoint"). The user pointed out they never type those — they run `/speckit.specify AI-powered document analysis` and the pipeline handles the rest.

**This changed the entire design.** Skills needed to:
- Provide knowledge the plan phase's research would otherwise re-discover
- Encode patterns that tasks.md references by file:line
- Fill gaps in the pipeline (no verification step existed)

## Step 2: Knowledge Bottleneck Analysis

### Bottleneck 1: ezy-ai Integration (highest impact)

**Evidence**: Features 003, 004, and 008 all used the same 3-tier choreography:
- .NET uploads to S3 → generates presigned URL → POSTs to ezy-ai
- ezy-ai validates with Zod → calls ClaudeService → returns structured JSON
- Angular triggers via HTTP → receives response

**Research cost**: The plan phase dispatched codebase-analyzer to read `EzyAiFeedbackService.cs` (1,119 lines), `summarize.ts`, `extract-facts.ts`, `types/api.ts`, `claude.ts`, and `server.ts` every time. ~6 files, ~3,000 lines of reading per feature.

**Gotcha cost**: The dual IAIFeedbackService implementation trap broke builds on multiple features. Tasks.md had to explicitly include "add stub to AIFeedbackService" every time.

→ **Skill: ezy-ai-recipe** (Recipe category)

### Bottleneck 2: Post-Implementation Verification (gap in pipeline)

**Evidence**: speckit.implement marks tasks `[X]` but doesn't verify the feature works. The completion validation step was aspirational prose. Docker containers need different rebuild commands per tier. Health endpoints exist but nobody checks them.

**Gap cost**: Features shipped with compilation errors caught late, containers not rebuilt, quickstart.md verification scenarios never executed.

→ **Skill: speckit-verify** (Verification category)

### Bottleneck 3: Domain Knowledge for Spec Writing (medium impact)

**Evidence**: The specify phase extracts "key concepts" from the user description. Without domain knowledge, it generates generic edge cases and misses entity relationships. The clarify phase asks questions that could be pre-answered with domain context.

**Research cost**: Moderate. The spec template is good, but every spec independently discovers the same edge case categories (empty state, service failure, scale, race conditions).

→ **Skill: speckit-enhance** (Domain Knowledge category)

### What we skipped

- `dotnet-service-scaffold` — tasks.md already provides exact file paths and patterns
- `angular-component-patterns` — constitution covers OnPush rules, tasks reference specific patterns
- `docker-dev` — too simple for a skill, folded into speckit-verify
- `ef-migration` — tasks.md handles with exact commands
- `deploy-pipeline` — operational, not part of feature development

## Step 3: Pattern Extraction

### For ezy-ai-recipe

Dispatched two parallel codebase-analyzer agents:

**Agent 1**: "Extract the complete ezy-ai integration pattern across features 003, 004, 008"
- Traced the data flow from Angular → .NET → ezy-ai → Claude
- Extracted exact method signatures: `PostToEzyAiAsync`, `SummarizeDocumentAsync`, etc.
- Identified two variants: S3-presigned-URL (document features) vs direct-data (structured features)
- Documented the dual-service trap with exact code from `AIFeedbackService.cs`

**Agent 2**: "Extract the ezy-ai route creation pattern"
- Read all route files, identified the canonical structure
- Read service files, found the `claudeService.structuredOutput()` pattern
- Extracted the Zod schema definition pattern from `types/api.ts`
- Built a complete copy-paste template for new endpoints

### For speckit-verify

Dispatched one codebase-analyzer agent to map the verification gap:
- Read `speckit.implement.md` — found the completion validation is aspirational
- Read `check-api.md`, `check-frontend.md`, `check-all.md` — compilation only, not auto-invoked
- Read `docker-compose.yaml` — mapped all 7 services, ports, healthchecks
- Read CI workflows — found tests are commented out, no ezy-ai build check
- Read ezy-ai smoke tests — found they exist but are never invoked automatically

### For speckit-enhance

Dispatched two parallel agents:

**Agent 1**: "Extract domain model and business knowledge"
- Read all entity files in `EzyLegal.Core/Business/Entities/`
- Extracted the full Case entity (30+ properties, 20+ relationships)
- Mapped the CaseStatus lifecycle (17 statuses, 3 groups, typical flow)
- Catalogued the role system (system roles, account roles, case roles)
- Found Australian-specific data (jurisdictions, courts, ABN/ACN, ATSI, document taxonomy)

**Agent 2**: "Analyze spec quality patterns"
- Read spec.md files for features 003, 004, 005, 006, 007, 008
- Identified user story anatomy (5-part structure, priority distribution)
- Categorized acceptance scenarios (happy path, behavioral preservation, graceful degradation)
- Extracted functional requirement phrasing patterns (MUST exclusively)
- Built edge case taxonomy (8 categories across all specs)

## Step 4: Skill Structure Decisions

### SKILL.md vs References split

**Rule applied**: SKILL.md should be readable in 30 seconds. If Claude needs code templates, those go in references.

| Skill | SKILL.md | References |
|-------|----------|------------|
| ezy-ai-recipe | Architecture diagram, integration checklist (11 files), critical traps | 3 files: .NET pattern, ezy-ai template, dual-service trap |
| speckit-verify | 6-step verification flow, troubleshooting | 1 file: Docker service map |
| speckit-enhance | Spec quality bar, edge case categories, domain concept rules | 3 files: domain model, edge case library, Australian legal reference |

### Description design

Descriptions reference specific workflow phases and entities:

```yaml
# Good — triggers correctly during speckit
description: >
  Use when planning or implementing any feature that involves AI processing...
  Also use when speckit plan/implement phases touch IAIFeedbackService...

# Bad — would trigger on everything
description: >
  Helps with building features in the EzyLegal project.
```

## Step 5: Outcome

### Final skill set

```
.claude/skills/
├── ezy-ai-recipe/          # 4 files, ~1,800 lines total
├── speckit-verify/          # 2 files, ~400 lines total
├── speckit-enhance/         # 4 files, ~600 lines total
└── skill-builder-playbook/  # This playbook (meta-skill)
```

### Phase mapping

| Speckit Phase | Skill | Knowledge Provided |
|---|---|---|
| /speckit.specify | speckit-enhance | Domain model, edge case checklist, spec quality bar |
| /speckit.clarify | speckit-enhance | Proactive clarification patterns |
| /speckit.plan | ezy-ai-recipe | Pre-packaged integration pattern (saves ~6 file reads) |
| /speckit.tasks | ezy-ai-recipe | 11-file implementation checklist, dual-service trap |
| /speckit.implement | ezy-ai-recipe | Copy-paste templates for routes, services, schemas |
| Post-implement | speckit-verify | Compilation + Docker rebuild + health + quickstart walkthrough |

### What makes this approach different from generic skill building

1. **Skills don't create new workflows** — they inject knowledge into existing pipeline phases
2. **Skills are designed for the AI, not the human** — descriptions trigger on workflow context, not user commands
3. **Skills encode cross-feature patterns** — extracted from 3+ real implementations, not hypothetical templates
4. **Skills complement existing automation** — constitution handles rules, skills handle recipes
5. **References are from actual code** — method signatures, file paths, line numbers from the real codebase
