/**
 * Fixed Assets API Client
 *
 * Provides types and API functions for Xero fixed assets (Spec 025).
 */

import { apiClient } from '../api-client';

// =============================================================================
// Types
// =============================================================================

export type AssetStatus = 'Draft' | 'Registered' | 'Disposed';
export type DepreciationMethod = 'StraightLine' | 'DiminishingValue100' | 'DiminishingValue150' | 'DiminishingValue200' | 'NoDepreciation';
export type AveragingMethod = 'FullMonth' | 'ActualDays';

export interface AssetType {
  id: string;
  connection_id: string;
  xero_asset_type_id: string;
  asset_type_name: string;
  book_depreciation_method: DepreciationMethod | null;
  book_averaging_method: AveragingMethod | null;
  book_depreciation_rate: number | null;
  book_effective_life_years: number | null;
  tax_depreciation_method: DepreciationMethod | null;
  tax_averaging_method: AveragingMethod | null;
  tax_depreciation_rate: number | null;
  tax_effective_life_years: number | null;
  created_at: string;
  updated_at: string;
}

export interface Asset {
  id: string;
  connection_id: string;
  xero_asset_id: string;
  asset_number: string | null;
  asset_name: string;
  asset_type_id: string | null;
  asset_type_name: string | null;
  status: AssetStatus;
  purchase_date: string | null;
  purchase_price: number | null;
  disposal_date: string | null;
  disposal_price: number | null;
  book_depreciation_method: DepreciationMethod | null;
  book_depreciation_rate: number | null;
  book_depreciation_effective_life_years: number | null;
  book_current_capital_gain: number | null;
  book_current_gain_loss: number | null;
  book_depreciation_start_date: string | null;
  book_accumulated_depreciation: number | null;
  book_value: number | null;
  book_depreciation_this_year: number | null;
  book_prior_year_depreciation: number | null;
  tax_depreciation_method: DepreciationMethod | null;
  tax_depreciation_rate: number | null;
  tax_depreciation_effective_life_years: number | null;
  tax_depreciation_start_date: string | null;
  tax_accumulated_depreciation: number | null;
  tax_book_value: number | null;
  tax_depreciation_this_year: number | null;
  is_delete_enabled: boolean;
  is_lock_enabled: boolean;
  serial_number: string | null;
  warranty_expiry_date: string | null;
  synced_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface AssetListResponse {
  assets: Asset[];
  total: number;
  limit: number;
  offset: number;
}

export interface AssetTypeListResponse {
  asset_types: AssetType[];
  total: number;
  limit: number;
  offset: number;
}

export interface DepreciationSummary {
  total_depreciation_this_year: number;
  total_book_value: number;
  total_purchase_price: number;
  asset_count: number;
  by_asset_type: Array<{
    asset_type_name: string;
    depreciation_this_year: number;
    book_value: number;
    count: number;
  }>;
  by_method: Array<{
    depreciation_method: string;
    depreciation_this_year: number;
    book_value: number;
    count: number;
  }>;
}

export interface SyncJobResponse {
  success: boolean;
  message: string;
  records_processed: number;
  records_created: number;
  records_updated: number;
  records_failed: number;
}

// =============================================================================
// API Functions
// =============================================================================

/**
 * Get list of asset types for a connection
 */
export async function getAssetTypes(
  token: string,
  connectionId: string,
  limit = 50,
  offset = 0
): Promise<AssetTypeListResponse> {
  const response = await apiClient.get(
    `/api/v1/integrations/xero/connections/${connectionId}/asset-types?limit=${limit}&offset=${offset}`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );
  return apiClient.handleResponse<AssetTypeListResponse>(response);
}

/**
 * Get list of fixed assets for a connection
 */
export async function getAssets(
  token: string,
  connectionId: string,
  options?: {
    limit?: number;
    offset?: number;
    status?: AssetStatus;
    assetTypeId?: string;
  }
): Promise<AssetListResponse> {
  const params = new URLSearchParams();
  params.set('limit', String(options?.limit ?? 50));
  params.set('offset', String(options?.offset ?? 0));
  if (options?.status) {
    params.set('status', options.status);
  }
  if (options?.assetTypeId) {
    params.set('asset_type_id', options.assetTypeId);
  }

  const response = await apiClient.get(
    `/api/v1/integrations/xero/connections/${connectionId}/assets?${params.toString()}`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );
  return apiClient.handleResponse<AssetListResponse>(response);
}

/**
 * Get a specific asset by ID
 */
export async function getAsset(
  token: string,
  connectionId: string,
  assetId: string
): Promise<Asset> {
  const response = await apiClient.get(
    `/api/v1/integrations/xero/connections/${connectionId}/assets/${assetId}`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );
  return apiClient.handleResponse<Asset>(response);
}

/**
 * Sync fixed assets from Xero
 */
export async function syncAssets(
  token: string,
  connectionId: string,
  status?: AssetStatus
): Promise<SyncJobResponse> {
  const params = status ? `?status=${status}` : '';
  const response = await apiClient.post(
    `/api/v1/integrations/xero/connections/${connectionId}/assets/sync${params}`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );
  return apiClient.handleResponse<SyncJobResponse>(response);
}

/**
 * Get depreciation summary for a connection
 */
export async function getDepreciationSummary(
  token: string,
  connectionId: string
): Promise<DepreciationSummary> {
  const response = await apiClient.get(
    `/api/v1/integrations/xero/connections/${connectionId}/assets/depreciation-summary`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );
  return apiClient.handleResponse<DepreciationSummary>(response);
}

// =============================================================================
// Helper Functions
// =============================================================================

/**
 * Get display name for asset status
 */
export function getStatusDisplayName(status: AssetStatus): string {
  return status;
}

/**
 * Get color classes for asset status badge
 */
export function getStatusColor(status: AssetStatus): string {
  switch (status) {
    case 'Draft':
      return 'bg-yellow-100 text-yellow-800';
    case 'Registered':
      return 'bg-green-100 text-green-800';
    case 'Disposed':
      return 'bg-gray-100 text-gray-800';
    default:
      return 'bg-gray-100 text-gray-800';
  }
}

/**
 * Get display name for depreciation method
 */
export function getDepreciationMethodDisplayName(method: DepreciationMethod | null): string {
  if (!method) return 'None';
  switch (method) {
    case 'StraightLine':
      return 'Straight Line';
    case 'DiminishingValue100':
      return 'Diminishing Value (100%)';
    case 'DiminishingValue150':
      return 'Diminishing Value (150%)';
    case 'DiminishingValue200':
      return 'Diminishing Value (200%)';
    case 'NoDepreciation':
      return 'No Depreciation';
    default:
      return method;
  }
}

/**
 * Format currency amount
 */
export function formatCurrency(amount: number | null): string {
  if (amount === null || amount === undefined) return '-';
  return new Intl.NumberFormat('en-AU', {
    style: 'currency',
    currency: 'AUD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount);
}

/**
 * Format date string
 */
export function formatDate(dateString: string | null): string {
  if (!dateString) return '-';
  return new Date(dateString).toLocaleDateString('en-AU', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

// =============================================================================
// Purchase Orders (Spec 025 - User Story 5)
// =============================================================================

export type PurchaseOrderStatus = 'DRAFT' | 'SUBMITTED' | 'AUTHORISED' | 'BILLED' | 'DELETED';

export interface PurchaseOrder {
  id: string;
  xero_purchase_order_id: string;
  purchase_order_number: string | null;
  contact_id: string | null;
  contact_name: string | null;
  reference: string | null;
  date: string;
  delivery_date: string | null;
  status: PurchaseOrderStatus;
  sub_total: number;
  total_tax: number;
  total: number;
  currency_code: string | null;
  expected_arrival_date: string | null;
  delivery_address: string | null;
  attention_to: string | null;
  telephone: string | null;
  delivery_instructions: string | null;
  sent_to_contact: boolean;
  has_attachments: boolean;
  updated_date_utc: string | null;
  created_at: string;
  updated_at: string;
}

export interface PurchaseOrderListResponse {
  orders: PurchaseOrder[];
  total: number;
  limit: number;
  offset: number;
}

export interface PurchaseOrderSummary {
  outstanding_count: number;
  outstanding_total: number;
  by_status: Record<string, number>;
  upcoming_deliveries: Array<{
    po_number: string | null;
    contact_name: string | null;
    expected_date: string | null;
    total: number;
  }>;
}

/**
 * Get list of purchase orders for a connection
 */
export async function getPurchaseOrders(
  token: string,
  connectionId: string,
  options?: {
    limit?: number;
    offset?: number;
    status?: PurchaseOrderStatus;
  }
): Promise<PurchaseOrderListResponse> {
  const params = new URLSearchParams();
  params.set('limit', String(options?.limit ?? 50));
  params.set('offset', String(options?.offset ?? 0));
  if (options?.status) {
    params.set('status', options.status);
  }

  const response = await apiClient.get(
    `/api/v1/integrations/xero/connections/${connectionId}/purchase-orders?${params.toString()}`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );
  return apiClient.handleResponse<PurchaseOrderListResponse>(response);
}

/**
 * Get purchase order summary for cash flow planning
 */
export async function getPurchaseOrderSummary(
  token: string,
  connectionId: string
): Promise<PurchaseOrderSummary> {
  const response = await apiClient.get(
    `/api/v1/integrations/xero/connections/${connectionId}/purchase-orders/summary`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );
  return apiClient.handleResponse<PurchaseOrderSummary>(response);
}

/**
 * Sync purchase orders from Xero
 */
export async function syncPurchaseOrders(
  token: string,
  connectionId: string,
  status?: PurchaseOrderStatus
): Promise<{ synced: number; created: number; updated: number; errors: string[] }> {
  const params = status ? `?status=${status}` : '';
  const response = await apiClient.post(
    `/api/v1/integrations/xero/connections/${connectionId}/purchase-orders/sync${params}`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );
  return apiClient.handleResponse(response);
}

/**
 * Get status color for purchase order
 */
export function getPurchaseOrderStatusColor(status: PurchaseOrderStatus): string {
  switch (status) {
    case 'DRAFT':
      return 'bg-gray-100 text-gray-800';
    case 'SUBMITTED':
      return 'bg-blue-100 text-blue-800';
    case 'AUTHORISED':
      return 'bg-green-100 text-green-800';
    case 'BILLED':
      return 'bg-purple-100 text-purple-800';
    case 'DELETED':
      return 'bg-red-100 text-red-800';
    default:
      return 'bg-gray-100 text-gray-800';
  }
}

// =============================================================================
// Repeating Invoices (Spec 025 - User Story 6)
// =============================================================================

export type RepeatingInvoiceStatus = 'DRAFT' | 'AUTHORISED';
export type ScheduleUnit = 'WEEKLY' | 'MONTHLY' | 'YEARLY';

export interface RepeatingInvoice {
  id: string;
  xero_repeating_invoice_id: string;
  invoice_type: 'ACCPAY' | 'ACCREC';
  contact_id: string | null;
  contact_name: string | null;
  status: RepeatingInvoiceStatus;
  schedule_unit: ScheduleUnit;
  schedule_period: number;
  start_date: string | null;
  end_date: string | null;
  next_scheduled_date: string | null;
  reference: string | null;
  currency_code: string | null;
  sub_total: number;
  total_tax: number;
  total: number;
  has_attachments: boolean;
  approved_for_sending: boolean;
  send_copy: boolean;
  mark_as_sent: boolean;
  include_pdf: boolean;
  updated_date_utc: string | null;
  created_at: string;
  updated_at: string;
}

export interface RepeatingInvoiceListResponse {
  invoices: RepeatingInvoice[];
  total: number;
  limit: number;
  offset: number;
}

export interface RecurringSummary {
  monthly_receivables: number;
  monthly_payables: number;
  annual_receivables: number;
  annual_payables: number;
  active_receivable_count: number;
  active_payable_count: number;
}

/**
 * Get list of repeating invoices for a connection
 */
export async function getRepeatingInvoices(
  token: string,
  connectionId: string,
  options?: {
    limit?: number;
    offset?: number;
    invoice_type?: 'ACCPAY' | 'ACCREC';
    status?: RepeatingInvoiceStatus;
  }
): Promise<RepeatingInvoiceListResponse> {
  const params = new URLSearchParams();
  params.set('limit', String(options?.limit ?? 50));
  params.set('offset', String(options?.offset ?? 0));
  if (options?.invoice_type) {
    params.set('invoice_type', options.invoice_type);
  }
  if (options?.status) {
    params.set('status', options.status);
  }

  const response = await apiClient.get(
    `/api/v1/integrations/xero/connections/${connectionId}/repeating-invoices?${params.toString()}`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );
  return apiClient.handleResponse<RepeatingInvoiceListResponse>(response);
}

/**
 * Get recurring revenue/expense summary
 */
export async function getRecurringSummary(
  token: string,
  connectionId: string
): Promise<RecurringSummary> {
  const response = await apiClient.get(
    `/api/v1/integrations/xero/connections/${connectionId}/repeating-invoices/summary`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );
  return apiClient.handleResponse<RecurringSummary>(response);
}

/**
 * Sync repeating invoices from Xero
 */
export async function syncRepeatingInvoices(
  token: string,
  connectionId: string,
  status?: RepeatingInvoiceStatus
): Promise<{ synced: number; created: number; updated: number; errors: string[] }> {
  const params = status ? `?status=${status}` : '';
  const response = await apiClient.post(
    `/api/v1/integrations/xero/connections/${connectionId}/repeating-invoices/sync${params}`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );
  return apiClient.handleResponse(response);
}

/**
 * Get schedule display text
 */
export function getScheduleDisplayText(unit: ScheduleUnit, period: number): string {
  const unitText = unit.toLowerCase().replace('ly', '');
  if (period === 1) {
    return `Every ${unitText}`;
  }
  return `Every ${period} ${unitText}s`;
}

// =============================================================================
// Tracking Categories (Spec 025 - User Story 7)
// =============================================================================

export interface TrackingOption {
  id: string;
  name: string;
  status: string;
}

export interface TrackingCategory {
  id: string;
  xero_tracking_category_id: string;
  name: string;
  status: string;
  option_count: number;
  options: TrackingOption[];
  created_at: string;
  updated_at: string;
}

export interface TrackingCategoryListResponse {
  categories: TrackingCategory[];
  total: number;
}

/**
 * Get list of tracking categories for a connection
 */
export async function getTrackingCategories(
  token: string,
  connectionId: string,
  includeArchived = false
): Promise<TrackingCategoryListResponse> {
  const params = new URLSearchParams();
  if (includeArchived) {
    params.set('include_archived', 'true');
  }

  const response = await apiClient.get(
    `/api/v1/integrations/xero/connections/${connectionId}/tracking-categories?${params.toString()}`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );
  return apiClient.handleResponse<TrackingCategoryListResponse>(response);
}

/**
 * Sync tracking categories from Xero
 */
export async function syncTrackingCategories(
  token: string,
  connectionId: string,
  includeArchived = false
): Promise<{ synced: number; created: number; updated: number; errors: string[] }> {
  const params = includeArchived ? '?include_archived=true' : '';
  const response = await apiClient.post(
    `/api/v1/integrations/xero/connections/${connectionId}/tracking-categories/sync${params}`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );
  return apiClient.handleResponse(response);
}

// =============================================================================
// Quotes (Spec 025 - User Story 8)
// =============================================================================

export type QuoteStatus = 'DRAFT' | 'SENT' | 'DECLINED' | 'ACCEPTED' | 'INVOICED' | 'DELETED';

export interface Quote {
  id: string;
  xero_quote_id: string;
  quote_number: string | null;
  contact_id: string | null;
  contact_name: string | null;
  reference: string | null;
  date: string;
  expiry_date: string | null;
  status: QuoteStatus;
  title: string | null;
  summary: string | null;
  sub_total: number;
  total_tax: number;
  total: number;
  total_discount: number | null;
  currency_code: string | null;
  updated_date_utc: string | null;
  created_at: string;
  updated_at: string;
}

export interface QuoteListResponse {
  quotes: Quote[];
  total: number;
  limit: number;
  offset: number;
}

export interface QuotePipelineSummary {
  total_quotes: number;
  total_value: number;
  by_status: Record<string, { count: number; value: number }>;
  conversion_rate: number | null;
  average_quote_value: number | null;
}

/**
 * Get list of quotes for a connection
 */
export async function getQuotes(
  token: string,
  connectionId: string,
  options?: {
    limit?: number;
    offset?: number;
    status?: QuoteStatus;
  }
): Promise<QuoteListResponse> {
  const params = new URLSearchParams();
  params.set('limit', String(options?.limit ?? 50));
  params.set('offset', String(options?.offset ?? 0));
  if (options?.status) {
    params.set('status', options.status);
  }

  const response = await apiClient.get(
    `/api/v1/integrations/xero/connections/${connectionId}/quotes?${params.toString()}`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );
  return apiClient.handleResponse<QuoteListResponse>(response);
}

/**
 * Get quote pipeline summary
 */
export async function getQuotePipeline(
  token: string,
  connectionId: string
): Promise<QuotePipelineSummary> {
  const response = await apiClient.get(
    `/api/v1/integrations/xero/connections/${connectionId}/quotes/pipeline`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );
  return apiClient.handleResponse<QuotePipelineSummary>(response);
}

/**
 * Sync quotes from Xero
 */
export async function syncQuotes(
  token: string,
  connectionId: string,
  status?: QuoteStatus
): Promise<{ synced: number; created: number; updated: number; errors: string[] }> {
  const params = status ? `?status=${status}` : '';
  const response = await apiClient.post(
    `/api/v1/integrations/xero/connections/${connectionId}/quotes/sync${params}`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );
  return apiClient.handleResponse(response);
}

/**
 * Get status color for quote
 */
export function getQuoteStatusColor(status: QuoteStatus): string {
  switch (status) {
    case 'DRAFT':
      return 'bg-gray-100 text-gray-800';
    case 'SENT':
      return 'bg-blue-100 text-blue-800';
    case 'ACCEPTED':
      return 'bg-green-100 text-green-800';
    case 'INVOICED':
      return 'bg-purple-100 text-purple-800';
    case 'DECLINED':
      return 'bg-red-100 text-red-800';
    case 'DELETED':
      return 'bg-gray-100 text-gray-600';
    default:
      return 'bg-gray-100 text-gray-800';
  }
}

/**
 * Check if a quote is expiring soon (within 7 days)
 */
export function isQuoteExpiringSoon(expiryDate: string | null): boolean {
  if (!expiryDate) return false;
  const expiry = new Date(expiryDate);
  const now = new Date();
  const daysUntilExpiry = Math.ceil((expiry.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
  return daysUntilExpiry >= 0 && daysUntilExpiry <= 7;
}
