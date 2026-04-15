'use client';

/**
 * Client Detail Page
 *
 * CRITICAL: In Clairo, "client" = XeroConnection = one business = one BAS to lodge.
 * This page shows a single client BUSINESS (XeroConnection) with tabs:
 * - Overview: Financial summary cards
 * - Contacts: Customers/suppliers OF this business (XeroClients)
 * - Invoices: Sales and purchase invoices
 * - Transactions: Bank transactions
 */

import { useAuth } from '@clerk/nextjs';
import {
  ArrowLeft,
  BookOpen,
  Briefcase,
  Calendar,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  CreditCard,
  FileText,
  Loader2,
  Mail,
  Minus,
  Phone,
  Receipt,
  Users,
  Wallet,
} from 'lucide-react';
import Link from 'next/link';
import { useParams, useSearchParams } from 'next/navigation';
import { useCallback, useEffect, useState } from 'react';
import { toast } from 'sonner';

import { ConvertInsightModal } from '@/components/action-items';
import { BASTab } from '@/components/bas';
import {
  LedgerCardsHeader,
  TrafficLightDashboard,
  type Tab,
} from '@/components/client-detail';
import { ClientNotesBar } from '@/components/clients/ClientNotesBar';
import { InsightsDashboard } from '@/components/insights';
import { SyncPhaseIndicator } from '@/components/integrations/xero';
import { InviteToPortalModal } from '@/components/portal';
import { QualityScoreCard, QualityIssuesList } from '@/components/quality';
import { TaxPlanningWorkspace } from '@/components/tax-planning/TaxPlanningWorkspace';
import { Card } from '@/components/ui/card';
import {
  dismissInsight,
  expandInsight,
  generateInsights,
  getInsights,
  markInsightActioned,
  markInsightViewed,
} from '@/lib/api/insights';
import {
  getCreditNotes,
  getJournals,
  getManualJournals,
  getPayments,
  type CreditNote,
  type Journal,
  type ManualJournal,
  type Payment,
} from '@/lib/api/transactions';
import { apiClient } from '@/lib/api-client';
import { formatCurrency, formatDate } from '@/lib/formatters';
import {
  type QualityIssue,
  type QualityScoreResponse,
  dismissQualityIssue,
  getQualityIssues,
  getQualityScore,
  recalculateQuality,
} from '@/lib/quality';
import { cn } from '@/lib/utils';
import { getSyncHistory } from '@/lib/xero-sync';
import type { Insight } from '@/types/insights';

// =============================================================================
// Types
// =============================================================================

interface ClientDetail {
  id: string;
  organization_name: string;
  xero_tenant_id: string;
  status: string;
  last_full_sync_at: string | null;
  bas_status: string;
  total_sales: string;
  total_purchases: string;
  gst_collected: string;
  gst_paid: string;
  net_gst: string;
  invoice_count: number;
  transaction_count: number;
  contact_count: number;
  quarter_label: string;
  quarter: number;
  fy_year: number;
  // Payroll/PAYG data
  has_payroll: boolean;
  total_wages: string;
  total_tax_withheld: string;
  total_super: string;
  pay_run_count: number;
  employee_count: number;
  last_payroll_sync_at: string | null;
  // Quality data
  quality_score: string | null;
  critical_issues: number;
  // Contact info
  contact_email?: string | null;
}

interface Contact {
  id: string;
  name: string;
  email: string | null;
  contact_number: string | null;
  abn: string | null;
  contact_type: string;
  is_active: boolean;
}

interface Invoice {
  id: string;
  invoice_number: string | null;
  invoice_type: string;
  contact_name: string | null;
  status: string;
  issue_date: string;
  due_date: string | null;
  subtotal: string;
  tax_amount: string;
  total_amount: string;
  currency: string;
  line_items: Array<{
    description: string | null;
    quantity: string | null;
    unit_amount: string | null;
    account_code: string | null;
    tax_type: string | null;
    line_amount: string | null;
  }> | null;
}

interface Transaction {
  id: string;
  transaction_type: string;
  contact_name: string | null;
  status: string;
  transaction_date: string;
  reference: string | null;
  subtotal: string;
  tax_amount: string;
  total_amount: string;
}

interface Employee {
  id: string;
  xero_employee_id: string;
  first_name: string | null;
  last_name: string | null;
  full_name: string | null;
  email: string | null;
  status: string;
  start_date: string | null;
  termination_date: string | null;
  job_title: string | null;
}

interface PayRun {
  id: string;
  xero_pay_run_id: string;
  status: string;
  period_start: string | null;
  period_end: string | null;
  payment_date: string | null;
  total_wages: string;
  total_tax: string;
  total_super: string;
  total_net_pay: string;
  employee_count: number;
}

// Tab type imported from ClientNavigation component

// =============================================================================
// Constants
// =============================================================================

const CONTACT_TYPE_LABELS: Record<string, string> = {
  customer: 'Customer',
  supplier: 'Supplier',
  both: 'Both',
};

const INVOICE_TYPE_LABELS: Record<string, string> = {
  accrec: 'Sales',
  accpay: 'Purchase',
};

const INVOICE_STATUS_DOT: Record<string, string> = {
  paid: 'bg-status-success',
  authorised: 'bg-status-info',
  draft: 'bg-status-neutral',
  voided: 'bg-status-danger',
  submitted: 'bg-status-warning',
};

const CONTACT_TYPE_DOT: Record<string, string> = {
  customer: 'bg-status-success',
  supplier: 'bg-status-info',
  both: 'bg-status-warning',
};

// =============================================================================
// Component
// =============================================================================

export default function ClientDetailPage() {
  const { id } = useParams();
  const searchParams = useSearchParams();
  const { getToken } = useAuth();

  // Get initial tab from URL query param
  const tabFromUrl = searchParams.get('tab') as Tab | null;
  const validTabs: Tab[] = ['overview', 'bas', 'quality', 'insights', 'tax-planning', 'contacts', 'invoices', 'transactions', 'employees'];
  const initialTab = tabFromUrl && validTabs.includes(tabFromUrl) ? tabFromUrl : 'overview';

  // Client state
  const [client, setClient] = useState<ClientDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Portal invite modal
  const [inviteModalOpen, setInviteModalOpen] = useState(false);

  // Tab state
  const [activeTab, setActiveTab] = useState<Tab>(initialTab);

  // Quarter selector
  const [selectedQuarter, setSelectedQuarter] = useState<number | null>(null);
  const [selectedFyYear, setSelectedFyYear] = useState<number | null>(null);
  const [quarterDropdownOpen, setQuarterDropdownOpen] = useState(false);

  // Contacts state
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [contactsLoading, setContactsLoading] = useState(false);
  const [contactsTotal, setContactsTotal] = useState(0);
  const [contactsPage, setContactsPage] = useState(1);
  const [contactTypeFilter, setContactTypeFilter] = useState('');

  // Invoices state
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [invoicesLoading, setInvoicesLoading] = useState(false);
  const [invoicesTotal, setInvoicesTotal] = useState(0);
  const [invoicesPage, setInvoicesPage] = useState(1);
  const [expandedInvoice, setExpandedInvoice] = useState<string | null>(null);

  // Transactions state
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [transactionsLoading, setTransactionsLoading] = useState(false);
  const [transactionsTotal, setTransactionsTotal] = useState(0);
  const [transactionsPage, setTransactionsPage] = useState(1);

  // Employees state (Payroll)
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [employeesLoading, setEmployeesLoading] = useState(false);
  const [employeesTotal, setEmployeesTotal] = useState(0);
  const [employeesPage, setEmployeesPage] = useState(1);
  const [employeeStatusFilter, setEmployeeStatusFilter] = useState('');

  // Pay Runs state (Payroll)
  const [payRuns, setPayRuns] = useState<PayRun[]>([]);
  const [payRunsLoading, setPayRunsLoading] = useState(false);
  const [payRunsTotal, setPayRunsTotal] = useState(0);
  const [payRunsPage, setPayRunsPage] = useState(1);

  // Credit Notes state (Spec 024)
  const [creditNotes, setCreditNotes] = useState<CreditNote[]>([]);
  const [creditNotesLoading, setCreditNotesLoading] = useState(false);
  const [creditNotesTotal, setCreditNotesTotal] = useState(0);
  const [creditNotesPage, setCreditNotesPage] = useState(1);
  const [creditNoteTypeFilter, setCreditNoteTypeFilter] = useState<'accpaycredit' | 'accreccredit' | ''>('');
  const [expandedCreditNote, setExpandedCreditNote] = useState<string | null>(null);

  // Payments state (Spec 024)
  const [payments, setPayments] = useState<Payment[]>([]);
  const [paymentsLoading, setPaymentsLoading] = useState(false);
  const [paymentsTotal, setPaymentsTotal] = useState(0);
  const [paymentsPage, setPaymentsPage] = useState(1);

  // Journals state (Spec 024)
  const [journals, setJournals] = useState<Journal[]>([]);
  const [journalsLoading, setJournalsLoading] = useState(false);
  const [journalsTotal, setJournalsTotal] = useState(0);
  const [journalsPage, setJournalsPage] = useState(1);
  const [manualJournals, setManualJournals] = useState<ManualJournal[]>([]);
  const [manualJournalsLoading, setManualJournalsLoading] = useState(false);
  const [manualJournalsTotal, setManualJournalsTotal] = useState(0);
  const [journalViewMode, setJournalViewMode] = useState<'system' | 'manual'>('system');
  const [expandedJournal, setExpandedJournal] = useState<string | null>(null);

  // Refresh state
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Active sync phase tracking (Spec 043: Progressive Sync)
  const [activeSyncPhase, setActiveSyncPhase] = useState<number | null>(null);

  // Quality state
  const [quality, setQuality] = useState<QualityScoreResponse | null>(null);
  const [qualityIssues, setQualityIssues] = useState<QualityIssue[]>([]);
  const [qualityLoading, setQualityLoading] = useState(false);
  const [isRecalculating, setIsRecalculating] = useState(false);

  // Insights state
  const [isGeneratingInsights, setIsGeneratingInsights] = useState(false);


  const [insights, setInsights] = useState<Insight[]>([]);
  const [insightsLoading, setInsightsLoading] = useState(false);
  const [insightsTotal, setInsightsTotal] = useState(0);
  const [insightToConvert, setInsightToConvert] = useState<Insight | null>(null);
  const [isExpandingInsight, setIsExpandingInsight] = useState(false);

  // ==========================================================================
  // Data Fetching
  // ==========================================================================

  const fetchClient = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const token = await getToken();
      if (!token) throw new Error('Not authenticated');

      const params = new URLSearchParams();
      if (selectedQuarter) params.set('quarter', selectedQuarter.toString());
      if (selectedFyYear) params.set('fy_year', selectedFyYear.toString());

      const url = `/api/v1/clients/${id}${params.toString() ? `?${params}` : ''}`;
      const response = await apiClient.get(url, {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!response.ok) {
        if (response.status === 404) throw new Error('Client not found');
        throw new Error('Failed to fetch client');
      }

      const data: ClientDetail = await response.json();
      setClient(data);

      // Initialize quarter selection from response
      if (!selectedQuarter) {
        setSelectedQuarter(data.quarter);
        setSelectedFyYear(data.fy_year);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setIsLoading(false);
    }
  }, [getToken, id, selectedQuarter, selectedFyYear]);

  const fetchContacts = useCallback(async () => {
    try {
      setContactsLoading(true);
      const token = await getToken();
      if (!token) return;

      const params = new URLSearchParams({
        page: contactsPage.toString(),
        limit: '25',
      });
      if (contactTypeFilter) params.set('contact_type', contactTypeFilter);

      const response = await apiClient.get(
        `/api/v1/clients/${id}/contacts?${params}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );

      if (response.ok) {
        const data = await response.json();
        setContacts(data.contacts || []);
        setContactsTotal(data.total || 0);
      }
    } catch (err) {
      console.error('Failed to fetch contacts:', err);
    } finally {
      setContactsLoading(false);
    }
  }, [getToken, id, contactsPage, contactTypeFilter]);

  const fetchInvoices = useCallback(async () => {
    try {
      setInvoicesLoading(true);
      const token = await getToken();
      if (!token) return;

      const params = new URLSearchParams({
        page: invoicesPage.toString(),
        limit: '20',
      });

      const response = await apiClient.get(
        `/api/v1/clients/${id}/invoices?${params}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );

      if (response.ok) {
        const data = await response.json();
        setInvoices(data.invoices || []);
        setInvoicesTotal(data.total || 0);
      }
    } catch (err) {
      console.error('Failed to fetch invoices:', err);
    } finally {
      setInvoicesLoading(false);
    }
  }, [getToken, id, invoicesPage]);

  const fetchTransactions = useCallback(async () => {
    try {
      setTransactionsLoading(true);
      const token = await getToken();
      if (!token) return;

      const params = new URLSearchParams({
        page: transactionsPage.toString(),
        limit: '20',
      });

      const response = await apiClient.get(
        `/api/v1/clients/${id}/transactions?${params}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );

      if (response.ok) {
        const data = await response.json();
        setTransactions(data.transactions || []);
        setTransactionsTotal(data.total || 0);
      }
    } catch (err) {
      console.error('Failed to fetch transactions:', err);
    } finally {
      setTransactionsLoading(false);
    }
  }, [getToken, id, transactionsPage]);

  const fetchEmployees = useCallback(async () => {
    try {
      setEmployeesLoading(true);
      const token = await getToken();
      if (!token) return;

      const params = new URLSearchParams({
        page: employeesPage.toString(),
        limit: '25',
      });
      if (employeeStatusFilter) params.set('status', employeeStatusFilter);

      const response = await apiClient.get(
        `/api/v1/clients/${id}/employees?${params}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );

      if (response.ok) {
        const data = await response.json();
        setEmployees(data.employees || []);
        setEmployeesTotal(data.total || 0);
      }
    } catch (err) {
      console.error('Failed to fetch employees:', err);
    } finally {
      setEmployeesLoading(false);
    }
  }, [getToken, id, employeesPage, employeeStatusFilter]);

  const fetchPayRuns = useCallback(async () => {
    try {
      setPayRunsLoading(true);
      const token = await getToken();
      if (!token) return;

      const params = new URLSearchParams({
        page: payRunsPage.toString(),
        limit: '20',
      });

      const response = await apiClient.get(
        `/api/v1/clients/${id}/pay-runs?${params}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );

      if (response.ok) {
        const data = await response.json();
        setPayRuns(data.pay_runs || []);
        setPayRunsTotal(data.total || 0);
      }
    } catch (err) {
      console.error('Failed to fetch pay runs:', err);
    } finally {
      setPayRunsLoading(false);
    }
  }, [getToken, id, payRunsPage]);

  // Spec 024: Credit Notes fetch
  const fetchCreditNotes = useCallback(async () => {
    try {
      setCreditNotesLoading(true);
      const token = await getToken();
      if (!token || !client?.id) return;

      const data = await getCreditNotes(token, client.id, {
        page: creditNotesPage,
        limit: 20,
        credit_note_type: creditNoteTypeFilter || undefined,
      });
      setCreditNotes(data.credit_notes || []);
      setCreditNotesTotal(data.total || 0);
    } catch (err) {
      console.error('Failed to fetch credit notes:', err);
    } finally {
      setCreditNotesLoading(false);
    }
  }, [getToken, client?.id, creditNotesPage, creditNoteTypeFilter]);

  // Spec 024: Payments fetch
  const fetchPayments = useCallback(async () => {
    try {
      setPaymentsLoading(true);
      const token = await getToken();
      if (!token || !client?.id) return;

      const data = await getPayments(token, client.id, {
        page: paymentsPage,
        limit: 20,
      });
      setPayments(data.payments || []);
      setPaymentsTotal(data.total || 0);
    } catch (err) {
      console.error('Failed to fetch payments:', err);
    } finally {
      setPaymentsLoading(false);
    }
  }, [getToken, client?.id, paymentsPage]);

  // Spec 024: Journals fetch
  const fetchJournals = useCallback(async () => {
    try {
      setJournalsLoading(true);
      const token = await getToken();
      if (!token || !client?.id) return;

      const data = await getJournals(token, client.id, {
        page: journalsPage,
        limit: 20,
      });
      setJournals(data.journals || []);
      setJournalsTotal(data.total || 0);
    } catch (err) {
      console.error('Failed to fetch journals:', err);
    } finally {
      setJournalsLoading(false);
    }
  }, [getToken, client?.id, journalsPage]);

  // Spec 024: Manual Journals fetch
  const fetchManualJournals = useCallback(async () => {
    try {
      setManualJournalsLoading(true);
      const token = await getToken();
      if (!token || !client?.id) return;

      const data = await getManualJournals(token, client.id, {
        page: journalsPage,
        limit: 20,
      });
      setManualJournals(data.manual_journals || []);
      setManualJournalsTotal(data.total || 0);
    } catch (err) {
      console.error('Failed to fetch manual journals:', err);
    } finally {
      setManualJournalsLoading(false);
    }
  }, [getToken, client?.id, journalsPage]);

  const fetchQuality = useCallback(async () => {
    try {
      setQualityLoading(true);
      const token = await getToken();
      if (!token || !client?.id) return;

      const connectionId = client.id;

      // Fetch quality score and issues in parallel for the selected quarter
      const [scoreData, issuesData] = await Promise.all([
        getQualityScore(token, connectionId, selectedQuarter ?? undefined, selectedFyYear ?? undefined),
        getQualityIssues(token, connectionId, {
          quarter: selectedQuarter ?? undefined,
          fyYear: selectedFyYear ?? undefined,
        }),
      ]);

      setQuality(scoreData);
      setQualityIssues(issuesData.issues || []);
    } catch (err) {
      console.error('Failed to fetch quality data:', err);
    } finally {
      setQualityLoading(false);
    }
  }, [getToken, client?.id, selectedQuarter, selectedFyYear]);

  const handleRecalculateQuality = useCallback(async () => {
    try {
      setIsRecalculating(true);
      const token = await getToken();
      if (!token || !client?.id) return;

      await recalculateQuality(token, client.id, selectedQuarter ?? undefined, selectedFyYear ?? undefined);
      // Refetch quality data after recalculation
      await fetchQuality();
    } catch (err) {
      console.error('Failed to recalculate quality:', err);
    } finally {
      setIsRecalculating(false);
    }
  }, [getToken, client?.id, fetchQuality, selectedQuarter, selectedFyYear]);

  const handleDismissIssue = useCallback(async (issueId: string, reason: string) => {
    try {
      const token = await getToken();
      if (!token || !client?.id) return;

      await dismissQualityIssue(token, client.id, issueId, reason);
      // Refetch issues after dismissal
      const issuesData = await getQualityIssues(token, client.id);
      setQualityIssues(issuesData.issues || []);
    } catch (err) {
      console.error('Failed to dismiss issue:', err);
    }
  }, [getToken, client?.id]);

  const fetchInsights = useCallback(async () => {
    try {
      setInsightsLoading(true);
      const token = await getToken();
      if (!token || !client?.id) return;

      const response = await getInsights(token, {
        client_id: client.id,
        limit: 50,
      });
      setInsights(response.insights || []);
      setInsightsTotal(response.total || 0);
    } catch (err) {
      console.error('Failed to fetch insights:', err);
    } finally {
      setInsightsLoading(false);
    }
  }, [getToken, client?.id]);

  // Initial load
  useEffect(() => {
    fetchClient();
  }, [fetchClient]);

  // Poll for active sync phase (Spec 043: Progressive Sync)
  useEffect(() => {
    const checkActiveSync = async () => {
      try {
        const token = await getToken();
        if (!token || !client?.id) return;
        const history = await getSyncHistory(token, client.id, 1, 0);
        const activeJob = history.jobs.find(
          (j) => j.status === 'in_progress' || j.status === 'pending'
        );
        setActiveSyncPhase(activeJob?.sync_phase ?? null);
      } catch {
        // Silently ignore — non-critical UI enhancement
      }
    };

    checkActiveSync();
    // Poll every 30 seconds while there might be an active sync (skip when tab hidden)
    const interval = setInterval(() => {
      if (!document.hidden) checkActiveSync();
    }, 30000);
    return () => clearInterval(interval);
  }, [client?.id, getToken]);

  // Load tab data when tab changes
  useEffect(() => {
    if (activeTab === 'quality') fetchQuality();
    if (activeTab === 'insights') fetchInsights();
    if (activeTab === 'contacts') fetchContacts();
    if (activeTab === 'invoices') fetchInvoices();
    if (activeTab === 'transactions') fetchTransactions();
    if (activeTab === 'employees') fetchEmployees();
    if (activeTab === 'pay-runs') fetchPayRuns();
    // Spec 024: New transaction tabs
    if (activeTab === 'credit-notes') fetchCreditNotes();
    if (activeTab === 'payments') fetchPayments();
    if (activeTab === 'journals') {
      if (journalViewMode === 'system') fetchJournals();
      else fetchManualJournals();
    }
  }, [activeTab, fetchQuality, fetchInsights, fetchContacts, fetchInvoices, fetchTransactions, fetchEmployees, fetchPayRuns, fetchCreditNotes, fetchPayments, fetchJournals, fetchManualJournals, journalViewMode]);

  // ==========================================================================
  // Handlers
  // ==========================================================================

  const handleRefresh = async () => {
    setIsRefreshing(true);
    try {
      await fetchClient();
      if (activeTab === 'quality') await fetchQuality();
      if (activeTab === 'contacts') await fetchContacts();
      if (activeTab === 'invoices') await fetchInvoices();
      if (activeTab === 'transactions') await fetchTransactions();
      if (activeTab === 'employees') await fetchEmployees();
      if (activeTab === 'pay-runs') await fetchPayRuns();
      // Spec 024: New transaction tabs
      if (activeTab === 'credit-notes') await fetchCreditNotes();
      if (activeTab === 'payments') await fetchPayments();
      if (activeTab === 'journals') {
        await fetchJournals();
        await fetchManualJournals();
      }
    } finally {
      setIsRefreshing(false);
    }
  };

  const handleGenerateInsights = async () => {
    const toastId = toast.loading('Analyzing client data with AI...', {
      description: 'This usually takes 20-30 seconds',
    });

    try {
      setIsGeneratingInsights(true);
      const token = await getToken();
      if (!token || !client?.id) {
        toast.dismiss(toastId);
        return;
      }

      const result = await generateInsights(token, client.id);

      toast.success(
        result.generated_count > 0
          ? `Generated ${result.generated_count} new insight${result.generated_count !== 1 ? 's' : ''}`
          : 'Analysis complete — no new insights',
        { id: toastId, description: 'AI analysis finished' }
      );

      // Refresh insights and switch to insights tab
      if (result.generated_count > 0) {
        setActiveTab('insights');
      }
      await fetchInsights();
    } catch (err) {
      toast.error('Insight generation failed', {
        id: toastId,
        description: err instanceof Error ? err.message : 'Please try again',
      });
    } finally {
      setIsGeneratingInsights(false);
    }
  };

  const handleInsightAction = async (insightId: string, action: 'view' | 'action' | 'dismiss') => {
    try {
      const token = await getToken();
      if (!token) return;

      if (action === 'view') {
        await markInsightViewed(token, insightId);
      } else if (action === 'action') {
        await markInsightActioned(token, insightId);
      } else if (action === 'dismiss') {
        await dismissInsight(token, insightId);
      }

      // Update local state
      setInsights(prev => prev.map(i => {
        if (i.id !== insightId) return i;
        if (action === 'view') return { ...i, status: 'viewed' as const };
        if (action === 'action') return { ...i, status: 'actioned' as const };
        if (action === 'dismiss') return { ...i, status: 'dismissed' as const };
        return i;
      }).filter(i => action !== 'dismiss' || i.id !== insightId));
    } catch (err) {
      console.error(`Failed to ${action} insight:`, err);
    }
  };

  const handleExpandInsight = async (insightId: string) => {
    try {
      setIsExpandingInsight(true);
      const token = await getToken();
      if (!token) return;

      const expandedInsight = await expandInsight(token, insightId);

      // Update in the insights list (InsightsDashboard syncs selectedInsight via useEffect)
      setInsights(prev => prev.map(i =>
        i.id === insightId ? expandedInsight : i
      ));
    } catch (err) {
      console.error('Failed to expand insight:', err);
    } finally {
      setIsExpandingInsight(false);
    }
  };

  // ==========================================================================
  // Helpers
  // ==========================================================================

  // Generate quarter options (current + 4 previous)
  const getQuarterOptions = () => {
    const options = [];
    const now = new Date();
    const currentMonth = now.getMonth() + 1;
    const currentYear = now.getFullYear();

    let q, fy;
    if (currentMonth >= 7) {
      fy = currentYear + 1;
      q = currentMonth <= 9 ? 1 : 2;
    } else {
      fy = currentYear;
      q = currentMonth <= 3 ? 3 : 4;
    }

    for (let i = 0; i < 5; i++) {
      options.push({ quarter: q, fy_year: fy, label: `Q${q} FY${String(fy).slice(-2)}` });
      q--;
      if (q < 1) {
        q = 4;
        fy--;
      }
    }
    return options;
  };

  // Generate quarter options for dropdown
  const quarterOptions = getQuarterOptions();

  // ==========================================================================
  // Render
  // ==========================================================================

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error || !client) {
    return (
      <div className="space-y-5">
        <Link
          href="/clients"
          className="inline-flex items-center gap-2 text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Clients
        </Link>
        <Card className="p-6 text-center">
          <p className="text-status-danger">{error || 'Client not found'}</p>
        </Card>
      </div>
    );
  }

  return (
    <div className="-mx-6 -mt-6 bg-background min-h-[calc(100vh-4rem)]">
      {/* Ledger Cards Header with Navigation */}
      <LedgerCardsHeader
        client={{
          name: client.organization_name,
          status: client.status,
          lastSynced: client.last_full_sync_at,
          quarterLabel: client.quarter_label,
          hasPayroll: client.has_payroll,
        }}
        counts={{
          criticalIssues: client.critical_issues,
          insights: insightsTotal,
          contacts: client.contact_count,
          invoices: client.invoice_count,
          transactions: client.transaction_count,
          creditNotes: creditNotesTotal,
          payments: paymentsTotal,
          journals: journalsTotal,
          employees: client.employee_count,
          payRuns: client.pay_run_count,
        }}
        activeTab={activeTab}
        onTabChange={setActiveTab}
        onRefresh={handleRefresh}
        onAnalyze={handleGenerateInsights}
        onInvite={() => setInviteModalOpen(true)}
        isRefreshing={isRefreshing}
        isAnalyzing={isGeneratingInsights}
        quarterDropdownOpen={quarterDropdownOpen}
        setQuarterDropdownOpen={setQuarterDropdownOpen}
        quarterOptions={quarterOptions}
        onQuarterSelect={(quarter, year) => {
          setSelectedQuarter(quarter);
          setSelectedFyYear(year);
          setQuarterDropdownOpen(false);
        }}
        clientId={id as string}
      />

      {/* Persistent Client Notes (Spec 058 - US3) */}
      <ClientNotesBar clientId={id as string} getToken={getToken} />

      {/* Main Content - Full width with padding */}
      <div className="px-4 sm:px-6 lg:px-8 py-6">
        {/* Tab Content */}
      {activeTab === 'overview' && (
        <TrafficLightDashboard
          client={client}
          qualityIssues={qualityIssues}
          insights={insights}
          onViewAllIssues={() => setActiveTab('quality')}
          onViewAllInsights={() => setActiveTab('insights')}
          onRefreshData={handleRefresh}
          isRefreshing={isRefreshing}
          clientId={id as string}
        />
      )}

      {activeTab === 'bas' && (
        <>
          <SyncPhaseIndicator requiredPhase={2} activeSyncPhase={activeSyncPhase} dataLabel="financial" />
          <BASTab
            connectionId={client.id}
            getToken={getToken}
            selectedQuarter={selectedQuarter || client.quarter}
            selectedFyYear={selectedFyYear || client.fy_year}
          />
        </>
      )}

      {activeTab === 'quality' && (
        <div className="space-y-5">
          {/* Quality Score Card */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <QualityScoreCard
              quality={quality}
              isLoading={qualityLoading}
              onRecalculate={handleRecalculateQuality}
              isRecalculating={isRecalculating}
            />

            {/* Quality Explanation Card */}
            <div className="bg-card rounded-xl border border-border p-6">
              <h3 className="text-lg font-semibold text-foreground mb-4">
                Understanding Quality Scores
              </h3>
              <div className="space-y-4 text-sm text-muted-foreground">
                <div>
                  <h4 className="font-medium text-foreground">Data Freshness (20%)</h4>
                  <p>How recently data was synced from Xero. Syncing within 24 hours = 100%.</p>
                </div>
                <div>
                  <h4 className="font-medium text-foreground">Reconciliation (30%)</h4>
                  <p>Percentage of bank transactions that have been reviewed and authorised in Xero.</p>
                </div>
                <div>
                  <h4 className="font-medium text-foreground">Categorization (20%)</h4>
                  <p>Percentage of invoices and transactions with proper GST/tax codes assigned.</p>
                </div>
                <div>
                  <h4 className="font-medium text-foreground">Completeness (15%)</h4>
                  <p>Presence of all required data types: chart of accounts, contacts, invoices, and transactions.</p>
                </div>
                <div>
                  <h4 className="font-medium text-foreground">PAYG Readiness (15%)</h4>
                  <p>If payroll is enabled, checks for employees and pay runs. Not applicable if no payroll access.</p>
                </div>
                <div className="pt-4 border-t">
                  <h4 className="font-medium text-foreground">Score Tiers</h4>
                  <div className="mt-2 space-y-1">
                    <p><span className="inline-block w-3 h-3 bg-status-success rounded-full mr-2"></span> Good (80%+): Ready for BAS</p>
                    <p><span className="inline-block w-3 h-3 bg-status-warning rounded-full mr-2"></span> Fair (50-80%): Review recommended</p>
                    <p><span className="inline-block w-3 h-3 bg-status-danger rounded-full mr-2"></span> Poor (&lt;50%): Action required</p>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Quality Issues */}
          {qualityIssues.length > 0 && (
            <div className="bg-card rounded-xl border border-border p-6">
              <h3 className="text-lg font-semibold text-foreground mb-4">
                Issues Found ({qualityIssues.length})
              </h3>
              <QualityIssuesList
                issues={qualityIssues}
                onDismiss={handleDismissIssue}
              />
            </div>
          )}

          {qualityIssues.length === 0 && !qualityLoading && quality?.has_score && (
            <Card className="p-6 text-center">
              <CheckCircle2 className="w-12 h-12 text-status-success mx-auto mb-3" />
              <h3 className="text-lg font-semibold text-foreground">
                No Issues Found
              </h3>
              <p className="text-muted-foreground mt-1">
                Data quality is good for {client.quarter_label}. Ready for BAS preparation.
              </p>
            </Card>
          )}
        </div>
      )}

      {activeTab === 'insights' && (
        <>
          <InsightsDashboard
            insights={insights}
            insightsLoading={insightsLoading}
            clientName={client.organization_name}
            onInsightAction={handleInsightAction}
            onExpandInsight={handleExpandInsight}
            onConvertInsight={(insight) => setInsightToConvert(insight)}
            isExpandingInsight={isExpandingInsight}
          />

          {/* Convert to Action Item Modal */}
          {insightToConvert && (
            <ConvertInsightModal
              insight={{
                id: insightToConvert.id,
                title: insightToConvert.title,
                summary: insightToConvert.summary,
                priority: insightToConvert.priority,
                client_name: insightToConvert.client_name,
                action_deadline: insightToConvert.action_deadline,
              }}
              isOpen={!!insightToConvert}
              onClose={() => setInsightToConvert(null)}
              onSuccess={() => {
                fetchInsights();
              }}
            />
          )}
        </>
      )}

      {activeTab === 'tax-planning' && client && (
        <TaxPlanningWorkspace
          connectionId={client.id}
          clientName={client.organization_name}
        />
      )}

      {activeTab === 'contacts' && (
        <div className="space-y-4">
          {/* Filter */}
          <div className="flex items-center gap-4">
            <select
              value={contactTypeFilter}
              onChange={(e) => {
                setContactTypeFilter(e.target.value);
                setContactsPage(1);
              }}
              className="border border-border bg-card text-foreground rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            >
              <option value="">All Types</option>
              <option value="customer">Customers</option>
              <option value="supplier">Suppliers</option>
            </select>
          </div>

          {/* Contacts Table */}
          <div className="bg-card rounded-xl border border-border overflow-hidden">
            {contactsLoading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
              </div>
            ) : contacts.length === 0 ? (
              <div className="p-8 text-center">
                <Users className="w-12 h-12 text-muted-foreground/30 mx-auto mb-4" />
                <p className="text-muted-foreground">No contacts found</p>
              </div>
            ) : (
              <>
                <table className="w-full">
                  <thead className="bg-muted border-b border-border">
                    <tr>
                      <th className="text-left px-4 py-2 text-sm font-medium text-muted-foreground">Contact</th>
                      <th className="text-left px-4 py-2 text-sm font-medium text-muted-foreground">Type</th>
                      <th className="text-left px-4 py-2 text-sm font-medium text-muted-foreground">Email</th>
                      <th className="text-left px-4 py-2 text-sm font-medium text-muted-foreground">ABN</th>
                      <th className="text-left px-4 py-2 text-sm font-medium text-muted-foreground">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {contacts.map((contact) => (
                      <tr key={contact.id} className="hover:bg-muted">
                        <td className="px-4 py-2.5">
                          <div className="flex items-center gap-3">
                            <div className="w-8 h-8 bg-muted rounded-full flex items-center justify-center">
                              <Users className="w-4 h-4 text-muted-foreground" />
                            </div>
                            <div>
                              <p className="font-medium text-foreground">{contact.name}</p>
                              {contact.contact_number && (
                                <p className="text-sm text-muted-foreground flex items-center gap-1">
                                  <Phone className="w-3 h-3" />
                                  {contact.contact_number}
                                </p>
                              )}
                            </div>
                          </div>
                        </td>
                        <td className="px-4 py-2.5">
                          <span className="inline-flex items-center gap-1.5 text-xs">
                            <span className={cn('h-1.5 w-1.5 rounded-full', CONTACT_TYPE_DOT[contact.contact_type] || 'bg-status-neutral')} />
                            <span className="text-muted-foreground">{CONTACT_TYPE_LABELS[contact.contact_type] || contact.contact_type}</span>
                          </span>
                        </td>
                        <td className="px-4 py-2.5 text-sm text-muted-foreground">
                          {contact.email ? (
                            <span className="flex items-center gap-1">
                              <Mail className="w-3 h-3" />
                              {contact.email}
                            </span>
                          ) : '-'}
                        </td>
                        <td className="px-4 py-2.5 text-sm text-muted-foreground">{contact.abn || '-'}</td>
                        <td className="px-4 py-2.5">
                          <span className="inline-flex items-center gap-1.5 text-xs">
                            <span className={cn('h-1.5 w-1.5 rounded-full', contact.is_active ? 'bg-status-success' : 'bg-status-neutral')} />
                            <span className="text-muted-foreground">{contact.is_active ? 'Active' : 'Inactive'}</span>
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {/* Pagination */}
                {Math.ceil(contactsTotal / 25) > 1 && (
                  <div className="px-4 py-2.5 border-t border-border flex items-center justify-between">
                    <p className="text-sm text-muted-foreground">
                      Showing {(contactsPage - 1) * 25 + 1} to {Math.min(contactsPage * 25, contactsTotal)} of {contactsTotal}
                    </p>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => setContactsPage(p => Math.max(1, p - 1))}
                        disabled={contactsPage === 1}
                        className="p-2 rounded-lg border border-border disabled:opacity-50 hover:bg-muted"
                      >
                        <ChevronLeft className="w-4 h-4" />
                      </button>
                      <span className="text-sm text-muted-foreground">
                        Page {contactsPage} of {Math.ceil(contactsTotal / 25)}
                      </span>
                      <button
                        onClick={() => setContactsPage(p => Math.min(Math.ceil(contactsTotal / 25), p + 1))}
                        disabled={contactsPage >= Math.ceil(contactsTotal / 25)}
                        className="p-2 rounded-lg border border-border disabled:opacity-50 hover:bg-muted"
                      >
                        <ChevronRight className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}

      {activeTab === 'invoices' && (
        <div className="bg-card rounded-xl border border-border overflow-hidden">
          {invoicesLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
            </div>
          ) : invoices.length === 0 ? (
            <div className="p-8 text-center">
              <FileText className="w-12 h-12 text-muted-foreground/30 mx-auto mb-4" />
              <p className="text-muted-foreground">No invoices found for this quarter</p>
            </div>
          ) : (
            <>
              <table className="w-full">
                <thead className="bg-muted border-b border-border">
                  <tr>
                    <th className="text-left px-4 py-2 text-sm font-medium text-muted-foreground">Invoice</th>
                    <th className="text-left px-4 py-2 text-sm font-medium text-muted-foreground">Type</th>
                    <th className="text-left px-4 py-2 text-sm font-medium text-muted-foreground">Contact</th>
                    <th className="text-left px-4 py-2 text-sm font-medium text-muted-foreground">Date</th>
                    <th className="text-left px-4 py-2 text-sm font-medium text-muted-foreground">Status</th>
                    <th className="text-right px-4 py-2 text-sm font-medium text-muted-foreground">Amount</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {invoices.map((invoice) => (
                    <>
                      <tr
                        key={invoice.id}
                        className="hover:bg-muted cursor-pointer"
                        onClick={() => setExpandedInvoice(expandedInvoice === invoice.id ? null : invoice.id)}
                      >
                        <td className="px-4 py-2.5 font-medium text-foreground">
                          {invoice.invoice_number || '-'}
                        </td>
                        <td className="px-4 py-2.5">
                          <span className="inline-flex items-center gap-1.5 text-xs">
                            <span className={cn('h-1.5 w-1.5 rounded-full', invoice.invoice_type === 'accrec' ? 'bg-status-success' : 'bg-status-info')} />
                            <span className="text-muted-foreground">{INVOICE_TYPE_LABELS[invoice.invoice_type] || invoice.invoice_type}</span>
                          </span>
                        </td>
                        <td className="px-4 py-2.5 text-sm text-muted-foreground">{invoice.contact_name || '-'}</td>
                        <td className="px-4 py-2.5 text-sm text-muted-foreground">{formatDate(invoice.issue_date)}</td>
                        <td className="px-4 py-2.5">
                          <span className="inline-flex items-center gap-1.5 text-xs">
                            <span className={cn('h-1.5 w-1.5 rounded-full', INVOICE_STATUS_DOT[invoice.status] || 'bg-status-neutral')} />
                            <span className="text-muted-foreground capitalize">{invoice.status}</span>
                          </span>
                        </td>
                        <td className="px-4 py-2.5 text-right font-medium text-foreground tabular-nums">
                          {formatCurrency(invoice.total_amount)}
                        </td>
                      </tr>
                      {expandedInvoice === invoice.id && invoice.line_items && (
                        <tr key={`${invoice.id}-details`}>
                          <td colSpan={6} className="px-4 py-2.5 bg-muted">
                            <div className="text-sm">
                              <p className="font-medium text-foreground mb-2">Line Items</p>
                              <table className="w-full">
                                <thead>
                                  <tr className="text-xs text-muted-foreground">
                                    <th className="text-left pb-2">Description</th>
                                    <th className="text-right pb-2">Qty</th>
                                    <th className="text-right pb-2">Unit Price</th>
                                    <th className="text-right pb-2">Amount</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {invoice.line_items.map((item, idx) => (
                                    <tr key={idx} className="text-muted-foreground">
                                      <td className="py-1">{item.description || '-'}</td>
                                      <td className="py-1 text-right">{item.quantity || '-'}</td>
                                      <td className="py-1 text-right tabular-nums">{item.unit_amount ? formatCurrency(item.unit_amount) : '-'}</td>
                                      <td className="py-1 text-right tabular-nums">{item.line_amount ? formatCurrency(item.line_amount) : '-'}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          </td>
                        </tr>
                      )}
                    </>
                  ))}
                </tbody>
              </table>
              {/* Pagination */}
              {Math.ceil(invoicesTotal / 20) > 1 && (
                <div className="px-4 py-2.5 border-t border-border flex items-center justify-between">
                  <p className="text-sm text-muted-foreground">
                    Showing {(invoicesPage - 1) * 20 + 1} to {Math.min(invoicesPage * 20, invoicesTotal)} of {invoicesTotal}
                  </p>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setInvoicesPage(p => Math.max(1, p - 1))}
                      disabled={invoicesPage === 1}
                      className="p-2 rounded-lg border border-border disabled:opacity-50 hover:bg-muted"
                    >
                      <ChevronLeft className="w-4 h-4" />
                    </button>
                    <span className="text-sm text-muted-foreground">
                      Page {invoicesPage} of {Math.ceil(invoicesTotal / 20)}
                    </span>
                    <button
                      onClick={() => setInvoicesPage(p => Math.min(Math.ceil(invoicesTotal / 20), p + 1))}
                      disabled={invoicesPage >= Math.ceil(invoicesTotal / 20)}
                      className="p-2 rounded-lg border border-border disabled:opacity-50 hover:bg-muted"
                    >
                      <ChevronRight className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {activeTab === 'transactions' && (
        <>
          <SyncPhaseIndicator requiredPhase={2} activeSyncPhase={activeSyncPhase} dataLabel="transaction" />
          <div className="bg-card rounded-xl border border-border overflow-hidden">
            {transactionsLoading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
            </div>
          ) : transactions.length === 0 ? (
            <div className="p-8 text-center">
              <Receipt className="w-12 h-12 text-muted-foreground/30 mx-auto mb-4" />
              <p className="text-muted-foreground">No transactions found for this quarter</p>
            </div>
          ) : (
            <>
              <table className="w-full">
                <thead className="bg-muted border-b border-border">
                  <tr>
                    <th className="text-left px-4 py-2 text-sm font-medium text-muted-foreground">Reference</th>
                    <th className="text-left px-4 py-2 text-sm font-medium text-muted-foreground">Type</th>
                    <th className="text-left px-4 py-2 text-sm font-medium text-muted-foreground">Contact</th>
                    <th className="text-left px-4 py-2 text-sm font-medium text-muted-foreground">Date</th>
                    <th className="text-left px-4 py-2 text-sm font-medium text-muted-foreground">Status</th>
                    <th className="text-right px-4 py-2 text-sm font-medium text-muted-foreground">Amount</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {transactions.map((tx) => (
                    <tr key={tx.id} className="hover:bg-muted">
                      <td className="px-4 py-2.5 font-medium text-foreground">{tx.reference || '-'}</td>
                      <td className="px-4 py-2.5">
                        <span className="inline-flex items-center gap-1.5 text-xs">
                          <span className={cn('h-1.5 w-1.5 rounded-full', tx.transaction_type === 'receive' ? 'bg-status-success' : 'bg-status-danger')} />
                          <span className="text-muted-foreground capitalize">{tx.transaction_type}</span>
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-sm text-muted-foreground">{tx.contact_name || '-'}</td>
                      <td className="px-4 py-2.5 text-sm text-muted-foreground">{formatDate(tx.transaction_date)}</td>
                      <td className="px-4 py-2.5">
                        <span className="inline-flex items-center gap-1.5 text-xs">
                          <span className="h-1.5 w-1.5 rounded-full bg-status-neutral" />
                          <span className="text-muted-foreground">{tx.status}</span>
                        </span>
                      </td>
                      <td className={cn('px-4 py-2.5 text-right font-medium tabular-nums', tx.transaction_type === 'receive' ? 'text-status-success' : 'text-status-danger')}>
                        {tx.transaction_type === 'receive' ? '+' : '-'}{formatCurrency(tx.total_amount)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {/* Pagination */}
              {Math.ceil(transactionsTotal / 20) > 1 && (
                <div className="px-4 py-2.5 border-t border-border flex items-center justify-between">
                  <p className="text-sm text-muted-foreground">
                    Showing {(transactionsPage - 1) * 20 + 1} to {Math.min(transactionsPage * 20, transactionsTotal)} of {transactionsTotal}
                  </p>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setTransactionsPage(p => Math.max(1, p - 1))}
                      disabled={transactionsPage === 1}
                      className="p-2 rounded-lg border border-border disabled:opacity-50 hover:bg-muted"
                    >
                      <ChevronLeft className="w-4 h-4" />
                    </button>
                    <span className="text-sm text-muted-foreground">
                      Page {transactionsPage} of {Math.ceil(transactionsTotal / 20)}
                    </span>
                    <button
                      onClick={() => setTransactionsPage(p => Math.min(Math.ceil(transactionsTotal / 20), p + 1))}
                      disabled={transactionsPage >= Math.ceil(transactionsTotal / 20)}
                      className="p-2 rounded-lg border border-border disabled:opacity-50 hover:bg-muted"
                    >
                      <ChevronRight className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
        </>
      )}

      {/* Spec 024: Credit Notes Tab */}
      {activeTab === 'credit-notes' && (
        <div className="space-y-4">
          <SyncPhaseIndicator requiredPhase={2} activeSyncPhase={activeSyncPhase} dataLabel="credit note" />
          {/* Filter */}
          <div className="flex items-center gap-4">
            <select
              value={creditNoteTypeFilter}
              onChange={(e) => {
                setCreditNoteTypeFilter(e.target.value as 'accpaycredit' | 'accreccredit' | '');
                setCreditNotesPage(1);
              }}
              className="border border-border bg-card text-foreground rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            >
              <option value="">All Credit Notes</option>
              <option value="accreccredit">Sales (Receivable)</option>
              <option value="accpaycredit">Purchase (Payable)</option>
            </select>
          </div>

          {/* Credit Notes Table */}
          <div className="bg-card rounded-xl border border-border overflow-hidden">
            {creditNotesLoading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
              </div>
            ) : creditNotes.length === 0 ? (
              <div className="p-8 text-center">
                <Minus className="w-12 h-12 text-muted-foreground/30 mx-auto mb-4" />
                <p className="text-muted-foreground">No credit notes found</p>
              </div>
            ) : (
              <>
                <table className="w-full">
                  <thead className="bg-muted border-b border-border">
                    <tr>
                      <th className="text-left px-4 py-2 text-sm font-medium text-muted-foreground">Number</th>
                      <th className="text-left px-4 py-2 text-sm font-medium text-muted-foreground">Type</th>
                      <th className="text-left px-4 py-2 text-sm font-medium text-muted-foreground">Contact</th>
                      <th className="text-left px-4 py-2 text-sm font-medium text-muted-foreground">Date</th>
                      <th className="text-left px-4 py-2 text-sm font-medium text-muted-foreground">Status</th>
                      <th className="text-right px-4 py-2 text-sm font-medium text-muted-foreground">Total</th>
                      <th className="text-right px-4 py-2 text-sm font-medium text-muted-foreground">GST</th>
                      <th className="text-right px-4 py-2 text-sm font-medium text-muted-foreground">Remaining</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {creditNotes.map((note) => (
                      <>
                        <tr
                          key={note.id}
                          className="hover:bg-muted cursor-pointer"
                          onClick={() => setExpandedCreditNote(expandedCreditNote === note.id ? null : note.id)}
                        >
                          <td className="px-4 py-2.5 font-medium text-foreground">{note.credit_note_number || '-'}</td>
                          <td className="px-4 py-2.5">
                            <span className="inline-flex items-center gap-1.5 text-xs">
                              <span className={cn('h-1.5 w-1.5 rounded-full', note.credit_note_type === 'accreccredit' ? 'bg-status-success' : 'bg-status-info')} />
                              <span className="text-muted-foreground">{note.credit_note_type === 'accreccredit' ? 'Sales' : 'Purchase'}</span>
                            </span>
                          </td>
                          <td className="px-4 py-2.5 text-sm text-muted-foreground">{note.contact_name || '-'}</td>
                          <td className="px-4 py-2.5 text-sm text-muted-foreground">{formatDate(note.issue_date)}</td>
                          <td className="px-4 py-2.5">
                            <span className="inline-flex items-center gap-1.5 text-xs">
                              <span className={cn('h-1.5 w-1.5 rounded-full',
                                note.status === 'authorised' ? 'bg-status-info' :
                                note.status === 'paid' ? 'bg-status-success' :
                                'bg-status-neutral'
                              )} />
                              <span className="text-muted-foreground capitalize">{note.status}</span>
                            </span>
                          </td>
                          <td className="px-4 py-2.5 text-right font-medium text-foreground tabular-nums">{formatCurrency(note.total_amount)}</td>
                          <td className="px-4 py-2.5 text-right text-sm text-muted-foreground tabular-nums">{formatCurrency(note.tax_amount)}</td>
                          <td className="px-4 py-2.5 text-right text-sm text-status-warning tabular-nums">{formatCurrency(note.remaining_credit)}</td>
                        </tr>
                        {expandedCreditNote === note.id && note.allocations && note.allocations.length > 0 && (
                          <tr key={`${note.id}-alloc`}>
                            <td colSpan={8} className="px-4 py-2.5 bg-muted">
                              <div className="text-sm">
                                <p className="font-medium text-foreground mb-2">Allocations</p>
                                <table className="w-full">
                                  <thead>
                                    <tr className="text-xs text-muted-foreground">
                                      <th className="text-left pb-2">Invoice</th>
                                      <th className="text-right pb-2">Amount</th>
                                      <th className="text-right pb-2">Date</th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {note.allocations.map((alloc, idx) => (
                                      <tr key={idx} className="text-muted-foreground">
                                        <td className="py-1">{alloc.invoice_number || alloc.invoice_id}</td>
                                        <td className="py-1 text-right tabular-nums">{formatCurrency(alloc.amount)}</td>
                                        <td className="py-1 text-right">{formatDate(alloc.allocated_at)}</td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                            </td>
                          </tr>
                        )}
                      </>
                    ))}
                  </tbody>
                </table>
                {Math.ceil(creditNotesTotal / 20) > 1 && (
                  <div className="px-4 py-2.5 border-t border-border flex items-center justify-between">
                    <p className="text-sm text-muted-foreground">
                      Showing {(creditNotesPage - 1) * 20 + 1} to {Math.min(creditNotesPage * 20, creditNotesTotal)} of {creditNotesTotal}
                    </p>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => setCreditNotesPage(p => Math.max(1, p - 1))}
                        disabled={creditNotesPage === 1}
                        className="p-2 rounded-lg border border-border disabled:opacity-50 hover:bg-muted"
                      >
                        <ChevronLeft className="w-4 h-4" />
                      </button>
                      <span className="text-sm text-muted-foreground">
                        Page {creditNotesPage} of {Math.ceil(creditNotesTotal / 20)}
                      </span>
                      <button
                        onClick={() => setCreditNotesPage(p => Math.min(Math.ceil(creditNotesTotal / 20), p + 1))}
                        disabled={creditNotesPage >= Math.ceil(creditNotesTotal / 20)}
                        className="p-2 rounded-lg border border-border disabled:opacity-50 hover:bg-muted"
                      >
                        <ChevronRight className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}

      {/* Spec 024: Payments Tab */}
      {activeTab === 'payments' && (
        <>
          <SyncPhaseIndicator requiredPhase={2} activeSyncPhase={activeSyncPhase} dataLabel="payment" />
          <div className="bg-card rounded-xl border border-border overflow-hidden">
            {paymentsLoading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
            </div>
          ) : payments.length === 0 ? (
            <div className="p-8 text-center">
              <Wallet className="w-12 h-12 text-muted-foreground/30 mx-auto mb-4" />
              <p className="text-muted-foreground">No payments found</p>
            </div>
          ) : (
            <>
              <table className="w-full">
                <thead className="bg-muted border-b border-border">
                  <tr>
                    <th className="text-left px-4 py-2 text-sm font-medium text-muted-foreground">Reference</th>
                    <th className="text-left px-4 py-2 text-sm font-medium text-muted-foreground">Type</th>
                    <th className="text-left px-4 py-2 text-sm font-medium text-muted-foreground">Contact</th>
                    <th className="text-left px-4 py-2 text-sm font-medium text-muted-foreground">Invoice</th>
                    <th className="text-left px-4 py-2 text-sm font-medium text-muted-foreground">Date</th>
                    <th className="text-left px-4 py-2 text-sm font-medium text-muted-foreground">Status</th>
                    <th className="text-right px-4 py-2 text-sm font-medium text-muted-foreground">Amount</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {payments.map((payment) => (
                    <tr key={payment.id} className="hover:bg-muted">
                      <td className="px-4 py-2.5 font-medium text-foreground">{payment.reference || '-'}</td>
                      <td className="px-4 py-2.5">
                        <span className="inline-flex items-center gap-1.5 text-xs">
                          <span className={cn('h-1.5 w-1.5 rounded-full', payment.payment_type === 'accrecpayment' ? 'bg-status-success' : 'bg-status-info')} />
                          <span className="text-muted-foreground">{payment.payment_type === 'accrecpayment' ? 'Received' : 'Made'}</span>
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-sm text-muted-foreground">{payment.contact_name || '-'}</td>
                      <td className="px-4 py-2.5 text-sm text-foreground">{payment.invoice_number || '-'}</td>
                      <td className="px-4 py-2.5 text-sm text-muted-foreground">{formatDate(payment.payment_date)}</td>
                      <td className="px-4 py-2.5">
                        <span className="inline-flex items-center gap-1.5 text-xs">
                          <span className={cn('h-1.5 w-1.5 rounded-full', payment.is_reconciled ? 'bg-status-success' : 'bg-status-warning')} />
                          <span className="text-muted-foreground">{payment.is_reconciled ? 'Reconciled' : 'Unreconciled'}</span>
                        </span>
                      </td>
                      <td className={cn('px-4 py-2.5 text-right font-medium tabular-nums', payment.payment_type === 'accrecpayment' ? 'text-status-success' : 'text-status-danger')}>
                        {payment.payment_type === 'accrecpayment' ? '+' : '-'}{formatCurrency(payment.amount)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {Math.ceil(paymentsTotal / 20) > 1 && (
                <div className="px-4 py-2.5 border-t border-border flex items-center justify-between">
                  <p className="text-sm text-muted-foreground">
                    Showing {(paymentsPage - 1) * 20 + 1} to {Math.min(paymentsPage * 20, paymentsTotal)} of {paymentsTotal}
                  </p>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setPaymentsPage(p => Math.max(1, p - 1))}
                      disabled={paymentsPage === 1}
                      className="p-2 rounded-lg border border-border disabled:opacity-50 hover:bg-muted"
                    >
                      <ChevronLeft className="w-4 h-4" />
                    </button>
                    <span className="text-sm text-muted-foreground">
                      Page {paymentsPage} of {Math.ceil(paymentsTotal / 20)}
                    </span>
                    <button
                      onClick={() => setPaymentsPage(p => Math.min(Math.ceil(paymentsTotal / 20), p + 1))}
                      disabled={paymentsPage >= Math.ceil(paymentsTotal / 20)}
                      className="p-2 rounded-lg border border-border disabled:opacity-50 hover:bg-muted"
                    >
                      <ChevronRight className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
        </>
      )}

      {/* Spec 024: Journals Tab */}
      {activeTab === 'journals' && (
        <div className="space-y-4">
          <SyncPhaseIndicator requiredPhase={3} activeSyncPhase={activeSyncPhase} dataLabel="journal" />
          {/* View Mode Toggle */}
          <div className="flex items-center gap-4">
            <div className="flex rounded-lg border border-border overflow-hidden">
              <button
                onClick={() => setJournalViewMode('system')}
                className={`px-4 py-2 text-sm font-medium ${
                  journalViewMode === 'system'
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-card text-muted-foreground hover:bg-muted'
                }`}
              >
                System Journals ({journalsTotal})
              </button>
              <button
                onClick={() => setJournalViewMode('manual')}
                className={`px-4 py-2 text-sm font-medium ${
                  journalViewMode === 'manual'
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-card text-muted-foreground hover:bg-muted'
                }`}
              >
                Manual Journals ({manualJournalsTotal})
              </button>
            </div>
          </div>

          {/* System Journals */}
          {journalViewMode === 'system' && (
            <div className="bg-card rounded-xl border border-border overflow-hidden">
              {journalsLoading ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
                </div>
              ) : journals.length === 0 ? (
                <div className="p-8 text-center">
                  <BookOpen className="w-12 h-12 text-muted-foreground/30 mx-auto mb-4" />
                  <p className="text-muted-foreground">No journals found</p>
                </div>
              ) : (
                <>
                  <table className="w-full">
                    <thead className="bg-muted border-b border-border">
                      <tr>
                        <th className="text-left px-4 py-2 text-sm font-medium text-muted-foreground">Number</th>
                        <th className="text-left px-4 py-2 text-sm font-medium text-muted-foreground">Date</th>
                        <th className="text-left px-4 py-2 text-sm font-medium text-muted-foreground">Source</th>
                        <th className="text-left px-4 py-2 text-sm font-medium text-muted-foreground">Reference</th>
                        <th className="text-right px-4 py-2 text-sm font-medium text-muted-foreground">Lines</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {journals.map((journal) => (
                        <>
                          <tr
                            key={journal.id}
                            className="hover:bg-muted cursor-pointer"
                            onClick={() => setExpandedJournal(expandedJournal === journal.id ? null : journal.id)}
                          >
                            <td className="px-4 py-2.5 font-medium text-foreground">{journal.journal_number}</td>
                            <td className="px-4 py-2.5 text-sm text-muted-foreground">{formatDate(journal.journal_date)}</td>
                            <td className="px-4 py-2.5">
                              <span className="inline-flex items-center gap-1.5 text-xs">
                                <span className="h-1.5 w-1.5 rounded-full bg-status-neutral" />
                                <span className="text-muted-foreground capitalize">{journal.source_type?.replace(/_/g, ' ') || 'Unknown'}</span>
                              </span>
                            </td>
                            <td className="px-4 py-2.5 text-sm text-muted-foreground">{journal.reference || '-'}</td>
                            <td className="px-4 py-2.5 text-right text-sm text-muted-foreground">{journal.journal_lines?.length || 0}</td>
                          </tr>
                          {expandedJournal === journal.id && journal.journal_lines && (
                            <tr key={`${journal.id}-lines`}>
                              <td colSpan={5} className="px-4 py-2.5 bg-muted">
                                <div className="text-sm">
                                  <p className="font-medium text-foreground mb-2">Journal Lines</p>
                                  <table className="w-full">
                                    <thead>
                                      <tr className="text-xs text-muted-foreground">
                                        <th className="text-left pb-2">Account</th>
                                        <th className="text-left pb-2">Description</th>
                                        <th className="text-right pb-2">Debit</th>
                                        <th className="text-right pb-2">Credit</th>
                                      </tr>
                                    </thead>
                                    <tbody>
                                      {journal.journal_lines.map((line, idx) => (
                                        <tr key={idx} className="text-muted-foreground">
                                          <td className="py-1">{line.account_code} - {line.account_name}</td>
                                          <td className="py-1">{line.description || '-'}</td>
                                          <td className="py-1 text-right text-status-success tabular-nums">
                                            {line.is_debit ? formatCurrency(line.gross_amount) : '-'}
                                          </td>
                                          <td className="py-1 text-right text-status-danger tabular-nums">
                                            {!line.is_debit ? formatCurrency(Math.abs(parseFloat(line.gross_amount))) : '-'}
                                          </td>
                                        </tr>
                                      ))}
                                    </tbody>
                                  </table>
                                </div>
                              </td>
                            </tr>
                          )}
                        </>
                      ))}
                    </tbody>
                  </table>
                  {Math.ceil(journalsTotal / 20) > 1 && (
                    <div className="px-4 py-2.5 border-t border-border flex items-center justify-between">
                      <p className="text-sm text-muted-foreground">
                        Showing {(journalsPage - 1) * 20 + 1} to {Math.min(journalsPage * 20, journalsTotal)} of {journalsTotal}
                      </p>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => setJournalsPage(p => Math.max(1, p - 1))}
                          disabled={journalsPage === 1}
                          className="p-2 rounded-lg border border-border disabled:opacity-50 hover:bg-muted"
                        >
                          <ChevronLeft className="w-4 h-4" />
                        </button>
                        <span className="text-sm text-muted-foreground">
                          Page {journalsPage} of {Math.ceil(journalsTotal / 20)}
                        </span>
                        <button
                          onClick={() => setJournalsPage(p => Math.min(Math.ceil(journalsTotal / 20), p + 1))}
                          disabled={journalsPage >= Math.ceil(journalsTotal / 20)}
                          className="p-2 rounded-lg border border-border disabled:opacity-50 hover:bg-muted"
                        >
                          <ChevronRight className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          )}

          {/* Manual Journals */}
          {journalViewMode === 'manual' && (
            <div className="bg-card rounded-xl border border-border overflow-hidden">
              {manualJournalsLoading ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
                </div>
              ) : manualJournals.length === 0 ? (
                <div className="p-8 text-center">
                  <BookOpen className="w-12 h-12 text-muted-foreground/30 mx-auto mb-4" />
                  <p className="text-muted-foreground">No manual journals found</p>
                </div>
              ) : (
                <>
                  <table className="w-full">
                    <thead className="bg-muted border-b border-border">
                      <tr>
                        <th className="text-left px-4 py-2 text-sm font-medium text-muted-foreground">Narration</th>
                        <th className="text-left px-4 py-2 text-sm font-medium text-muted-foreground">Date</th>
                        <th className="text-left px-4 py-2 text-sm font-medium text-muted-foreground">Status</th>
                        <th className="text-left px-4 py-2 text-sm font-medium text-muted-foreground">Cash Basis</th>
                        <th className="text-right px-4 py-2 text-sm font-medium text-muted-foreground">Lines</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {manualJournals.map((mj) => (
                        <>
                          <tr
                            key={mj.id}
                            className="hover:bg-muted cursor-pointer"
                            onClick={() => setExpandedJournal(expandedJournal === mj.id ? null : mj.id)}
                          >
                            <td className="px-4 py-2.5 font-medium text-foreground">{mj.narration || '-'}</td>
                            <td className="px-4 py-2.5 text-sm text-muted-foreground">{formatDate(mj.journal_date)}</td>
                            <td className="px-4 py-2.5">
                              <span className="inline-flex items-center gap-1.5 text-xs">
                                <span className={cn('h-1.5 w-1.5 rounded-full',
                                  mj.status === 'posted' ? 'bg-status-success' :
                                  mj.status === 'draft' ? 'bg-status-neutral' :
                                  'bg-status-warning'
                                )} />
                                <span className="text-muted-foreground capitalize">{mj.status}</span>
                              </span>
                            </td>
                            <td className="px-4 py-2.5">
                              {mj.show_on_cash_basis_reports ? (
                                <span className="text-status-success text-sm">Yes</span>
                              ) : (
                                <span className="text-muted-foreground text-sm">No</span>
                              )}
                            </td>
                            <td className="px-4 py-2.5 text-right text-sm text-muted-foreground">{mj.journal_lines?.length || 0}</td>
                          </tr>
                          {expandedJournal === mj.id && mj.journal_lines && (
                            <tr key={`${mj.id}-lines`}>
                              <td colSpan={5} className="px-4 py-2.5 bg-muted">
                                <div className="text-sm">
                                  <p className="font-medium text-foreground mb-2">Journal Lines</p>
                                  <table className="w-full">
                                    <thead>
                                      <tr className="text-xs text-muted-foreground">
                                        <th className="text-left pb-2">Account</th>
                                        <th className="text-left pb-2">Description</th>
                                        <th className="text-right pb-2">Debit</th>
                                        <th className="text-right pb-2">Credit</th>
                                      </tr>
                                    </thead>
                                    <tbody>
                                      {mj.journal_lines.map((line, idx) => (
                                        <tr key={idx} className="text-muted-foreground">
                                          <td className="py-1">{line.account_code}</td>
                                          <td className="py-1">{line.description || '-'}</td>
                                          <td className="py-1 text-right text-status-success tabular-nums">
                                            {line.is_debit ? formatCurrency(line.line_amount) : '-'}
                                          </td>
                                          <td className="py-1 text-right text-status-danger tabular-nums">
                                            {!line.is_debit ? formatCurrency(Math.abs(parseFloat(line.line_amount))) : '-'}
                                          </td>
                                        </tr>
                                      ))}
                                    </tbody>
                                  </table>
                                </div>
                              </td>
                            </tr>
                          )}
                        </>
                      ))}
                    </tbody>
                  </table>
                  {Math.ceil(manualJournalsTotal / 20) > 1 && (
                    <div className="px-4 py-2.5 border-t border-border flex items-center justify-between">
                      <p className="text-sm text-muted-foreground">
                        Showing {(journalsPage - 1) * 20 + 1} to {Math.min(journalsPage * 20, manualJournalsTotal)} of {manualJournalsTotal}
                      </p>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => setJournalsPage(p => Math.max(1, p - 1))}
                          disabled={journalsPage === 1}
                          className="p-2 rounded-lg border border-border disabled:opacity-50 hover:bg-muted"
                        >
                          <ChevronLeft className="w-4 h-4" />
                        </button>
                        <span className="text-sm text-muted-foreground">
                          Page {journalsPage} of {Math.ceil(manualJournalsTotal / 20)}
                        </span>
                        <button
                          onClick={() => setJournalsPage(p => Math.min(Math.ceil(manualJournalsTotal / 20), p + 1))}
                          disabled={journalsPage >= Math.ceil(manualJournalsTotal / 20)}
                          className="p-2 rounded-lg border border-border disabled:opacity-50 hover:bg-muted"
                        >
                          <ChevronRight className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          )}
        </div>
      )}

      {activeTab === 'employees' && (
        <div className="space-y-4">
          {/* Filter */}
          <div className="flex items-center gap-4">
            <select
              value={employeeStatusFilter}
              onChange={(e) => {
                setEmployeeStatusFilter(e.target.value);
                setEmployeesPage(1);
              }}
              className="border border-border bg-card text-foreground rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            >
              <option value="">All Employees</option>
              <option value="active">Active</option>
              <option value="terminated">Terminated</option>
            </select>
          </div>

          {/* Employees Table */}
          <div className="bg-card rounded-xl border border-border overflow-hidden">
            {employeesLoading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
              </div>
            ) : employees.length === 0 ? (
              <div className="p-8 text-center">
                <Briefcase className="w-12 h-12 text-muted-foreground/30 mx-auto mb-4" />
                <p className="text-muted-foreground">No employees found</p>
              </div>
            ) : (
              <>
                <table className="w-full">
                  <thead className="bg-muted border-b border-border">
                    <tr>
                      <th className="text-left px-4 py-2 text-sm font-medium text-muted-foreground">Employee</th>
                      <th className="text-left px-4 py-2 text-sm font-medium text-muted-foreground">Email</th>
                      <th className="text-left px-4 py-2 text-sm font-medium text-muted-foreground">Job Title</th>
                      <th className="text-left px-4 py-2 text-sm font-medium text-muted-foreground">Start Date</th>
                      <th className="text-left px-4 py-2 text-sm font-medium text-muted-foreground">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {employees.map((employee) => (
                      <tr key={employee.id} className="hover:bg-muted">
                        <td className="px-4 py-2.5">
                          <div className="flex items-center gap-3">
                            <div className="w-8 h-8 bg-muted rounded-full flex items-center justify-center">
                              <span className="text-muted-foreground font-medium text-sm">
                                {employee.first_name?.charAt(0) || ''}{employee.last_name?.charAt(0) || ''}
                              </span>
                            </div>
                            <div>
                              <p className="font-medium text-foreground">{employee.full_name || `${employee.first_name || ''} ${employee.last_name || ''}`.trim() || '-'}</p>
                            </div>
                          </div>
                        </td>
                        <td className="px-4 py-2.5 text-sm text-muted-foreground">
                          {employee.email ? (
                            <span className="flex items-center gap-1">
                              <Mail className="w-3 h-3" />
                              {employee.email}
                            </span>
                          ) : '-'}
                        </td>
                        <td className="px-4 py-2.5 text-sm text-muted-foreground">{employee.job_title || '-'}</td>
                        <td className="px-4 py-2.5 text-sm text-muted-foreground">{formatDate(employee.start_date)}</td>
                        <td className="px-4 py-2.5">
                          <span className="inline-flex items-center gap-1.5 text-xs">
                            <span className={cn('h-1.5 w-1.5 rounded-full', employee.status === 'active' ? 'bg-status-success' : 'bg-status-neutral')} />
                            <span className="text-muted-foreground capitalize">{employee.status}</span>
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {/* Pagination */}
                {Math.ceil(employeesTotal / 25) > 1 && (
                  <div className="px-4 py-2.5 border-t border-border flex items-center justify-between">
                    <p className="text-sm text-muted-foreground">
                      Showing {(employeesPage - 1) * 25 + 1} to {Math.min(employeesPage * 25, employeesTotal)} of {employeesTotal}
                    </p>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => setEmployeesPage(p => Math.max(1, p - 1))}
                        disabled={employeesPage === 1}
                        className="p-2 rounded-lg border border-border disabled:opacity-50 hover:bg-muted"
                      >
                        <ChevronLeft className="w-4 h-4" />
                      </button>
                      <span className="text-sm text-muted-foreground">
                        Page {employeesPage} of {Math.ceil(employeesTotal / 25)}
                      </span>
                      <button
                        onClick={() => setEmployeesPage(p => Math.min(Math.ceil(employeesTotal / 25), p + 1))}
                        disabled={employeesPage >= Math.ceil(employeesTotal / 25)}
                        className="p-2 rounded-lg border border-border disabled:opacity-50 hover:bg-muted"
                      >
                        <ChevronRight className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}

      {activeTab === 'pay-runs' && (
        <div className="bg-card rounded-xl border border-border overflow-hidden">
          {payRunsLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
            </div>
          ) : payRuns.length === 0 ? (
            <div className="p-8 text-center">
              <CreditCard className="w-12 h-12 text-muted-foreground/30 mx-auto mb-4" />
              <p className="text-muted-foreground">No pay runs found for this quarter</p>
            </div>
          ) : (
            <>
              <table className="w-full">
                <thead className="bg-muted border-b border-border">
                  <tr>
                    <th className="text-left px-4 py-2 text-sm font-medium text-muted-foreground">Pay Period</th>
                    <th className="text-left px-4 py-2 text-sm font-medium text-muted-foreground">Payment Date</th>
                    <th className="text-left px-4 py-2 text-sm font-medium text-muted-foreground">Employees</th>
                    <th className="text-left px-4 py-2 text-sm font-medium text-muted-foreground">Status</th>
                    <th className="text-right px-4 py-2 text-sm font-medium text-muted-foreground">Wages</th>
                    <th className="text-right px-4 py-2 text-sm font-medium text-muted-foreground">Tax</th>
                    <th className="text-right px-4 py-2 text-sm font-medium text-muted-foreground">Super</th>
                    <th className="text-right px-4 py-2 text-sm font-medium text-muted-foreground">Net Pay</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {payRuns.map((payRun) => (
                    <tr key={payRun.id} className="hover:bg-muted">
                      <td className="px-4 py-2.5">
                        <div className="flex items-center gap-2">
                          <Calendar className="w-4 h-4 text-muted-foreground" />
                          <span className="text-sm text-foreground">
                            {formatDate(payRun.period_start)} - {formatDate(payRun.period_end)}
                          </span>
                        </div>
                      </td>
                      <td className="px-4 py-2.5 text-sm text-muted-foreground">{formatDate(payRun.payment_date)}</td>
                      <td className="px-4 py-2.5 text-sm text-muted-foreground">{payRun.employee_count}</td>
                      <td className="px-4 py-2.5">
                        <span className="inline-flex items-center gap-1.5 text-xs">
                          <span className={cn('h-1.5 w-1.5 rounded-full', payRun.status === 'posted' ? 'bg-status-success' : 'bg-status-warning')} />
                          <span className="text-muted-foreground capitalize">{payRun.status}</span>
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-right text-sm font-medium text-foreground tabular-nums">
                        {formatCurrency(payRun.total_wages)}
                      </td>
                      <td className="px-4 py-2.5 text-right text-sm font-medium text-status-warning tabular-nums">
                        {formatCurrency(payRun.total_tax)}
                      </td>
                      <td className="px-4 py-2.5 text-right text-sm font-medium text-status-info tabular-nums">
                        {formatCurrency(payRun.total_super)}
                      </td>
                      <td className="px-4 py-2.5 text-right text-sm font-medium text-foreground tabular-nums">
                        {formatCurrency(payRun.total_net_pay)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {/* Pagination */}
              {Math.ceil(payRunsTotal / 20) > 1 && (
                <div className="px-4 py-2.5 border-t border-border flex items-center justify-between">
                  <p className="text-sm text-muted-foreground">
                    Showing {(payRunsPage - 1) * 20 + 1} to {Math.min(payRunsPage * 20, payRunsTotal)} of {payRunsTotal}
                  </p>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setPayRunsPage(p => Math.max(1, p - 1))}
                      disabled={payRunsPage === 1}
                      className="p-2 rounded-lg border border-border disabled:opacity-50 hover:bg-muted"
                    >
                      <ChevronLeft className="w-4 h-4" />
                    </button>
                    <span className="text-sm text-muted-foreground">
                      Page {payRunsPage} of {Math.ceil(payRunsTotal / 20)}
                    </span>
                    <button
                      onClick={() => setPayRunsPage(p => Math.min(Math.ceil(payRunsTotal / 20), p + 1))}
                      disabled={payRunsPage >= Math.ceil(payRunsTotal / 20)}
                      className="p-2 rounded-lg border border-border disabled:opacity-50 hover:bg-muted"
                    >
                      <ChevronRight className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}
      </div>

      {/* Invite to Portal Modal */}
      <InviteToPortalModal
        open={inviteModalOpen}
        onOpenChange={setInviteModalOpen}
        connectionId={client?.id || ''}
        clientName={client?.organization_name || 'Client'}
        defaultEmail={client?.contact_email || ''}
      />
    </div>
  );
}
