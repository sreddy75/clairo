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

# GST basis audit event constants (Spec 062)
BAS_GST_BASIS_SET = "bas.gst_basis.set"
BAS_GST_BASIS_CHANGED = "bas.gst_basis.changed"
BAS_GST_BASIS_CHANGED_POST_LODGEMENT = "bas.gst_basis.changed_post_lodgement"
BAS_INSTALMENT_ENTERED = "bas.instalment.entered"

# Reconciliation warning audit event constants
BAS_RECONCILIATION_WARNING_SHOWN = "bas.reconciliation.warning_shown"
BAS_RECONCILIATION_PROCEED_ANYWAY = "bas.reconciliation.proceed_anyway"

# Xero cross-check audit event constants
BAS_FIGURES_CROSS_CHECK_DISCREPANCY = "bas.figures.cross_check_discrepancy"
