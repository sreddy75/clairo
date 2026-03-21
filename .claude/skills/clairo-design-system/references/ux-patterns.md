# UX Patterns — Information Architecture & Content Strategy

Source: `docs/UX/user-journey-accountants.md`, `docs/UX/user-journey-business-owners.md`, `docs/ux-knowledge-experience-design.md`

---

## Core Principle: Data Is the Hero, Actions Are the Point

Every page must answer two questions:
1. **What do I need to know?** (data/status)
2. **What should I do about it?** (actions)

If a page only shows data without suggesting actions, it's incomplete. If a page has actions without clear data context, it's confusing.

---

## User Personas (Who We're Designing For)

### Primary: Accountants (the paying users)

| Persona | Clients | Need | Design Implication |
|---------|---------|------|-------------------|
| **Sarah** — Practice Manager | 120 | "See all 120 clients at once, not click through 120 Xero files" | Portfolio-level views, batch operations, status-at-a-glance |
| **David** — Solo Scaling | 45 | "Double clients without doubling hours" | Efficiency, automation cues, quick-action patterns |
| **Margaret** — Traditional | 35 | Familiar patterns, not overwhelmed by AI | Progressive disclosure, optional advanced features, simple defaults |

**Design for Sarah first** (the power user with the most to manage). David benefits from the same design at smaller scale. Margaret benefits from progressive disclosure — simple by default, powerful on demand.

### Secondary: Business Owners (portal users — read-only)

- **Don't add burden.** The portal should require zero learning.
- **Show status, not complexity.** BAS estimate, due date, one-click approval.
- **Multi-channel:** Email works fine. Portal is optional depth.

---

## 7 Jobs To Be Done → Page Mapping

Every page in Clairo maps to one or more JTBD. When building a page, identify which job(s) it serves and prioritize content accordingly.

| # | Job | Trigger | Page(s) | Success Criteria |
|---|-----|---------|---------|-----------------|
| 1 | **Triage My Portfolio** | Opening Clairo, start of day | Dashboard/Today View | Know top 3-5 priorities within 60 seconds |
| 2 | **Review & Lodge Compliance** | BAS deadline approaching | Lodgements, Client Detail > BAS tab | Spot issues before lodging, confident it's correct |
| 3 | **Answer a Client Question** | Phone call, email | AI Assistant, Client Detail | Accurate answer within minutes, with citations |
| 4 | **Spot Advisory Opportunities** | During client review, system alert | Dashboard (opportunities), Client Detail, Insights | Identify opportunity, build case, present to client |
| 5 | **Manage Employer Obligations** | Employee events, threshold changes | Client Detail > Compliance tab | Confident across payroll, super, Fair Work, workers comp |
| 6 | **Stay Ahead of Changes** | Regulatory update detected | Dashboard (alerts), Notifications | Know within 24h which clients are impacted |
| 7 | **Prepare for Client Meeting** | Calendar event | Client Detail, Meeting Prep | 2-page briefing: health, compliance, 2-3 discussion points |

---

## Information Hierarchy Rules

### Rule 1: Priority Queue > Metrics Dashboard

The dashboard is NOT a vanity metrics page. It's a **triage tool**.

**Wrong order:** Revenue → Client count → Charts → Eventually, what needs attention
**Right order:** What needs attention NOW → Upcoming deadlines → Advisory opportunities → Portfolio summary

```
PRIORITY (the current dashboard gets this backwards):
1. NEEDS ATTENTION — things requiring action today (alerts, overdue items, anomalies)
2. UPCOMING DEADLINES — time-sensitive items in the next 7-14 days
3. ADVISORY OPPORTUNITIES — revenue-generating suggestions (justifies the subscription)
4. PORTFOLIO OVERVIEW — KPIs and summary stats (stat cards)
5. CLIENT TABLE — the full list for drill-down
```

### Rule 2: Multi-Client Awareness

Accountants think in **portfolios**, not individual clients. Every alert, every metric should show how many clients are affected.

- "BAS Q3 due in 5 days — **12 clients** not yet reviewed" (not just "BAS is due")
- "Payday Super changes — **45 clients** affected" (not just "new regulation")
- "Data anomaly: Coastal Cafe" (individual when the anomaly is specific)

### Rule 3: Progressive Disclosure (3 Levels)

Never front-load complexity. Every piece of information follows 3 levels:

| Level | What | Where | Example |
|-------|------|-------|---------|
| **L1: Headline** | One-line summary | Dashboard card, table row | "Labour costs 8% above benchmark" |
| **L2: Context** | Paragraph with explanation | Expanded card, sidebar panel | "ATO benchmarks for cafes flag labour % above 38% as unusual. Current: 42%." |
| **L3: Deep Dive** | Full source material | Linked page, modal, external source | ATO Small Business Benchmarks PDF, specific ruling |

**Design implication:** Cards show L1. Clicking/expanding shows L2. "View source" or "Learn more" links to L3.

### Rule 4: Actionable Over Informational

Every surfaced piece of data should suggest a next step:

- "Review with client" → links to client detail
- "Add to advisory agenda" → creates action item
- "Lodge amendment" → starts lodgement workflow
- "See affected clients" → filtered client list

**If there's no action, question whether it belongs on the page.**

### Rule 5: Intelligence, Not Information

Don't show raw data. Show interpreted, contextualised intelligence:

- **Raw:** "Labour costs: $374K" ← just a number
- **Intelligent:** "Labour costs 42% of revenue — 8% above ATO benchmark for cafes. Common audit trigger." ← contextual, compared, actionable

---

## Knowledge Delivery: 3 Channels

Every page should consider which channel(s) it serves:

### Push — "You need to know this"
System proactively surfaces information. Dashboard alerts, notification bell, email digests.
- Regulatory changes affecting clients
- Compliance deadlines approaching
- Anomalies detected in client data
- Advisory opportunities identified

### Contextual — "Since you're looking at this..."
Knowledge appears alongside what the user is already viewing. Client detail sidebars, inline benchmarks, BAS review tips.
- Industry benchmarks when viewing a client
- GST rules when reviewing a BAS line item
- Fair Work requirements when viewing payroll
- The user didn't ask — the context triggered it

### Pull — "I have a question"
User actively seeks knowledge. AI Assistant, search, advisory workflows.
- "What CGT concessions apply to this client?"
- "Is this a contractor or employee?"
- Full depth of knowledge base accessible, guided by AI with client context

---

## Page-Specific UX Rules

### Dashboard / Today View
**Job:** #1 Triage, #6 Stay Ahead, #4 Advisory

**Information priority:**
1. **Needs Attention** — action items ranked by urgency/impact (not just count)
2. **Upcoming Deadlines** — timeline of next 14 days
3. **Advisory Opportunities** — front and centre, not buried (this justifies the subscription)
4. **Portfolio Health** — stat cards (quality score, ready count, attention count, no-activity count)
5. **Client Table** — sortable, filterable, status at a glance

**UX rules:**
- Greeting with date: "Good morning, Sarah. Mon 10 Mar 26"
- Each alert card has a clear [Action →] link
- Multi-client counts on every alert: "12 clients", "45 affected"
- Stat cards are clickable — filter the table below

### Client List
**Job:** #1 Triage (subset)

**Information priority:**
1. Name + status dot (immediate triage)
2. Key financial metric (Net GST or revenue — one number, not five)
3. Quality score / health indicator
4. Last synced (data freshness)

**UX rules:**
- Tab filters with counts: All (45), Needs Review (8), Ready (30), No Activity (7)
- Search is prominent
- Status dots (not colored pills) — minimal, Logiqc-style
- Rows are links to client detail

### Client Detail
**Job:** #2 Compliance, #3 Answer Questions, #4 Advisory, #5 Employer, #7 Meeting Prep

**Information priority:**
1. **Health Score** — composite: data quality + compliance + financial health (3 mini-cards)
2. **Financial Snapshot + Industry Benchmarks** — side by side (the context that makes numbers meaningful)
3. **Compliance Obligations** — living checklist (what's done, what's due)
4. **Opportunities & Risks** — knowledge-driven, each with source citation + action button
5. **[Ask Clairo]** — always accessible, pre-loaded with this client's context

**UX rules:**
- Tabs: Overview, BAS, Transactions, Documents, Notes
- "Ask Clairo" button in header — client-context-aware
- Benchmarks compared visually: client value vs industry range
- Each opportunity/risk card cites its source and has an action link

### AI Assistant / Ask Clairo
**Job:** #3 Answer Questions, #4 Advisory

**UX rules:**
- Client context shown in header: "Context: Coastal Cafe"
- Client selector to switch context without leaving chat
- Citations on every answer — numbered sources, clickable
- Action buttons below answers: "Generate advisory note", "Add to agenda"
- Empty state: rotating contextual suggestions based on current client portfolio
- No "collection picker" — user never sees knowledge base structure

### Lodgements
**Job:** #2 Compliance

**Information priority:**
1. Deadline countdown (days remaining, not just date)
2. Client count by readiness: Ready to Lodge, Needs Review, Not Started
3. Table with status, BAS liability, quality score

### Settings
**Job:** None — utility page

**UX rules:**
- Left nav for sections, right panel for forms
- Minimal — settings should be quick and forgettable

---

## Emotional Design Rules

| Situation | Emotion Goal | Design Response |
|-----------|-------------|-----------------|
| Start of day | Calm confidence | Priority queue, not information overload |
| Approaching deadline | Focused urgency | Clear counts, clear actions, no panic |
| Client question | Quick competence | AI answers with citations, actionable |
| Advisory opportunity | Professional excitement | Clear value proposition, client-ready output |
| Everything on track | Satisfaction | Green status dots, "All clear" empty states |
| Something went wrong | Clear next steps | Error states with retry actions, not dead ends |

---

## Content Writing Rules

1. **Plain English.** No accounting jargon in UI labels. "Needs Review" not "Requires Reconciliation Assessment."
2. **Numbers first.** Lead with the number, then the label. "$7,200" catches the eye; "BAS Liability: $7,200" is for the detail.
3. **Time-aware.** "Due in 5 days" not "Due 21 Mar" — relative time creates urgency.
4. **Multi-client counts.** "12 clients" not "several clients" — specific numbers build trust.
5. **Actions as verbs.** "Review", "Lodge", "Export", "Ask Clairo" — not "Client Review Page" or "Lodgement Centre."
