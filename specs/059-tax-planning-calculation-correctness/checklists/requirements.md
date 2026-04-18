# Specification Quality Checklist: Tax Planning — Calculation Correctness

**Feature**: `059-tax-planning-calculation-correctness`
**Generated**: 2026-04-18
**Source Brief**: `specs/briefs/2026-04-18-tax-planning-calculation-correctness.md`

## Content Quality

- [x] No implementation details (languages, frameworks, APIs) — spec describes behaviour and invariants, not technology
- [x] Focused on user value and business needs — framed around accountant trust, zero-tolerance for wrong numbers in client sessions
- [x] Written for non-technical stakeholders — code-level file:line references kept in the brief, not this spec
- [x] All mandatory sections completed — User Scenarios, Requirements, Audit, Success Criteria

## Requirement Completeness

- [x] Max 3 [NEEDS CLARIFICATION] markers — 1 item (annualisation rule)
- [x] Requirements are testable and unambiguous — every FR has a corresponding acceptance scenario or success criterion
- [x] Success criteria are measurable and technology-agnostic — dollar tolerances, percentages, response counts, user-reported outcomes
- [x] Acceptance scenarios defined for all user stories — 8 stories, all with Given/When/Then scenarios
- [x] Edge cases identified — 8 edge cases covering boundary, failure, and concurrency conditions
- [x] Assumptions marked with 💡 — 6 assumptions clearly flagged
- [x] Dependencies on other specs explicit — 041, 046, 049, 050

## Clairo-Specific Quality

- [x] Audit checklist completed — 8 event types defined, not boilerplate
- [x] Multi-tenancy implications considered — tax plans are tenant-scoped; no changes to tenancy model
- [x] User types correctly identified — primary is accountant (tenant/subscriber), secondary is business-owner client (of the accountant); the business-owner client is never a direct user of the tax planning feature
- [x] Compliance context appropriate for Australian tax domain — Stage 3 rate currency explicit, professional liability framing in problem statement
- [x] Layer alignment — L3/L4 (Knowledge & AI, Proactive Advisory); no violations of build-order

## Scope & Focus

- [x] Single coherent spec — all 8 user stories serve the "correctness audit" goal
- [x] Explicit out-of-scope section — multi-entity group model, UX rethink, engagement thread, ATO integrations, non-Xero ingest
- [x] Independently shippable — each P1 user story delivers value on its own; P2 stories are quality polish
- [x] Does not expand scope beyond the brief — every FR traces to a bug or testing need in the brief

## Testability

- [x] Golden-dataset fixture is the central regression gate (SC-001, SC-004)
- [x] Contract test for prompt scanning is mandated (FR-027, SC-005)
- [x] Independent-derivation reviewer is mandated (FR-020, SC-006)
- [x] Provenance rendering is mandated at 100% (FR-011, FR-014, SC-003)
- [x] Every user story includes an "Independent Test" description

## Known Risks

- **Golden dataset availability**: SC-001 assumes Unni can supply the fixture; if not, the test structure is still built but populated later — noted as an assumption.
- **Annualisation rule**: one [NEEDS CLARIFICATION] remaining; running `/speckit.clarify` before `/speckit.plan` is recommended.
- **Reviewer independence**: the spec makes the reviewer deterministic, which may weaken qualitative "does this make sense" checks — noted as an assumption; LLM reviewer is future work.

## Ready for Next Phase?

- [x] Review spec with Suren + Unni — especially Open Question (annualisation rule) and the 💡 assumptions
- [ ] Run `/speckit.clarify` to resolve the NEEDS CLARIFICATION item
- [ ] Run `/speckit.plan` once clarified and approved
- [ ] Run `/speckit.tasks` after plan approval
