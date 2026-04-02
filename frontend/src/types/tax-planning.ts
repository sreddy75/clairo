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
  // Bank context (FR-015 to FR-018)
  bank_balances?: BankAccountBalance[];
  total_bank_balance?: number;
  last_reconciliation_date?: string;
  period_coverage?: string;
  unreconciled_summary?: UnreconciledSummary;
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
}

export interface SourceChunkRef {
  chunk_id: string;
  source_type: string;
  title: string;
  ruling_number: string | null;
  section_ref: string | null;
  relevance_score: number;
}

export type VerificationStatus = 'verified' | 'partially_verified' | 'unverified' | 'no_citations';

export interface CitationVerification {
  total_citations: number;
  verified_count: number;
  unverified_count: number;
  verification_rate: number;
  status: VerificationStatus;
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
