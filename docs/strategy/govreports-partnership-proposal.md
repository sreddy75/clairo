# Partnership Proposal — Clairo × GovReports

**Your 13 API Capabilities × Our 4-Layer Platform**
*BAS Lodgement Is Just the Entry Point*

Prepared by: Suren | Founder, Clairo
suren@kr8it.com | clairo.com.au
26 March 2026 | Confidential

---

## Executive Summary

Most partnership proposals start with "we need BAS lodgement." This one doesn't. Because BAS lodgement is *one workflow* inside a platform that has **dozens**.

**Clairo** is a four-layer practice operating system for Australian accounting practices. We've built: a compliance platform covering BAS, GST, PAYG, and data quality scoring; a business owner portal with document collection and mobile app; an AI intelligence layer with specialist agents and a comprehensive Australian tax knowledge base; and a proactive advisory engine that generates alerts, action items, and risk scores across the entire client portfolio.

Your API services include **13 capabilities**: 8 ATO form types and 5 ATO Online Services. What makes this partnership different is that **your data services feed every layer of our platform, not just lodgement**. Your Lodgement List powers our compliance dashboard. Your Income Tax Account data feeds our AI alert engine. Your ATO Communications replace three planned engineering workstreams. Your Client Update Services feed our data quality scoring. This isn't an integration — it's a platform-wide dependency.

> **The proposition in one sentence:**
>
> Clairo doesn't just lodge forms through GovReports. It consumes the entire GovReports API surface — across all four platform layers, dozens of workflows, and every practice it onboards. Every feature we ship drives more volume through your infrastructure. Every practice we onboard becomes a paying GovReports subscriber. And we build it all — zero engineering effort on your side.

---

## What Clairo Actually Is: A Four-Layer Platform

Most conversations about Clairo focus on BAS. That's Layer 1. Here's the full picture:

| Layer | What It Does | Key Capabilities | GovReports API Used |
|-------|-------------|-----------------|-------------------|
| **Layer 1** — Core Compliance | End-to-end compliance workflows from data ingestion through lodgement | BAS/IAS preparation, GST calculation, PAYG withholding, variance analysis, data quality scoring, lodgement tracking | **All 8 form types** + Activity Statement Summary |
| **Layer 2** — Client Engagement | Business owner portal with document requests, mobile app, push notifications | Client portal, bulk document requests, auto-reminders, mobile PWA with camera capture, offline support | **Income Tax Account** (debt alerts surfaced to clients) |
| **Layer 3** — AI Intelligence | Specialist AI agents powered by a comprehensive Australian tax knowledge base | Compliance agent, quality agent, strategy agent, insight agent, client-context chat, 50K+ vector knowledge base | **ATO Communications** + Client Update Services (structured data for AI context) |
| **Layer 4** — Proactive Advisory | Automated insight generation, action items, trigger-based alerts across the full client portfolio | Compliance risk scoring, cash flow warnings, deadline alerts, audit risk indicators, bulk portfolio monitoring | **Lodgement List** + Income Tax Account (live data for proactive alerts) |

**This is why BAS lodgement undersells the opportunity.** Lodgement is one workflow in Layer 1. But your ATO Online Services power Layers 2, 3, and 4 — the features that make practices adopt the platform, stay permanently, and expand their usage.

---

## How GovReports Data Feeds Every Layer

Each of your 5 ATO Online Services creates value across multiple Clairo layers simultaneously. Below is what this looks like for a single practice.

### 1. Lodgement List → Practice Compliance Dashboard

**The problem:** The Tax Practitioners Board requires an 85% on-time lodgement rate. Falling below triggers sanctions and potential deregistration. No tool currently shows this metric live.

**What Clairo builds:** A real-time compliance gauge ("78% lodged — target 85% by 15 May"), per-client lodgement verification against ATO records, and AI-powered alerts when the practice trends below threshold. Feeds our automated trigger system for escalation.

**Sync frequency:** Daily per practice. This is a background heartbeat — always running, always current.

### 2. Activity Statement Summary → Reconciliation & Quality Engine

**The problem:** After lodgement, no automated way to verify calculated figures against ATO's records. Discrepancies go undetected for quarters.

**What Clairo builds:** Post-lodgement reconciliation comparing Clairo's calculations against ATO summaries. Flags discrepancies automatically. Feeds our data quality scoring engine (which scores each client 0–100% on BAS readiness) and pre-fills data for faster next-period preparation.

**Sync frequency:** Per client per quarter, triggered after each lodgement. Scales naturally with practice size.

### 3. Income Tax Account → AI-Powered Debt Monitor

**The problem:** Client ATO debts accrue General Interest Charge daily. Accountants only discover debts weeks too late.

**What Clairo builds:** Proactive debt monitor showing client ATO balances by obligation type. Overdue flags and GIC warnings surface through our insight engine and push to accountants via alerts. For practices using our client portal, debt alerts surface to business owners — turning reactive debt management into proactive advisory (a billable service for the practice).

**Sync frequency:** Weekly per client. A practice with 100 clients generates a steady, recurring call pattern.

### 4. ATO Client Communication → Structured Communications Hub

**The problem:** ATO correspondence arrives fragmented via email and portal. Easy to miss, impossible to track systematically across a portfolio.

**What Clairo builds:** Structured communications hub pulling ATO correspondence directly into per-client tabs and practice-wide alert views. Feeds our AI agents (which contextualise correspondence against client data) and our action item system (which tracks required responses with deadlines). This single capability replaces three engineering workstreams we had planned around email-based parsing.

**Sync frequency:** Daily per practice. One of the highest-value services for retention — once practices see ATO comms inside Clairo, they don't go back.

### 5. Client Update Services → Practice Health Check

**The problem:** ATO's client list drifts out of sync with practice management records. Missing clients create compliance risk.

**What Clairo builds:** Automated reconciliation of ATO's client list against Clairo's records. Flags mismatches. Feeds multi-client dashboard and data quality scoring. Essential for accurate 85% lodgement rate calculation.

**Sync frequency:** Monthly per practice. Low-frequency but foundational — it underpins the accuracy of everything else.

---

## ATO Forms: 8 Lodgement Types Across Our Roadmap

Each form type is a compliance workflow generating recurring lodgement volume through GovReports. These are listed in the order we intend to build them.

### 1. Activity Statements — BAS / IAS Lodgement
- **Clairo Workflow:** End-to-end: data ingestion → automated GST calculation (G1–G11, 1A, 1B, W1, W2) → AI review → variance analysis → approval → one-click lodgement. Includes bulk lodgement and practice-wide workboard.
- **Frequency:** Every client, every quarter (or monthly). The most frequent lodgement obligation in Australian compliance.
- **Phase:** Building now

### 2. TFN Declarations — Employee Onboarding
- **Clairo Workflow:** Client employee onboarding submitted directly from Clairo. Integrates with payroll compliance workflows.
- **Frequency:** Every new employee across every client. Ongoing throughout the year.
- **Phase:** Included in initial build

### 3. TPAR — Contractor Payment Reporting
- **Clairo Workflow:** Automated TPAR: pull contractor payment data, validate, AI review, and lodge. Identified as high-value quick win by practitioner advisors.
- **Frequency:** Annual per client in building, cleaning, courier, IT, and security industries.
- **Phase:** Near-term roadmap

### 4. Fringe Benefits Tax — FBT Return Lodgement
- **Clairo Workflow:** FBT compliance: identify FBT-liable benefits, calculate, prepare, lodge. AI flags common oversights.
- **Frequency:** Annual per applicable client. High-value engagement per return.
- **Phase:** Near-term roadmap

### 5. Single Touch Payroll — Payroll Reporting
- **Clairo Workflow:** STP compliance monitoring and lodgement. Monitors finalisation deadlines across client base.
- **Frequency:** Every pay run for every client with payroll. The highest-frequency lodgement type by nature.
- **Phase:** Medium-term roadmap

### 6. Company Tax Return — Annual Tax Compliance
- **Clairo Workflow:** CTR preparation: financial data, tax adjustments, taxable income calculation, lodgement. AI identifies adjustment oversights.
- **Frequency:** Annual per company client.
- **Phase:** Medium-term roadmap

### 7. Trust Tax Return — Trust Compliance
- **Clairo Workflow:** Trust returns: distributions, beneficiary allocations, trust income calculations. AI validates distribution logic.
- **Frequency:** Annual per trust client. Common in Australian business structures.
- **Phase:** Medium-term roadmap

### 8. SMSF & Partnership — Specialist Returns
- **Clairo Workflow:** SMSF Annual Return and Partnership Tax Return with AI validation of contribution caps and allocations.
- **Frequency:** Annual per SMSF/partnership client.
- **Phase:** Medium-term roadmap

---

## What One Practice Looks Like

Rather than projecting aggregate numbers, here's what happens when a **single typical practice** (80–120 clients) uses Clairo with GovReports:

> **Lodgement activity (8 form types):**
> - Activity Statements lodged quarterly or monthly per client
> - TFN Declarations submitted as employees join client businesses
> - TPAR, FBT, CTR, Trust, SMSF/Partnership returns lodged annually per applicable client
> - STP events triggered every pay run across payroll clients
>
> **ATO data services (5 capabilities, always running):**
> - Lodgement List synced daily — compliance dashboard stays current
> - Activity Statement Summary pulled after each lodgement — reconciliation runs automatically
> - Income Tax Account checked weekly per client — debt monitoring is continuous
> - ATO Communications pulled daily — nothing is missed
> - Client Update Services reconciled monthly — data integrity maintained
>
> **One practice = thousands of API transactions per year, across all 13 capabilities, running continuously.**

The key insight: this isn't one-off lodgement volume. It's **always-on background activity** — data syncs, reconciliation checks, debt monitoring, comms pulls — that runs whether the accountant is actively working or not. And it compounds: as we ship more workflows (Layers 2–4), each practice generates more API activity without needing more practices.

We don't need to promise you 1,000 practices to make this partnership worthwhile. We need to show you what *each one* looks like — and let the maths speak for itself as we grow.

---

## Zero Risk to Your Platform

| Concern | Reality |
|---------|---------|
| *"Does this require platform changes?"* | **No.** We consume your published API as-is. No custom endpoints, no engineering from your team. |
| *"What if Clairo doesn't scale?"* | Your risk is limited to API access. If we don't grow, you've invested nothing. If we do, you gain a high-value channel you didn't have to build. |
| *"Who handles support?"* | **Clairo handles everything.** OAuth, setup, troubleshooting. Practices interact with Clairo. GovReports operates behind the scenes. |
| *"Will this cannibalise existing customers?"* | **No.** Clairo targets next-generation practices — cloud-native, entering the market now. These are net-new customers who wouldn't evaluate GovReports as a standalone product. |
| *"What about competitive risk?"* | **The risk is in not partnering.** If we integrate with a different provider, they gain this entire API surface. GovReports is our first choice — but we will ship ATO connectivity regardless. |

---

## Why This Partnership Makes Sense Now

We're not asking GovReports to bet on market projections. We're asking you to look at what's already changing in the industry:

1. **Generational shift.** 58–65% of current practitioners are over 50. The next generation of practice owners are digital-native and expect integrated platforms, not standalone tools.
2. **AI is becoming table stakes.** 99.6% of Australian accountants have used AI tools. The first platform to offer an integrated AI-to-ATO workflow — where AI reviews, prepares, and lodges — will define the category.
3. **Competitors are moving.** Alternative lodgement providers are offering free access to capture emerging platforms. The window to establish GovReports as the connectivity layer for next-gen practice tools is open now.
4. **Clairo is building now.** We have a working platform in pilot. BAS lodgement is our next engineering milestone. The terms set today shape a relationship that grows with each feature we ship.

---

## Proposed Partnership Structure

We're early-stage and transparent about that. But the economics of this partnership are already clear, because **you've already signalled how you value referrals**. GovReports has indicated willingness to pay a referral fee for each accountant that subscribes through our platform. That's revenue sharing — and it tells us we're aligned on the core premise: Clairo drives paying subscribers to GovReports.

The question is how to structure this so the referral relationship and API access work together rather than against each other. Here are three options:

### Option A: Referral Fee Offsets API Access (Recommended)

GovReports grants Partner API access. Referral fees for each practice Clairo onboards accumulate and are credited against the Partner API cost. Once the API cost is covered, Clairo begins receiving referral fees as cash.

| Element | How It Works |
|---------|-------------|
| **API Access** | Partner API from day one. Clairo builds the integration, handles all support. |
| **Referral Fees** | Per-practice fee credited to a GovReports account. Offsets the Partner API cost. |
| **Break-Even** | Once referral credits cover the API cost, the fee is paid. Everything after is net positive for both sides. |
| **GovReports Risk** | **Zero.** If Clairo doesn't onboard enough practices, GovReports simply pays less in referral fees. The API access costs them nothing in net terms because subscriber revenue exceeds it from the first few practices. |

**Why this works:** It uses GovReports' own referral model as the commercial mechanism. No new fee structure to negotiate — just an offset arrangement using terms you've already proposed. Both sides have skin in the game, and costs align with actual results.

### Option B: Referral Fee Replaces API Fee

No upfront API fee. Clairo gets Partner API access. GovReports pays referral fees per subscriber. The API access is the "investment" and the referral fee is the "return." Each practice Clairo brings in pays GovReports a subscription ($500–800/year) *far exceeding* the referral fee. GovReports is net positive on every single referral.

### Option C: Phased Ramp with Referral Credit

Pilot phase (0–12 months): Partner API access at $0 while Clairo builds and onboards initial practices. Growth phase: referral fees begin, credited against a reduced API rate. Scale phase: full commercial terms, referral fees paid as cash. **Lowest risk for GovReports** — subscriber revenue from day one, API cost deferred until traction is proven.

---

## About Clairo

Clairo is a four-layer AI-powered practice operating system for Australian accounting practices. Our team includes practitioner advisors — a registered tax agent and a practising accountant — who guide every product decision. We're early-stage with a working platform in pilot. ATO connectivity completes our end-to-end offering and is our highest engineering priority.

---

## Next Steps

1. **Align on structure** — We're flexible on terms. The key is getting started.
2. **API access** — Clairo begins development, starting with Activity Statements and TFND.
3. **Pilot** — Prove the model with initial practices. Demonstrate real volume.
4. **Joint review** — Assess results together. Plan next wave of capabilities based on what the data shows.
5. **Scale** — Expand across all 13 capabilities as new workflows go live.

---

> GovReports has built the ATO connectivity layer that the industry relies on. Clairo is building the AI intelligence layer that the next generation of practices will adopt. Together, we create something neither of us can offer alone — and every workflow we ship, across all four platform layers, drives more volume through your infrastructure.
>
> Suren | suren@kr8it.com | clairo.com.au

---

*This document is confidential and intended for GovReports leadership.*
