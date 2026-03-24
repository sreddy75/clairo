# GovReports Integration Strategy — Closing the Last Mile to ATO

> **Status**: Draft for team alignment
> **Date**: 2026-03-24
> **Author**: Suren (with input from Unni's PRD and prior research)
> **Audience**: Asaf (dev), Unni (tax agent), Vik (accountant), Suren (founder/dev)
> **Decision needed**: Align on priority, phasing, and what to build first

---

## TL;DR

Clairo already does the hard part of BAS — pulling Xero data, calculating GST, variance analysis, review, and approval. But the accountant still has to leave Clairo and manually lodge in the ATO portal. That's our biggest gap.

GovReports has a **free Developer API** that lets us close this gap by submitting BAS directly to the ATO from within Clairo. This is the single fastest path to a monetisable, differentiated product.

This document lays out what we can build now (free), what we can build later (paid), and how it all fits into what we've already built.

---

## The Gap We're Closing

Here's what an accountant experiences in Clairo today:

```
Step 1: CALCULATE
  Clairo pulls data from Xero, calculates GST fields (G1-G11, 1A, 1B)
  and PAYG withholding (W1, W2). Shows the total payable/refund.

Step 2: REVIEW
  Accountant reviews the figures. AI highlights anomalies.
  Tax code resolution catches transactions with missing/wrong codes.

Step 3: ADJUST
  Manual corrections if needed. Each adjustment recorded with a
  reason for the audit trail.

Step 4: APPROVE
  Senior accountant approves the BAS.

Step 5: RECORD LODGEMENT  ← THE PROBLEM
  ┌──────────────────────────────────────────────────────────┐
  │  Accountant LEAVES Clairo.                               │
  │  Logs into ATO portal (or Xero, or GovReports directly). │
  │  Manually enters the same BAS figures Clairo calculated. │
  │  Comes back to Clairo.                                   │
  │  Records that they lodged, when, and how.                │
  │  Pastes in the ATO reference number.                     │
  └──────────────────────────────────────────────────────────┘
```

Step 5 is manual, error-prone, non-billable time. Multiply by 100+ clients per quarter and it's hours of work that Clairo should be doing automatically.

We also have a **Lodgements Workboard** — a practice-wide view showing all clients' BAS status (overdue, due this week, lodged, not started). It works well but only knows what the accountant tells it. It can't verify against the ATO whether something was actually lodged.

---

## What GovReports Offers

GovReports is the 1st ATO-certified cloud SBR app (since 2010). Used by PwC, EY, CumulusTax, TaxToday. Their API sits between us and the ATO's SBR2 protocol — which is complex, archaic, and not something we should build ourselves.

There are **two API tiers** with very different economics:

### Developer API — Free to Clairo

| | Detail |
|---|---|
| **Cost to us** | $0 |
| **Practice requirement** | Each practice needs their own GovReports subscription ($44-294/mo) |
| **Lodgement forms** | Activity Statements (BAS/IAS), TFND, SMSFAR, PAYG |
| **ATO Online Services** | Not included |
| **Lodgement limit** | Per practice's GovReports plan |
| **White-label** | GovReports does not appear as the developer |
| **Auth** | OAuth 2.0, 20-min token expiry, IP address auth |

### Partner API — ~$30K/yr (unconfirmed)

| | Detail |
|---|---|
| **Cost to us** | ~$30K/yr (needs negotiation with GovReports) |
| **Practice requirement** | None — GovReports is invisible to them |
| **Lodgement forms** | Everything above PLUS STP, Tax Returns (Company, Trust, SMSF, Partnership), TPAR, FBT |
| **ATO Online Services** | Lodgement List, Activity Statement Summary, Income Tax Account, ATO Client Communications, Client Update Services |
| **Lodgement limit** | Unlimited |

### What This Means for Us

**We cannot afford the Partner API right now.** That's fine — the Developer API gives us the most important capability for free: **direct BAS/IAS lodgement**.

Here's what maps to which API tier:

| Capability | Developer API (free) | Partner API (~$30K/yr) |
|---|:---:|:---:|
| Direct BAS lodgement from Clairo | **Yes** | Yes |
| Direct IAS lodgement from Clairo | **Yes** | Yes |
| TFND lodgement | **Yes** | Yes |
| PAYG lodgement | **Yes** | Yes |
| 85% lodgement rate tracking | No | **Yes** |
| ATO correspondence feed | No | **Yes** |
| Client debt/liability monitoring | No | **Yes** |
| ATO client list reconciliation | No | **Yes** |
| Tax return lodgement (ITR) | No | **Yes** |
| TPAR, FBT, STP lodgement | No | **Yes** |

The top 4 rows — the ones we get for free — are enough to ship a monetisable product.

---

## What We Build Now: Direct BAS/IAS Lodgement

### The Change (Minimal, High Impact)

The accountant's workflow stays **identical** through steps 1-4. The only change is step 5:

```
TODAY                                  WITH GOVREPORTS
─────                                  ───────────────
Approve → "Record Lodgement"           Approve → "Lodge to ATO"  ← NEW primary CTA
           (manual recording)                     ↓
           Accountant picks:                Clairo submits BAS via API
           - ATO Portal                           ↓
           - Xero                           ATO confirms receipt
           - Other                                 ↓
                                            Status auto-updates to "Lodged"
                                            ATO reference number auto-populated

                                           Still available:
                                           "Record Manual Lodgement"
                                           (for practices not using GovReports)
```

### What the Practice Needs to Do (One-Time Setup)

1. Sign up for a GovReports subscription ($44-294/mo depending on practice size)
2. Complete a one-off ATO software nomination (standard process)
3. Connect their GovReports account to Clairo (OAuth flow — similar to how they connected Xero)

After setup, lodging a BAS is one click.

### Why the GovReports Subscription Cost Isn't a Problem

Practices charge **$500-2,000+ per BAS return**. A $44-294/mo GovReports subscription is noise.

| Practice Size | Likely GovReports Plan | Annual Cost | Per Client/Month |
|---|---|---|---|
| Small BAS agent (15 clients) | BAS Starter $44/mo | $528/yr | ~$2.93 |
| Mid BAS agent (50 clients) | Tax Starter $53/mo | $636/yr | ~$1.06 |
| Growing practice (200 clients) | Tax Growing $117/mo | $1,404/yr | ~$0.59 |
| Large practice (unlimited) | Tax Professional $294/mo | $3,528/yr | Pennies |

Most practices already pay for a lodgement tool (GovReports, LodgeiT, or similar). For those already on GovReports, the setup is just connecting their existing account. For those on other tools, GovReports is competitively priced and the switch is justified by the Clairo integration.

### Where It Fits in the Existing UX

**Lodgement Modal** — today this modal asks the accountant to record how they lodged (ATO Portal / Xero / Other). We extend it:

```
┌─────────────────────────────────────────────────────┐
│  Lodge BAS — Client ABC Pty Ltd — Q2 FY2026         │
│                                                     │
│  Total Payable: $12,450.00                          │
│                                                     │
│  ┌─────────────────────────────────────────────┐    │
│  │  ⚡ Lodge to ATO via Clairo    [PRIMARY]    │    │
│  │  One-click submission. Requires GovReports  │    │
│  │  connection.                                │    │
│  └─────────────────────────────────────────────┘    │
│                                                     │
│  ── or record a manual lodgement ──                 │
│                                                     │
│  ○ ATO Portal   ○ Xero   ○ Other                   │
│  Date: [________]  Reference: [________]            │
│                                                     │
│              [Cancel]    [Confirm]                   │
└─────────────────────────────────────────────────────┘
```

If the practice hasn't connected GovReports yet, the primary button becomes a setup prompt: "Connect GovReports to enable one-click lodgement →"

**Lodgements Workboard** — gains a bulk action: "Lodge Selected to ATO" for batch lodgement of multiple approved BAS sessions at once. This is the killer feature for BAS season when practices are lodging dozens per day.

**BAS State Machine** — adds one intermediate state:

```
CURRENT:   approved → lodged (instant, manual recording)
NEW:       approved → submitting → lodged (async, ATO confirmation)
                         ↓
                    submission_failed (retry or fall back to manual)
```

### What This Does NOT Include (Developer API Limitations)

To be transparent with the team — the Developer API **only handles lodgement**. It does not give us:

- **85% lodgement rate tracking** — we can't pull the practice's overall ATO lodgement position. Our workboard will still track based on what's lodged through Clairo, but can't see lodgements made via other tools. (Partner API needed)
- **ATO correspondence** — we can't pull ATO notices, letters, or communications. (Partner API needed)
- **Client debt/liability data** — we can't show ATO account balances or overdue debts. (Partner API needed)
- **ATO client list reconciliation** — we can't compare our client list against the ATO's. (Partner API needed)

These are all valuable features (detailed in Unni's PRD), but they require the Partner API which costs ~$30K/yr. We park them for now and revisit once revenue justifies the investment.

---

## What We Build Later: The Partner API Roadmap

Once we have paying customers and revenue to justify ~$30K/yr, the Partner API unlocks four additional capabilities. These are documented here so the team understands the full vision, but **none of this is Phase 1 scope**.

### Future Feature: 85% Lodgement Tracking

**Extends**: Existing Lodgements Workboard at `/lodgements`

Adds a live practice-wide lodgement rate gauge ("78% lodged — target 85% by 15 May"), ATO-confirmed status per client, and mismatch detection. The TPB 85% rule is the number that keeps practice principals up at night. No current tool shows this live.

### Future Feature: ATO Communications Hub

**Replaces**: ATOtrack (Specs 026-028)

Instead of connecting email and using AI to parse ATO notices, we pull structured correspondence data directly from the ATO via API. Per-client correspondence tab plus a practice-wide alert view. Cleaner, more reliable, and replaces 3 planned specs with one integration.

### Future Feature: Proactive Liability & Debt Monitor

**New surface**: Dashboard widget + per-client detail

Shows each client's ATO balance by obligation type, overdue flags, GIC accrual warnings, and payment arrangement tracking. Plugs into our existing trigger system for automated alerts.

### Future Feature: ATO Client List Reconciliation

**New surface**: Practice health check view

Compares ATO's client list against Clairo's. Flags clients in ATO but not in Clairo, in Clairo but not in ATO, and detail mismatches. Also requires XPM API integration for full value.

### Future Lodgement Forms

Partner API also covers: Tax Returns (Company, Trust, SMSF, Partnership), STP, TPAR, FBT. These map directly to gaps in Vik's service map — particularly TPAR (flagged as a "quick win") and FBT.

---

## Impact on Current Roadmap

### What Changes

```
CURRENT ROADMAP                           PROPOSED CHANGE
───────────────                           ───────────────

Phase E.5: ATOtrack (Specs 026-028)       Phase E.5: GovReports BAS Lodgement
  ├── 026: Email OAuth                      └── Spec 049: GovReports Foundation
  ├── 027: ATO Parsing                              + Direct BAS/IAS Lodgement
  └── 028: Workflow Integration

  3 specs, email-based, AI parsing          1 spec, API-based, lodgement-focused
  Covers: ATO correspondence only           Covers: E2E BAS lodgement
  Revenue impact: Indirect                  Revenue impact: DIRECT
```

### What's Deferred

| Spec | Status | Reason |
|---|---|---|
| 026: Email OAuth | **Deferred** | GovReports Partner API will provide ATO comms via structured API when affordable. Email integration may still be needed for non-ATO correspondence — revisit later. |
| 027: ATO Parsing | **Deferred** | Superseded by structured ATO data from Partner API. No AI parsing ambiguity. |
| 028: ATOtrack Workflow | **Deferred** | Depends on 026/027. The workflow integration pattern still applies when we build the comms hub. |

### What's Added

| Spec | Phase | Depends On |
|---|---|---|
| **049: GovReports Foundation + BAS Lodgement** | **Now** (Developer API, free) | Existing BAS workflow (Specs 009/011) |
| 050: Practice Compliance Dashboard | Later (Partner API, ~$30K/yr) | Spec 049 foundation |
| 051: ATO Communications Hub | Later (Partner API, ~$30K/yr) | Spec 049 foundation |

**Spec 049 is the only one we need to build right now.** Specs 050 and 051 are defined here for vision but won't be specced until we have revenue and can justify the Partner API cost.

---

## The Pitch This Enables

For the team to understand why this matters commercially:

**Before GovReports integration:**
> "Clairo helps you prepare BAS faster with AI-powered review and variance analysis."
> (Nice to have. Hard to quantify. Accountant still does the tedious part.)

**After GovReports integration:**
> "Prepare and lodge BAS to the ATO without leaving Clairo. One click."
> (Complete workflow. Quantifiable time saving. Clear before/after.)

The before pitch is a tool. The after pitch is a solution.

---

## Relationship to Vik's Service Map

For context, Vik's service map identified 31 services across 5 pillars. Clairo currently covers 5 fully, 7 partially, and has 15 gaps. GovReports integration directly addresses the biggest gap in Pillar 2 (Compliance Reporting) and Pillar 4 (Software & Tools):

| Gap from Vik's Map | How GovReports Addresses It |
|---|---|
| **Tax Forms** — "No tax form generation. BAS data is prepped but not submitted to ATO." | **Phase 1 (now)**: Direct BAS/IAS submission via Developer API |
| **TPAR reporting** — flagged as a quick win | **Future (Partner API)**: TPAR lodgement included |
| **FBT** — knowledge base only, no return workflow | **Future (Partner API)**: FBT lodgement included |
| **Communication Tools** — email integration planned | **Future (Partner API)**: ATO comms via structured API |
| **IAS workflow separation** — flagged as pilot blocker | **Phase 1 (now)**: IAS lodgement supported alongside BAS |

---

## What We Need to Decide Together

### 1. Is direct BAS lodgement the right first feature?

From a practice perspective, is "prepare and lodge BAS without leaving Clairo" the thing that would make a practice pay for Clairo? Or is something else more urgent?

**Vik, Unni**: What would make you (or a practice you know) pay for Clairo tomorrow?

### 2. Is the GovReports pass-through model acceptable for early adopters?

With the Developer API, practices need their own GovReports subscription ($44-294/mo). This is standard — most practices already pay for a lodgement tool. But it does mean the setup has an extra step.

**Vik**: Would your practice find it reasonable to connect a GovReports account, similar to how you connect Xero? Or is the extra subscription a turn-off?

### 3. Are we comfortable deferring ATOtrack (Specs 026-028)?

The four features in Unni's PRD (comms, 85% tracking, debt monitoring, client reconciliation) all require the Partner API we can't afford yet. The email-based ATOtrack approach in Specs 026-028 could partially address the comms use case, but it's more engineering effort for a less reliable result.

**Unni**: Is ATO correspondence monitoring critical for pilot, or can we defer it until we can afford the Partner API? Is there correspondence that only arrives by email and wouldn't appear in the GovReports API?

### 4. Should IAS be in Phase 1 scope?

The GovReports Developer API supports IAS (Instalment Activity Statements) alongside BAS. Vik's service map flagged IAS separation as a pilot blocker.

**Vik**: How many of your clients lodge IAS vs BAS? Is it enough to warrant including IAS in the first build?

### 5. Which pricing tier should ATO lodgement live in?

Options:
- **All tiers** — maximum adoption, lodgement becomes a core feature
- **Professional and above** — premium differentiator, justifies higher price
- **Separate add-on** — practices opt in and pay extra

**Team**: Given that the practice is also paying for GovReports separately, what feels right?

---

## Next Steps

| Step | Owner | When |
|------|-------|------|
| Review this document | All | This week |
| Respond to the 5 decision points above (Slack or async) | All | By end of week |
| Explore GovReports Developer API sandbox | Asaf / Suren | Parallel with review |
| Sign up for Developer API access | Suren | This week |
| Draft Spec 049 (Foundation + BAS Lodgement) | Suren | After team alignment |
| Follow up with Tiana on Partner API pricing (for future planning) | Suren / Unni | After Phase 1 shipped |

---

## Reference Documents

| Document | Location | What It Covers |
|----------|----------|----------------|
| ATO Integration Research | `docs/ato-integration-strategy.md` | Full evaluation of all 4 ATO integration paths (GovReports, DSP+Gateway, Full DIY, Wait) |
| Unni's PRD | Shared separately | Four GovReports features with practitioner business case |
| Vik's Service Map | Shared separately | Practice service coverage scorecard (5 built, 7 partial, 15 gaps) |
| Service Map Workshop | Shared separately | Detailed gap analysis across all 5 service pillars |
| GovReports API Brochure | Shared separately | Developer vs Partner API comparison |
| BAS Workflow Spec | `specs/009-bas-workflow/spec.md` | Current BAS preparation workflow |
| Lodgement Spec | `specs/011-interim-lodgement/spec.md` | Current lodgement recording and tracking |
| ATOtrack Specs (deferred) | `specs/026-028-*/spec.md` | Email-based ATO correspondence approach |
| GovReports Developer API Sandbox | `sandbox-devapi.govreports.com.au/swagger` | API documentation and test environment |
| GovReports Contact | Tiana Tran — tiana@govreports.com.au — 0403 333 880 | Our contact for API access |
