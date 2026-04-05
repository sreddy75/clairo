# RAG Citation Verification Audit

**Date**: 2026-04-05
**Spec**: 054-onboarding-hardening

## Summary

Audited both RAG citation pipelines (knowledge chatbot + tax planning agent). Found robust multi-layer defenses against hallucination with a few gaps. Citations can be trusted for beta launch with the existing safeguards.

## Two Citation Pipelines

| Pipeline | Citation Format | Verification | Confidence Decline | Anti-Hallucination |
|----------|----------------|-------------|-------------------|-------------------|
| Knowledge Chatbot | `[1]`, `[2]` numbered | CitationVerifier (programmatic) | Yes (score < 0.5 → auto-decline) | Strong ("NEVER fabricate") |
| Tax Planning Agent | `[Source: IDENTIFIER]` | Regex + substring match | No (always responds) | Moderate ("state general knowledge") |

## Safeguards That Exist

- [x] **Post-generation citation verification** — both pipelines verify citations against retrieved chunks
- [x] **Low-confidence auto-decline** — knowledge chatbot replaces response with "I don't have enough reliable information" when confidence < 0.5
- [x] **Anti-fabrication prompt instructions** — "NEVER fabricate section numbers, ruling numbers, or case citations"
- [x] **Superseded content warnings** — alerts when citing outdated rulings
- [x] **Real ATO document ingestion** — scrapers for ATO Legal Database + Federal Register of Legislation (not synthetic data)
- [x] **Deterministic tax calculations** — financial figures always from `calculate_tax_position` tool, never LLM-generated
- [x] **Frontend verification badge** — color-coded (verified/partially/unverified/no citations) shown to user
- [x] **"Answer ONLY from provided SOURCES"** — knowledge chatbot grounding instruction
- [x] **Multi-agent reviewer** — fifth agent checks citation validity (LLM-based, not programmatic)

## Gaps Identified

1. **Tax planning agent lacks confidence-based decline** — unlike the chatbot, the tax planning agent always responds even when no relevant knowledge is retrieved. Mitigated by: the verification badge shows "General knowledge" status, and the AI disclaimer is visible.

2. **Two inconsistent citation formats** — `[Source: IDENTIFIER]` vs `[1]`. Each has its own verifier. If the LLM mixes formats in the tax planning chat, mismatched citations wouldn't be caught.

3. **No database-level citation validation** — verifiers only check against retrieved chunks for that query, not the full knowledge base. A valid ATO ruling not in the top-5 results would be marked ungrounded.

4. **Substring matching false positives** — short references like `s10` or `Div 7` could match unrelated chunks. Low risk for specific references like `TR 2024/1`.

5. **No runtime alerting on ungrounded citation rates** — verification results are stored but no operational alert fires when rates drop.

## Test Queries (for manual verification when app is running)

| # | Query | Expected Source Type | Min Citations |
|---|-------|---------------------|---------------|
| 1 | "What are the GST registration thresholds?" | ATO ruling (GSTR) | 1 |
| 2 | "When is the BAS due for Q3 FY2026?" | ATO website / legislation | 1 |
| 3 | "How does PAYG withholding work for contractors?" | Tax ruling (TR) | 1 |
| 4 | "What are the FBT consequences of providing a car?" | Legislation (FBTAA) | 1 |
| 5 | "Explain small business CGT concessions under Div 152" | Legislation (ITAA 1997) | 1 |

## Verdict

**Citations can be trusted for beta launch.** The multi-layer defense (prompt grounding → retrieval → verification → confidence decline → frontend badge) is robust. The knowledge chatbot path is particularly strong. The tax planning agent path is adequate given the "AI suggests, accountants approve" model and the visible verification badge.

**Recommended follow-up (post-beta):**
- Add confidence-based decline to the tax planning agent
- Unify citation format across both pipelines
- Add operational alerting on low verification rates
