# TODOS

## P1 — Blocks Implementation

### Observation → Build Decision Gate
**What:** After the 2-hour BAS observation session with Unni, write up findings and compare against plan assumptions before proceeding to build.
**Why:** The observation may reveal the workflow is fundamentally different from advisor walkthroughs. Building without processing observations wastes the insight.
**How:** Write a 1-page observation report: what you saw, what surprised you, what contradicts assumptions, what confirms them. Decide: proceed as planned, adjust scope, or pivot.
**Effort:** XS (human: ~1 hour) | **Priority:** P1 | **Depends on:** Observation session scheduled

## P2 — Needed After Pilot

### Multi-Client Workboard Integration
**What:** Expose the existing WorkboardService in the BAS Draft Pack experience.
**Why:** After single-client pilot validates, practices with 80+ clients need a portfolio view: "Q3 FY2026: 87 clients, 12 prepared, 3 overdue."
**How:** The backend service is already built (`workboard_service.py`). Needs frontend integration.
**Effort:** S (CC: ~1 hour, already built) | **Priority:** P2 | **Depends on:** Single-client pilot validates demand

### Pricing and Willingness-to-Pay Test
**What:** Design a WTP test for the BAS Draft Pack. Define pricing hypothesis, trial structure, and conversion metrics.
**Why:** "At least one practice offers to pay" is a success criterion but there's no price, trial length, or packaging defined.
**Effort:** S (human: ~2 hours) | **Priority:** P2 | **Depends on:** Non-advisor practice pilot

## P3 — Future Considerations

### GovReports Messaging Alignment
**What:** Reconcile the partnership proposal (positions Clairo as 4-layer platform) with the v0.1 positioning (focused BAS tool).
**Why:** If GovReports responds, they'll encounter a different product than described. The v0.1 tool is the entry point to the platform described in the proposal.
**Effort:** XS (human: ~30 min) | **Priority:** P3 | **Depends on:** GovReports response

### Chart of Accounts Drift Detection
**What:** Detect when a client's chart of accounts or tax mappings change between periods, which would make variance analysis misleading.
**Why:** In small practices, account mapping changes quarterly. Prior period comparisons assume consistent mapping.
**Effort:** M (CC: ~3 hours) | **Priority:** P3 | **Depends on:** Variance analysis in production
