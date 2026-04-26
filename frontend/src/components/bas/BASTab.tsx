'use client';

/**
 * BAS Tab Component - Premium Edition
 *
 * Professional BAS preparation interface designed for Australian accountants.
 * Features tabbed layout, workflow progress, and hero summary panel.
 */

import { useQueryClient } from '@tanstack/react-query';
import {
  AlertCircle,
  ArrowRight,
  Bot,
  Calculator,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Download,
  Eye,
  FileSpreadsheet,
  FileText,
  History,
  Lightbulb,
  Loader2,
  MessageSquare,
  PencilLine,
  Plus,
  RefreshCw,
  RotateCcw,
  Send,
  ShieldCheck,
  Table,
  ThumbsDown,
  Trash2,
  TrendingDown,
  TrendingUp,
  UserCheck,
  X,
  Zap,
} from 'lucide-react';
import React, { useCallback, useEffect, useRef, useState } from 'react';

import { ThresholdTooltip } from '@/components/insights/ThresholdTooltip';
import {
  basQueryKeys,
  useBASCalculation,
  useBASVariance,
  useBASAdjustments,
  useBASTaxCodeSummary,
  useBASCrossCheck,
} from '@/hooks/useBASData';
import {
  type BASCalculation,
  type BASSession,
  type BASFieldTransactionsResponse,
  type ExportFormat,
  type LodgementRecordRequest,
  type LodgementUpdateRequest,
  type ReconciliationStatus,
  type WritebackJobDetailResponse,
  listBASSessions,
  createBASSession,
  triggerBASCalculation,
  markBASSessionReviewed,
  exportBASWorkingPapers,
  exportBASWithLodgementSummary,
  exportBASAsCSV,
  addBASAdjustment,
  deleteBASAdjustment,
  getBASFieldTransactions,
  getReconciliationStatus,
  recordLodgement,
  updateLodgementDetails,
  getSessionStatusLabel,
  formatBASCurrency,
  formatPercentage,
  getVarianceSeverityColor,
  getVarianceSeverityBgColor,
  getBASFieldLabel,
  isSessionEditable,
  canRecordLodgement,
  isSessionLodged,
  isInReviewState,
  approveBASSession,
  requestChanges,
  reopenBASSession,
  getXeroBASCrossCheck,
  updatePAYGManual,
} from '@/lib/bas';

import { GSTBasisModal } from './GSTBasisModal';
import { InstalmentSection } from './InstalmentSection';
import { LodgementBadge } from './LodgementBadge';
import { LodgementModal } from './LodgementModal';
import { TaxCodeResolutionPanel } from './TaxCodeResolutionPanel';
import { UnreconciledWarning } from './UnreconciledWarning';
import { XeroBASCrossCheck } from './XeroBASCrossCheck';

// =============================================================================
// PAYG Manual Entry Component (FR-006)
// Shown when Xero payroll data is unavailable — lets accountant enter W1/W2 directly.
// =============================================================================

function PAYGManualEntry({
  calculation,
  getToken,
  onUpdated,
}: {
  calculation: BASCalculation;
  getToken: () => Promise<string | null>;
  onUpdated: (updated: BASCalculation) => void;
}) {
  const [w1, setW1] = React.useState<string>(
    calculation.w1_total_wages && parseFloat(calculation.w1_total_wages) > 0
      ? String(parseFloat(calculation.w1_total_wages))
      : '',
  );
  const [w2, setW2] = React.useState<string>(
    calculation.w2_amount_withheld && parseFloat(calculation.w2_amount_withheld) > 0
      ? String(parseFloat(calculation.w2_amount_withheld))
      : '',
  );
  const [isSaving, setIsSaving] = React.useState(false);
  const [saveError, setSaveError] = React.useState<string | null>(null);

  const handleBlur = async () => {
    setSaveError(null);
    const w1Val = w1 !== '' ? parseFloat(w1) : 0;
    const w2Val = w2 !== '' ? parseFloat(w2) : 0;
    const existingW1 = parseFloat(calculation.w1_total_wages ?? '0');
    const existingW2 = parseFloat(calculation.w2_amount_withheld ?? '0');
    if (w1Val === existingW1 && w2Val === existingW2) return;

    setIsSaving(true);
    try {
      const token = await getToken();
      if (!token) throw new Error('Not authenticated');
      const updated = await updatePAYGManual(token, calculation.id, {
        w1_total_wages: isNaN(w1Val) ? 0 : w1Val,
        w2_amount_withheld: isNaN(w2Val) ? 0 : w2Val,
      });
      onUpdated(updated);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Failed to save');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-xs text-muted-foreground bg-muted/40 rounded-lg px-3 py-2 border border-border">
        <FileText className="w-3.5 h-3.5 shrink-0" />
        No payroll data found in Xero — enter wages manually if applicable
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div className="space-y-1">
          <label className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
            W1 — Total wages paid
          </label>
          <div className="relative">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground text-sm select-none">$</span>
            <input
              type="number"
              min="0"
              step="0.01"
              placeholder="0.00"
              value={w1}
              onChange={(e) => setW1(e.target.value)}
              onBlur={handleBlur}
              className="w-full pl-7 pr-3 py-2 text-sm font-mono rounded-lg border border-border bg-background focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
            />
          </div>
        </div>
        <div className="space-y-1">
          <label className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
            W2 — Tax withheld
          </label>
          <div className="relative">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground text-sm select-none">$</span>
            <input
              type="number"
              min="0"
              step="0.01"
              placeholder="0.00"
              value={w2}
              onChange={(e) => setW2(e.target.value)}
              onBlur={handleBlur}
              className="w-full pl-7 pr-3 py-2 text-sm font-mono rounded-lg border border-border bg-background focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
            />
          </div>
        </div>
      </div>
      {isSaving && <p className="text-[10px] text-muted-foreground animate-pulse">Saving…</p>}
      {saveError && <p className="text-xs text-status-danger">{saveError}</p>}
    </div>
  );
}

// =============================================================================
// Types
// =============================================================================

interface BASTabProps {
  connectionId: string;
  getToken: () => Promise<string | null>;
  selectedQuarter: number;
  selectedFyYear: number;
  /** Current saved GST reporting basis for this client; null = not yet set */
  clientGstBasis?: string | null;
  /** Called after the accountant sets/changes the GST basis */
  onGstBasisChanged?: (basis: string) => void;
}

type DetailTab = 'gst' | 'payg' | 'variance' | 'adjustments';

// =============================================================================
// Workflow Steps
// =============================================================================

const WORKFLOW_STEPS = [
  { id: 'calculate', label: 'Calculate', icon: Calculator },
  { id: 'review', label: 'Review', icon: ShieldCheck },
  { id: 'adjust', label: 'Adjust', icon: PencilLine },
  { id: 'approve', label: 'Approve', icon: CheckCircle2 },
  { id: 'lodge', label: 'Lodge', icon: Send },
] as const;

function getWorkflowStep(session: BASSession | null, hasCalculation: boolean): number {
  if (!session) return 0;
  if (session.status === 'lodged' || session.lodged_at) return 5;
  if (session.status === 'approved') return 4;
  if (session.reviewed_by) return 3;
  if (hasCalculation) return 2;
  return 1;
}

// =============================================================================
// Component
// =============================================================================

export function BASTab({
  connectionId,
  getToken,
  selectedQuarter,
  selectedFyYear,
  clientGstBasis,
  onGstBasisChanged,
}: BASTabProps) {
  // State
  const [sessions, setSessions] = useState<BASSession[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const hasLoadedSessionsRef = useRef(false);
  const [error, setError] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [isCalculating, setIsCalculating] = useState(false);
  const [isReviewing, setIsReviewing] = useState(false);
  const [isExporting, setIsExporting] = useState<ExportFormat | null>(null);

  // Selected session for detail view
  const [selectedSession, setSelectedSession] = useState<BASSession | null>(null);

  // React Query client for cache invalidation in mutation handlers
  const queryClient = useQueryClient();
  const sessionId = selectedSession?.id;
  const hasCalculation = selectedSession?.has_calculation ?? false;

  // Session detail — cached per session, instant on return navigation
  const { data: calculation, isFetching: calcFetching } = useBASCalculation(
    connectionId, sessionId, getToken, hasCalculation,
  );
  const { data: variance, isFetching: varianceFetching } = useBASVariance(
    connectionId, sessionId, getToken,
  );
  const { data: adjustmentsData, isFetching: adjustmentsFetching } = useBASAdjustments(
    connectionId, sessionId, getToken,
  );
  const adjustments = adjustmentsData ?? [];
  const { data: taxCodeSummary } = useBASTaxCodeSummary(
    connectionId, sessionId, getToken, hasCalculation,
  );
  const { data: xeroCrossCheck, isFetching: crossCheckFetching } = useBASCrossCheck(
    connectionId, sessionId, getToken,
  );
  // Core data loading — gates the main spinner.
  // Cross-check and tax code summary are excluded: they load independently
  // so the BAS figures appear in ~2s rather than waiting for the slow Xero API call.
  const detailLoading = varianceFetching || adjustmentsFetching || (hasCalculation && calcFetching);

  // Tab state
  const [activeTab, setActiveTab] = useState<DetailTab>('gst');

  // Adjustment form state
  const [showAdjustmentForm, setShowAdjustmentForm] = useState(false);
  const [adjustmentFieldName, setAdjustmentFieldName] = useState('g1_total_sales');
  const [adjustmentAmount, setAdjustmentAmount] = useState('');
  const [adjustmentReason, setAdjustmentReason] = useState('');
  const [adjustmentReference, setAdjustmentReference] = useState('');
  const [isAddingAdjustment, setIsAddingAdjustment] = useState(false);
  const [isDeletingAdjustment, setIsDeletingAdjustment] = useState<string | null>(null);

  // Variance review state
  const [expandedVariance, setExpandedVariance] = useState<string | null>(null);
  const [acknowledgedVariances, setAcknowledgedVariances] = useState<Set<string>>(new Set());

  // Transaction drilldown modal state
  const [transactionModalOpen, setTransactionModalOpen] = useState(false);
  const [transactionModalData, setTransactionModalData] = useState<BASFieldTransactionsResponse | null>(null);
  const [transactionModalLoading, setTransactionModalLoading] = useState(false);

  // Lodgement modal state (Spec 011)
  const [lodgementModalOpen, setLodgementModalOpen] = useState(false);
  const [isLodgementUpdate, setIsLodgementUpdate] = useState(false);

  // Review workflow state (Spec 010)
  const [isApproving, setIsApproving] = useState(false);
  const [isRequestingChanges, setIsRequestingChanges] = useState(false);
  const [isReopening, setIsReopening] = useState(false);
  const [showRequestChangesModal, setShowRequestChangesModal] = useState(false);
  const [changeRequestFeedback, setChangeRequestFeedback] = useState('');

  // Tax code suggestion state (Spec 046)

  // GST basis modal state (Spec 062 - US1)
  const [showGSTBasisModal, setShowGSTBasisModal] = useState(false);
  // Optimistic local copy — updated immediately on save so handleCalculate doesn't
  // re-open the modal before the parent's fetchClient() round-trip completes
  const [localGstBasis, setLocalGstBasis] = useState<string | null>(clientGstBasis ?? null);

  // Reconciliation warning state (Spec 062 - US11)
  const [reconciliationStatus, setReconciliationStatus] = useState<ReconciliationStatus | null>(null);
  const [showUnreconciledWarning, setShowUnreconciledWarning] = useState(false);
  const [proceededWithUnreconciled, setProceededWithUnreconciled] = useState(false);

  // Xero write-back state (Spec 049)
  const [activeWritebackJobId, setActiveWritebackJobId] = useState<string | null>(null);
  const [completedWritebackJob, setCompletedWritebackJob] = useState<WritebackJobDetailResponse | null>(null);

  // Keep localGstBasis in sync when the parent prop updates after fetchClient()
  useEffect(() => {
    setLocalGstBasis(clientGstBasis ?? null);
  }, [clientGstBasis]);

  // ==========================================================================
  // Data Fetching
  // ==========================================================================

  const fetchSessions = useCallback(async () => {
    // Only show the full-page loading spinner on the very first load.
    // Subsequent calls (triggered by onSessionUpdated, onJobComplete, etc.) run
    // silently in the background so the panel doesn't flicker.
    const isInitial = !hasLoadedSessionsRef.current;
    try {
      if (isInitial) setIsLoading(true);
      setError(null);
      const token = await getToken();
      if (!token) throw new Error('Not authenticated');

      const response = await listBASSessions(token, connectionId);
      setSessions(response.sessions);
      hasLoadedSessionsRef.current = true;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load BAS sessions');
    } finally {
      if (isInitial) setIsLoading(false);
    }
  }, [getToken, connectionId]);

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  // Auto-select the session matching the selected quarter, or first session.
  // Also re-sync selectedSession from the refreshed sessions list so fields like
  // approved_unsynced_count stay current after fetchSessions() is called.
  useEffect(() => {
    if (sessions.length === 0) return;
    if (!selectedSession) {
      const matching = sessions.find(
        (s) => s.period_display_name?.includes(`Q${selectedQuarter}`) &&
               s.period_display_name?.includes(`FY${selectedFyYear}`)
      );
      setSelectedSession(matching ?? sessions[0] ?? null);
    } else {
      const updated = sessions.find((s) => s.id === selectedSession.id);
      if (updated) setSelectedSession(updated);
    }
  }, [sessions, selectedQuarter, selectedFyYear]); // eslint-disable-line react-hooks/exhaustive-deps

  // Clear non-query state when session is deselected
  useEffect(() => {
    if (!selectedSession) {
      setShowAdjustmentForm(false);
      setActiveWritebackJobId(null);
      setCompletedWritebackJob(null);
      setReconciliationStatus(null);
      setShowUnreconciledWarning(false);
      setProceededWithUnreconciled(false);
    }
  }, [selectedSession]);

  // Fetch reconciliation status when a session is selected (Spec 062 - US11)
  useEffect(() => {
    if (!selectedSession) return;
    let cancelled = false;
    (async () => {
      try {
        const token = await getToken();
        if (!token || cancelled) return;
        const status = await getReconciliationStatus(
          token,
          connectionId,
          selectedSession.start_date,
          selectedSession.end_date,
        );
        if (!cancelled) {
          setReconciliationStatus(status);
          if (status.unreconciled_count > 0 && !proceededWithUnreconciled) {
            setShowUnreconciledWarning(true);
          }
        }
      } catch {
        // Non-critical — silently ignore reconciliation check failures
      }
    })();
    return () => { cancelled = true; };
  }, [selectedSession?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  // ==========================================================================
  // Handlers
  // ==========================================================================

  const handleRefreshCrossCheck = async () => {
    if (!selectedSession) return;
    const token = await getToken();
    if (!token) return;
    const fresh = await getXeroBASCrossCheck(token, connectionId, selectedSession.id, true);
    queryClient.setQueryData(basQueryKeys.crossCheck(connectionId, selectedSession.id), fresh);
  };

  const handleCreateSession = async () => {
    try {
      setIsCreating(true);
      const token = await getToken();
      if (!token) throw new Error('Not authenticated');

      const newSession = await createBASSession(
        token,
        connectionId,
        selectedQuarter,
        selectedFyYear
      );

      setSessions((prev) => [newSession, ...prev]);
      setSelectedSession(newSession);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create session');
    } finally {
      setIsCreating(false);
    }
  };

  const handleCalculate = async (effectiveBasis?: string) => {
    if (!selectedSession) return;

    // US1: Require GST basis to be set before calculating
    const basisToUse = effectiveBasis ?? localGstBasis;
    if (basisToUse === null || basisToUse === undefined) {
      setShowGSTBasisModal(true);
      return;
    }

    try {
      setIsCalculating(true);
      const token = await getToken();
      if (!token) throw new Error('Not authenticated');

      await triggerBASCalculation(token, connectionId, selectedSession.id);

      // Mark has_calculation on the local session so that the calculation/summary
      // hooks become enabled before the invalidation triggers a refetch
      setSessions((prev) =>
        prev.map((s) =>
          s.id === selectedSession.id ? { ...s, has_calculation: true } : s
        )
      );
      setSelectedSession((prev) => prev ? { ...prev, has_calculation: true } : null);

      // Invalidate all session detail queries — React Query will refetch in parallel
      await queryClient.invalidateQueries({
        queryKey: ['bas', connectionId, selectedSession.id],
        exact: false,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to calculate BAS');
    } finally {
      setIsCalculating(false);
    }
  };

  const handleMarkReviewed = async () => {
    if (!selectedSession) return;

    try {
      setIsReviewing(true);
      const token = await getToken();
      if (!token) throw new Error('Not authenticated');

      const updatedSession = await markBASSessionReviewed(token, connectionId, selectedSession.id);

      setSessions((prev) =>
        prev.map((s) =>
          s.id === selectedSession.id ? updatedSession : s
        )
      );
      setSelectedSession(updatedSession);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to mark session as reviewed');
    } finally {
      setIsReviewing(false);
    }
  };

  const handleExport = async (format: ExportFormat) => {
    if (!selectedSession) return;

    try {
      setIsExporting(format);
      const token = await getToken();
      if (!token) throw new Error('Not authenticated');

      await exportBASWorkingPapers(token, connectionId, selectedSession.id, format);
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to export ${format.toUpperCase()}`);
    } finally {
      setIsExporting(null);
    }
  };

  const handleAddAdjustment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedSession) return;

    try {
      setIsAddingAdjustment(true);
      const token = await getToken();
      if (!token) throw new Error('Not authenticated');

      const amount = parseFloat(adjustmentAmount);
      if (isNaN(amount)) {
        setError('Please enter a valid amount');
        return;
      }

      await addBASAdjustment(
        token,
        connectionId,
        selectedSession.id,
        adjustmentFieldName,
        amount,
        adjustmentReason,
        adjustmentReference || undefined
      );

      await queryClient.invalidateQueries({
        queryKey: basQueryKeys.adjustments(connectionId, selectedSession.id),
      });

      setAdjustmentAmount('');
      setAdjustmentReason('');
      setAdjustmentReference('');
      setShowAdjustmentForm(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add adjustment');
    } finally {
      setIsAddingAdjustment(false);
    }
  };

  const handleDeleteAdjustment = async (adjustmentId: string) => {
    if (!selectedSession) return;

    try {
      setIsDeletingAdjustment(adjustmentId);
      const token = await getToken();
      if (!token) throw new Error('Not authenticated');

      await deleteBASAdjustment(token, connectionId, selectedSession.id, adjustmentId);
      await queryClient.invalidateQueries({
        queryKey: basQueryKeys.adjustments(connectionId, selectedSession.id),
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete adjustment');
    } finally {
      setIsDeletingAdjustment(null);
    }
  };

  const handleViewFieldTransactions = async (fieldName: string) => {
    if (!selectedSession) return;

    try {
      setTransactionModalOpen(true);
      setTransactionModalLoading(true);
      setTransactionModalData(null);

      const token = await getToken();
      if (!token) throw new Error('Not authenticated');

      const data = await getBASFieldTransactions(
        token,
        connectionId,
        selectedSession.id,
        fieldName
      );

      setTransactionModalData(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load transactions');
      setTransactionModalOpen(false);
    } finally {
      setTransactionModalLoading(false);
    }
  };

  // Lodgement handlers (Spec 011)
  const handleOpenLodgementModal = (isUpdate: boolean = false) => {
    setIsLodgementUpdate(isUpdate);
    setLodgementModalOpen(true);
  };

  const handleLodgementSubmit = async (request: LodgementRecordRequest | LodgementUpdateRequest) => {
    if (!selectedSession) return;

    const token = await getToken();
    if (!token) throw new Error('Not authenticated');

    let updatedSession: BASSession;
    if (isLodgementUpdate) {
      updatedSession = await updateLodgementDetails(
        token,
        connectionId,
        selectedSession.id,
        request as LodgementUpdateRequest
      );
    } else {
      updatedSession = await recordLodgement(
        token,
        connectionId,
        selectedSession.id,
        request as LodgementRecordRequest
      );
    }

    // Update session in list and selected
    setSessions((prev) =>
      prev.map((s) => (s.id === selectedSession.id ? updatedSession : s))
    );
    setSelectedSession(updatedSession);
    setLodgementModalOpen(false);
  };

  const handleExportWithLodgement = async (format: ExportFormat) => {
    if (!selectedSession) return;

    try {
      setIsExporting(format);
      const token = await getToken();
      if (!token) throw new Error('Not authenticated');

      await exportBASWithLodgementSummary(token, connectionId, selectedSession.id, format);
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to export ${format.toUpperCase()}`);
    } finally {
      setIsExporting(null);
    }
  };

  const handleExportCSV = async () => {
    if (!selectedSession) return;

    try {
      setIsExporting('csv');
      const token = await getToken();
      if (!token) throw new Error('Not authenticated');

      await exportBASAsCSV(token, connectionId, selectedSession.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to export CSV');
    } finally {
      setIsExporting(null);
    }
  };

  // ==========================================================================
  // Review Workflow Handlers (Spec 010)
  // ==========================================================================

  const handleApprove = async () => {
    if (!selectedSession) return;

    try {
      setIsApproving(true);
      const token = await getToken();
      if (!token) throw new Error('Not authenticated');

      const updatedSession = await approveBASSession(token, connectionId, selectedSession.id);

      setSessions((prev) =>
        prev.map((s) => (s.id === selectedSession.id ? updatedSession : s))
      );
      setSelectedSession(updatedSession);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to approve session');
    } finally {
      setIsApproving(false);
    }
  };

  const handleRequestChanges = async () => {
    if (!selectedSession || !changeRequestFeedback.trim()) return;

    try {
      setIsRequestingChanges(true);
      const token = await getToken();
      if (!token) throw new Error('Not authenticated');

      const updatedSession = await requestChanges(
        token,
        connectionId,
        selectedSession.id,
        changeRequestFeedback.trim()
      );

      setSessions((prev) =>
        prev.map((s) => (s.id === selectedSession.id ? updatedSession : s))
      );
      setSelectedSession(updatedSession);
      setShowRequestChangesModal(false);
      setChangeRequestFeedback('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to request changes');
    } finally {
      setIsRequestingChanges(false);
    }
  };

  const handleReopen = async () => {
    if (!selectedSession) return;

    try {
      setIsReopening(true);
      const token = await getToken();
      if (!token) throw new Error('Not authenticated');

      const updatedSession = await reopenBASSession(token, connectionId, selectedSession.id);

      setSessions((prev) =>
        prev.map((s) => (s.id === selectedSession.id ? updatedSession : s))
      );
      setSelectedSession(updatedSession);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to reopen session');
    } finally {
      setIsReopening(false);
    }
  };

  // ==========================================================================
  // Helpers
  // ==========================================================================

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleDateString('en-AU', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    });
  };

  const formatDateTime = (dateStr: string | null) => {
    if (!dateStr) return 'Never';
    return new Date(dateStr).toLocaleDateString('en-AU', {
      day: 'numeric',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const existingSession = sessions.find(
    (s) => s.quarter === selectedQuarter && s.fy_year === selectedFyYear
  );

  const currentWorkflowStep = getWorkflowStep(selectedSession, !!calculation);

  const significantVariances = variance?.prior_quarter?.variances?.filter(
    (v) => v.severity === 'critical' || v.severity === 'warning'
  ) || [];

  // ==========================================================================
  // Render
  // ==========================================================================

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="text-center">
          <Loader2 className="w-8 h-8 animate-spin text-muted-foreground mx-auto mb-3" />
          <p className="text-sm text-muted-foreground font-medium tracking-wide">Loading BAS sessions...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-status-danger/10 border border-status-danger/20 rounded-2xl p-8 text-center">
        <AlertCircle className="w-10 h-10 text-status-danger mx-auto mb-3" />
        <p className="text-status-danger font-medium mb-1">Unable to load BAS data</p>
        <p className="text-status-danger text-sm mb-1">{error}</p>
        <p className="text-status-danger/70 text-xs mb-4">Xero may be unavailable. Check the Xero connection in Settings, then try again.</p>
        <button
          onClick={() => { setError(null); fetchSessions(); }}
          className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-status-danger hover:text-status-danger hover:bg-status-danger/10 rounded-lg transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="min-h-[600px]">
      {/* GST Basis selection modal (Spec 062 - US1) */}
      <GSTBasisModal
        open={showGSTBasisModal}
        connectionId={connectionId}
        getToken={getToken}
        currentBasis={clientGstBasis ?? null}
        isLodged={selectedSession ? isSessionLodged(selectedSession) : false}
        onClose={() => setShowGSTBasisModal(false)}
        onSaved={(basis) => {
          setShowGSTBasisModal(false);
          setLocalGstBasis(basis);
          onGstBasisChanged?.(basis);
          // Pass basis directly to avoid stale closure on localGstBasis
          setTimeout(() => handleCalculate(basis), 100);
        }}
      />

      {/* Unreconciled data warning dialog (Spec 062 - US11) */}
      {selectedSession && reconciliationStatus && (
        <UnreconciledWarning
          open={showUnreconciledWarning}
          unreconciledCount={reconciliationStatus.unreconciled_count}
          totalTransactions={reconciliationStatus.total_transactions}
          asOf={reconciliationStatus.as_of}
          onProceed={() => {
            setShowUnreconciledWarning(false);
            setProceededWithUnreconciled(true);
          }}
          onGoBack={() => {
            // Dismiss the dialog and stay on the current session.
            // Clearing the session would drop the user on an empty "select a quarter"
            // screen — the quarter dropdown is still on Q4 in the parent so there is
            // nowhere sensible to snap back to from inside BASTab.
            // The user can use the quarter dropdown to navigate back to Q3 themselves,
            // or open Xero in a new tab to reconcile and then recalculate here.
            setShowUnreconciledWarning(false);
          }}
        />
      )}

      {/* Header - only show Create button when needed */}
      <div className="flex items-center justify-end mb-4">
        {!existingSession && sessions.length > 0 && (
          <button
            onClick={handleCreateSession}
            disabled={isCreating}
            className="inline-flex items-center gap-2 px-4 py-2.5 bg-foreground text-white text-sm font-medium rounded-xl hover:bg-foreground/90 disabled:opacity-50 transition-all shadow-sm"
          >
            {isCreating ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Plus className="w-4 h-4" />
            )}
            New BAS Session
          </button>
        )}
      </div>

      {/* Empty State */}
      {sessions.length === 0 ? (
        <div className="bg-muted rounded-2xl p-12 text-center border border-border">
          <div className="w-16 h-16 bg-muted rounded-2xl flex items-center justify-center mx-auto mb-6">
            <FileText className="w-8 h-8 text-muted-foreground" />
          </div>
          <h3 className="text-lg font-semibold text-foreground mb-2">
            No BAS Sessions Yet
          </h3>
          <p className="text-muted-foreground mb-6 max-w-md mx-auto">
            Start preparing your Business Activity Statement for Q{selectedQuarter} FY{selectedFyYear}
          </p>
          <button
            onClick={handleCreateSession}
            disabled={isCreating}
            className="inline-flex items-center gap-2 px-6 py-3 bg-foreground text-white font-medium rounded-xl hover:bg-foreground/90 disabled:opacity-50 transition-all shadow-lg shadow-foreground/10"
          >
            {isCreating ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Zap className="w-4 h-4" />
            )}
            Create First BAS Session
          </button>
        </div>
      ) : (
        <div>
          {/* Main Content - Full Width */}
          <div>
            {selectedSession ? (
              <div className="space-y-4">
                {/* Workflow Progress Bar */}
                <div className="bg-card rounded-2xl border border-border p-4">
                  <div className="flex items-center justify-between overflow-x-auto">
                    {WORKFLOW_STEPS.map((step, index) => {
                      const StepIcon = step.icon;
                      const isCompleted = index < currentWorkflowStep;
                      const isCurrent = index === currentWorkflowStep - 1;

                      return (
                        <div key={step.id} className="flex items-center flex-shrink-0">
                          <div className={`flex items-center gap-1.5 sm:gap-2 px-2 sm:px-3 py-1 sm:py-1.5 rounded-lg ${
                            isCompleted
                              ? 'bg-status-success/10 text-status-success'
                              : isCurrent
                                ? 'bg-primary/10 text-primary'
                                : 'text-muted-foreground'
                          }`}>
                            <StepIcon className="w-4 h-4" />
                            <span className="hidden sm:inline text-xs font-semibold uppercase tracking-wide">
                              {step.label}
                            </span>
                            {isCompleted && <CheckCircle2 className="w-3.5 h-3.5" />}
                          </div>
                          {index < WORKFLOW_STEPS.length - 1 && (
                            <ArrowRight className={`w-4 h-4 mx-1 sm:mx-2 hidden sm:block ${
                              index < currentWorkflowStep - 1 ? 'text-status-success' : 'text-border'
                            }`} />
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Unreconciled data persistent banner (Spec 062 - US11) */}
                {proceededWithUnreconciled && reconciliationStatus && reconciliationStatus.unreconciled_count > 0 && (
                  <div className="flex items-center gap-3 bg-status-warning/10 border border-status-warning/20 rounded-xl px-4 py-3">
                    <AlertCircle className="w-4 h-4 text-status-warning shrink-0" />
                    <p className="text-status-warning text-sm">
                      Warning: based on unreconciled data as at {reconciliationStatus.as_of ? new Date(reconciliationStatus.as_of).toLocaleDateString('en-AU', { day: 'numeric', month: 'short', year: 'numeric' }) : 'unknown'}
                    </p>
                  </div>
                )}

                {/* Hero Summary Panel */}
                <div className={`rounded-2xl p-6 ${
                  calculation?.is_refund
                    ? 'bg-primary'
                    : 'bg-foreground'
                }`}>
                  <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
                    <div>
                      <div className="flex items-center gap-3 mb-1">
                        <h3 className="text-white/70 text-sm font-medium uppercase tracking-wider">
                          {selectedSession.period_display_name}
                        </h3>
                        <span className={`px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wide ${
                          calculation?.is_refund
                            ? 'bg-white/20 text-white'
                            : 'bg-white/10 text-white/90'
                        }`}>
                          {getSessionStatusLabel(selectedSession.status)}
                        </span>
                      </div>
                      <p className="text-white/50 text-xs mb-2">
                        {formatDate(selectedSession.start_date)} – {formatDate(selectedSession.end_date)}
                      </p>

                      {/* Status indicators: coding + GST basis */}
                      <div className="flex flex-wrap items-center gap-2 mb-4">
                        {taxCodeSummary && (
                          taxCodeSummary.unresolved_count > 0 ? (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wide bg-status-warning/30 text-status-warning border border-status-warning/40">
                              {taxCodeSummary.unresolved_count} uncoded
                            </span>
                          ) : taxCodeSummary.resolved_count > 0 ? (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wide bg-status-success/20 text-status-success border border-status-success/30">
                              All coded ✓
                            </span>
                          ) : null
                        )}
                        {selectedSession.gst_basis_used && (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wide bg-white/10 text-white/70 border border-white/20">
                            GST: {selectedSession.gst_basis_used === 'cash' ? 'Cash basis' : 'Accrual basis'}
                          </span>
                        )}
                      </div>

                      {calculation ? (
                        <>
                          <p className="text-white/60 text-sm font-medium mb-1">
                            {calculation.is_refund ? 'Refund from ATO' : 'Payable to ATO'}
                          </p>
                          <p className="text-3xl font-bold text-white tracking-tight tabular-nums">
                            {formatBASCurrency(Math.abs(parseFloat(calculation.total_payable)))}
                          </p>
                          <div className="flex flex-wrap items-center gap-3 sm:gap-6 mt-4">
                            <div>
                              <p className="text-white/40 text-[10px] font-medium uppercase tracking-wider">1A GST Collected</p>
                              <p className="text-white text-lg font-semibold tabular-nums">
                                {formatBASCurrency(calculation.field_1a_gst_on_sales)}
                              </p>
                            </div>
                            <div className="w-px h-8 bg-white/20" />
                            <div>
                              <p className="text-white/40 text-[10px] font-medium uppercase tracking-wider">1B GST Paid</p>
                              <p className="text-white text-lg font-semibold tabular-nums">
                                {formatBASCurrency(calculation.field_1b_gst_on_purchases)}
                              </p>
                            </div>
                            {parseFloat(calculation.w2_amount_withheld) > 0 && (
                              <>
                                <div className="w-px h-8 bg-white/20" />
                                <div>
                                  <p className="text-white/40 text-[10px] font-medium uppercase tracking-wider">W2 PAYG</p>
                                  <p className="text-white text-lg font-semibold tabular-nums">
                                    {formatBASCurrency(calculation.w2_amount_withheld)}
                                  </p>
                                </div>
                              </>
                            )}
                          </div>
                        </>
                      ) : (
                        <div>
                          <p className="text-white/60 text-sm font-medium mb-1">Total Payable</p>
                          <p className="text-3xl font-bold text-white/30">—</p>
                          <p className="text-white/40 text-sm mt-2">Calculate to see BAS figures</p>
                        </div>
                      )}
                    </div>

                    {/* Actions */}
                    <div className="flex flex-col sm:items-end gap-2">
                      <button
                        onClick={() => handleCalculate()}
                        disabled={isCalculating}
                        className="inline-flex items-center gap-2 px-5 py-2.5 bg-white text-foreground text-sm font-semibold rounded-xl hover:bg-white/90 disabled:opacity-50 transition-all shadow-lg"
                      >
                        {isCalculating ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <Calculator className="w-4 h-4" />
                        )}
                        {calculation ? 'Recalculate' : 'Calculate'}
                      </button>

                      {calculation && (
                        <div className="flex flex-col sm:items-end gap-2">
                          <div className="flex flex-wrap items-center gap-2">
                            <button
                              onClick={() => handleExport('pdf')}
                              disabled={isExporting !== null}
                              className="inline-flex items-center gap-1.5 px-3 py-2 bg-white/10 hover:bg-white/20 text-white text-sm font-medium rounded-lg disabled:opacity-50 transition-all"
                            >
                              {isExporting === 'pdf' ? (
                                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                              ) : (
                                <Download className="w-3.5 h-3.5" />
                              )}
                              PDF
                            </button>
                            <button
                              onClick={() => handleExport('excel')}
                              disabled={isExporting !== null}
                              className="inline-flex items-center gap-1.5 px-3 py-2 bg-white/10 hover:bg-white/20 text-white text-sm font-medium rounded-lg disabled:opacity-50 transition-all"
                            >
                              {isExporting === 'excel' ? (
                                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                              ) : (
                                <FileSpreadsheet className="w-3.5 h-3.5" />
                              )}
                              Excel
                            </button>
                            <button
                              onClick={handleExportCSV}
                              disabled={isExporting !== null}
                              className="inline-flex items-center gap-1.5 px-3 py-2 bg-white/10 hover:bg-white/20 text-white text-sm font-medium rounded-lg disabled:opacity-50 transition-all"
                            >
                              {isExporting === 'csv' ? (
                                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                              ) : (
                                <Table className="w-3.5 h-3.5" />
                              )}
                              CSV
                            </button>
                          </div>
                          {/* Lodgement Summary Export (for approved/lodged sessions) */}
                          {(selectedSession.status === 'approved' || isSessionLodged(selectedSession)) && (
                            <button
                              onClick={() => handleExportWithLodgement('pdf')}
                              disabled={isExporting !== null}
                              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-status-success/20 hover:bg-status-success/30 text-status-success text-xs font-medium rounded-lg disabled:opacity-50 transition-all"
                            >
                              {isExporting === 'pdf' ? (
                                <Loader2 className="w-3 h-3 animate-spin" />
                              ) : (
                                <CheckCircle2 className="w-3 h-3" />
                              )}
                              Lodgement Summary
                            </button>
                          )}
                        </div>
                      )}

                      {calculation && (
                        <p className="text-white/30 text-[10px] mt-2">
                          {calculation.invoice_count} invoices · {calculation.transaction_count} txns
                        </p>
                      )}
                    </div>
                  </div>
                </div>

                {/* Review Banner - Only show if needed */}
                {selectedSession.auto_created && !selectedSession.reviewed_by && calculation && (
                  <div className="bg-status-warning/10 border border-status-warning/20 rounded-xl p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 bg-status-warning/20 rounded-xl flex items-center justify-center">
                          <Bot className="w-5 h-5 text-status-warning" />
                        </div>
                        <div>
                          <h5 className="font-semibold text-status-warning text-sm">Review Required</h5>
                          <p className="text-status-warning/70 text-xs">
                            Auto-generated session needs accountant review
                          </p>
                        </div>
                      </div>
                      <button
                        onClick={handleMarkReviewed}
                        disabled={isReviewing}
                        className="inline-flex items-center gap-2 px-4 py-2 bg-status-warning text-white text-sm font-semibold rounded-lg hover:bg-status-warning/90 disabled:opacity-50 transition-all"
                      >
                        {isReviewing ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <ShieldCheck className="w-4 h-4" />
                        )}
                        Mark Reviewed
                      </button>
                    </div>
                  </div>
                )}

                {/* Reviewed Badge */}
                {selectedSession.reviewed_by && !isSessionLodged(selectedSession) && selectedSession.status !== 'approved' && (
                  <div className="bg-status-success/10 border border-status-success/20 rounded-xl px-4 py-3">
                    <div className="flex items-center gap-2">
                      <UserCheck className="w-4 h-4 text-status-success" />
                      <span className="text-status-success text-sm font-medium">
                        Reviewed by {selectedSession.reviewed_by_name || 'accountant'}
                      </span>
                      <span className="text-status-success text-xs">
                        · {formatDateTime(selectedSession.reviewed_at)}
                      </span>
                    </div>
                  </div>
                )}

                {/* Tax Code Exclusion Banner (Spec 046) — only when there are excluded items */}
                {calculation && taxCodeSummary && taxCodeSummary.excluded_count > 0 && (
                  <div className="w-full bg-status-warning/10 border border-status-warning/20 rounded-xl p-4">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 bg-status-warning/20 rounded-xl flex items-center justify-center">
                        <AlertCircle className="w-5 h-5 text-status-warning" />
                      </div>
                      <div>
                        <h5 className="font-semibold text-status-warning text-sm">
                          {taxCodeSummary.unresolved_count > 0
                            ? `${taxCodeSummary.excluded_count} transactions (${formatBASCurrency(taxCodeSummary.excluded_amount)}) excluded from this BAS`
                            : 'All excluded transactions resolved'}
                        </h5>
                        <p className="text-status-warning/70 text-xs">
                          {taxCodeSummary.unresolved_count > 0
                            ? `${taxCodeSummary.unresolved_count} need tax codes · ${taxCodeSummary.resolved_count} resolved`
                            : `${taxCodeSummary.resolved_count} resolved — recalculate to update BAS`}
                        </p>
                      </div>
                    </div>
                  </div>
                )}

                {/* Transaction Resolution Panel — always shown when session has calculations (Spec 057) */}
                {calculation && selectedSession && (
                  <div className="border border-border rounded-xl p-4">
                    <TaxCodeResolutionPanel
                      connectionId={connectionId}
                      sessionId={selectedSession.id}
                      getToken={getToken}
                      onSummaryChange={(summary) => {
                        if (selectedSession) {
                          queryClient.setQueryData(
                            basQueryKeys.taxCodeSummary(connectionId, selectedSession.id),
                            summary,
                          );
                        }
                      }}
                      onRecalculated={() => {
                        if (selectedSession) {
                          queryClient.invalidateQueries({
                            queryKey: ['bas', connectionId, selectedSession.id],
                            exact: false,
                          });
                        }
                      }}
                      onSessionUpdated={fetchSessions}
                      completedWritebackJob={completedWritebackJob}
                      activeWritebackJobId={activeWritebackJobId}
                      approvedUnsyncedCount={selectedSession.approved_unsynced_count ?? 0}
                      onJobCreated={(job) => {
                        setActiveWritebackJobId(job.id);
                        setCompletedWritebackJob(null);
                      }}
                      onJobComplete={(job) => {
                        setActiveWritebackJobId(null);
                        setCompletedWritebackJob(job);
                        fetchSessions();
                      }}
                    />
                  </div>
                )}

                {/* Review Workflow Actions (Spec 010) */}
                {isInReviewState(selectedSession.status) && calculation && (
                  <div className="bg-primary/10 border border-primary/20 rounded-xl p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 bg-primary/20 rounded-xl flex items-center justify-center">
                          <ShieldCheck className="w-5 h-5 text-primary" />
                        </div>
                        <div>
                          <h5 className="font-semibold text-primary text-sm">Ready for Approval</h5>
                          <p className="text-primary/70 text-xs">
                            Review complete - approve or request changes
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => setShowRequestChangesModal(true)}
                          disabled={isRequestingChanges}
                          className="inline-flex items-center gap-2 px-4 py-2 bg-card border border-border text-foreground text-sm font-semibold rounded-lg hover:bg-muted disabled:opacity-50 transition-all"
                        >
                          <ThumbsDown className="w-4 h-4" />
                          Request Changes
                        </button>
                        <button
                          onClick={handleApprove}
                          disabled={isApproving}
                          className="inline-flex items-center gap-2 px-4 py-2 bg-status-success text-white text-sm font-semibold rounded-lg hover:bg-status-success/90 disabled:opacity-50 transition-all"
                        >
                          {isApproving ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                          ) : (
                            <CheckCircle2 className="w-4 h-4" />
                          )}
                          Approve
                        </button>
                      </div>
                    </div>
                  </div>
                )}

                {/* Reopen Banner - for approved sessions */}
                {selectedSession.status === 'approved' && !isSessionLodged(selectedSession) && (
                  <div className="bg-status-success/10 border border-status-success/20 rounded-xl px-4 py-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <CheckCircle2 className="w-4 h-4 text-status-success" />
                        <span className="text-status-success text-sm font-medium">
                          Approved - Ready for lodgement
                        </span>
                      </div>
                      <button
                        onClick={handleReopen}
                        disabled={isReopening}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-muted rounded-lg transition-all"
                      >
                        {isReopening ? (
                          <Loader2 className="w-3 h-3 animate-spin" />
                        ) : (
                          <RotateCcw className="w-3 h-3" />
                        )}
                        Reopen
                      </button>
                    </div>
                  </div>
                )}

                {/* Lodgement Section (Spec 011) */}
                {isSessionLodged(selectedSession) && (
                  <LodgementBadge
                    session={selectedSession}
                    variant="detailed"
                    onEditClick={() => handleOpenLodgementModal(true)}
                  />
                )}

                {/* Record Lodgement Banner - for approved sessions pending lodgement */}
                {canRecordLodgement(selectedSession) && calculation && (
                  <div className="bg-status-success/10 border border-status-success/20 rounded-xl p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 bg-status-success/20 rounded-xl flex items-center justify-center">
                          <Send className="w-5 h-5 text-status-success" />
                        </div>
                        <div>
                          <h5 className="font-semibold text-status-success text-sm">Ready to Lodge</h5>
                          <p className="text-status-success/70 text-xs">
                            Approved and ready for ATO submission
                          </p>
                        </div>
                      </div>
                      <button
                        onClick={() => handleOpenLodgementModal(false)}
                        className="inline-flex items-center gap-2 px-4 py-2 bg-status-success text-white text-sm font-semibold rounded-lg hover:bg-status-success/90 transition-all"
                      >
                        <Send className="w-4 h-4" />
                        Record Lodgement
                      </button>
                    </div>
                  </div>
                )}

                {/* Tabbed Content */}
                {calculation && (
                  <div className="bg-card rounded-2xl border border-border overflow-hidden">
                    {/* Tab Headers */}
                    <div className="flex border-b border-border overflow-x-auto">
                      {[
                        { id: 'gst' as DetailTab, label: 'GST Details', icon: Calculator },
                        { id: 'payg' as DetailTab, label: 'PAYG', icon: FileText, badge: parseFloat(calculation.w1_total_wages) > 0 },
                        { id: 'variance' as DetailTab, label: 'Variance', icon: TrendingUp, badge: significantVariances.length > 0, badgeCount: significantVariances.length },
                        { id: 'adjustments' as DetailTab, label: 'Adjustments', icon: PencilLine, badge: adjustments.length > 0, badgeCount: adjustments.length },
                      ].map((tab) => {
                        const TabIcon = tab.icon;
                        const isActive = activeTab === tab.id;

                        return (
                          <button
                            key={tab.id}
                            onClick={() => setActiveTab(tab.id)}
                            className={`flex items-center gap-2 px-5 py-3.5 text-sm font-medium border-b-2 transition-all flex-shrink-0 ${
                              isActive
                                ? 'border-foreground text-foreground bg-muted/50'
                                : 'border-transparent text-muted-foreground hover:text-foreground  hover:bg-muted/30 '
                            }`}
                          >
                            <TabIcon className="w-4 h-4" />
                            {tab.label}
                            {tab.badge && tab.badgeCount && (
                              <span className={`px-1.5 py-0.5 text-[10px] font-bold rounded-full ${
                                tab.id === 'variance'
                                  ? 'bg-status-warning/10 text-status-warning'
                                  : 'bg-muted text-muted-foreground '
                              }`}>
                                {tab.badgeCount}
                              </span>
                            )}
                          </button>
                        );
                      })}
                    </div>

                    {/* Tab Content */}
                    <div className="p-5">
                      {detailLoading ? (
                        <div className="flex items-center justify-center py-12">
                          <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
                        </div>
                      ) : (
                        <>
                          {/* Xero BAS Cross-Check (Spec 056) — loads independently of main content */}
                          {crossCheckFetching && !xeroCrossCheck && (
                            <div className="mb-4 h-9 rounded-lg bg-muted animate-pulse" />
                          )}
                          {xeroCrossCheck && (
                            <XeroBASCrossCheck
                              data={xeroCrossCheck}
                              onRefresh={handleRefreshCrossCheck}
                            />
                          )}

                          {/* GST Tab */}
                          {activeTab === 'gst' && (
                            <div className="space-y-4">
                              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                                {/* Sales Section */}
                                <div className="col-span-3">
                                  <h5 className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider mb-3">Sales</h5>
                                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                                    <div className="bg-muted rounded-xl p-4">
                                      <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1">G1 Total Sales</p>
                                      <p className="text-lg font-bold text-foreground tabular-nums">
                                        {formatBASCurrency(calculation.g1_total_sales)}
                                      </p>
                                    </div>
                                    <div className="bg-muted rounded-xl p-4">
                                      <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1">G2 Export Sales</p>
                                      <p className="text-lg font-bold text-foreground tabular-nums">
                                        {formatBASCurrency(calculation.g2_export_sales)}
                                      </p>
                                    </div>
                                    <div className="bg-muted rounded-xl p-4">
                                      <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1">G3 GST-Free</p>
                                      <p className="text-lg font-bold text-foreground tabular-nums">
                                        {formatBASCurrency(calculation.g3_gst_free_sales)}
                                      </p>
                                    </div>
                                  </div>
                                </div>

                                {/* Purchases Section */}
                                <div className="col-span-3">
                                  <h5 className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider mb-3">Purchases</h5>
                                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                    <div className="bg-muted rounded-xl p-4">
                                      <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1">G11 Non-Capital</p>
                                      <p className="text-lg font-bold text-foreground tabular-nums">
                                        {formatBASCurrency(calculation.g11_non_capital_purchases)}
                                      </p>
                                    </div>
                                    <div className="bg-muted rounded-xl p-4">
                                      <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1">G10 Capital</p>
                                      <p className="text-lg font-bold text-foreground tabular-nums">
                                        {formatBASCurrency(calculation.g10_capital_purchases)}
                                      </p>
                                    </div>
                                  </div>
                                </div>

                                {/* GST Summary */}
                                <div className="col-span-3">
                                  <h5 className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider mb-3">GST Summary</h5>
                                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                                    <div className="bg-status-success/10 rounded-xl p-4 border border-status-success/20">
                                      <p className="text-[10px] font-semibold text-status-success uppercase tracking-wider mb-1">1A GST Collected</p>
                                      <p className="text-lg font-bold text-status-success tabular-nums">
                                        {formatBASCurrency(calculation.field_1a_gst_on_sales)}
                                      </p>
                                    </div>
                                    <div className="bg-status-danger/10 rounded-xl p-4 border border-status-danger/20">
                                      <p className="text-[10px] font-semibold text-status-danger uppercase tracking-wider mb-1">1B GST Paid</p>
                                      <p className="text-lg font-bold text-status-danger tabular-nums">
                                        {formatBASCurrency(calculation.field_1b_gst_on_purchases)}
                                      </p>
                                    </div>
                                    <div className={`rounded-xl p-4 border ${
                                      calculation.is_refund
                                        ? 'bg-primary/10 border-primary/20'
                                        : 'bg-status-warning/10 border-status-warning/20'
                                    }`}>
                                      <p className={`text-[10px] font-semibold uppercase tracking-wider mb-1 ${
                                        calculation.is_refund ? 'text-primary' : 'text-status-warning'
                                      }`}>
                                        Net GST {calculation.is_refund ? '(Refund)' : '(Payable)'}
                                      </p>
                                      <p className={`text-lg font-bold tabular-nums ${
                                        calculation.is_refund ? 'text-primary' : 'text-status-warning'
                                      }`}>
                                        {formatBASCurrency(Math.abs(parseFloat(calculation.gst_payable)))}
                                      </p>
                                    </div>
                                  </div>
                                </div>
                              </div>
                            </div>
                          )}

                          {/* PAYG Tab */}
                          {activeTab === 'payg' && (
                            <div className="space-y-4">
                              {parseFloat(calculation.w1_total_wages) > 0 ? (
                                <>
                                  {/* Source label */}
                                  <p className="text-xs text-muted-foreground">
                                    {calculation.payg_source_label ||
                                      `From Xero Payroll — ${formatDate(selectedSession.start_date)} to ${formatDate(selectedSession.end_date)}`}
                                  </p>
                                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                                    <div className="bg-accent/10 rounded-xl p-4 border border-accent/20">
                                      <p className="text-[10px] font-semibold text-accent-foreground uppercase tracking-wider mb-1">W1 Total Wages</p>
                                      <p className="text-lg font-bold text-accent-foreground tabular-nums">
                                        {formatBASCurrency(calculation.w1_total_wages)}
                                      </p>
                                    </div>
                                    <div className="bg-status-warning/10 rounded-xl p-4 border border-status-warning/20">
                                      <p className="text-[10px] font-semibold text-status-warning uppercase tracking-wider mb-1">W2 Tax Withheld</p>
                                      <p className="text-lg font-bold text-status-warning tabular-nums">
                                        {formatBASCurrency(calculation.w2_amount_withheld)}
                                      </p>
                                    </div>
                                    <div className="bg-muted rounded-xl p-4">
                                      <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1">Pay Runs</p>
                                      <p className="text-lg font-bold text-foreground tabular-nums">
                                        {calculation.pay_run_count}
                                      </p>
                                    </div>
                                  </div>
                                  {/* Draft pay run caveat */}
                                  {(calculation.draft_pay_run_count ?? 0) > 0 && (
                                    <div className="flex items-center gap-2 text-xs text-status-warning bg-status-warning/10 rounded-lg px-3 py-2 border border-status-warning/20">
                                      <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                                      {calculation.draft_pay_run_count} draft pay run{(calculation.draft_pay_run_count ?? 0) !== 1 ? 's' : ''} not included — finalise in Xero to include in W1/W2.
                                    </div>
                                  )}
                                </>
                              ) : (
                                <PAYGManualEntry
                                  calculation={calculation}
                                  getToken={getToken}
                                  onUpdated={(updated) => {
                                    queryClient.setQueryData(
                                      basQueryKeys.calculation(connectionId, sessionId!),
                                      updated,
                                    );
                                  }}
                                />
                              )}

                              {/* PAYG Instalment (T1/T2) — always visible */}
                              <InstalmentSection
                                calculation={calculation}
                                getToken={getToken}
                                onUpdated={(updated) => {
                                  queryClient.setQueryData(
                                    basQueryKeys.calculation(connectionId, sessionId!),
                                    updated,
                                  );
                                }}
                              />
                            </div>
                          )}

                          {/* Variance Tab */}
                          {activeTab === 'variance' && (
                            <div>
                              {variance?.prior_quarter?.has_data ? (
                                <div className="space-y-4">
                                  {/* Guidance Header */}
                                  <div className="bg-primary/10 border border-primary/20 rounded-xl p-4">
                                    <div className="flex items-start gap-3">
                                      <div className="p-1.5 bg-primary/20 rounded-lg">
                                        <Lightbulb className="w-4 h-4 text-primary" />
                                      </div>
                                      <div>
                                        <h5 className="text-sm font-semibold text-primary">Review Significant Changes</h5>
                                        <p className="text-xs text-primary/70 mt-0.5">
                                          Large variances may indicate business changes, data issues, or items needing adjustment.
                                          Review each item and acknowledge once verified.
                                        </p>
                                      </div>
                                    </div>
                                  </div>

                                  {/* Comparison Header */}
                                  <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-2">
                                      <History className="w-4 h-4 text-muted-foreground" />
                                      <span className="text-sm text-muted-foreground">
                                        Compared with <span className="font-semibold">{variance.prior_quarter.comparison_period_name}</span>
                                      </span>
                                    </div>
                                    <div className="flex items-center gap-2">
                                      {acknowledgedVariances.size > 0 && (
                                        <span className="px-2 py-1 bg-status-success/20 text-status-success text-xs font-semibold rounded-lg">
                                          {acknowledgedVariances.size} reviewed
                                        </span>
                                      )}
                                      {significantVariances.length > 0 && (
                                        <span className="px-2 py-1 bg-status-warning/20 text-status-warning text-xs font-semibold rounded-lg">
                                          {significantVariances.filter(v => !acknowledgedVariances.has(v.field_name)).length} pending review
                                        </span>
                                      )}
                                    </div>
                                  </div>

                                  {/* Variance Items */}
                                  <div className="space-y-2">
                                    {variance.prior_quarter.variances
                                      .filter((v) => v.severity !== 'normal' || Math.abs(parseFloat(v.absolute_change || '0')) > 0)
                                      .map((v) => {
                                        const isExpanded = expandedVariance === v.field_name;
                                        const isAcknowledged = acknowledgedVariances.has(v.field_name);

                                        return (
                                          <div
                                            key={v.field_name}
                                            className={`rounded-xl border transition-all ${
                                              isAcknowledged
                                                ? 'bg-muted border-border'
                                                : `${getVarianceSeverityBgColor(v.severity)} border-transparent`
                                            }`}
                                          >
                                            {/* Main Row */}
                                            <button
                                              onClick={() => setExpandedVariance(isExpanded ? null : v.field_name)}
                                              className="w-full flex items-center justify-between p-3 text-left"
                                            >
                                              <div className="flex items-center gap-3">
                                                <ChevronDown className={`w-4 h-4 text-muted-foreground transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
                                                {v.severity === 'critical' && !isAcknowledged && (
                                                  <AlertCircle className="w-4 h-4 text-status-danger" />
                                                )}
                                                {isAcknowledged && (
                                                  <Check className="w-4 h-4 text-status-success" />
                                                )}
                                                <span className={`text-sm font-medium ${isAcknowledged ? 'text-muted-foreground' : 'text-foreground'}`}>
                                                  {v.field_label}
                                                </span>
                                              </div>
                                              <div className="flex items-center gap-6">
                                                <div className="text-right">
                                                  <p className="text-xs text-muted-foreground">Current</p>
                                                  <p className="text-sm font-semibold text-foreground tabular-nums">
                                                    {formatBASCurrency(v.current_value)}
                                                  </p>
                                                </div>
                                                <div className="text-right">
                                                  <p className="text-xs text-muted-foreground">Prior</p>
                                                  <p className="text-sm text-muted-foreground tabular-nums">
                                                    {formatBASCurrency(v.prior_value || '0')}
                                                  </p>
                                                </div>
                                                <ThresholdTooltip metricKey="bas_variance_severity">
                                                  <div className={`flex items-center gap-1 px-2 py-1 rounded-lg text-sm font-semibold ${
                                                    isAcknowledged ? 'bg-muted text-muted-foreground' : getVarianceSeverityColor(v.severity)
                                                  }`}>
                                                    {parseFloat(v.absolute_change || '0') >= 0 ? (
                                                      <TrendingUp className="w-4 h-4" />
                                                    ) : (
                                                      <TrendingDown className="w-4 h-4" />
                                                    )}
                                                    {formatPercentage(v.percent_change || '0')}
                                                  </div>
                                                </ThresholdTooltip>
                                              </div>
                                            </button>

                                            {/* Expanded Actions Panel */}
                                            {isExpanded && (
                                              <div className="px-3 pb-3 pt-1 border-t border-border/50">
                                                <div className="flex items-center justify-between">
                                                  <div className="text-xs text-muted-foreground tabular-nums">
                                                    <span className="font-medium">Change:</span>{' '}
                                                    {parseFloat(v.absolute_change || '0') >= 0 ? '+' : ''}
                                                    {formatBASCurrency(v.absolute_change || '0')}
                                                    {' '}from prior quarter
                                                  </div>
                                                  <div className="flex items-center gap-2">
                                                    {/* View Transactions */}
                                                    <button
                                                      onClick={(e) => {
                                                        e.stopPropagation();
                                                        handleViewFieldTransactions(v.field_name);
                                                      }}
                                                      className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-muted rounded-lg transition-all"
                                                    >
                                                      <Eye className="w-3.5 h-3.5" />
                                                      View Details
                                                    </button>

                                                    {/* Add Adjustment */}
                                                    {isSessionEditable(selectedSession.status) && (
                                                      <button
                                                        onClick={(e) => {
                                                          e.stopPropagation();
                                                          setAdjustmentFieldName(v.field_name);
                                                          setShowAdjustmentForm(true);
                                                          setActiveTab('adjustments');
                                                        }}
                                                        className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-muted rounded-lg transition-all"
                                                      >
                                                        <PencilLine className="w-3.5 h-3.5" />
                                                        Add Adjustment
                                                      </button>
                                                    )}

                                                    {/* Acknowledge/Mark Reviewed */}
                                                    <button
                                                      onClick={(e) => {
                                                        e.stopPropagation();
                                                        setAcknowledgedVariances(prev => {
                                                          const next = new Set(prev);
                                                          if (next.has(v.field_name)) {
                                                            next.delete(v.field_name);
                                                          } else {
                                                            next.add(v.field_name);
                                                          }
                                                          return next;
                                                        });
                                                      }}
                                                      className={`inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-semibold rounded-lg transition-all ${
                                                        isAcknowledged
                                                          ? 'bg-status-success/20 text-status-success hover:bg-status-success/30'
                                                          : 'bg-foreground text-white hover:bg-foreground/90'
                                                      }`}
                                                    >
                                                      <Check className="w-3.5 h-3.5" />
                                                      {isAcknowledged ? 'Reviewed' : 'Mark Reviewed'}
                                                    </button>
                                                  </div>
                                                </div>
                                              </div>
                                            )}
                                          </div>
                                        );
                                      })}
                                  </div>

                                  {/* All Reviewed Banner */}
                                  {significantVariances.length > 0 &&
                                   significantVariances.every(v => acknowledgedVariances.has(v.field_name)) && (
                                    <div className="bg-status-success/10 border border-status-success/20 rounded-xl p-4 text-center">
                                      <CheckCircle2 className="w-6 h-6 text-status-success mx-auto mb-2" />
                                      <p className="text-sm font-semibold text-status-success">All variances reviewed</p>
                                      <p className="text-xs text-status-success mt-1">
                                        You can proceed with approval or make adjustments if needed.
                                      </p>
                                    </div>
                                  )}
                                </div>
                              ) : (
                                <div className="text-center py-8">
                                  <div className="w-12 h-12 bg-muted rounded-xl flex items-center justify-center mx-auto mb-3">
                                    <TrendingUp className="w-6 h-6 text-muted-foreground" />
                                  </div>
                                  <p className="text-muted-foreground font-medium">No prior data</p>
                                  <p className="text-muted-foreground text-sm">Variance analysis requires prior quarter data</p>
                                </div>
                              )}
                            </div>
                          )}

                          {/* Adjustments Tab */}
                          {activeTab === 'adjustments' && (
                            <div className="space-y-4">
                              {isSessionEditable(selectedSession.status) && (
                                <div className="flex justify-end">
                                  <button
                                    onClick={() => setShowAdjustmentForm(!showAdjustmentForm)}
                                    className="inline-flex items-center gap-2 px-3 py-2 text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-muted rounded-lg transition-all"
                                  >
                                    {showAdjustmentForm ? (
                                      <>
                                        <X className="w-4 h-4" /> Cancel
                                      </>
                                    ) : (
                                      <>
                                        <Plus className="w-4 h-4" /> Add Adjustment
                                      </>
                                    )}
                                  </button>
                                </div>
                              )}

                              {showAdjustmentForm && (
                                <form onSubmit={handleAddAdjustment} className="bg-muted rounded-xl p-4 space-y-4">
                                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                    <div>
                                      <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">
                                        Field
                                      </label>
                                      <select
                                        value={adjustmentFieldName}
                                        onChange={(e) => setAdjustmentFieldName(e.target.value)}
                                        className="w-full px-3 py-2.5 bg-card border border-border rounded-lg text-sm focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all"
                                      >
                                        <option value="g1_total_sales">G1 Total Sales</option>
                                        <option value="g2_export_sales">G2 Export Sales</option>
                                        <option value="g3_gst_free_sales">G3 GST-Free Sales</option>
                                        <option value="g10_capital_purchases">G10 Capital Purchases</option>
                                        <option value="g11_non_capital_purchases">G11 Non-Capital Purchases</option>
                                        <option value="field_1a_gst_on_sales">1A GST on Sales</option>
                                        <option value="field_1b_gst_on_purchases">1B GST on Purchases</option>
                                        <option value="w1_total_wages">W1 Total Wages</option>
                                        <option value="w2_amount_withheld">W2 PAYG Withheld</option>
                                      </select>
                                    </div>
                                    <div>
                                      <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">
                                        Amount
                                      </label>
                                      <input
                                        type="number"
                                        step="0.01"
                                        value={adjustmentAmount}
                                        onChange={(e) => setAdjustmentAmount(e.target.value)}
                                        placeholder="Use negative for decrease"
                                        required
                                        className="w-full px-3 py-2.5 bg-card border border-border rounded-lg text-sm focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all"
                                      />
                                    </div>
                                  </div>
                                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                    <div>
                                      <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">
                                        Reason
                                      </label>
                                      <input
                                        type="text"
                                        value={adjustmentReason}
                                        onChange={(e) => setAdjustmentReason(e.target.value)}
                                        placeholder="Explain the adjustment..."
                                        required
                                        className="w-full px-3 py-2.5 bg-card border border-border rounded-lg text-sm focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all"
                                      />
                                    </div>
                                    <div>
                                      <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">
                                        Reference <span className="text-muted-foreground font-normal">(optional)</span>
                                      </label>
                                      <input
                                        type="text"
                                        value={adjustmentReference}
                                        onChange={(e) => setAdjustmentReference(e.target.value)}
                                        placeholder="Invoice #, document ref..."
                                        className="w-full px-3 py-2.5 bg-card border border-border rounded-lg text-sm focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all"
                                      />
                                    </div>
                                  </div>
                                  <div className="flex justify-end pt-2">
                                    <button
                                      type="submit"
                                      disabled={isAddingAdjustment || !adjustmentReason || !adjustmentAmount}
                                      className="inline-flex items-center gap-2 px-4 py-2.5 bg-foreground text-white text-sm font-semibold rounded-lg hover:bg-foreground/90 disabled:opacity-50 transition-all"
                                    >
                                      {isAddingAdjustment ? (
                                        <Loader2 className="w-4 h-4 animate-spin" />
                                      ) : (
                                        <Plus className="w-4 h-4" />
                                      )}
                                      Add Adjustment
                                    </button>
                                  </div>
                                </form>
                              )}

                              {adjustments.length > 0 ? (
                                <div className="space-y-2">
                                  {adjustments.map((adjustment) => (
                                    <div
                                      key={adjustment.id}
                                      className="flex items-center justify-between p-4 bg-muted rounded-xl"
                                    >
                                      <div className="flex-1">
                                        <div className="flex items-center gap-3">
                                          <span className="font-semibold text-foreground">
                                            {getBASFieldLabel(adjustment.field_name)}
                                          </span>
                                          <span
                                            className={`px-2 py-0.5 rounded-md text-sm font-bold tabular-nums ${
                                              parseFloat(adjustment.adjustment_amount) >= 0
                                                ? 'bg-status-success/20 text-status-success'
                                                : 'bg-status-danger/20 text-status-danger'
                                            }`}
                                          >
                                            {parseFloat(adjustment.adjustment_amount) >= 0 ? '+' : ''}
                                            {formatBASCurrency(adjustment.adjustment_amount)}
                                          </span>
                                        </div>
                                        <p className="text-sm text-muted-foreground mt-1">{adjustment.reason}</p>
                                        {adjustment.reference && (
                                          <p className="text-xs text-muted-foreground mt-0.5">Ref: {adjustment.reference}</p>
                                        )}
                                      </div>
                                      {isSessionEditable(selectedSession.status) && (
                                        <button
                                          onClick={() => handleDeleteAdjustment(adjustment.id)}
                                          disabled={isDeletingAdjustment === adjustment.id}
                                          className="p-2 text-muted-foreground hover:text-status-danger hover:bg-status-danger/10 rounded-lg disabled:opacity-50 transition-all"
                                        >
                                          {isDeletingAdjustment === adjustment.id ? (
                                            <Loader2 className="w-4 h-4 animate-spin" />
                                          ) : (
                                            <Trash2 className="w-4 h-4" />
                                          )}
                                        </button>
                                      )}
                                    </div>
                                  ))}
                                </div>
                              ) : !showAdjustmentForm && (
                                <div className="text-center py-8">
                                  <div className="w-12 h-12 bg-muted rounded-xl flex items-center justify-center mx-auto mb-3">
                                    <PencilLine className="w-6 h-6 text-muted-foreground" />
                                  </div>
                                  <p className="text-muted-foreground font-medium">No adjustments</p>
                                  <p className="text-muted-foreground text-sm">
                                    {isSessionEditable(selectedSession.status)
                                      ? 'Add manual corrections if needed'
                                      : 'No manual adjustments were made'}
                                  </p>
                                </div>
                              )}
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  </div>
                )}

                {/* No Calculation State */}
                {!calculation && !detailLoading && (
                  <div className="bg-muted/50 rounded-2xl border border-border p-12 text-center">
                    <div className="w-16 h-16 bg-muted rounded-2xl flex items-center justify-center mx-auto mb-6">
                      <Calculator className="w-8 h-8 text-muted-foreground" />
                    </div>
                    <h4 className="text-lg font-semibold text-foreground mb-2">
                      Ready to Calculate
                    </h4>
                    <p className="text-muted-foreground mb-6 max-w-md mx-auto">
                      Click the Calculate button above to compute GST and PAYG figures from synced Xero data.
                    </p>
                  </div>
                )}
              </div>
            ) : (
              <div className="bg-muted/50 rounded-2xl border border-border p-12 text-center">
                <div className="w-16 h-16 bg-muted rounded-2xl flex items-center justify-center mx-auto mb-6">
                  <ChevronRight className="w-8 h-8 text-muted-foreground" />
                </div>
                <p className="text-muted-foreground font-medium">Select a quarter from the dropdown above</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Transaction Detail Modal */}
      {transactionModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/50 backdrop-blur-sm"
            onClick={() => setTransactionModalOpen(false)}
          />

          {/* Modal */}
          <div className="relative bg-card rounded-2xl shadow-2xl w-full max-w-3xl max-h-[80vh] overflow-hidden mx-2 sm:mx-4">
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-border">
              <div>
                <h3 className="text-lg font-semibold text-foreground">
                  {transactionModalData?.field_label || 'Transaction Details'}
                </h3>
                {transactionModalData && (
                  <p className="text-sm text-muted-foreground">
                    {formatDate(transactionModalData.period_start)} – {formatDate(transactionModalData.period_end)}
                  </p>
                )}
              </div>
              <button
                onClick={() => setTransactionModalOpen(false)}
                className="p-2 text-muted-foreground hover:text-muted-foreground hover:bg-muted rounded-lg transition-all"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Content */}
            <div className="overflow-y-auto max-h-[calc(80vh-140px)]">
              {transactionModalLoading ? (
                <div className="flex items-center justify-center py-16">
                  <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
                </div>
              ) : transactionModalData ? (
                <div className="p-6">
                  {/* Summary */}
                  <div className="flex items-center justify-between mb-6 p-4 bg-muted rounded-xl">
                    <div>
                      <p className="text-sm text-muted-foreground">Total Amount</p>
                      <p className="text-2xl font-bold text-foreground tabular-nums">
                        {formatBASCurrency(transactionModalData.total_amount)}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-sm text-muted-foreground">Transactions</p>
                      <p className="text-2xl font-bold text-foreground tabular-nums">
                        {transactionModalData.transaction_count}
                      </p>
                    </div>
                  </div>

                  {/* Transaction List */}
                  {transactionModalData.transactions.length > 0 ? (
                    <div className="space-y-2">
                      {transactionModalData.transactions.map((txn) => (
                        <div
                          key={txn.id}
                          className="flex items-center justify-between p-3 bg-muted rounded-lg hover:bg-muted transition-all"
                        >
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <span className={`px-1.5 py-0.5 text-[10px] font-semibold uppercase rounded ${
                                txn.source === 'invoice'
                                  ? 'bg-primary/20 text-primary'
                                  : 'bg-accent/20 text-accent-foreground'
                              }`}>
                                {txn.source === 'invoice' ? 'INV' : 'TXN'}
                              </span>
                              <span className="text-sm font-medium text-foreground truncate">
                                {txn.reference || 'No reference'}
                              </span>
                            </div>
                            <p className="text-xs text-muted-foreground mt-0.5 truncate">
                              {txn.description}
                            </p>
                            {txn.contact_name && (
                              <p className="text-xs text-muted-foreground mt-0.5">
                                {txn.contact_name}
                              </p>
                            )}
                          </div>
                          <div className="flex flex-wrap sm:flex-nowrap items-center gap-2 sm:gap-4 ml-2 sm:ml-4">
                            <div className="text-right">
                              <p className="text-xs text-muted-foreground">Date</p>
                              <p className="text-sm text-foreground">{formatDate(txn.date)}</p>
                            </div>
                            <div className="text-right min-w-[80px]">
                              <p className="text-xs text-muted-foreground">Amount</p>
                              <p className="text-sm font-semibold text-foreground tabular-nums">
                                {formatBASCurrency(txn.total_amount)}
                              </p>
                            </div>
                            {parseFloat(txn.tax_amount) > 0 && (
                              <div className="text-right min-w-[60px]">
                                <p className="text-xs text-muted-foreground">GST</p>
                                <p className="text-sm text-status-success tabular-nums">
                                  {formatBASCurrency(txn.tax_amount)}
                                </p>
                              </div>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-center py-12">
                      <FileText className="w-10 h-10 text-muted-foreground/50 mx-auto mb-3" />
                      <p className="text-muted-foreground">No transactions found</p>
                    </div>
                  )}
                </div>
              ) : (
                <div className="text-center py-16">
                  <AlertCircle className="w-10 h-10 text-muted-foreground/50 mx-auto mb-3" />
                  <p className="text-muted-foreground">Failed to load transactions</p>
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="flex items-center justify-end px-6 py-4 border-t border-border bg-muted">
              <button
                onClick={() => setTransactionModalOpen(false)}
                className="px-4 py-2 text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-muted rounded-lg transition-all"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Lodgement Modal (Spec 011) */}
      {selectedSession && calculation && (
        <LodgementModal
          session={selectedSession}
          totalPayable={calculation.total_payable}
          isRefund={calculation.is_refund}
          isOpen={lodgementModalOpen}
          onClose={() => setLodgementModalOpen(false)}
          onSubmit={handleLodgementSubmit}
          isUpdate={isLodgementUpdate}
        />
      )}

      {/* Request Changes Modal (Spec 010) */}
      {showRequestChangesModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div
            className="absolute inset-0 bg-black/50 backdrop-blur-sm"
            onClick={() => setShowRequestChangesModal(false)}
          />
          <div className="relative bg-card rounded-2xl shadow-2xl w-full max-w-md mx-4 overflow-hidden">
            <div className="px-6 py-4 border-b border-border">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-status-warning/20 rounded-xl flex items-center justify-center">
                    <MessageSquare className="w-5 h-5 text-status-warning" />
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold text-foreground">Request Changes</h3>
                    <p className="text-sm text-muted-foreground">
                      {selectedSession?.period_display_name}
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => setShowRequestChangesModal(false)}
                  className="p-2 text-muted-foreground hover:text-muted-foreground hover:bg-muted rounded-lg transition-all"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>
            <div className="p-6">
              <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">
                Feedback / Required Changes
              </label>
              <textarea
                value={changeRequestFeedback}
                onChange={(e) => setChangeRequestFeedback(e.target.value)}
                placeholder="Describe the changes needed..."
                rows={4}
                className="w-full px-3 py-2.5 bg-card border border-border rounded-lg text-sm focus:ring-2 focus:ring-status-warning/20 focus:border-status-warning outline-none transition-all resize-none"
                autoFocus
              />
            </div>
            <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-border bg-muted">
              <button
                onClick={() => setShowRequestChangesModal(false)}
                className="px-4 py-2.5 text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-muted rounded-lg transition-all"
              >
                Cancel
              </button>
              <button
                onClick={handleRequestChanges}
                disabled={isRequestingChanges || !changeRequestFeedback.trim()}
                className="inline-flex items-center gap-2 px-5 py-2.5 bg-status-warning text-white text-sm font-semibold rounded-lg hover:bg-status-warning/90 disabled:opacity-50 transition-all"
              >
                {isRequestingChanges ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <ThumbsDown className="w-4 h-4" />
                )}
                Request Changes
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default BASTab;
