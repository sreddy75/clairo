"""
Tax Planning Module — AI Tax Planning & Advisory.

Provides tax estimation for Australian companies, individuals, trusts, and partnerships.
Integrates with Xero P&L data and offers AI-powered scenario modelling via Claude tool-use.

Entities:
    - TaxPlan: One plan per client per financial year
    - TaxScenario: Modelled what-if scenarios within a plan
    - TaxPlanMessage: Conversation history for AI chat
    - TaxRateConfig: Australian tax rates stored as configuration data

Dependencies:
    - integrations.xero (via service layer for P&L data)
    - auth (for tenant context)
"""
