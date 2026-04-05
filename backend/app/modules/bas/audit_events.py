"""Audit event type definitions for BAS AI classification."""

BAS_AI_AUDIT_EVENTS = {
    "ai.bas.classification": {
        "category": "data",
        "description": "AI LLM tax code classification completed",
        "retention": "7y",
    },
    "ai.bas.client_classification": {
        "category": "data",
        "description": "AI client-based tax code classification completed",
        "retention": "7y",
    },
}
