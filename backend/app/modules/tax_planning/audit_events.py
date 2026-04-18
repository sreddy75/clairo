"""Audit event type definitions for the tax planning module."""

TAX_PLANNING_AUDIT_EVENTS = {
    "ai.tax_planning.chat": {
        "category": "data",
        "description": "AI tax planning conversation turn completed",
        "retention": "7y",
    },
    "ai.tax_planning.analysis": {
        "category": "data",
        "description": "AI multi-agent tax plan analysis step completed",
        "retention": "7y",
    },
    "ai.suggestion.approved": {
        "category": "data",
        "description": "Accountant approved an AI-generated suggestion",
        "retention": "7y",
    },
    "ai.suggestion.modified": {
        "category": "data",
        "description": "Accountant modified an AI-generated suggestion",
        "retention": "7y",
    },
    "ai.suggestion.rejected": {
        "category": "data",
        "description": "Accountant rejected an AI-generated suggestion",
        "retention": "7y",
    },
    # Spec 059 — Calculation correctness events
    "tax_planning.financials.annualised": {
        "category": "data",
        "description": "YTD financials annualised to full FY at ingest",
        "retention": "7y",
    },
    "tax_planning.payroll.sync_triggered": {
        "category": "integration",
        "description": "On-demand Xero payroll sync triggered by tax plan creation",
        "retention": "7y",
    },
    "tax_planning.payroll.unavailable": {
        "category": "integration",
        "description": "Payroll data could not be loaded for a tax plan",
        "retention": "7y",
    },
    "tax_planning.scenario.provenance_confirmed": {
        "category": "data",
        "description": "Accountant confirmed a previously AI-estimated scenario figure",
        "retention": "7y",
    },
    "tax_planning.scenario.requires_group_model_flag": {
        "category": "data",
        "description": "Scenario flagged as requiring the multi-entity group tax model",
        "retention": "7y",
    },
    "tax_planning.review.verification_failed": {
        "category": "compliance",
        "description": "Reviewer detected a modeller/ground-truth divergence",
        "retention": "7y",
    },
    "tax_planning.citation.verification_outcome": {
        "category": "data",
        "description": "Citation verification completed for an AI response",
        "retention": "7y",
    },
    "tax_planning.manual_financials.saved": {
        "category": "data",
        "description": "Accountant saved manually-entered tax plan financials",
        "retention": "7y",
    },
}
