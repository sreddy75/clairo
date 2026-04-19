---
name: brief-to-spec
description: "Transform an SME brief into a full speckit-compatible feature specification. Use when the user says '/brief-to-spec' or wants to convert a brief/requirements document into an engineering spec. Takes a brief from /sme-capture and produces a spec.md ready for /speckit.plan."
---

## Purpose

This skill takes a **raw SME brief** (produced by `/sme-capture` or written manually) and transforms it into a **full feature specification** in the project's speckit format. The output is a `spec.md` that follows the exact structure and quality standards the engineering team expects, ready to feed into `/speckit.plan` → `/speckit.tasks` → `/speckit.implement`.

## User Input

```text
$ARGUMENTS
```

The user should provide either:
- A path to a brief file (e.g., `specs/briefs/2026-04-11-feature-name.md`)
- A brief filename to look up in `specs/briefs/`
- Or if no argument, list available briefs in `specs/briefs/` and ask which one to convert

## Process

### Step 1: Load Inputs

1. **Load the brief**: Read the SME brief file
2. **Load the spec template**: Read `.specify/templates/spec-template.md`
3. **Load the constitution**: Read `.specify/memory/constitution.md` (specifically for audit requirements, architecture principles, and layer rules)
4. **Load domain knowledge**: Read `.claude/skills/clairo-domain-knowledge/SKILL.md` for Clairo-specific terminology and patterns
5. **Scan existing specs**: List `specs/` directories to understand numbering and avoid duplication. Also check for specs that might overlap with this brief's scope.

### Step 2: Analyze the Brief

Before writing anything, analyze the brief for:

1. **Completeness Check** — Does the brief cover enough to write a spec?
   - Problem statement: REQUIRED (cannot proceed without it)
   - Users/roles: REQUIRED (need to know who the actors are)
   - Core workflow: REQUIRED (need at least a happy path)
   - Success criteria: Can be inferred if missing
   - Edge cases: Can be inferred from domain knowledge if missing
   - Data/integrations: Can be inferred from workflow if missing
   - Compliance/audit: Can be inferred from Clairo's domain (almost always required)

2. **Gap Assessment** — For each gap:
   - Can it be filled from Clairo domain knowledge? → Fill it and note the assumption
   - Can it be reasonably inferred? → Infer it and note the assumption
   - Is it critical and unanswerable? → Mark as [NEEDS CLARIFICATION] (max 3 total per speckit rules)

3. **Scope Sizing** — Is this a single spec or should it be split?
   - If the brief describes multiple independent features, recommend splitting
   - Each spec should be independently shippable

4. **Dependency Mapping** — What existing specs does this depend on?
   - Check the brief's data/integration needs against existing specs
   - Check for infrastructure reuse opportunities (auth, portal, email, etc.)

### Step 3: Report Findings (Before Writing)

Present a brief summary to the user before generating the spec:

```
## Brief Analysis: [Title]

**Completeness**: [Good/Adequate/Has Gaps]
**Gaps filled by inference**: [List any assumptions made]
**Needs clarification**: [List any critical unknowns, max 3]
**Suggested spec number**: [Next available number]-[short-name]
**Dependencies**: [List related specs]
**Scope**: [Single spec / Recommend splitting into N specs]

Ready to generate? Or want to adjust anything first?
```

Wait for user confirmation before proceeding (unless the brief is complete and clean).

### Step 4: Generate the Spec

Transform the brief into a full `spec.md` following the project's template. Here's how each brief section maps to spec sections:

#### Mapping: Brief → Spec

| Brief Section | Spec Section | Transformation |
|--------------|-------------|----------------|
| Problem Statement | Origin + Problem | Expand into context paragraph. Include SME quotes if available. |
| Background Context | Problem (continued) | Weave in as supporting context for why this matters |
| Users & Roles | User Stories preamble | Identify actors for Given/When/Then scenarios |
| Core Workflow | User Stories (P1) | Convert numbered steps into User Story format with acceptance scenarios |
| Edge Cases | Edge Cases section + lower-priority User Stories | Formalize into Given/When/Then |
| Data & Integrations | Key Entities + Functional Requirements | Extract entities, define FR items for each integration point |
| Compliance & Audit | Auditing & Compliance Checklist | Fill the standard audit checklist template |
| Out of Scope | Dependencies / Out of Scope | Formalize as explicit boundaries |
| Success Criteria | Success Criteria (Measurable Outcomes) | Convert SME language to measurable, technology-agnostic metrics |
| Raw Notes | Inform tone and assumptions | Use for context but don't copy directly |

#### Spec Quality Standards (from speckit)

When writing each section, enforce these rules:

**User Stories**:
- Prioritize as P1, P2, P3 — P1 must deliver standalone value
- Each story must be independently testable
- Each story must have: plain-language narrative, priority justification, independent test description, acceptance scenarios in Given/When/Then format
- Acceptance scenarios must be specific — no vague outcomes

**Functional Requirements**:
- Numbered FR-001, FR-002, etc.
- Use MUST/SHOULD language
- Organize by subsystem if there are multiple user types (e.g., "Accountant Side", "Client Side", "System/AI")
- Every FR must be testable — if you can't write a test for it, it's too vague
- Reference existing Clairo infrastructure where applicable (e.g., "using the existing portal email infrastructure" or "within the existing TaxCodeResolutionPanel")

**Key Entities**:
- Name entities with their relationships
- Don't specify database columns — that's for plan.md
- Do specify what the entity represents and its key attributes conceptually

**Audit Checklist**:
- Check every applicable audit type (Clairo is in tax/BAS domain — audit is almost always required)
- Fill the audit implementation table with specific event types following Clairo's naming convention (e.g., `bas.period.created`, `classification.client.submitted`)
- Default retention: 7 years (ATO compliance)
- Note any sensitive data masking needs (TFN, bank details)

**Success Criteria**:
- Technology-agnostic (no frameworks, APIs, or database references)
- Measurable (include specific numbers: time, percentage, count)
- User-focused (describe outcomes from user/business perspective)
- Verifiable (can be tested without knowing implementation)

### Step 5: Write the Spec File

1. **Determine spec number**: Find the highest existing spec number and increment
2. **Create directory**: `specs/[###-feature-name]/`
3. **Write spec.md**: Full specification following the template
4. **DO NOT create plan.md or tasks.md** — those are separate speckit phases

### Step 6: Quality Validation

After writing, validate against the speckit quality checklist:

1. **Content Quality**:
   - [ ] No implementation details (languages, frameworks, APIs)
   - [ ] Focused on user value and business needs
   - [ ] Written for non-technical stakeholders
   - [ ] All mandatory sections completed

2. **Requirement Completeness**:
   - [ ] Max 3 [NEEDS CLARIFICATION] markers
   - [ ] Requirements are testable and unambiguous
   - [ ] Success criteria are measurable and technology-agnostic
   - [ ] Acceptance scenarios are defined for all user stories
   - [ ] Edge cases identified

3. **Clairo-Specific**:
   - [ ] Audit checklist completed (not just boilerplate)
   - [ ] Multi-tenancy implications considered
   - [ ] User types correctly identified (tenant/accountant vs client/business owner)
   - [ ] Compliance context appropriate for Australian tax domain

If any check fails, fix it before presenting to the user.

### Step 7: Create Quality Checklist

Generate `specs/[###-feature-name]/checklists/requirements.md` following the speckit template (same format as `/speckit.specify` would produce).

### Step 8: Present Results

```
## Spec Generated: [###-feature-name]

**From brief**: [brief filename]
**Spec file**: specs/[###-feature-name]/spec.md
**Checklist**: specs/[###-feature-name]/checklists/requirements.md

### Summary
- [X] user stories ([Y] P1, [Z] P2, ...)
- [N] functional requirements
- [N] edge cases covered
- Audit checklist: [complete/partial]
- Assumptions made: [count] (documented in spec)

### Next Steps
1. **Review the spec** — check assumptions marked with 💡
2. **Clarify unknowns** — run `/speckit.clarify` if [NEEDS CLARIFICATION] items remain
3. **Generate technical plan** — run `/speckit.plan` when spec is approved
4. **Generate tasks** — run `/speckit.tasks` after plan is approved

### Assumptions Made (review these)
- [List each assumption with brief justification]
```

### Step 9: Update Brief Status

Update the original brief file's status line from `Raw — ready for /brief-to-spec` to `Converted — see specs/[###-feature-name]/spec.md`

## Edge Cases

- **Brief is too thin**: If the brief has fewer than 3 of the 7 required sections filled, warn the user and suggest running `/sme-capture` again or filling gaps manually before converting.
- **Brief describes multiple features**: Recommend splitting. Offer to create multiple specs or ask which feature to spec first.
- **Brief overlaps existing spec**: Flag the overlap, reference the existing spec, and ask whether this is an extension/enhancement or a replacement.
- **No brief file provided**: List available briefs in `specs/briefs/` and ask which one to convert.

## Important Notes

- **Preserve the SME's voice in the Origin section.** Engineering specs can be dry — the Origin/Problem section is where the "why" lives. Keep the human motivation visible.
- **Don't over-engineer the spec.** The brief captures what the SME needs. The spec formalizes it. Don't add features the SME didn't ask for.
- **Mark assumptions clearly.** Use 💡 emoji prefix for assumptions: `💡 Assumption: [what was assumed and why]`. This makes them easy to find during review.
- **Respect speckit boundaries.** This skill produces `spec.md` only. It does NOT produce `plan.md`, `tasks.md`, data models, or API contracts. Those are downstream speckit phases.
