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
}
