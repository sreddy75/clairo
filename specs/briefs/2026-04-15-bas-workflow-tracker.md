# Brief: BAS Workflow Tracker — Practice Management Layer

**Date**: 2026-04-15
**Source**: Gap analysis of Vik Dhawan's BAS workflow Excel ("BAS Workflow Lucas and Co") + Unni & Vik huddle feedback (13 April 2026)
**Author**: Suren (product), with codebase analysis

---

## Problem Statement

Vik and Unni each manage ~280 BAS/IAS obligations per quarter using Excel spreadsheets. They've been trying to alpha-test Clairo but can't replace their Excel because Clairo's BAS workflow is built around individual client BAS preparation — it doesn't solve the practice-level management job of "which of my 280 clients are ready, who's handling what, and what's blocked."

The platform has a sophisticated BAS processing engine (tax code classification, AI suggestions, Xero sync, lodgement workflow). What's missing is the "practice management" layer on top — the daily triage and team coordination that accountants do before they even open a single client's BAS.

**Key principle**: Solve the job, don't replicate the spreadsheet. The Excel has 10 columns but only 3 represent genuinely missing capabilities. The rest are manual workarounds for things Clairo can auto-derive from data it already has.

---

## Users

- **Primary**: Accountants (practice owners like Vik/Unni and their team members — Pawan, Aarti, Anil)
- **Context**: Australian accounting practices managing quarterly BAS obligations for their client base. Team of 2-5 people. Mix of Xero, QuickBooks, MYOB, and email-based clients.

---

## Jobs to Be Done

### Job 1: Team Assignment (MUST HAVE)

**The need**: "I need to assign each client to a team member so we know who's responsible for whose BAS."

**Why the platform can't auto-derive this**: It's a human decision. Only the practice owner knows that Pawan handles the QB clients and Aarti handles the Xero ones.

**Current state**: 
- `PracticeUser` model exists with roles (admin, accountant, staff)
- `listTenantUsers()` API exists in frontend
- Client import page (`/clients/import`) already has team member assignment UI with `assigned_user_id`
- But: assignment doesn't persist beyond the import step. No `assigned_user_id` on `XpmClient` or `XeroConnection`. No way to filter the dashboard by team member.
- Vik's minimum requirement: "add at least 1 team member"

**What to build**:
- Persistent `assigned_user_id` on the client record (FK to `practice_users.id`)
- Carry the assignment from bulk import through to the client model
- "Assigned to" column on the dashboard client table
- "My clients" filter on the dashboard (default view for non-admin users)
- Ability to reassign clients (dropdown on client detail or bulk reassignment)

**Reference**: Vik's team is 4 people: Vik, Pawan, Aarti, Anil. Each handles a subset of the ~280 clients. The allocation column in his Excel is one of the most-used for daily triage.

---

### Job 2: Client Exclusion (MUST HAVE)

**The need**: "Some clients don't need a BAS this quarter. I need to mark them so they don't clutter my working list."

**Why the platform can't auto-derive this**: The reasons are varied and human-known — GST registration cancelled, entity is dormant, a separate bookkeeper handles lodgement, client has left the practice. Some of these could eventually be detected from data signals, but not reliably enough today.

**Current state**:
- No exclusion mechanism. Every active client appears in the dashboard regardless of whether they need a BAS.
- `BASSessionStatus` has no "not required" state
- In Vik's Excel this is the "Not required" value in the status column

**What to build**:
- A way to mark a client as "excluded" or "not required" for a specific quarter (not permanently — they might need BAS next quarter)
- Excluded clients should not count in summary card totals (Portfolio Health, Ready to Lodge, etc.)
- Should be reversible (can un-exclude)
- Optional: reason field (dormant, lodged externally, GST cancelled, other)
- Excluded clients should still be accessible if you filter for them, just hidden from the default working view

**Design note**: This is NOT a new BAS session status. It's a property of the client-quarter relationship. A client can be excluded for Q3 but active for Q4.

---

### Job 3: Persistent Client Notes (SHOULD HAVE)

**The need**: "When my team member opens a client's BAS, they need to know how this client works — who does the bookkeeping, what software they use, any special instructions."

**Why the platform can't auto-derive this**: It's tribal knowledge. "Client does the bookkeeping, usually sends on the last day." "We do the coding. Bank statements pending." "He provided the bank statement, needs to upload into QB. Just let him know."

**Current state**:
- `BASSession.internal_notes` — per-session notes that reset each quarter
- `SuggestionNoteEditor` — notes on individual tax code suggestions
- `AgentTransactionNote` — agent notes on individual transactions
- No persistent per-client notes that carry across quarters

**What to build**:
- A `notes` text field on the client record (persistent across quarters)
- Prominently displayed when a team member opens a client's BAS session — this is the first thing they should see
- Editable by any practice user
- Optional: last edited timestamp and by whom
- The existing `BASSession.internal_notes` should remain for quarter-specific context

**Examples from Vik's Excel** (these are real notes):
- "Client does the bookkeeping"
- "We do the bookkeeping, and client uploads the sales invoices in the link"
- "He provided the bank statement, needs to upload into QB, Just let him know that you have uploaded the statement. He will do the coding"
- "Payg I - check each quarter, abn numbers requested"
- "We do the coding. Coding is completed. Bank statements pending"
- "Tammy always provides the Bank stmt in excel by email then she comes in to handover the invoices"
- "Monthly BAS"
- "Reminder Sent 19/02/2026"
- "GST cancelled"
- "Client does the Coding"
- "ABN required for subcontractors"

---

### Job 4: Non-Xero Client Visibility (SHOULD HAVE)

**The need**: "I manage 280 clients. Only about 60% are on Xero. I need to see ALL my clients in one place, even if Clairo can't pull data for the non-Xero ones."

**Current state**:
- Dashboard and workboard only show Xero-connected clients
- ~40% of Vik's clients use QB, MYOB, or send bank statements by email
- These clients are completely invisible to Clairo
- The 6 April meeting decision parked QB/MYOB integrations for post-launch

**What to build**:
- `accounting_software` field on the client record (enum: xero, quickbooks, myob, email, other, unknown)
- Auto-set to `xero` when a Xero connection exists
- Non-Xero clients should appear in the dashboard client table with a clear indicator that they're not connected
- For non-Xero clients, BAS status can only be manually tracked (session status progression) — no auto-derived readiness
- This ensures the dashboard is a complete view of the practice, not just the Xero slice

**Important constraint**: We are NOT building QB/MYOB integrations. This is about visibility and completeness of the client list. The accountant can still do their BAS work for these clients outside Clairo — they just need to see them in the list so nothing falls through the cracks.

---

### Job 5: Smarter Readiness Signals (SHOULD HAVE)

**The need**: "Don't tell me a client is 'Ready' when they have 50 unreconciled bank transactions."

**Current state**:
- `BASStatus` is derived in `clients/repository.py` (lines 191-205) from: invoice count, transaction count, sync freshness
- Does NOT factor in reconciliation status
- `XeroBankTransaction.is_reconciled` field exists and is indexed
- Asaf's recent fix surfaces unreconciled transactions in the parked section on the BAS page (per-client level)
- But at the dashboard level, a client with many unreconciled transactions can still show as "Ready"

**What to build**:
- Include unreconciled transaction count in the `BASStatus` derivation logic
- If a client has significant unreconciled transactions (threshold TBD — maybe > 5 or > 10), status should be `NEEDS_REVIEW` or a new `NOT_READY` status, not `READY`
- Optionally: show unreconciled count as a data point on the dashboard client table row (like Quality score is shown today)
- The "Attention Needed" insight cards on the dashboard could also flag clients with high unreconciled counts

**Design note**: The threshold should probably be configurable per practice, since some clients always have a few unreconciled items that the accountant knows about. But a sensible default is fine for alpha.

---

## What NOT to Build

These things exist in Vik's Excel but are already solved by Clairo or are not needed:

| Excel column | Why not to build it |
|---|---|
| Status (Not in / Work in / Completed) | Auto-derived from `BASStatus` + `BASSessionStatus` progression |
| Date In | `last_full_sync_at` + `ClassificationRequest.submitted_at` already capture data arrival for Xero clients. For non-Xero, session status progression serves as manual trigger. |
| TFN/ABN display | `XpmClient.abn` exists. Low priority cosmetic addition. |
| BAS vs IAS type | System adapts implicitly based on data present (no GST = IAS sections empty). Could add as a label later but doesn't change workflow. |
| File Code | `xpm_client_id` exists for XPM practices. Display could be improved but not a workflow gap. |
| SMS notifications | Out of scope for now. In-app + email notifications exist. SMS is a long-term enhancement. |

---

## Technical Context

**Key models involved**:
- `XpmClient` (backend/app/modules/integrations/xero/models.py) — the client record, likely home for `assigned_user_id`, `notes`, `accounting_software`, exclusion flag
- `PracticeUser` (backend/app/modules/auth/models.py) — team members with roles
- `BASSession` (backend/app/modules/bas/models.py) — per-quarter BAS work session
- `BASPeriod` (backend/app/modules/bas/models.py) — quarterly period definitions
- `XeroBankTransaction` (backend/app/modules/integrations/xero/models.py) — has `is_reconciled` field

**Key services/endpoints**:
- `clients/repository.py` lines 191-205 — `BASStatus` derivation logic (needs reconciliation signal)
- `bas/workboard_service.py` — lodgement workboard (may need to join XpmClient for complete client list)
- `clients/service.py` — client detail response (needs new fields)
- Dashboard page (`frontend/src/app/(protected)/dashboard/page.tsx`) — client table needs new columns

**Existing patterns to follow**:
- Bulk import page already has team member assignment UI with `assigned_user_id` dropdown
- `BASSession.internal_notes` pattern for text notes
- `XeroConnectionStatus` enum pattern for new enums
- Dashboard filter tabs (All, Needs Review, Ready, No Activity) — extend with team filter

---

## Success Criteria

1. Vik can see all his ~280 clients (including non-Xero) in the dashboard for a given quarter
2. Vik can assign clients to team members and filter by "My clients"
3. Vik can mark clients as "not required" for a quarter and they disappear from the active working list
4. When a team member opens a client's BAS, they see persistent notes about how to handle that client
5. The dashboard doesn't show a client as "Ready" when it has significant unreconciled transactions
6. Vik says: "I can close my Excel spreadsheet"

---

## Open Questions

1. Should `assigned_user_id` live on `XpmClient` (permanent assignment) or on `BASSession` (per-quarter assignment), or both? Vik's allocation is mostly permanent with rare quarterly overrides.
2. What's the right threshold for unreconciled transactions before readiness drops from "Ready" to "Needs Review"? Need input from Vik/Unni.
3. How should non-Xero clients be added to Clairo? Currently clients only enter via Xero OAuth. Need a manual "add client" flow or CSV import for QB/MYOB clients.
4. Should client exclusion be a flag on the client record or a separate junction table (client_id + quarter + exclusion_reason)? Needs to be per-quarter.
