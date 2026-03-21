"""AI Agent tools.

Spec 024: Credit Notes, Payments & Journals
- User Story 4: Cash flow analysis tools
- User Story 7: Journal analysis tools

Spec 025: Fixed Assets & Enhanced Analysis
- User Story 2: Instant write-off detection (T031)
- User Story 3: Depreciation analysis (T036)
- User Story 7: Tracking category analysis (T060)
"""

from app.modules.agents.tools.asset_tools import (
    ASSET_ANALYSIS_TOOLS,
    get_capex_analysis_tool,
    get_depreciation_analysis_tool,
    get_tracking_category_analysis_tool,
    get_write_off_eligibility_tool,
)
from app.modules.agents.tools.journal_analysis import (
    JOURNAL_ANALYSIS_TOOLS,
    get_audit_risk_score_tool,
    get_journal_anomalies_tool,
)
from app.modules.agents.tools.payment_tools import (
    PAYMENT_TOOLS,
    get_cash_flow_summary_tool,
    get_contact_payment_behavior_tool,
    get_payment_patterns_tool,
)

__all__ = [
    # Payment tools
    "get_cash_flow_summary_tool",
    "get_contact_payment_behavior_tool",
    "get_payment_patterns_tool",
    "PAYMENT_TOOLS",
    # Journal analysis tools
    "get_journal_anomalies_tool",
    "get_audit_risk_score_tool",
    "JOURNAL_ANALYSIS_TOOLS",
    # Asset analysis tools (Spec 025)
    "get_write_off_eligibility_tool",
    "get_depreciation_analysis_tool",
    "get_capex_analysis_tool",
    "get_tracking_category_analysis_tool",
    "ASSET_ANALYSIS_TOOLS",
]
