# Feature Specification: AI Tax Code Resolution for BAS Preparation

**Feature Branch**: `046-ai-tax-code-resolution`
**Created**: 2026-03-14
**Status**: Draft
**Input**: Accountant user testing revealed that BAS calculations silently exclude transactions with unmapped tax codes (NONE, BASEXCLUDED, unknown), producing understated BAS figures. This feature adds AI-powered tax code suggestion and resolution so accountants can identify, review, approve, and resolve all unmapped transactions before approving a BAS for lodgement.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See What's Missing from the BAS (Priority: P1)

After a Xero sync and BAS calculation, the accountant opens the BAS tab for a client and immediately sees how many transactions were excluded due to missing or unrecognised tax codes, along with the total dollar impact on the BAS.

**Why this priority**: Without visibility into excluded transactions, the accountant cannot trust the BAS figures. This is the root cause of the problem reported in user testing — the BAS looks complete but is silently understated. Everything else depends on this.

**Independent Test**: Can be fully tested by importing Xero data containing transactions with NONE/BASEXCLUDED tax types and verifying the BAS review screen displays a clear count and dollar impact of excluded items.

**Acceptance Scenarios**:

1. **Given** a BAS calculation has been run for a quarter, **When** the accountant opens the BAS tab, **Then** a prominent banner displays the count of excluded transactions and the total excluded dollar amount (e.g., "23 transactions ($14,280) excluded from this BAS — tax codes needed").
2. **Given** all transactions for a quarter have valid tax codes, **When** the accountant opens the BAS tab, **Then** no exclusion banner is shown.
3. **Given** excluded transactions exist, **When** the accountant clicks the banner, **Then** a detailed view opens showing each excluded transaction with its description, amount, account, date, and source (invoice/bank transaction).
4. **Given** the BAS is recalculated after tax codes are resolved, **When** the accountant views the banner, **Then** the excluded count updates to reflect only remaining unresolved items.

---

### User Story 2 - Review and Approve AI Tax Code Suggestions (Priority: P1)

The system automatically generates tax code suggestions for each excluded transaction using available signals (account defaults, historical patterns, cross-client patterns). The accountant reviews these suggestions grouped by confidence level and can approve them individually or in bulk.

**Why this priority**: This is the core value proposition — the AI does the heavy lifting so the accountant doesn't have to manually classify each transaction. Without this, the accountant would need to leave the platform and fix codes in Xero.

**Independent Test**: Can be tested by having unmapped transactions where the account's default tax type is known, verifying the system suggests the correct code, and confirming the accountant can approve the suggestion with one click.

**Acceptance Scenarios**:

1. **Given** an excluded transaction whose account has a known default tax type in Xero, **When** the suggestion engine runs, **Then** the system suggests that default tax type with a confidence indicator (e.g., "High — based on account default").
2. **Given** an excluded transaction whose account has no default but 95% of historical transactions on that account used OUTPUT, **When** the suggestion engine runs, **Then** the system suggests OUTPUT with a confidence indicator (e.g., "High — 95% of prior transactions used this code").
3. **Given** multiple high-confidence suggestions exist, **When** the accountant clicks "Approve All High Confidence", **Then** all high-confidence suggestions are applied in one action.
4. **Given** a suggestion the accountant disagrees with, **When** the accountant clicks the suggestion, **Then** they can select a different tax code from a dropdown of valid options.
5. **Given** a suggestion with low confidence, **When** the accountant views it, **Then** they see the transaction details (description, amount, counterparty, account) and the reasoning behind the suggestion to make an informed decision.
6. **Given** the accountant manually assigns a tax code (overriding or in absence of a suggestion), **When** they confirm, **Then** the assignment is recorded with the same audit trail as an approved suggestion.

---

### User Story 3 - BAS Recalculates After Approvals (Priority: P1)

After the accountant approves tax code suggestions (individually or in bulk), the BAS figures automatically recalculate to include the newly mapped transactions. The accountant sees the updated BAS totals and can proceed through the normal approval workflow.

**Why this priority**: The entire purpose of resolving tax codes is to produce an accurate BAS. If the figures don't update after approvals, the workflow is broken.

**Independent Test**: Can be tested by approving a tax code suggestion for an excluded transaction and verifying the BAS field totals increase by the expected amount.

**Acceptance Scenarios**:

1. **Given** the accountant approves a tax code suggestion mapping a $1,000 purchase to INPUT, **When** the BAS recalculates, **Then** G11 (non-capital purchases) increases by $1,000 and 1B (GST on purchases) increases by the GST component.
2. **Given** multiple suggestions are approved in bulk, **When** the BAS recalculates, **Then** all newly mapped transactions are reflected in the correct BAS fields.
3. **Given** the BAS recalculation completes, **When** the accountant views the variance analysis, **Then** the variance figures reflect the updated totals (compared to the prior period).
4. **Given** all excluded transactions have been resolved, **When** the accountant views the BAS, **Then** the exclusion banner disappears and the session can proceed to approval and lodgement.

---

### User Story 4 - Audit Trail for AI Suggestions and Approvals (Priority: P2)

Every AI suggestion, accountant approval, rejection, and manual override is recorded in a tamper-evident audit trail that satisfies ATO compliance requirements.

**Why this priority**: ATO compliance requires knowing how BAS figures were derived. AI-assisted classification introduces a new type of change that must be traceable — who approved it, when, what the AI suggested vs what was applied, and the confidence basis.

**Independent Test**: Can be tested by approving a suggestion and then viewing the audit log to verify all required fields are captured.

**Acceptance Scenarios**:

1. **Given** the accountant approves an AI suggestion, **When** they view the BAS audit trail, **Then** the entry shows: timestamp, user, transaction reference, original tax code (NONE), suggested tax code, applied tax code, confidence level, suggestion basis (e.g., "account default"), and session context.
2. **Given** the accountant overrides an AI suggestion with a different code, **When** they view the audit trail, **Then** the entry distinguishes the AI suggestion from the manually selected code.
3. **Given** the accountant rejects an AI suggestion without providing an alternative, **When** they view the audit trail, **Then** the rejection is recorded and the transaction remains excluded from BAS.

---

### User Story 5 - Re-sync Conflict Handling (Priority: P2)

When Xero data is re-synced after tax codes have been applied locally, the system detects whether Xero's data has changed and flags any conflicts between the locally applied codes and the incoming Xero data.

**Why this priority**: Without conflict handling, a re-sync could silently overwrite the accountant's approved tax codes, reverting the BAS to its understated state. This protects the accountant's work.

**Independent Test**: Can be tested by applying a tax code locally, modifying the same transaction in Xero with a different tax code, triggering a re-sync, and verifying the system flags the conflict.

**Acceptance Scenarios**:

1. **Given** a tax code was applied locally via AI suggestion, **When** a re-sync imports the same transaction unchanged from Xero, **Then** the locally applied tax code is preserved.
2. **Given** a tax code was applied locally, **When** a re-sync imports the same transaction with a different tax code from Xero, **Then** the system flags the conflict and presents both values to the accountant for resolution.
3. **Given** a tax code was applied locally, **When** a re-sync imports the same transaction with the same tax code now set in Xero, **Then** the local override is cleared (Xero is now the source of truth) and no conflict is shown.

---

### User Story 6 - LLM Classification for Ambiguous Transactions (Priority: P3)

For transactions where account defaults and historical patterns provide insufficient confidence, the system uses an LLM to classify the transaction based on its description, amount, counterparty, and account context.

**Why this priority**: This handles the long tail of transactions that can't be classified by simple pattern matching. It's lower priority because account defaults and historical patterns should resolve the majority of cases.

**Independent Test**: Can be tested by creating a transaction with no account default and no historical pattern, verifying the system sends context to the LLM, and checking the returned suggestion is reasonable.

**Acceptance Scenarios**:

1. **Given** an excluded transaction with no account default and insufficient historical data, **When** the suggestion engine runs, **Then** the system classifies the transaction using an LLM and returns a suggestion with a lower confidence indicator (e.g., "Moderate — AI classification based on transaction details").
2. **Given** an LLM classification, **When** the accountant views the suggestion, **Then** they see the reasoning provided by the LLM (e.g., "This appears to be a GST-inclusive office supply purchase based on the description 'Officeworks stationery'").
3. **Given** the LLM cannot classify a transaction with reasonable confidence, **When** the suggestion is generated, **Then** it is marked as "Manual review required" with no pre-selected tax code.

---

### Edge Cases

- What happens when a transaction has line items with mixed tax codes (some valid, some NONE)? Only the NONE line items should be flagged; valid line items remain unchanged.
- What happens when an account code on a transaction doesn't exist in the local XeroAccount table? The system should flag this as an anomaly and fall through to lower-confidence tiers.
- What happens when the same transaction appears in multiple BAS sessions (e.g., session was duplicated or period overlaps)? Suggestions should be scoped to the BAS session; applying in one session does not automatically apply in another.
- What happens when a transaction has `tax_type: "BASEXCLUDED"` which is intentionally excluded? The system should still surface these for review but clearly indicate the original code was "BAS Excluded" — the accountant may confirm exclusion is correct (dismiss) or reclassify.
- What happens if the accountant approves suggestions but then the BAS session is reopened? Applied tax codes remain; the accountant can re-review and modify if needed.
- What happens when no Xero accounts have been synced yet (no default_tax_type data available)? Tier 1 is skipped; the system falls through to historical patterns, cross-client patterns, and LLM.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST detect all transactions excluded from BAS calculation due to missing, NONE, BASEXCLUDED, or unrecognised tax codes.
- **FR-002**: System MUST display the count and total dollar amount of excluded transactions prominently on the BAS review screen.
- **FR-003**: System MUST provide a detailed view of each excluded transaction showing description, amount, date, counterparty, account code, account name, and source type (invoice/bank transaction/credit note).
- **FR-004**: System MUST generate tax code suggestions for excluded transactions using a tiered confidence approach: account defaults, same-client historical patterns, cross-client patterns within the tenant, and LLM classification.
- **FR-005**: System MUST display a confidence level and basis for each suggestion (e.g., "High — account default", "Moderate — 87% historical match").
- **FR-006**: System MUST allow accountants to approve suggestions individually (one at a time) or in bulk (all high-confidence suggestions at once).
- **FR-007**: System MUST allow accountants to override a suggestion by selecting a different valid tax code from the full list of recognised Xero tax types.
- **FR-008**: System MUST allow accountants to dismiss an excluded transaction (confirm it should remain excluded from BAS) with optional reason.
- **FR-009**: System MUST automatically recalculate BAS figures after tax code approvals, reflecting newly mapped transactions in the correct BAS fields.
- **FR-010**: System MUST record all AI suggestions, approvals, rejections, overrides, and dismissals in the BAS audit trail with timestamp, user, and full context.
- **FR-011**: System MUST preserve locally applied tax codes across Xero re-syncs when the Xero data is unchanged.
- **FR-012**: System MUST detect and flag conflicts when a re-sync brings different tax code data from Xero for a transaction that has been locally modified.
- **FR-013**: System MUST be idempotent — re-running the suggestion engine for the same BAS session MUST NOT create duplicate suggestions or lose previous approvals.
- **FR-014**: System MUST scope all suggestion data to the BAS session, tenant, and connection — no cross-tenant data leakage.
- **FR-015**: System MUST provide LLM-based classification for transactions that cannot be classified by deterministic methods, including a human-readable explanation of the classification reasoning.
- **FR-016**: System MUST prevent BAS approval when excluded transactions remain unresolved, unless the accountant has explicitly dismissed each one.

### Key Entities

- **TaxCodeSuggestion**: A suggested tax code for a specific transaction line item within a BAS session. Captures the suggested code, confidence score, suggestion basis (which tier), the accountant's resolution (approved/rejected/overridden/dismissed), and the applied code if different from suggestion.
- **ExcludedTransaction**: A view/aggregation of all transactions and line items that were excluded from BAS calculation for a given session, with their current resolution status.
- **TaxCodeOverride**: A record of a locally applied tax code that differs from what Xero provides, used to detect and manage re-sync conflicts.

## Auditing & Compliance Checklist *(mandatory)*

### Audit Events Required

- [x] **Data Modification Events**: This feature creates, updates, and resolves tax code suggestions on business-critical BAS data.
- [x] **Compliance Events**: This feature directly affects BAS figures and lodgement readiness.
- [x] **Integration Events**: This feature must handle re-sync conflicts with Xero data.

### Audit Implementation Requirements

| Event Type | Trigger | Data Captured | Retention | Sensitive Data |
|------------|---------|---------------|-----------|----------------|
| tax_code.suggestion_generated | Suggestion engine completes for a session | Session ID, transaction ref, line item index, suggested code, confidence score, suggestion tier/basis | 7 years | None |
| tax_code.suggestion_approved | Accountant approves a suggestion | Session ID, transaction ref, original code, suggested code, applied code, user ID, timestamp | 7 years | None |
| tax_code.suggestion_rejected | Accountant rejects a suggestion | Session ID, transaction ref, suggested code, user ID, reason (if provided) | 7 years | None |
| tax_code.suggestion_overridden | Accountant selects a different code | Session ID, transaction ref, suggested code, override code, user ID, reason | 7 years | None |
| tax_code.transaction_dismissed | Accountant confirms exclusion is correct | Session ID, transaction ref, original code, user ID, dismissal reason | 7 years | None |
| tax_code.bulk_approved | Accountant bulk-approves suggestions | Session ID, count of items, confidence threshold used, user ID | 7 years | None |
| tax_code.conflict_detected | Re-sync finds conflicting data | Session ID, transaction ref, local code, incoming Xero code | 7 years | None |
| bas.recalculated_after_resolution | BAS recalculates post-approval | Session ID, fields changed, before/after values | 7 years | None |

### Compliance Considerations

- **ATO Requirements**: The audit trail must demonstrate that every BAS figure can be traced back to source transactions, and any AI-assisted classification is clearly marked with the accountant's explicit approval. The ATO requires that tax agents exercise professional judgement — this feature supports that by presenting AI as a suggestion tool, not an automatic classifier.
- **Data Retention**: All suggestion and resolution records must be retained for the standard 7-year ATO retention period, aligned with the BAS audit log retention.
- **Access Logging**: Audit logs for tax code resolutions should be visible to the same users who can access the BAS session audit trail (the accountant and practice manager).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Accountants can identify all transactions excluded from a BAS within 5 seconds of opening the BAS review screen (banner with count and dollar impact is immediately visible).
- **SC-002**: The system correctly suggests the right tax code for at least 80% of unmapped transactions (measured by accountant acceptance rate — approved without override).
- **SC-003**: Accountants can resolve all unmapped transactions for a typical quarterly BAS (up to 50 excluded items) in under 5 minutes using bulk approve and individual review.
- **SC-004**: After approving tax code resolutions, the BAS figures recalculate within 10 seconds and the accountant can immediately proceed to the approval step.
- **SC-005**: 100% of AI suggestions and accountant resolutions are captured in the audit trail with no gaps in traceability.
- **SC-006**: Zero silent exclusions — every transaction excluded from BAS is visible and requires explicit resolution (approve suggestion, override, or dismiss) before the BAS can be approved.
- **SC-007**: Re-sync conflicts are detected and surfaced within the normal sync completion time — no silently overwritten local changes.

## Assumptions

- The majority of unmapped transactions (estimated 60-70%) will be resolvable via Tier 1 (account default tax type) since most Xero accounts have a default tax type configured.
- Historical pattern data is available because the system syncs all invoices and bank transactions, not just those for the current quarter.
- Cross-client pattern matching within a tenant is acceptable from a data privacy perspective since all clients belong to the same accounting practice (tenant).
- BASEXCLUDED transactions are surfaced for review because accountants reported confusion about why amounts were missing — but the system should make it easy to confirm exclusion is intentional.
- Xero write-back is explicitly deferred to a future version (v2). For v1, all tax code changes are applied locally only.
- The existing BAS session workflow (draft -> in_progress -> ready_for_review -> approved -> lodged) remains unchanged; this feature adds a resolution step within the in_progress / ready_for_review phases.

## Out of Scope

- Writing tax code changes back to Xero (deferred to v2).
- Bank reconciliation — this remains a Xero responsibility; Clairo monitors reconciliation status but does not perform matching.
- Automated lodgement to the ATO — lodgement recording remains manual.
- Transaction-level anomaly detection beyond tax code classification (e.g., duplicate detection, amount outliers).
- Cross-tenant learning — suggestion models do not learn from other tenants' data.
