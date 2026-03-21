/**
 * Transactions API Client
 *
 * Provides typed API functions for Spec 024 transaction types:
 * - Credit Notes (with allocations)
 * - Payments (to invoices)
 * - Overpayments and Prepayments
 * - Journals (system-generated)
 * - Manual Journals (user-created)
 */

import { apiClient } from '../api-client';

const BASE = '/api/v1/integrations/xero/connections';

// =============================================================================
// Types
// =============================================================================

export interface CreditNoteAllocation {
  id: string;
  invoice_id: string;
  invoice_number: string | null;
  amount: string;
  allocated_at: string;
}

export interface CreditNote {
  id: string;
  xero_credit_note_id: string;
  credit_note_number: string | null;
  credit_note_type: 'accpaycredit' | 'accreccredit';
  status: string;
  contact_id: string | null;
  contact_name: string | null;
  issue_date: string;
  subtotal: string;
  tax_amount: string;
  total_amount: string;
  remaining_credit: string;
  currency: string;
  reference: string | null;
  fully_paid_on_date: string | null;
  allocations?: CreditNoteAllocation[];
}

export interface CreditNoteListResponse {
  credit_notes: CreditNote[];
  total: number;
  page: number;
  limit: number;
}

export interface Payment {
  id: string;
  xero_payment_id: string;
  payment_type: string;
  status: string;
  invoice_id: string | null;
  invoice_number: string | null;
  contact_id: string | null;
  contact_name: string | null;
  account_id: string | null;
  account_code: string | null;
  payment_date: string;
  amount: string;
  currency: string;
  reference: string | null;
  is_reconciled: boolean;
}

export interface PaymentListResponse {
  payments: Payment[];
  total: number;
  page: number;
  limit: number;
}

export interface Overpayment {
  id: string;
  xero_overpayment_id: string;
  overpayment_type: string;
  status: string;
  contact_id: string | null;
  contact_name: string | null;
  payment_date: string;
  subtotal: string;
  tax_amount: string;
  total_amount: string;
  remaining_credit: string;
  currency: string;
}

export interface OverpaymentListResponse {
  overpayments: Overpayment[];
  total: number;
  page: number;
  limit: number;
}

export interface Prepayment {
  id: string;
  xero_prepayment_id: string;
  prepayment_type: string;
  status: string;
  contact_id: string | null;
  contact_name: string | null;
  payment_date: string;
  subtotal: string;
  tax_amount: string;
  total_amount: string;
  remaining_credit: string;
  currency: string;
}

export interface PrepaymentListResponse {
  prepayments: Prepayment[];
  total: number;
  page: number;
  limit: number;
}

export interface JournalLine {
  account_id: string | null;
  account_code: string | null;
  account_name: string | null;
  description: string | null;
  net_amount: string;
  gross_amount: string;
  tax_amount: string;
  tax_type: string | null;
  is_debit: boolean;
}

export interface Journal {
  id: string;
  xero_journal_id: string;
  journal_number: number;
  journal_date: string;
  source_id: string | null;
  source_type: string | null;
  reference: string | null;
  journal_lines: JournalLine[];
}

export interface JournalListResponse {
  journals: Journal[];
  total: number;
  page: number;
  limit: number;
}

export interface ManualJournalLine {
  account_id: string | null;
  account_code: string | null;
  description: string | null;
  line_amount: string;
  tax_type: string | null;
  tax_amount: string | null;
  is_debit: boolean;
}

export interface ManualJournal {
  id: string;
  xero_manual_journal_id: string;
  narration: string;
  status: string;
  journal_date: string;
  show_on_cash_basis_reports: boolean;
  url: string | null;
  journal_lines: ManualJournalLine[];
}

export interface ManualJournalListResponse {
  manual_journals: ManualJournal[];
  total: number;
  page: number;
  limit: number;
}

export interface TransactionSyncStatus {
  credit_notes: { count: number; last_sync: string | null };
  payments: { count: number; last_sync: string | null };
  overpayments: { count: number; last_sync: string | null };
  prepayments: { count: number; last_sync: string | null };
  journals: { count: number; last_sync: string | null };
  manual_journals: { count: number; last_sync: string | null };
}

// =============================================================================
// Credit Notes
// =============================================================================

export async function getCreditNotes(
  token: string,
  connectionId: string,
  options: {
    page?: number;
    limit?: number;
    credit_note_type?: 'accpaycredit' | 'accreccredit';
    status?: string;
  } = {}
): Promise<CreditNoteListResponse> {
  const params = new URLSearchParams();
  if (options.page) params.set('page', options.page.toString());
  if (options.limit) params.set('limit', options.limit.toString());
  if (options.credit_note_type) params.set('credit_note_type', options.credit_note_type);
  if (options.status) params.set('status', options.status);

  const url = `${BASE}/${connectionId}/credit-notes${params.toString() ? `?${params}` : ''}`;
  const response = await apiClient.get(url, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return apiClient.handleResponse<CreditNoteListResponse>(response);
}

export async function getCreditNote(
  token: string,
  connectionId: string,
  creditNoteId: string
): Promise<CreditNote> {
  const response = await apiClient.get(
    `${BASE}/${connectionId}/credit-notes/${creditNoteId}`,
    { headers: { Authorization: `Bearer ${token}` } }
  );
  return apiClient.handleResponse<CreditNote>(response);
}

// =============================================================================
// Payments
// =============================================================================

export async function getPayments(
  token: string,
  connectionId: string,
  options: {
    page?: number;
    limit?: number;
    payment_type?: string;
    status?: string;
  } = {}
): Promise<PaymentListResponse> {
  const params = new URLSearchParams();
  if (options.page) params.set('page', options.page.toString());
  if (options.limit) params.set('limit', options.limit.toString());
  if (options.payment_type) params.set('payment_type', options.payment_type);
  if (options.status) params.set('status', options.status);

  const url = `${BASE}/${connectionId}/payments${params.toString() ? `?${params}` : ''}`;
  const response = await apiClient.get(url, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return apiClient.handleResponse<PaymentListResponse>(response);
}

export async function getPayment(
  token: string,
  connectionId: string,
  paymentId: string
): Promise<Payment> {
  const response = await apiClient.get(
    `${BASE}/${connectionId}/payments/${paymentId}`,
    { headers: { Authorization: `Bearer ${token}` } }
  );
  return apiClient.handleResponse<Payment>(response);
}

// =============================================================================
// Overpayments
// =============================================================================

export async function getOverpayments(
  token: string,
  connectionId: string,
  options: { page?: number; limit?: number } = {}
): Promise<OverpaymentListResponse> {
  const params = new URLSearchParams();
  if (options.page) params.set('page', options.page.toString());
  if (options.limit) params.set('limit', options.limit.toString());

  const url = `${BASE}/${connectionId}/overpayments${params.toString() ? `?${params}` : ''}`;
  const response = await apiClient.get(url, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return apiClient.handleResponse<OverpaymentListResponse>(response);
}

// =============================================================================
// Prepayments
// =============================================================================

export async function getPrepayments(
  token: string,
  connectionId: string,
  options: { page?: number; limit?: number } = {}
): Promise<PrepaymentListResponse> {
  const params = new URLSearchParams();
  if (options.page) params.set('page', options.page.toString());
  if (options.limit) params.set('limit', options.limit.toString());

  const url = `${BASE}/${connectionId}/prepayments${params.toString() ? `?${params}` : ''}`;
  const response = await apiClient.get(url, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return apiClient.handleResponse<PrepaymentListResponse>(response);
}

// =============================================================================
// Journals
// =============================================================================

export async function getJournals(
  token: string,
  connectionId: string,
  options: {
    page?: number;
    limit?: number;
    source_type?: string;
  } = {}
): Promise<JournalListResponse> {
  const params = new URLSearchParams();
  if (options.page) params.set('page', options.page.toString());
  if (options.limit) params.set('limit', options.limit.toString());
  if (options.source_type) params.set('source_type', options.source_type);

  const url = `${BASE}/${connectionId}/journals${params.toString() ? `?${params}` : ''}`;
  const response = await apiClient.get(url, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return apiClient.handleResponse<JournalListResponse>(response);
}

export async function getJournal(
  token: string,
  connectionId: string,
  journalId: string
): Promise<Journal> {
  const response = await apiClient.get(
    `${BASE}/${connectionId}/journals/${journalId}`,
    { headers: { Authorization: `Bearer ${token}` } }
  );
  return apiClient.handleResponse<Journal>(response);
}

// =============================================================================
// Manual Journals
// =============================================================================

export async function getManualJournals(
  token: string,
  connectionId: string,
  options: {
    page?: number;
    limit?: number;
    status?: string;
  } = {}
): Promise<ManualJournalListResponse> {
  const params = new URLSearchParams();
  if (options.page) params.set('page', options.page.toString());
  if (options.limit) params.set('limit', options.limit.toString());
  if (options.status) params.set('status', options.status);

  const url = `${BASE}/${connectionId}/manual-journals${params.toString() ? `?${params}` : ''}`;
  const response = await apiClient.get(url, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return apiClient.handleResponse<ManualJournalListResponse>(response);
}

export async function getManualJournal(
  token: string,
  connectionId: string,
  manualJournalId: string
): Promise<ManualJournal> {
  const response = await apiClient.get(
    `${BASE}/${connectionId}/manual-journals/${manualJournalId}`,
    { headers: { Authorization: `Bearer ${token}` } }
  );
  return apiClient.handleResponse<ManualJournal>(response);
}

// =============================================================================
// Sync Status
// =============================================================================

export async function getTransactionSyncStatus(
  token: string,
  connectionId: string
): Promise<TransactionSyncStatus> {
  const response = await apiClient.get(
    `${BASE}/${connectionId}/transactions/sync-status`,
    { headers: { Authorization: `Bearer ${token}` } }
  );
  return apiClient.handleResponse<TransactionSyncStatus>(response);
}
