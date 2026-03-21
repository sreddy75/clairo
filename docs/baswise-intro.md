# Clairo

**Rethinking How Australian Accountants Manage BAS**

---

## The Opportunity

Every quarter, Australian accountants face the same challenge: preparing and lodging Business Activity Statements for dozens—sometimes hundreds—of clients. It's repetitive, time-consuming, and high-stakes work that hasn't fundamentally changed in decades.

The numbers tell the story:

- **$33 billion** — Size of the Australian accounting services market
- **35,000** — Accounting practices across Australia
- **15,000-20,000** — Registered BAS agents
- **2.5M+** — SMEs requiring BAS services
- **250+ hours** — Quarterly BAS workload for a mid-sized firm (50 clients)
- **$222** — Penalty per 28-day period for late lodgement (and it compounds)

Despite widespread adoption of cloud accounting software like Xero and MYOB, the actual work of BAS preparation remains largely manual. Accountants still click through individual client files, reconcile transactions, chase missing data, and hope nothing slips through the cracks.

The typical accountant spends **4-6 hours per client per quarter** on BAS work. For a firm with 50 clients, that's over 250 hours—time that crowds out higher-value advisory work and leads to burnout during "BAS season."

---

## What We're Building

Clairo is a practice operating system designed specifically for Australian accounting firms managing BAS workflows.

We're not trying to replace the tools accountants already use. Instead, we're building the intelligence layer that sits above them—giving accountants visibility, automation, and control across their entire client portfolio.

**Think of it as the command centre for BAS season.**

### Core Capabilities

**1. Multi-Client Dashboard**
A single view of every client's BAS status, deadline, and readiness. No more clicking through 50+ Xero files to understand where things stand. Filter by deadline, risk level, assigned team member, or data quality score.

**2. Data Quality Engine**
This is our key differentiator. We proactively scan client data and score "BAS readiness" before preparation begins. The system identifies:
- Unreconciled bank transactions
- GST coding anomalies and inconsistencies
- PAYG/superannuation mismatches
- Missing or incomplete records
- Patterns that suggest potential ATO audit risk

Issues are classified as blocking (must fix) vs warnings (review recommended), with trend analysis showing recurring problems by client.

**3. Automated Variance Analysis**
When an accountant prepares a BAS, they need to compare current period against prior periods to spot anomalies. This typically takes 30-45 minutes per client of manual work. We automate this entirely—highlighting significant variances and letting accountants focus on investigating exceptions rather than generating reports.

**4. Exception-Based Workflow**
Instead of reviewing every client equally, seniors can focus on the 20% that have issues while batch-approving the 80% that are clean. This transforms how firms allocate their most expensive resource (senior accountant time).

**5. Client Communication Automation**
Automated reminders to clients about reconciliation, missing data, and BAS approval. Reduces the "chasing" that accountants hate.

### What We Don't Do

We're deliberately not competing with Xero or MYOB on transaction-level automation. They're investing heavily in AI for bank reconciliation, invoice processing, and single-business insights. That's their game.

We're focused on the **firm-level view**—the accountant managing 50+ clients who needs portfolio intelligence, not individual transaction help.

---

## How It's Different

### vs. Xero Tax (Free)
Xero Tax is a lodgement tool—manual, single-client, no proactive insights. Clairo is a practice management layer with multi-client visibility and AI-powered data quality analysis.

### vs. LodgeiT ($60/lodgement)
LodgeiT is a mature lodgement platform (since 2011, ATO Tier 1 DSP), but it's workflow-focused without AI capabilities. No proactive issue detection, no portfolio analytics.

### vs. Xero JAX (Xero's AI)
JAX is designed for business owners—single-business AI assistant for invoicing, reconciliation, cash flow. Clairo is designed for accountants managing many clients. Different user, different problem.

**Our sustainable advantages:**
1. **Accountant-first design** — Built for multi-client operations, not single-business self-service
2. **Proactive data quality scoring** — No one else is doing pre-BAS readiness assessment
3. **Multi-ledger flexibility** — Xero today, MYOB next, not locked to one ecosystem
4. **Australia-specific compliance intelligence** — ATO rules, penalty calculations, audit risk indicators
5. **White-label capability** — Firms can offer branded client portals (Enterprise tier)

---

## Target Market

**Primary: BAS-Focused Accounting Practices**
- 20-200 BAS clients
- Using Xero or MYOB as primary ledger
- Quarterly BAS crunch consumes 40%+ of billable capacity
- Aspirations to shift from compliance processing to advisory services
- Tech-comfortable but frustrated by tool fragmentation

**Secondary: Growing Bookkeeping Firms**
- 10-50 clients, scaling up
- Manual processes don't scale; errors increase with volume
- Need efficiency to grow without proportional headcount

**Not targeting (for now):**
- Solo practitioners (<10 clients) — overhead too high for value
- Large firms (500+ clients) — enterprise sales cycle, custom requirements
- Firms not using Xero/MYOB — integration complexity

---

## Business Model

SaaS subscription priced on value delivered (compliance risk reduction, time saved), not per-lodgement.

| Tier | Monthly | Clients | Key Features |
|------|---------|---------|--------------|
| Starter | $49 | Up to 15 | Dashboard, data quality scoring, basic reporting |
| Professional | $149 | Up to 50 | Full automation, variance analysis, team workflows, compliance analytics |
| Enterprise | $399 | Unlimited | White-label client portal, API access, priority support |

**Expansion opportunities:** Advisory module add-on, white-label setup fees, API usage, training services.

**Target unit economics:**
- CAC <$500
- LTV >$3,000 (LTV:CAC >6:1)
- Monthly churn <3%
- Gross margin >80%

---

## Why Now?

**Regulatory tailwinds:** From April 2025, businesses with poor compliance history face mandatory monthly BAS reporting. This dramatically increases accountant workload and makes tools like ours more valuable.

**AI adoption gap:** 99.6% of accountants use AI tools, but only 25% are actively investing in training. They want turnkey solutions that work immediately.

**Platform limitations:** Xero JAX focuses on business owners. Accountants managing portfolios are underserved. There's a clear gap in the market.

**Window of opportunity:** 12-18 months before Xero potentially expands JAX to serve accountants directly. First-mover advantage in accountant-centric tooling is available now.

---

## Go-to-Market

**Phase 1: Validation (Months 1-6)**
- Recruit 5-10 accounting firms as design partners
- Free access during beta in exchange for weekly feedback
- Success criteria: 50% BAS prep time reduction, 80% pre-BAS issue detection, NPS >40

**Phase 2: Early Traction (Months 7-12)**
- Convert design partners to paid subscriptions
- Referral program for organic growth
- Content marketing (BAS compliance guides, webinars)
- Target: 50 paying firms, $25K+ MRR

**Phase 3: Scale (Year 2+)**
- Xero App Store listing (App Partner certification)
- Accounting association partnerships (IPA, CPA)
- Practice management software integrations
- Target: 200+ firms, $100K+ MRR

---

## Roadmap

**Phase 1 — Foundation (MVP)**
- Multi-client dashboard with pipeline view
- Xero integration (OAuth2)
- Data quality engine with readiness scoring
- Variance analysis automation
- Basic team workflows

**Phase 2 — Intelligence**
- MYOB integration
- Compliance analytics dashboard
- Penalty risk and audit probability scoring
- Client communication automation
- Cash flow patterns and GST recovery insights

**Phase 3 — Platform**
- White-label client portal
- Direct ATO integration (DSP certification)
- Advanced advisory tools
- API for practice management integrations

---

## Key Risks & How We're Thinking About Them

| Risk | Our Thinking |
|------|--------------|
| **Xero builds this** | JAX is business-owner focused. Even if they expand, our accountant-centric, multi-ledger positioning is defensible. We complement Xero, not compete. |
| **Xero API changes** | Diversifying to MYOB/QBO. Maintaining App Partner compliance. Building relationships, not just integrations. |
| **Slow accountant adoption** | Leading with compliance risk messaging (fear of penalties) rather than efficiency (nice-to-have). Design partner validation before scaling. |
| **AI accuracy concerns** | Human-in-the-loop design. AI assists, accountants approve. Full audit trails. Conservative automation—we'd rather miss an insight than create a false positive. |

---

## Early Validation

We've spoken with accountants across different practice sizes and consistently hear the same frustrations:

> *"I need to see all my clients at once, not click through 120 separate files."*

> *"I spend more time chasing clients for data than actually doing the BAS."*

> *"By the time I find an issue, I'm already against the deadline."*

> *"I want to grow my practice, but I'm already working 60-hour weeks during BAS season."*

> *"The tools I use were built for business owners, not for accountants managing dozens of clients."*

These aren't edge cases—they're the norm. And they represent a significant opportunity to improve how an entire industry works.

---

## The Team

We're a small team with deep experience in [placeholder - add relevant background: fintech, accounting software, B2B SaaS, Australian tax compliance, etc.].

We understand both the technical challenges of building integrations with accounting platforms and the operational realities of running an accounting practice.

---

## What We're Looking For

We're currently in the early stages of development and seeking:

- **Design partners** — Accounting firms (20-100 BAS clients, Xero-primary) willing to provide feedback and test early versions
- **Strategic advisors** — People with deep experience in Australian accounting, fintech, or B2B SaaS
- **Investment conversations** — For the right partners who share our vision and can help us move quickly through the market window

If any of these resonate, we'd love to have a deeper conversation.

---

## Get in Touch

**Suren**
suren@kr8it.com

---

*December 2024*
