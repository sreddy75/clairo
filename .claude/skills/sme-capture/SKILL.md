---
name: sme-capture
description: "Guided conversational requirements capture session for busy SMEs. Produces a structured brief from natural conversation. Use when an SME says '/sme-capture' or wants to capture requirements, describe a feature, or brain-dump what they need built."
---

## Purpose

This skill runs a **10-15 minute conversational session** with a subject matter expert (SME) to capture feature requirements. The SME talks naturally — no forms, no templates, no jargon. Claude asks smart follow-up questions and produces a **structured brief** that can be transformed into a full engineering spec via `/brief-to-spec`.

## Why This Exists

SMEs (accountants, domain experts, founders) are time-poor. They know *what* needs to be built but shouldn't have to learn spec-writing. This skill bridges the gap between "I need a thing that does X" and a structured document an engineer can act on.

## User Input

```text
$ARGUMENTS
```

## Process

### Phase 1: Set the Scene (1-2 minutes)

1. **Greet warmly and set expectations**:
   - "This will take about 10-15 minutes. Just describe what you need in your own words — I'll ask follow-up questions and turn it into a brief the dev team can use."
   - If `$ARGUMENTS` contains a topic/feature description, acknowledge it and use it as the starting point
   - If empty, ask: "What's the feature or problem you want to talk through?"

2. **Identify the SME's role** (if not already known from memory):
   - Are they an accountant, business owner, product person, founder?
   - This shapes the language Claude uses and the follow-ups it asks

### Phase 2: Conversational Discovery (8-12 minutes)

Run through these **discovery dimensions** conversationally — NOT as a checklist. Weave questions naturally based on what the SME says. Skip dimensions that don't apply. Double down on dimensions where the SME has strong opinions.

**The 7 Discovery Dimensions:**

1. **The Problem** — What's broken, missing, or painful today?
   - "What's the trigger for this? What happened that made you think 'we need this'?"
   - "How are people working around this today?"
   - Listen for: real incidents, customer complaints, compliance gaps, time sinks

2. **The Users** — Who specifically will use this?
   - In Clairo context: accountant, business owner (portal user), admin, or system?
   - "Walk me through who touches this and when"
   - Listen for: multiple user types, different permission levels, handoff points

3. **The Happy Path** — What does "working perfectly" look like?
   - "If I built exactly what you want, walk me through what happens step by step"
   - "What does the user see? What do they click? What happens next?"
   - Listen for: the core workflow, the minimum viable flow, the "must have" vs "nice to have"

4. **The Sad Paths** — What can go wrong?
   - "What if the user does something unexpected?"
   - "What if data is missing or wrong?"
   - "Are there compliance or audit implications if this breaks?"
   - Listen for: error handling expectations, edge cases the SME already knows about

5. **The Data** — What information is involved?
   - "What data does this need to work? Where does it come from?"
   - "Does this create new data or modify existing data?"
   - In Clairo context: Xero data, BAS data, tax codes, client records?
   - Listen for: data sources, data transformations, what needs to be stored vs computed

6. **The Boundaries** — What is this NOT?
   - "Is there anything people might assume this does that it shouldn't?"
   - "What's explicitly out of scope for now?"
   - Listen for: scope creep risks, phase 2 ideas, things to defer

7. **The Success** — How do we know it's working?
   - "If we shipped this next week, how would you know it's successful?"
   - "What would make you say 'yes, this is exactly what I needed'?"
   - Listen for: measurable outcomes, time savings, error reduction, compliance confidence

**Conversation Rules:**
- Ask ONE question at a time (max TWO if tightly related)
- Use the SME's own language back to them — don't translate to tech jargon
- When the SME says something vague ("it should be smart about it"), dig in: "Smart how? Give me an example"
- When the SME gives a great concrete example, say so: "That's a great example, I'll capture that"
- If the SME goes on a tangent that's useful context but not a requirement, note it as background
- If the SME is clearly done with a topic, move on — don't interrogate
- **Respect their time** — if you have enough for a solid brief after 8 minutes, start wrapping up

### Phase 3: Playback & Confirm (2-3 minutes)

Before writing the brief, do a **quick verbal summary**:

1. "Let me play back what I've got to make sure I haven't missed anything:"
2. Summarize in 4-6 bullet points:
   - The problem being solved
   - Who it's for
   - The core workflow (happy path)
   - Key constraints or compliance needs
   - What's out of scope
   - How success is measured
3. Ask: "Did I miss anything? Anything you'd change?"
4. Incorporate any corrections

### Phase 4: Write the Brief

After confirmation, generate the brief file.

**Brief Location**: `specs/briefs/[YYYY-MM-DD]-[short-name].md`

Create the `specs/briefs/` directory if it doesn't exist.

**Brief Format**:

```markdown
# Feature Brief: [Short descriptive title]

**Captured**: [DATE]
**SME**: [Name/role if known, otherwise "Domain Expert"]
**Status**: Raw — ready for `/brief-to-spec`
**Session**: [Cowork session reference if available]

---

## Problem Statement

[2-4 sentences describing the problem in the SME's own words. Include the trigger/motivation.]

## Background Context

[Any relevant context the SME shared that isn't a direct requirement but helps understand the domain. Include workarounds currently in use, related features, compliance context.]

## Users & Roles

| User Type | What They Do | Key Needs |
|-----------|-------------|-----------|
| [e.g. Accountant] | [Their role in this feature] | [What they need from it] |
| [e.g. Business Owner] | [Their role in this feature] | [What they need from it] |

## Core Workflow (Happy Path)

[Numbered steps describing the ideal flow from the SME's perspective. Use their language.]

1. [Step 1]
2. [Step 2]
3. [Step 3]
...

## Edge Cases & Error Handling

[Bullet points of what can go wrong and what should happen, as described by the SME]

- **[Scenario]**: [Expected behavior]
- **[Scenario]**: [Expected behavior]

## Data & Integrations

[What data is involved, where it comes from, what gets created/modified]

- **Input data**: [Sources]
- **Output data**: [What gets created or changed]
- **Integrations**: [External systems involved — Xero, ATO, email, etc.]

## Compliance & Audit

[Any audit trail, ATO, or regulatory requirements mentioned. In Clairo's domain this is almost always relevant.]

## Out of Scope (for now)

[Things the SME mentioned but explicitly deferred]

- [Deferred item 1]
- [Deferred item 2]

## Success Criteria (SME's words)

[How the SME will know this is working. Keep in their language — the spec conversion will formalize these.]

- [Criterion 1]
- [Criterion 2]

## Raw Notes

[Any additional quotes, examples, or anecdotes from the SME that add colour. These help the spec writer understand intent.]

> "[Direct quote if memorable]"

- [Additional note]
```

### Phase 5: Wrap Up

1. Save the brief file
2. Tell the SME:
   - "Done! I've captured everything in a brief. The next step is converting this to a full engineering spec — that happens async, you don't need to be involved unless we have questions."
   - Share the file path
3. Mention: "When you're ready to convert this to a spec, just say `/brief-to-spec [brief filename]`"

## Important Notes

- **This is a CONVERSATION, not a form.** Don't dump all 7 dimensions as questions upfront.
- **The SME's time is sacred.** If they give short answers, don't push — capture what you have and note gaps.
- **Use Clairo domain knowledge.** You know the platform — if the SME mentions "BAS prep" you should know what that means and ask informed follow-ups about tax codes, periods, client workflows, etc.
- **Capture quotes.** When the SME says something that perfectly captures intent, quote it verbatim in the brief.
- **Don't design the solution.** Capture the problem and requirements. The spec and plan phases handle the how.
- **Multiple sessions are fine.** If the SME runs out of time, save what you have and mark the brief as "Partial — needs follow-up on [dimensions]".
