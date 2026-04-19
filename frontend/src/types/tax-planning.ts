// Types for AI Tax Planning & Advisory module (Spec 049)

export type EntityType = 'company' | 'individual' | 'trust' | 'partnership';
export type TaxPlanStatus = 'draft' | 'in_progress' | 'finalised';
export type DataSource = 'xero' | 'manual' | 'xero_with_adjustments';
export type RiskRating = 'conservative' | 'moderate' | 'aggressive';

// ---------------------------------------------------------------------------
// Financial data structures (matching JSONB schemas)
// ---------------------------------------------------------------------------

export interface BreakdownItem {
  category: string;
  amount: number;
}

export interface AdjustmentItem {
  description: string;
  amount: number;
  type: 'add_back' | 'deduction';
}

export interface ProjectionMetadata {
  applied: boolean;
  rule: 'linear';
  months_elapsed: number;
  months_projected: number;
  ytd_snapshot: {
    income?: { total_income?: number; revenue?: number; [k: string]: unknown };
    expenses?: { total_expenses?: number; [k: string]: unknown };
    [k: string]: unknown;
  };
  applied_at: string;
  reason: string | null;
}

export interface FinancialsData {
  income: {
    revenue: number;
    other_income: number;
    total_income: number;
    breakdown?: BreakdownItem[];
  };
  expenses: {
    cost_of_sales: number;
    operating_expenses: number;
    total_expenses: number;
    breakdown?: BreakdownItem[];
  };
  credits: {
    payg_instalments: number;
    payg_withholding: number;
    franking_credits: number;
  };
  adjustments: AdjustmentItem[];
  turnover: number;
  months_data_available: number;
  is_annualised: boolean;
  // Bank context
  bank_balances?: BankAccountBalance[];
  total_bank_balance?: number | null;
  last_reconciliation_date?: string;
  period_coverage?: string;
  unreconciled_summary?: UnreconciledSummary;
  // Spec 059 FR-001 — authoritative projection state. The top-level income
  // and expenses above are ALREADY annualised when projection_metadata.applied
  // is true; `ytd_snapshot` preserves the original YTD values for display.
  projection_metadata?: ProjectionMetadata;
  // Deprecated: retained for backward compatibility with pre-059 payloads.
  projection?: {
    projected_revenue: number;
    projected_expenses: number;
    projected_net_profit: number;
    monthly_avg_revenue: number;
    monthly_avg_expenses: number;
    months_used: number;
    projection_method: string;
  } | null;
  // Prior year comparison (Spec 056 - US3)
  prior_year_ytd?: {
    revenue: number;
    total_income: number;
    total_expenses: number;
    net_profit: number;
    period_coverage: string;
    changes: {
      revenue_pct: number;
      expenses_pct: number;
      profit_pct: number;
    };
  } | null;
  // Multi-year trends (Spec 056 - US4)
  prior_years?: Array<{
    financial_year: string;
    revenue: number;
    expenses: number;
    net_profit: number;
  }> | null;
  // Strategy context (Spec 056 - US5)
  strategy_context?: {
    available_cash: number | null;
    monthly_operating_expenses: number;
    cash_buffer_3mo: number;
    max_strategy_budget: number | null;
    existing_asset_spend: number;
  } | null;
  // Payroll summary (Spec 056 - US6)
  payroll_summary?: {
    employee_count: number;
    total_wages_ytd: number;
    total_super_ytd: number;
    total_tax_withheld_ytd: number;
    has_owners: boolean;
    employees: Array<{ name: string; job_title: string | null; status: string }>;
  } | null;
}

export interface BankAccountBalance {
  account_name: string;
  account_id?: string;
  opening_balance: number;
  cash_received: number;
  cash_spent: number;
  closing_balance: number;
}

export interface UnreconciledSummary {
  transaction_count: number;
  unreconciled_income: number;
  unreconciled_expenses: number;
  gst_collected_estimate: number;
  gst_paid_estimate: number;
  quarter: string;
  is_provisional: boolean;
}

export interface TaxPosition {
  taxable_income: number;
  gross_tax: number;
  offsets: Record<string, number>;
  medicare_levy: number;
  help_repayment: number;
  total_tax_payable: number;
  credits_applied: {
    payg_instalments: number;
    payg_withholding: number;
    franking_credits: number;
    total: number;
  };
  net_position: number;
  effective_rate_pct: number;
  calculation_method: string;
  rate_config_year: string;
}

export interface ImpactData {
  before: {
    taxable_income: number;
    tax_payable: number;
    net_position: number;
  };
  after: {
    taxable_income: number;
    tax_payable: number;
    net_position: number;
  };
  change: {
    taxable_income_change: number;
    tax_saving: number;
    net_benefit: number;
  };
}

// ---------------------------------------------------------------------------
// API response types
// ---------------------------------------------------------------------------

// Spec 059 FR-011 — provenance tags keyed by JSON Pointer into
// impact_data / assumptions. Absent keys render as neutral badges, not red.
export type Provenance = 'confirmed' | 'derived' | 'estimated';

export type SourceTags = Record<string, Provenance>;

// Spec 059 FR-017 — closed taxonomy of tax planning strategy types.
export type StrategyCategory =
  | 'prepayment'
  | 'capex_deduction'
  | 'super_contribution'
  | 'director_salary'
  | 'trust_distribution'
  | 'dividend_timing'
  | 'spouse_contribution'
  | 'multi_entity_restructure'
  | 'other';

export interface TaxScenario {
  id: string;
  tax_plan_id: string;
  title: string;
  description: string;
  assumptions: { items?: string[] };
  impact_data: ImpactData;
  risk_rating: RiskRating;
  compliance_notes: string | null;
  cash_flow_impact: number | null;
  sort_order: number;
  created_at: string;
  // Spec 059 FR-017..FR-020 — multi-entity honesty flag. requires_group_model
  // is derived in code from strategy_category, never emitted by the LLM.
  strategy_category?: StrategyCategory;
  requires_group_model?: boolean;
  // Spec 059 FR-011..FR-016 — JSON Pointer → provenance map.
  source_tags?: SourceTags;
}

export interface SourceChunkRef {
  chunk_id: string;
  source_type: string;
  title: string;
  ruling_number: string | null;
  section_ref: string | null;
  relevance_score: number;
}

// Spec 059 FR-021 — `low_confidence` = retrieval confidence below threshold,
// distinct from unverified-citations cases.
export type VerificationStatus =
  | 'verified'
  | 'partially_verified'
  | 'unverified'
  | 'no_citations'
  | 'low_confidence';

export interface CitationVerificationItem {
  identifier: string;
  verified: boolean;
  matched_by?: string;
}

// Spec 060 T031 — per-citation strategy verification. `status` is the
// three-state classification the StrategyChip renders (green/amber/red).
export type StrategyCitationStatus =
  | 'verified'
  | 'partially_verified'
  | 'unverified';

export interface StrategyCitationItem {
  strategy_id: string;
  cited_name: string;
  status: StrategyCitationStatus;
  name_drift: number;
}

export interface CitationVerification {
  total_citations: number;
  verified_count: number;
  unverified_count: number;
  verification_rate: number;
  status: VerificationStatus;
  confidence_score?: number;
  citations?: CitationVerificationItem[];
  strategy_citations?: StrategyCitationItem[];
}

export interface ChatAttachment {
  filename: string;
  media_type: string;
  category: 'image' | 'pdf' | 'csv' | 'excel' | 'text';
  size_bytes: number;
}

export interface TaxPlanMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  scenario_ids: string[];
  created_at: string;
  source_chunks_used?: SourceChunkRef[] | null;
  citation_verification?: CitationVerification | null;
  attachment?: ChatAttachment | null;
}

export interface TaxPlan {
  id: string;
  tenant_id: string;
  xero_connection_id: string;
  client_name: string;
  financial_year: string;
  entity_type: EntityType;
  status: TaxPlanStatus;
  data_source: DataSource;
  financials_data: FinancialsData | null;
  tax_position: TaxPosition | null;
  notes: string | null;
  xero_report_fetched_at: string | null;
  created_at: string;
  updated_at: string;
  scenarios: TaxScenario[];
  scenario_count: number;
  message_count: number;
  xero_connection_status?: string | null;
  data_stale?: boolean;
  // Spec 059 FR-006 — bounded on-demand payroll sync status
  payroll_sync_status?: 'ready' | 'pending' | 'unavailable' | 'not_required' | null;
  // Spec 059.1 — user-selectable projection basis. ISO date (YYYY-MM-DD)
  // or null = follow the Xero reconciliation date.
  as_at_date?: string | null;
}

export interface TaxPlanListItem {
  id: string;
  xero_connection_id: string;
  client_name: string;
  financial_year: string;
  entity_type: EntityType;
  status: TaxPlanStatus;
  data_source: DataSource;
  scenario_count: number;
  net_position: number | null;
  updated_at: string;
}

export interface TaxPlanListResponse {
  items: TaxPlanListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface TaxScenarioListResponse {
  items: TaxScenario[];
  total: number;
}

export interface MessageListResponse {
  items: TaxPlanMessage[];
  total: number;
  page: number;
  page_size: number;
}

// ---------------------------------------------------------------------------
// Request types
// ---------------------------------------------------------------------------

export interface TaxPlanCreateRequest {
  xero_connection_id: string;
  financial_year: string;
  entity_type: EntityType;
  data_source: DataSource;
  replace_existing?: boolean;
}

export interface TaxPlanUpdateRequest {
  status?: TaxPlanStatus;
  notes?: string;
  entity_type?: EntityType;
}

export interface FinancialsInput {
  income: {
    revenue: number;
    other_income: number;
    breakdown?: BreakdownItem[];
  };
  expenses: {
    cost_of_sales: number;
    operating_expenses: number;
    breakdown?: BreakdownItem[];
  };
  credits?: {
    payg_instalments: number;
    payg_withholding: number;
    franking_credits: number;
  };
  adjustments?: AdjustmentItem[];
  turnover: number;
  has_help_debt?: boolean;
}

export interface FinancialsPullResponse {
  financials_data: FinancialsData;
  tax_position: TaxPosition;
  data_freshness?: {
    fetched_at: string;
    is_fresh: boolean;
    cache_age_minutes: number | null;
  };
}

export interface ChatMessageRequest {
  message: string;
}

export interface ChatResponse {
  message: TaxPlanMessage;
  scenarios_created: TaxScenario[];
  updated_tax_position: TaxPosition | null;
}

export interface TaxRateConfig {
  id: string;
  rate_type: string;
  rates_data: Record<string, unknown>;
  effective_from: string;
}

export interface TaxRatesResponse {
  financial_year: string;
  rates: TaxRateConfig[];
}

export interface XeroChanges {
  changes: Record<string, { old: number; new: number }> | null;
}

// SSE event types for streaming chat
export type ChatStreamEventType = 'thinking' | 'content' | 'scenario' | 'verification' | 'done' | 'error';

export interface ChatStreamEvent {
  type: ChatStreamEventType;
  content?: string;
  scenario?: TaxScenario;
  message_id?: string;
  scenarios_created?: string[];
  error?: string;
  data?: CitationVerification;
}
