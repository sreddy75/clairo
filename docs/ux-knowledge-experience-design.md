# Clairo UX: Making Knowledge Accessible

## The Problem

We're building a platform with ~45,000 chunks of knowledge across 5 domains (Strategic Advisory, Industry Knowledge, Business Fundamentals, Financial Management, People Operations), on top of existing tax compliance content and real-time client financial data from Xero.

None of this matters if accountants can't access it naturally within their workflow.

The risk: building a "knowledge base search page" that nobody uses. The opportunity: embedding intelligence so deeply into the workflow that accountants can't imagine working without it.

---

## Jobs To Be Done

Accountants don't think in terms of knowledge collections. They think in terms of work they need to get done. Every feature we build should map to one of these jobs.

### Job 1: Triage My Portfolio
**"I just sat down. Which clients need me today?"**

- When: Start of day, returning from lunch, Monday morning
- Trigger: Opening Clairo
- Success: Within 60 seconds, I know my top 3-5 priorities
- Failure: I have to click through 80 clients to figure out what's urgent

Knowledge needed: Deadline awareness, regulatory changes cross-referenced with client profiles, data anomalies, outstanding compliance items.

### Job 2: Review & Lodge Compliance
**"I need to get this BAS/STP/super done right and on time."**

- When: BAS cycle (monthly/quarterly), STP deadlines, super due dates
- Trigger: Approaching deadline, client data ready
- Success: I spot issues before lodging, I'm confident it's correct
- Failure: I miss an anomaly, I'm unsure about a GST treatment, I lodge late

Knowledge needed: GST rules, BAS requirements, industry-specific GST treatment, record-keeping obligations, STP Phase 2 requirements, super guarantee rules.

### Job 3: Answer a Client Question
**"My client just called and asked about [something]. I need a good answer fast."**

- When: Unpredictable. Phone call, email, meeting
- Trigger: Client asks something outside routine compliance
- Success: I give an accurate, confident answer within minutes (or during the call)
- Failure: I say "I'll get back to you", spend 45 minutes on the ATO website, and bill awkwardly

Knowledge needed: Could be ANY collection. Division 7A, FBT salary sacrifice, Fair Work leave entitlements, CGT concessions, business structures, privacy obligations, payroll tax thresholds -- anything.

This is the #1 job where conversational AI + comprehensive knowledge base creates massive value.

### Job 4: Spot & Act on Advisory Opportunities
**"I want to move beyond compliance and actually advise my clients."**

- When: During client review, when the system alerts me, preparing for a meeting
- Trigger: Anomaly in data, regulatory change, client milestone (turnover threshold, employee count), or just "I know this client could do better"
- Success: I identify an opportunity, build a credible case, present it to the client, and deliver advisory work they'll pay for
- Failure: I never look beyond the BAS numbers, I miss obvious restructuring opportunities, I can't articulate why a change would help

Knowledge needed: Strategic advisory (CGT concessions, Div 7A, trust structures, succession planning, R&D incentives), industry benchmarks (how do they compare?), financial management (cash flow coaching, funding options).

This is where Clairo justifies the Professional and Growth tier pricing. Advisory is $400-600/hr vs $150/hr compliance.

### Job 5: Manage Employer Obligations
**"My client has employees. I need to make sure they're compliant across payroll, super, Fair Work, and workers comp."**

- When: Onboarding new client with employees, new hire, termination, FBT year, payroll tax reconciliation
- Trigger: Employee events, threshold changes, regulatory updates (Payday Super July 2026)
- Success: I'm confident the client meets all employer obligations across federal and state
- Failure: I miss a payroll tax registration threshold, I get a Fair Work entitlement wrong, the client gets a super guarantee charge

Knowledge needed: People operations (PAYG, STP, super, FBT, Fair Work, payroll tax by state, workers comp by state, visa worker rules).

### Job 6: Stay Ahead of Changes
**"Something changed in regulation/legislation. Which of my clients are affected?"**

- When: ATO ruling update, Fair Work minimum wage increase, state payroll tax threshold change, new reporting requirement
- Trigger: Regulatory change detected by the system
- Success: I know within 24 hours which clients are impacted and what action to take
- Failure: I find out from a client, or worse, from a penalty notice

Knowledge needed: Regulatory monitoring (RSS, web scraping) cross-referenced with client attributes (industry, state, entity type, turnover, employee count).

### Job 7: Prepare for a Client Meeting
**"I'm meeting with [Client X] tomorrow. I need to walk in prepared."**

- When: Before scheduled client meetings
- Trigger: Calendar event, manual prep
- Success: I have a 2-page briefing covering their financial health, compliance status, and 2-3 advisory opportunities to discuss
- Failure: I scramble through spreadsheets and Xero, walk in with just the BAS numbers

Knowledge needed: Client financial data + industry benchmarks + applicable advisory opportunities + relevant compliance changes.

---

## Design Principles

### 1. Knowledge Comes to You
The accountant should never have to think "which knowledge collection do I search?" Knowledge surfaces contextually based on what they're doing, which client they're viewing, and what questions they're asking.

### 2. Intelligence, Not Information
Don't show raw ATO guidance. Show interpreted, contextualised intelligence: "This client's labour cost ratio is 42% — 8% above the ATO benchmark for cafes. This is an audit risk factor and a margin improvement opportunity."

### 3. Confidence Through Evidence
Every AI-generated insight must link back to its source. Accountants need to verify before advising. Show the citation, show the relevant excerpt, make it one click to read the full source.

### 4. Progressive Disclosure
Surface the insight first (one line). Let them expand for context (a paragraph). Let them dive deep into source material (full document). Don't front-load complexity.

### 5. Actionable Over Informational
Every piece of surfaced knowledge should suggest a next step: "Review with client", "Add to advisory agenda", "Lodge amendment", "Flag for year-end planning."

### 6. Multi-Client Awareness
Accountants manage 25-250 clients. Any regulatory change, benchmark, or compliance rule should be evaluated against the entire portfolio, not one client at a time.

---

## Experience Architecture

### The Three Channels of Knowledge Delivery

Knowledge reaches users through three channels. All three must work together.

```
+------------------+     +------------------+     +------------------+
|      PUSH        |     |    CONTEXTUAL    |     |       PULL       |
|  System tells    |     |  Knowledge sits  |     |   User asks a    |
|  you what you    |     |  alongside what  |     |   question and   |
|  need to know    |     |  you're already  |     |   gets an answer |
|                  |     |  looking at      |     |                  |
| - Alerts         |     | - Sidebars       |     | - AI Chat        |
| - Notifications  |     | - Inline tips    |     | - Search         |
| - Dashboard      |     | - Benchmarks     |     | - Advisory tools |
|   cards          |     | - Risk flags     |     |                  |
+------------------+     +------------------+     +------------------+
```

**Push** — "You need to know this." The system proactively surfaces information based on triggers: regulatory changes affecting your clients, compliance deadlines approaching, anomalies detected, advisory opportunities identified. This is the morning dashboard, the notification bell, the email digest.

**Contextual** — "Since you're looking at this..." When viewing a client, relevant benchmarks, obligations, and opportunities appear alongside the financial data. When reviewing a BAS line item, applicable GST rules appear. When looking at payroll, Fair Work and payroll tax requirements for that state surface. The user didn't ask — the context did.

**Pull** — "I have a question." The user actively seeks knowledge through AI chat ("What CGT concessions might apply to this client?") or advisory workflows ("Run a business structure review"). This is where the full depth of the knowledge base is accessible, but guided by AI that understands the client context.

---

## Screen-Level Design

### 1. Today View (Morning Dashboard)

**Job served: #1 Triage, #6 Stay Ahead**

This is the first thing an accountant sees. Not a generic dashboard with charts — a prioritised action queue.

```
+-----------------------------------------------------------------------+
| Good morning, Sarah.                                    Mon 10 Mar 26 |
+-----------------------------------------------------------------------+
|                                                                       |
| NEEDS ATTENTION (4)                                                   |
| +-------------------------------------------------------------------+ |
| | ! BAS Q3 due in 5 days — 12 clients not yet reviewed             | |
| |   [View clients ->]                                               | |
| +-------------------------------------------------------------------+ |
| | ! Payday Super changes (1 Jul 2026) — 45 clients affected        | |
| |   Action needed: Review SG payment timing for affected clients    | |
| |   [See impact analysis ->]                                        | |
| +-------------------------------------------------------------------+ |
| | @ Data anomaly: Coastal Cafe — GST collected but no GST reported  | |
| |   in Dec quarter. Possible coding error.                          | |
| |   [Review client ->]                                              | |
| +-------------------------------------------------------------------+ |
| | i ATO updated Division 7A guidance (3 Mar 2026)                   | |
| |   8 of your clients have Div 7A loans — review new benchmarks    | |
| |   [See affected clients ->]                                       | |
| +-------------------------------------------------------------------+ |
|                                                                       |
| ADVISORY OPPORTUNITIES (2)                                            |
| +-------------------------------------------------------------------+ |
| | Smith Building Group — Turnover crossed $2M threshold.            | |
| | May now be eligible for R&D Tax Incentive (43.5% offset).         | |
| | Est. value to client: $45K-$80K.  [Explore ->]                    | |
| +-------------------------------------------------------------------+ |
| | Janet Lee Consulting — Operating as sole trader, revenue $320K.   | |
| | Structure review recommended: company or trust may reduce tax by  | |
| | ~$18K/yr based on current income profile. [Build case ->]         | |
| +-------------------------------------------------------------------+ |
|                                                                       |
| UPCOMING DEADLINES                                                    |
| +-------------------------------------------------------------------+ |
| | 21 Mar  BAS Q3 (12 remaining)    28 Mar  STP finalisation (3)    | |
| | 28 Mar  Super Q3 (45 clients)    15 Apr  FBT return (8 clients)  | |
| +-------------------------------------------------------------------+ |
+-----------------------------------------------------------------------+
```

Key design decisions:
- **Priority queue, not dashboard widgets.** Ranked by urgency and impact.
- **Multi-client awareness built in.** "12 clients", "45 clients affected" — batch thinking.
- **Knowledge-driven alerts.** The Div 7A alert exists because we ingested the updated guidance AND cross-referenced it with client data.
- **Advisory opportunities are front and centre.** Not buried in a sub-menu. This is how accountants justify Clairo's subscription cost.
- **Each item has a clear action.** Not just information — a next step.

### 2. Client Intelligence View

**Job served: #2 Compliance, #3 Answer Questions, #4 Advisory, #5 Employer Obligations, #7 Meeting Prep**

When an accountant clicks into a client, they should get a holistic intelligence view — not just Xero data. This is where contextual knowledge delivery happens.

```
+-----------------------------------------------------------------------+
| Coastal Cafe Pty Ltd                          Industry: Cafes & Coffee |
| ABN 12 345 678 901 | Company | NSW | 6 employees        [Ask Clairo] |
+-----------------------------------------------------------------------+
|                                                                       |
| HEALTH SCORE                                                          |
| +------------------+------------------+------------------+            |
| | Data Quality     | Compliance       | Financial Health |            |
| |    87 / 100      |    92 / 100      |    71 / 100     |            |
| |  [3 issues]      |  [1 upcoming]    |  [2 concerns]   |            |
| +------------------+------------------+------------------+            |
|                                                                       |
+---------------------------+-------------------------------------------+
| FINANCIAL SNAPSHOT        | INDUSTRY BENCHMARKS (Cafes - ATO)         |
|                           |                                           |
| Revenue: $890K (FY26 YTD)|  Metric      Client  Benchmark  Status    |
| Expenses: $812K          |  Labour %     42%     34%       ! Above   |
| Net Profit: $78K         |  CoGS %       38%     36-42%    OK        |
| Cash: $34K (est 2.1mo)   |  Rent %       12%     8-12%     Borderline|
|                           |  Motor Veh %   2%     1-3%      OK        |
| GST Collected: $81K      |  Net Profit %  8.8%   10-15%    ! Below   |
| GST Paid: $74K           |                                            |
| BAS Liability: ~$7K      |  "Labour costs 8% above benchmark.        |
|                           |   Common audit trigger for cafes."         |
+---------------------------+-------------------------------------------+
|                                                                       |
| COMPLIANCE OBLIGATIONS                                                |
| +-------------------------------------------------------------------+ |
| | [x] BAS — Q3 due 21 Mar (draft ready)                            | |
| | [x] STP — Phase 2 compliant, last reported 28 Feb                | |
| | [x] Super — Q3 due 28 Mar ($18,400 est.)                         | |
| | [ ] Payroll Tax NSW — Annual reconciliation due 21 Jul            | |
| |     Wages: $412K (threshold: $1.2M — not yet liable)              | |
| | [x] Workers Comp NSW — Policy current, expires 30 Jun             | |
| | [ ] FBT — 2 reportable benefits identified (car, phone)          | |
| +-------------------------------------------------------------------+ |
|                                                                       |
| OPPORTUNITIES & RISKS                                                 |
| +-------------------------------------------------------------------+ |
| | RISK: Labour cost ratio may trigger ATO review                    | |
| |   ATO benchmarks for cafes flag labour % above 38% as unusual.   | |
| |   Current: 42%. Review staffing structure and award compliance.   | |
| |   Source: ATO Small Business Benchmarks — Cafes & Coffee Shops    | |
| |   [Review detail ->]  [Add to advisory agenda ->]                 | |
| +-------------------------------------------------------------------+ |
| | OPPORTUNITY: Instant asset write-off                              | |
| |   Client mentioned new coffee machine ($12K). Eligible for       | |
| |   immediate deduction under instant asset write-off ($20K cap).   | |
| |   Source: ATO Small Business Concessions — Depreciation           | |
| |   [Build advisory note ->]                                        | |
| +-------------------------------------------------------------------+ |
| | INFO: Payday Super from 1 Jul 2026                                | |
| |   SG payments will need to align with pay cycles (currently       | |
| |   quarterly). 6 employees affected. Discuss payroll system setup. | |
| |   Source: ATO Super for Employers — Payday Super                  | |
| |   [Create action item ->]                                         | |
| +-------------------------------------------------------------------+ |
+-----------------------------------------------------------------------+
```

Key design decisions:
- **Health score is a composite.** Data quality + compliance + financial health. One glance tells you if this client is okay or needs work.
- **Industry benchmarks are front and centre.** Not hidden in a report. The accountant immediately sees how the client compares to their industry.
- **Compliance obligations are a living checklist.** Pulled from knowledge base (what obligations apply to a NSW company with 6 employees?) crossed with client data (what's done, what's due).
- **Opportunities and risks are knowledge-driven.** Each one cites its source. Each one has an action button. The AI connected "cafe with 42% labour costs" to "ATO benchmark says 34%" — the accountant didn't have to look this up.
- **[Ask Clairo] button is always accessible.** Context-aware — it already knows which client you're looking at.

### 3. Ask Clairo (AI Chat)

**Job served: #3 Answer Questions, #4 Advisory, #5 Employer Obligations**

This is the universal knowledge interface. It should feel like talking to a knowledgeable colleague who has read every ATO ruling, Fair Work guide, and industry benchmark — and also knows your client's financials.

```
+-----------------------------------------------------------------------+
| Ask Clairo                                    Context: Coastal Cafe    |
+-----------------------------------------------------------------------+
|                                                                       |
| You: What salary sacrifice options could we set up for the owner      |
|      and employees to reduce FBT exposure?                            |
|                                                                       |
| Clairo:                                                               |
| For Coastal Cafe (6 employees, company structure), here are the       |
| main salary sacrifice arrangements to consider:                       |
|                                                                       |
| **FBT-Exempt Benefits**                                               |
| - Portable electronic devices (one per type per year) — e.g.,        |
|   laptops, phones for staff. No FBT if primarily for work.           |
| - Work-related training and education — exempt if related to          |
|   current employment.                                                 |
|                                                                       |
| **Concessionally Taxed**                                              |
| - Super salary sacrifice — employee contributions above SG reduce     |
|   income tax (15% vs marginal rate). Particularly effective for the   |
|   owner given current $78K profit level.                              |
|   Note: Concessional cap is $30,000/yr (FY26). Unused cap can be     |
|   carried forward up to 5 years if total super < $500K.              |
|                                                                       |
| **Reportable but Beneficial**                                         |
| - Car parking — only FBT-liable if commercial parking nearby          |
|   exceeds the threshold ($10.40/day FY26). Check your location.      |
|                                                                       |
| **Not Recommended for Cafes**                                         |
| - Meal entertainment — limited to 50% deduction, creates additional  |
|   FBT complexity. Not cost-effective at this scale.                   |
|                                                                       |
| Given the owner's income and the business size, **super salary        |
| sacrifice for the owner** is likely the highest-impact option.        |
| Potential tax saving: ~$4,500-$6,000/yr.                              |
|                                                                       |
| Sources:                                                              |
| [1] ATO — Salary sacrificing for employers                           |
| [2] ATO — FBT exempt benefits                                        |
| [3] ATO — Super contribution caps and limits                         |
|                                                                       |
| [Generate advisory note for client ->]                                |
| [Add to advisory agenda ->]                                           |
|                                                                       |
+-----------------------------------------------------------------------+
| Type a question... (Clairo knows your client context)       [Send]    |
+-----------------------------------------------------------------------+
```

Key design decisions:
- **Client-aware by default.** Clairo knows you're looking at Coastal Cafe. It factors in company structure, employee count, profit level, and industry.
- **Cites sources.** Every claim links back to ATO/Fair Work/etc. Accountants can verify.
- **Opinionated.** Doesn't just list options — recommends based on context. "Not recommended for cafes" and "highest-impact option" are the value-add.
- **Actionable outputs.** "Generate advisory note for client" turns the conversation into a deliverable. This is how knowledge becomes revenue.
- **No collection picker.** The user never sees "Strategic Advisory" or "People Operations." They just ask a question and get a complete answer drawing from all relevant sources.

### 4. Advisory Workbench

**Job served: #4 Advisory, #7 Meeting Prep**

For structured advisory work, guided workflows pull relevant knowledge at each step and produce client-ready outputs.

```
+-----------------------------------------------------------------------+
| Advisory Workbench                             Coastal Cafe Pty Ltd    |
+-----------------------------------------------------------------------+
|                                                                       |
| AVAILABLE WORKFLOWS                                                   |
|                                                                       |
| Tax Planning                                                          |
| +-------------------+ +-------------------+ +-------------------+     |
| | Business          | | Year-End Tax      | | CGT & Exit        |     |
| | Structure Review  | | Planning          | | Planning          |     |
| |                   | |                   | |                   |     |
| | Evaluate if       | | Pre-30 June       | | Succession,       |     |
| | current structure | | strategies for    | | sale, Div 152     |     |
| | is optimal        | | minimising tax    | | concessions       |     |
| | [Start ->]        | | [Start ->]        | | [Start ->]        |     |
| +-------------------+ +-------------------+ +-------------------+     |
|                                                                       |
| Employment & Compliance                                               |
| +-------------------+ +-------------------+ +-------------------+     |
| | New Employee      | | Award & Pay       | | FBT Review        |     |
| | Setup Guide       | | Compliance Check  | |                   |     |
| |                   | |                   | | Annual FBT        |     |
| | Onboarding        | | Fair Work award   | | exposure and      |     |
| | obligations       | | rates, NES,       | | planning          |     |
| | checklist         | | entitlements      | | [Start ->]        |     |
| | [Start ->]        | | [Start ->]        | |                   |     |
| +-------------------+ +-------------------+ +-------------------+     |
|                                                                       |
| Financial Health                                                      |
| +-------------------+ +-------------------+                           |
| | Cash Flow         | | Financial         |                           |
| | Health Check      | | Benchmarking      |                           |
| |                   | |                   |                           |
| | ATO coaching kit  | | Compare against   |                           |
| | + client data     | | industry peers    |                           |
| | [Start ->]        | | [Start ->]        |                           |
| +-------------------+ +-------------------+                           |
|                                                                       |
+-----------------------------------------------------------------------+
```

Each workflow is a guided, multi-step process:

```
+-----------------------------------------------------------------------+
| Business Structure Review                      Coastal Cafe Pty Ltd   |
+-----------------------------------------------------------------------+
|                                                                       |
| Step 1 of 5: Current Structure Analysis              [=====     ] 40% |
|                                                                       |
| CURRENT STRUCTURE                                                     |
| Entity: Company (Pty Ltd)                                             |
| Owners: Maria Chen (100% shares)                                      |
| Revenue: $890K | Profit: $78K | Employees: 6                         |
|                                                                       |
| CLAIRO'S ANALYSIS                                                     |
| +-------------------------------------------------------------------+ |
| | Your client is operating as a sole-shareholder company. Based on  | |
| | their profile, here are the key considerations:                   | |
| |                                                                   | |
| | CURRENT STRUCTURE STRENGTHS                                       | |
| | + Limited liability protection                                    | |
| | + Company tax rate: 25% (base rate entity, turnover < $50M)      | |
| | + Retained earnings taxed at 25% vs personal marginal rate        | |
| |                                                                   | |
| | POTENTIAL ISSUES                                                  | |
| | - No income splitting capability (sole shareholder)               | |
| | - Division 7A risk if owner draws beyond salary/dividends         | |
| | - No access to 50% CGT discount (companies excluded)             | |
| |                                                                   | |
| | ALTERNATIVE STRUCTURES TO EVALUATE                                | |
| | 1. Discretionary trust (income splitting, CGT discount access)    | |
| | 2. Trust + company (hybrid — flexibility + asset protection)      | |
| |                                                                   | |
| | Source: ATO Business Structures, ATO Division 7A Guide,           | |
| | ATO CGT Discount Rules                                            | |
| +-------------------------------------------------------------------+ |
|                                                                       |
| Does the client have family members who could receive trust           |
| distributions? [Yes] [No] [Discuss with client first]                 |
|                                                                       |
|                                          [Back]  [Continue to Step 2] |
+-----------------------------------------------------------------------+
```

Key design decisions:
- **Workflow templates map to advisory engagements.** Each one could become a billable advisory piece.
- **Knowledge is injected at each step.** The accountant doesn't research — Clairo presents the relevant rules, thresholds, and options pre-loaded.
- **Interactive.** The workflow asks questions and branches based on answers. "Does the client have family members?" changes the trust analysis.
- **Outputs are client-ready.** At the end, generate a professional advisory memo or letter.

### 5. Regulatory Radar

**Job served: #6 Stay Ahead**

A timeline of regulatory changes with impact analysis across the portfolio.

```
+-----------------------------------------------------------------------+
| Regulatory Radar                                                      |
+-----------------------------------------------------------------------+
|                                                                       |
| ACTIVE CHANGES AFFECTING YOUR CLIENTS                                 |
|                                                                       |
| +-------------------------------------------------------------------+ |
| | Jul 2026 — PAYDAY SUPER                              HIGH IMPACT | |
| | SG must align with pay cycles (currently quarterly).              | |
| | 45 of your 78 clients have employees — all affected.              | |
| | Action: Review payroll system capabilities, notify clients.       | |
| | [View affected clients] [Generate client communication]           | |
| +-------------------------------------------------------------------+ |
| | Mar 2026 — ATO DIVISION 7A BENCHMARK RATE UPDATE      MED IMPACT | |
| | New benchmark interest rate: 8.77% (was 8.27%).                   | |
| | 8 clients with Div 7A loans — repayment schedules need updating.  | |
| | [View affected clients] [Recalculate repayments]                  | |
| +-------------------------------------------------------------------+ |
| | Jul 2026 — FAIR WORK MINIMUM WAGE INCREASE (pending)  MED IMPACT | |
| | Expected 3-4% increase. Decision due June 2026.                   | |
| | 52 clients with award-covered employees.                           | |
| | [View affected clients] [Set reminder for announcement]           | |
| +-------------------------------------------------------------------+ |
|                                                                       |
| RECENTLY RESOLVED                                                     |
| [x] Feb 2026 — Updated STP reporting categories (applied)            |
| [x] Jan 2026 — NSW payroll tax threshold increase (reviewed)          |
|                                                                       |
+-----------------------------------------------------------------------+
```

### 6. Client Meeting Prep (One-Click Briefing)

**Job served: #7 Meeting Prep**

```
+-----------------------------------------------------------------------+
| Meeting Briefing: Coastal Cafe              Generated 10 Mar 2026     |
+-----------------------------------------------------------------------+
|                                                                       |
| FINANCIAL SUMMARY                                                     |
| Revenue: $890K (up 8% YoY) | Profit: $78K (down 3% YoY)             |
| Cash position: $34K (~2.1 months runway)                              |
| Key trend: Revenue growing but margins shrinking — labour costs       |
| increasing faster than revenue.                                       |
|                                                                       |
| COMPLIANCE STATUS                                                     |
| BAS: Q3 draft ready, $7K liability (consistent with prior quarters)   |
| Super: On track. Note Payday Super transition needed by Jul 2026.     |
| FBT: 2 minor reportable benefits. No action needed.                   |
| Payroll tax: Below NSW threshold — monitor (currently $412K/$1.2M).   |
|                                                                       |
| DISCUSSION POINTS                                                     |
| 1. Labour cost review — 42% vs 34% benchmark. Explore rostering      |
|    optimisation or casual vs permanent mix.                           |
| 2. Super salary sacrifice for Maria — potential $4.5-6K tax saving.  |
|    Carry-forward cap available (low super balance likely).            |
| 3. Equipment purchase planning — coffee machine discussed. Eligible   |
|    for instant asset write-off. Consider timing (this FY vs next).   |
| 4. Payday Super prep — discuss payroll system capability for         |
|    same-day SG payments starting Jul 2026.                           |
|                                                                       |
| [Export as PDF]  [Email to myself]  [Open in meeting mode]            |
+-----------------------------------------------------------------------+
```

---

## Information Architecture

### Navigation Structure

```
+------------------+
| CLAIRO           |
+------------------+
| Today            |  <-- Priority queue, alerts, opportunities
| Clients          |  <-- Client list with health scores
|   > Client view  |  <-- Intelligence view per client
| Compliance       |  <-- BAS, STP, Super, FBT — deadline-driven
| Advisory         |  <-- Workbench, opportunities pipeline
| Radar            |  <-- Regulatory changes, impact analysis
+------------------+
| Ask Clairo  [AI] |  <-- Always accessible, context-aware
+------------------+
```

### What Changed from Current Thinking

| Before | After | Why |
|--------|-------|-----|
| Knowledge is a separate section users search | Knowledge is embedded everywhere contextually | Accountants don't search knowledge bases |
| Dashboard shows charts and metrics | Today view shows a prioritised action queue | Accountants need "what do I do next", not "what happened" |
| Client view shows Xero financials | Client view shows intelligence (benchmarks, obligations, opportunities) | Financial data without context is just numbers |
| AI chat is a feature | AI chat is a persistent layer accessible from anywhere | Questions arise in context, not in a separate mode |
| Advisory is manual | Advisory is workflow-driven with knowledge pre-loaded | Removes the research barrier that stops accountants from doing advisory |
| Regulatory updates are news items | Regulatory updates are impact-analysed against your specific clients | "What changed" matters less than "how does this affect me" |

---

## How Knowledge Collections Map to UX

The user never sees collection names. Here's where each collection's content surfaces:

| Collection | Primary UX Surface | How It Appears |
|------------|-------------------|----------------|
| Strategic Advisory | Advisory Workbench, Opportunities cards, Ask Clairo | "Your client may be eligible for..." / workflow analysis steps |
| Industry Knowledge | Client Intelligence View (benchmarks panel), Today View (anomaly alerts) | "42% vs 34% benchmark" / "Above industry average" |
| Business Fundamentals | Compliance obligations checklist, Ask Clairo (general questions) | Living compliance checklist / answers to everyday questions |
| Financial Management | Client financial snapshot, Cash flow alerts, Advisory workflows | "2.1 months cash runway" / cash flow coaching workflow |
| People Operations | Employer obligations section, Regulatory Radar, Ask Clairo | State-specific payroll tax / Fair Work entitlements / Payday Super alerts |

---

## Key UX Flows

### Flow 1: Accountant Discovers an Advisory Opportunity

```
Today View
  -> Sees "Smith Building Group crossed $2M — R&D Tax Incentive eligible"
    -> Clicks [Explore]
      -> Client Intelligence View with R&D section highlighted
        -> Clicks [Build case] on the opportunity card
          -> Advisory Workbench: R&D Tax Incentive workflow
            -> Clairo walks through eligibility, calculations, documentation
              -> Generates advisory proposal for client
                -> Accountant sends to client, books advisory engagement
```

Total knowledge collections involved: Strategic Advisory (R&D rules), Industry Knowledge (construction industry context), Financial Management (turnover data). User touched zero of them directly.

### Flow 2: Client Calls with a Question

```
Phone rings — client asks about hiring a contractor vs employee
  -> Accountant opens Ask Clairo (already in client context)
    -> Types: "Is the new kitchen hand an employee or contractor?"
      -> Clairo answers using:
          - ATO employee vs contractor guidelines
          - Industry-specific examples for hospitality
          - Fair Work casual employment rules
          - Client's existing employment structure
        -> Provides answer with recommendations and citations
          -> Accountant advises client on the call
            -> [Optional] Clicks "Generate advisory note" for file
```

Total knowledge collections involved: People Operations (employee vs contractor), Industry Knowledge (hospitality-specific), Business Fundamentals (employment basics). Answered in real-time during a phone call.

### Flow 3: Regulatory Change Ripples Through Portfolio

```
ATO publishes Payday Super final guidance
  -> System ingests via ato_rss scraper
    -> Cross-references with all clients who have employees
      -> Generates Regulatory Radar alert with impact analysis
        -> Accountant sees on Today View: "45 clients affected"
          -> Clicks [View affected clients]
            -> Filtered client list with impact summary per client
              -> Clicks [Generate client communication]
                -> Clairo drafts email template explaining the change
                  -> Accountant customises and sends to 45 clients
```

Total knowledge collections involved: People Operations (super rules), Business Fundamentals (employer obligations). System-initiated, accountant just approves and sends.

---

## Discovery: Making Capability Visible

The biggest risk with a comprehensive knowledge base is users not knowing it exists. Here are specific patterns to address this:

### 1. Guided Onboarding
First-time users see a brief walkthrough:
- "Clairo knows Australian tax law, Fair Work, industry benchmarks, and business regulations."
- "Try asking: 'What deductions can my construction client claim?'"
- "Your client dashboard shows how each client compares to their industry."

### 2. Empty State Suggestions
When a user opens Ask Clairo with no history:
- "Try asking me about..." with rotating contextual suggestions based on their client portfolio
- "What FBT obligations does [Client X] have?"
- "How does [Client Y]'s profit margin compare to their industry?"
- "What are the CGT concession options for [Client Z]?"

### 3. Capability Badges on Client Cards
Client list shows small badges: "3 advisory opportunities", "2 compliance alerts" — drawing users into the intelligence layer.

### 4. Weekly Digest Email
"This week in your portfolio: 2 new advisory opportunities identified, 1 regulatory change affecting 12 clients, 3 clients with approaching deadlines." Links back into the platform.

### 5. Progressive Capability Reveal
Don't show everything on day one. As the accountant uses basic features (BAS review), gradually surface more: "Did you know? Clairo can compare this client's margins against ATO benchmarks for their industry. [Show me ->]"

---

## Success Metrics

| Metric | What It Measures | Target |
|--------|------------------|--------|
| Time to first advisory action | How quickly new users discover advisory features | < 7 days |
| Ask Clairo sessions per user/week | Pull channel adoption | > 5 sessions/week |
| Advisory workflows started | Structured advisory adoption | > 2/month per user |
| Regulatory alert click-through rate | Push channel relevance | > 60% |
| Client meeting preps generated | Meeting prep adoption | > 1/week per user |
| Advisory revenue attributed | Business impact | Track via advisory notes generated |
| "I don't know" rate in Ask Clairo | Knowledge coverage gaps | < 5% of queries |

---

## Implementation Priority

### Phase 1: Foundation
1. **Today View** — Replace current dashboard with priority queue
2. **Client Intelligence View** — Add benchmarks panel, compliance obligations, opportunities
3. **Ask Clairo (basic)** — Client-aware AI chat drawing from all knowledge collections

### Phase 2: Advisory Engine
4. **Advisory Workbench** — 3-4 initial workflow templates
5. **Meeting Prep** — One-click client briefing generation
6. **Opportunity detection** — Automated advisory opportunity identification

### Phase 3: Portfolio Intelligence
7. **Regulatory Radar** — Impact analysis across client portfolio
8. **Multi-client actions** — Batch communications, portfolio-wide compliance scanning
9. **Weekly digest** — Proactive email summaries

---

## Open Questions

1. **Mobile experience** — Accountants in client meetings may want to ask Clairo from their phone. How does Ask Clairo work on mobile?
2. **Client-facing outputs** — Should advisory notes/memos have Clairo branding, practice branding, or white-label? This affects Enterprise tier.
3. **Collaboration** — When multiple accountants in a practice work on the same client, how do shared notes/advisory agendas work?
4. **Feedback loop** — When an accountant dismisses an opportunity or corrects Clairo, how does that improve future suggestions?
5. **Billing integration** — Can advisory workflows feed into time tracking / invoice generation? "This advisory note took 45 minutes" -> auto-log.
