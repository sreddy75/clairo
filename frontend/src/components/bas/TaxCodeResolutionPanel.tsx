'use client';

import { AlertTriangle, CheckCircle2, Loader2 } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import { AIDisclaimer } from '@/components/ui/AIDisclaimer';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { useToast } from '@/hooks/use-toast';
import {
  type PeriodBankTransaction,
  type TaxCodeSuggestion,
  type TaxCodeSuggestionSummary,
  type WritebackJobDetailResponse,
  type WritebackJobResponse,
  type WritebackSkipReason,
  approveSuggestion,
  bulkApproveSuggestions,
  dismissSuggestion,
  generateTaxCodeSuggestions,
  getWritebackJob,
  listTaxCodeSuggestions,
  overrideSuggestion,
  recalculateBASWithSuggestions,
  refreshReconciliationStatus,
  retryWritebackJob,
  unparkSuggestion,
} from '@/lib/bas';
import { formatCurrency, formatDate } from '@/lib/formatters';

import { ClassificationRequestButton } from './ClassificationRequestButton';
import { SyncToXeroButton } from './SyncToXeroButton';
import { TaxCodeBulkActions } from './TaxCodeBulkActions';
import { TaxCodeSuggestionCard } from './TaxCodeSuggestionCard';
import { TransactionLineItemGroup } from './TransactionLineItemGroup';

const XERO_SKIP_LABELS: Record<WritebackSkipReason, string> = {
  voided: 'Voided',
  deleted: 'Deleted',
  period_locked: 'Period locked',
  reconciled: 'Reconciled',
  authorised_locked: 'Has payment',
  credit_note_applied: 'Credit applied',
  invalid_tax_type: 'Invalid code',
  conflict_changed: 'Modified in Xero since last sync',
};

interface TaxCodeResolutionPanelProps {
  connectionId: string;
  sessionId: string;
  getToken: () => Promise<string | null>;
  onSummaryChange?: (summary: TaxCodeSuggestionSummary) => void;
  onRecalculated?: () => void;
  /** Called after any action that creates/modifies overrides — parent should refresh the session to get fresh approved_unsynced_count. */
  onSessionUpdated?: () => void;
  completedWritebackJob?: WritebackJobDetailResponse | null;
  activeWritebackJobId?: string | null;
  approvedUnsyncedCount?: number;
  onJobCreated?: (job: WritebackJobResponse) => void;
  onJobComplete?: (job: WritebackJobDetailResponse) => void;
}

export function TaxCodeResolutionPanel({
  connectionId,
  sessionId,
  getToken,
  onSummaryChange,
  onRecalculated,
  onSessionUpdated,
  completedWritebackJob,
  activeWritebackJobId,
  approvedUnsyncedCount = 0,
  onJobCreated,
  onJobComplete,
}: TaxCodeResolutionPanelProps) {
  const [suggestions, setSuggestions] = useState<TaxCodeSuggestion[]>([]);
  const [periodTxns, setPeriodTxns] = useState<PeriodBankTransaction[]>([]);
  const [summary, setSummary] = useState<TaxCodeSuggestionSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [classificationStatus, setClassificationStatus] = useState<{
    id: string;
    status: string;
    classified_count: number;
    transaction_count: number;
  } | null>(null);
  const [showReview, setShowReview] = useState(false);
  // suggestion_id → "Client Said" display text (populated when a classification request exists)
  const [classifMap, setClassifMap] = useState<Map<string, string | null>>(new Map());
  // Controlled accordion — always start with all sections open
  const [openSections, setOpenSections] = useState<string[]>(['high', 'review', 'manual', 'resolved']);

  // Auto-open resolved section when sync-relevant state changes
  useEffect(() => {
    if (approvedUnsyncedCount > 0 || activeWritebackJobId || completedWritebackJob) {
      setOpenSections((prev) => (prev.includes('resolved') ? prev : [...prev, 'resolved']));
    }
  }, [approvedUnsyncedCount, activeWritebackJobId, completedWritebackJob]);

  const [isRetrying, setIsRetrying] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const { toast } = useToast();

  // IDs of approved/overridden suggestions that were included in the last recalculation.
  // Banner shows when any approved suggestion is NOT in this set.
  const [recalculatedIds, setRecalculatedIds] = useState<Set<string>>(new Set());

  // Use refs for callbacks to avoid dependency loops
  const onSummaryChangeRef = useRef(onSummaryChange);
  onSummaryChangeRef.current = onSummaryChange;
  const onJobCompleteRef = useRef(onJobComplete);
  onJobCompleteRef.current = onJobComplete;

  // Spec 057: Track whether we've auto-enriched reconciliation status for this session.
  // Resets when sessionId changes so each new session gets enriched on first load.
  const reconciliationEnrichedRef = useRef(false);

  // Poll active writeback job until it finishes
  useEffect(() => {
    if (!activeWritebackJobId) return;
    let active = true;
    async function poll() {
      const token = await getToken();
      if (!token || !active) return;
      try {
        const data = await getWritebackJob(token, connectionId, sessionId, activeWritebackJobId!);
        if (!active) return;
        if (data.status !== 'in_progress' && data.status !== 'pending') {
          onJobCompleteRef.current?.(data);
        }
      } catch { /* transient — ignore */ }
    }
    poll();
    const interval = setInterval(poll, 2000);
    return () => { active = false; clearInterval(interval); };
  }, [activeWritebackJobId, connectionId, sessionId, getToken]);

  const loadSuggestions = useCallback(async () => {
    try {
      const token = await getToken();
      if (!token) return;
      let data = await listTaxCodeSuggestions(token, connectionId, sessionId);

      // Spec 057: Auto-enrich reconciliation status on first load for sessions created
      // before this feature (is_reconciled = NULL on existing bank_transaction suggestions).
      // Runs silently once per session mount; user sees correct grouping immediately.
      if (!reconciliationEnrichedRef.current) {
        const needsEnrichment = data.suggestions.some(
          (s) => s.source_type === 'bank_transaction' && s.is_reconciled === null,
        );
        if (needsEnrichment) {
          reconciliationEnrichedRef.current = true;
          try {
            await refreshReconciliationStatus(token, connectionId, sessionId);
            data = await listTaxCodeSuggestions(token, connectionId, sessionId);
          } catch {
            // Non-fatal: proceed with un-enriched data if Xero is unavailable
          }
        }
      }

      setSuggestions(data.suggestions);
      setPeriodTxns(data.period_bank_transactions ?? []);
      setSummary(data.summary);
      onSummaryChangeRef.current?.(data.summary);

      // Check for classification request and load merged data
      try {
        const statusRes = await fetch(
          `/api/v1/clients/${connectionId}/bas/sessions/${sessionId}/classification/request`,
          { headers: { Authorization: `Bearer ${token}` } }
        );
        if (statusRes.ok) {
          const statusData = await statusRes.json();
          setClassificationStatus(statusData);
          if (statusData.status === 'submitted' || statusData.status === 'reviewing') {
            setShowReview(true);
          }

          // Load full review data to build "Client Said" map for the merged table
          const reviewRes = await fetch(
            `/api/v1/clients/${connectionId}/bas/sessions/${sessionId}/classification/review`,
            { headers: { Authorization: `Bearer ${token}` } }
          );
          if (reviewRes.ok) {
            const reviewData = await reviewRes.json();
            const map = new Map<string, string | null>();
            for (const item of reviewData.classifications ?? []) {
              if (item.suggestion_id) {
                const categoryLabel: string | null =
                  item.client_category_label?.replace(/\s*\(please describe\)/i, '').trim() || null;
                const text: string | null = item.client_is_personal
                  ? 'Personal expense'
                  : item.client_needs_help
                    ? (item.client_description?.trim() || 'Needs help')
                    : (item.client_description?.trim() || categoryLabel);
                map.set(item.suggestion_id, text);
              }
            }
            setClassifMap(map);
          }
        }
      } catch {
        // Classification request may not exist — that's fine
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load suggestions');
    } finally {
      setIsLoading(false);
    }
  }, [connectionId, sessionId, getToken]);

  // Load once when session changes — not on every render
  const loadedSessionRef = useRef<string | null>(null);
  useEffect(() => {
    if (loadedSessionRef.current === sessionId) return;
    loadedSessionRef.current = sessionId;
    reconciliationEnrichedRef.current = false; // Reset so new session gets auto-enriched
    loadSuggestions();
  }, [sessionId, loadSuggestions]);

  // Auto-generate on first load if no suggestions exist
  useEffect(() => {
    if (!isLoading && suggestions.length === 0 && !isGenerating && !error) {
      handleGenerate();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isLoading]);

  async function handleGenerate() {
    setIsGenerating(true);
    try {
      const token = await getToken();
      if (!token) return;
      await generateTaxCodeSuggestions(token, connectionId, sessionId);
      await loadSuggestions();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate suggestions');
    } finally {
      setIsGenerating(false);
    }
  }

  async function handleApprove(id: string) {
    const token = await getToken();
    if (!token) return;
    await approveSuggestion(token, connectionId, sessionId, id);

    await loadSuggestions();
    onSessionUpdated?.();
  }

  async function handleOverride(id: string, taxType: string) {
    const token = await getToken();
    if (!token) return;
    await overrideSuggestion(token, connectionId, sessionId, id, taxType);

    await loadSuggestions();
    onSessionUpdated?.();
  }

  async function handleDismiss(id: string) {
    const token = await getToken();
    if (!token) return;
    await dismissSuggestion(token, connectionId, sessionId, id);
    await loadSuggestions();
  }

  async function handleUnpark(id: string) {
    const token = await getToken();
    if (!token) return;
    await unparkSuggestion(token, connectionId, sessionId, id);
    await loadSuggestions();
  }

  async function handleBulkApprove() {
    const token = await getToken();
    if (!token) return;
    await bulkApproveSuggestions(token, connectionId, sessionId, 0.9);

    await loadSuggestions();
    onSessionUpdated?.();
  }

  async function handleRetry() {
    if (!completedWritebackJob || !onJobCreated) return;
    setIsRetrying(true);
    try {
      const token = await getToken();
      if (!token) return;
      const newJob = await retryWritebackJob(token, connectionId, sessionId, completedWritebackJob.id);
      onJobCreated({ id: newJob.id } as WritebackJobResponse);
    } finally {
      setIsRetrying(false);
    }
  }

  async function handleRefreshReconciliation() {
    setIsRefreshing(true);
    try {
      const token = await getToken();
      if (!token) return;
      const result = await refreshReconciliationStatus(token, connectionId, sessionId);
      await loadSuggestions();
      toast({
        title: 'Reconciliation status updated',
        description:
          result.reclassified_count > 0
            ? `${result.reclassified_count} transaction${result.reclassified_count !== 1 ? 's' : ''} reclassified`
            : 'No changes',
      });
    } catch (err: unknown) {
      const status = (err as { status?: number })?.status;
      toast({
        title: status === 503 ? 'Unable to refresh — Xero connection unavailable' : 'Failed to refresh reconciliation status',
        variant: 'destructive',
      });
    } finally {
      setIsRefreshing(false);
    }
  }

  function handleSplitsChanged() {
    // Splits affect BAS amounts — clear the recalculated snapshot so the banner reappears.
    setRecalculatedIds(new Set());
  }

  async function handleRecalculate() {
    const token = await getToken();
    if (!token) return;
    await recalculateBASWithSuggestions(token, connectionId, sessionId);
    // Snapshot which suggestion IDs were applied so the banner clears correctly.
    setRecalculatedIds(new Set(
      suggestions
        .filter((s) => s.status === 'approved' || s.status === 'overridden')
        .map((s) => s.id),
    ));
    await loadSuggestions();
    onRecalculated?.();
    onSessionUpdated?.();
  }

  if (isLoading || isGenerating) {
    return (
      <div className="flex items-center justify-center py-8 gap-2 text-muted-foreground">
        <Loader2 className="w-4 h-4 animate-spin" />
        <span className="text-sm">{isGenerating ? 'Analyzing transactions...' : 'Loading...'}</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center gap-2 p-4 text-status-urgent text-sm">
        <AlertTriangle className="w-4 h-4" />
        {error}
      </div>
    );
  }

  // No suggestions AND no period bank transactions — nothing to show
  if ((!summary || suggestions.length === 0) && periodTxns.length === 0) {
    return (
      <div className="flex items-center gap-2 p-4 text-status-success text-sm">
        <CheckCircle2 className="w-4 h-4" />
        All transactions have valid tax codes.
      </div>
    );
  }

  // Group suggestions by status
  const pending = suggestions.filter((s) => s.status === 'pending');
  const highConfidence = pending.filter((s) => (s.confidence_score ?? 0) >= 0.9);
  const needsReview = pending.filter(
    (s) => (s.confidence_score ?? 0) >= 0.7 && (s.confidence_score ?? 0) < 0.9
  );
  const manual = pending.filter(
    (s) => s.confidence_score === null || (s.confidence_score ?? 0) < 0.7
  );
  const parked = suggestions.filter((s) => s.status === 'dismissed' || s.status === 'rejected');
  const resolved = suggestions.filter((s) => s.status === 'approved' || s.status === 'overridden');

  // Spec 057: Period-level reconciliation grouping — ALL bank transactions, not just flagged ones.
  const reconciledTxns = periodTxns.filter((t) => t.is_reconciled);
  const unreconciledTxns = periodTxns.filter((t) => !t.is_reconciled);

  // Banner shows when any approved/overridden suggestion hasn't been included in a recalculation yet.
  const hasApprovedNotApplied = suggestions.some(
    (s) => (s.status === 'approved' || s.status === 'overridden') && !recalculatedIds.has(s.id),
  );

  // Build lookup: local_document_id → writeback item (for sync status badges)
  const syncMap = new Map<string, { status: string; skip_reason: string | null; error_detail: string | null }>();
  if (completedWritebackJob) {
    for (const item of completedWritebackJob.items) {
      syncMap.set(item.local_document_id, { status: item.status, skip_reason: item.skip_reason, error_detail: item.error_detail ?? null });
    }
  }

  function xeroSyncBadgeFor(suggestion: TaxCodeSuggestion) {
    if (activeWritebackJobId && (suggestion.status === 'approved' || suggestion.status === 'overridden')) {
      return (
        <Badge className="text-[10px] px-1.5 py-0 bg-amber-100 text-amber-700 border-amber-200 flex items-center gap-1">
          <Loader2 className="w-2.5 h-2.5 animate-spin" />
          Syncing…
        </Badge>
      );
    }
    const sync = syncMap.get(suggestion.source_id);
    if (!sync) return null;
    if (sync.status === 'success') {
      return (
        <Badge className="text-[10px] px-1.5 py-0 bg-emerald-100 text-emerald-700 border-emerald-200">
          Xero ✓
        </Badge>
      );
    }
    if (sync.status === 'skipped') {
      const label = sync.skip_reason ? (XERO_SKIP_LABELS[sync.skip_reason as WritebackSkipReason] ?? sync.skip_reason) : 'Skipped';
      return (
        <Badge className="text-[10px] px-1.5 py-0 bg-amber-100 text-amber-700 border-amber-200" title={label}>
          ⚠ {label}
        </Badge>
      );
    }
    if (sync.status === 'failed') {
      const errorMsg = sync.error_detail
        ? sync.error_detail.replace(/^A validation exception occurred:\s*/i, '')
        : 'Xero sync failed';
      return (
        <TooltipProvider delayDuration={0}>
          <Tooltip>
            <TooltipTrigger asChild>
              <div className="flex flex-col items-start gap-0.5 cursor-default">
                <Badge className="text-[10px] px-1.5 py-0 bg-red-100 text-red-700 border-red-200">
                  Xero ✗
                </Badge>
                <span className="text-[9px] text-red-600 leading-tight max-w-[11rem] truncate">{errorMsg}</span>
              </div>
            </TooltipTrigger>
            <TooltipContent side="left" className="max-w-xs text-xs">
              {errorMsg}
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      );
    }
    return null;
  }

  return (
    <div className="space-y-3">
      <AIDisclaimer />
      {/* Request client classification (Spec 047) */}
      {/* Client classification: request button or review panel */}
      {pending.length > 0 && (
        <div className="flex items-center justify-between">
          <ClassificationRequestButton
            connectionId={connectionId}
            sessionId={sessionId}
            clientEmail={null}
            unresolvedCount={pending.length}
            getToken={getToken}
            existingRequest={classificationStatus}
          />
          {classificationStatus &&
            (classificationStatus.status === 'submitted' || classificationStatus.status === 'reviewing') &&
            !showReview && (
              <Button
                size="sm"
                variant="default"
                onClick={() => setShowReview(true)}
              >
                Review Client Classifications ({classificationStatus.classified_count}/{classificationStatus.transaction_count})
              </Button>
            )}
        </div>
      )}

      {/* Client classification summary — compact info line (full detail merged into table below) */}
      {showReview && classificationStatus && (
        <div className="flex items-center gap-2 text-xs text-muted-foreground px-1">
          <CheckCircle2 className="w-3.5 h-3.5 text-status-success shrink-0" />
          <span>
            <strong className="text-foreground">{classificationStatus.classified_count}</strong> classified by client
            {' · '}
            <strong className="text-foreground">{classificationStatus.classified_count}</strong> reviewed — client notes shown in table below
          </span>
        </div>
      )}

      {/* Bulk actions bar */}
      {pending.length > 0 && summary && (
        <TaxCodeBulkActions
          summary={summary}
          onBulkApprove={handleBulkApprove}
          onRecalculate={handleRecalculate}
          hasApprovedNotApplied={hasApprovedNotApplied}
        />
      )}

      {/* Recalculate prompt when all resolved */}
      {pending.length === 0 && hasApprovedNotApplied && summary && (
        <TaxCodeBulkActions
          summary={summary}
          onBulkApprove={handleBulkApprove}
          onRecalculate={handleRecalculate}
          hasApprovedNotApplied={hasApprovedNotApplied}
        />
      )}

      {/* Spec 057: Reconciliation status summary + refresh button */}
      {periodTxns.length > 0 && (
        <div className="flex items-center justify-between text-xs text-muted-foreground px-1">
          <span>
            {reconciledTxns.length} reconciled · {unreconciledTxns.length} unreconciled of {periodTxns.length} bank transactions
          </span>
          <Button
            size="sm"
            variant="outline"
            className="text-xs h-7"
            disabled={isRefreshing}
            onClick={handleRefreshReconciliation}
          >
            {isRefreshing ? <Loader2 className="w-3 h-3 animate-spin mr-1" /> : null}
            Refresh reconciliation status
          </Button>
        </div>
      )}

      <div className="max-h-[600px] overflow-y-auto">
        <Accordion type="multiple" value={openSections} onValueChange={setOpenSections}>
          {highConfidence.length > 0 && (
            <AccordionItem value="high">
              <AccordionTrigger className="text-sm font-medium py-2">
                High Confidence ({highConfidence.length})
              </AccordionTrigger>
              <AccordionContent>
                <SuggestionTable suggestions={highConfidence} classifMap={classifMap} onApprove={handleApprove} onOverride={handleOverride} onDismiss={handleDismiss} getToken={getToken} connectionId={connectionId} sessionId={sessionId} completedWritebackJobId={completedWritebackJob?.id} syncMap={syncMap} onSplitsChanged={handleSplitsChanged} onNoteChanged={loadSuggestions} />
              </AccordionContent>
            </AccordionItem>
          )}

          {needsReview.length > 0 && (
            <AccordionItem value="review">
              <AccordionTrigger className="text-sm font-medium py-2">
                Needs Review ({needsReview.length})
              </AccordionTrigger>
              <AccordionContent>
                <SuggestionTable suggestions={needsReview} classifMap={classifMap} onApprove={handleApprove} onOverride={handleOverride} onDismiss={handleDismiss} getToken={getToken} connectionId={connectionId} sessionId={sessionId} completedWritebackJobId={completedWritebackJob?.id} syncMap={syncMap} onSplitsChanged={handleSplitsChanged} onNoteChanged={loadSuggestions} />
              </AccordionContent>
            </AccordionItem>
          )}

          {manual.length > 0 && (
            <AccordionItem value="manual">
              <AccordionTrigger className="text-sm font-medium py-2">
                Manual Required ({manual.length})
              </AccordionTrigger>
              <AccordionContent>
                <SuggestionTable suggestions={manual} classifMap={classifMap} onApprove={handleApprove} onOverride={handleOverride} onDismiss={handleDismiss} getToken={getToken} connectionId={connectionId} sessionId={sessionId} completedWritebackJobId={completedWritebackJob?.id} syncMap={syncMap} onSplitsChanged={handleSplitsChanged} onNoteChanged={loadSuggestions} />
              </AccordionContent>
            </AccordionItem>
          )}

          {parked.length > 0 && (
            <AccordionItem value="parked">
              <AccordionTrigger className="text-sm font-medium py-2 text-amber-700">
                Parked ({parked.length})
              </AccordionTrigger>
              <AccordionContent>
                <SuggestionTable suggestions={parked} classifMap={classifMap} onApprove={handleApprove} onOverride={handleOverride} onDismiss={handleDismiss} onUnpark={handleUnpark} getToken={getToken} connectionId={connectionId} sessionId={sessionId} completedWritebackJobId={completedWritebackJob?.id} syncMap={syncMap} onSplitsChanged={handleSplitsChanged} onNoteChanged={loadSuggestions} />
              </AccordionContent>
            </AccordionItem>
          )}

          {(resolved.length > 0 || activeWritebackJobId || completedWritebackJob || approvedUnsyncedCount > 0) && (
            <AccordionItem value="resolved">
              <AccordionTrigger className="text-sm font-medium py-2 text-muted-foreground">
                Resolved ({resolved.length})
              </AccordionTrigger>
              <AccordionContent>
                <div className="space-y-2">
                  {/* Sync button — shown when there are approved overrides ready to write back */}
                  {!activeWritebackJobId && approvedUnsyncedCount > 0 && onJobCreated && (
                    <div className="flex items-center justify-between py-1 px-1">
                      <span className="text-xs text-muted-foreground">
                        {approvedUnsyncedCount} override{approvedUnsyncedCount !== 1 ? 's' : ''} ready to sync to Xero
                      </span>
                      <SyncToXeroButton
                        connectionId={connectionId}
                        sessionId={sessionId}
                        approvedUnsyncedCount={approvedUnsyncedCount}
                        isJobInProgress={false}
                        getToken={getToken}
                        onJobCreated={onJobCreated}
                      />
                    </div>
                  )}
                  {resolved.length > 0 && (
                    <SuggestionTable suggestions={resolved} classifMap={classifMap} xeroSyncBadgeFor={xeroSyncBadgeFor} onApprove={handleApprove} onOverride={handleOverride} onDismiss={handleDismiss} getToken={getToken} connectionId={connectionId} sessionId={sessionId} completedWritebackJobId={completedWritebackJob?.id} syncMap={syncMap} onSplitsChanged={handleSplitsChanged} onNoteChanged={loadSuggestions} />
                  )}
                  {/* Compact retry row below table — only shown when previous sync had failures */}
                  {completedWritebackJob && !activeWritebackJobId && completedWritebackJob.failed_count > 0 && (
                    <div className="flex items-center gap-3 text-xs px-1 text-muted-foreground">
                      <span className="text-red-600">{completedWritebackJob.failed_count} failed to sync</span>
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-6 text-xs"
                        disabled={isRetrying}
                        onClick={handleRetry}
                      >
                        {isRetrying ? <Loader2 className="w-3 h-3 animate-spin mr-1" /> : null}
                        Retry failed
                      </Button>
                    </div>
                  )}
                </div>
              </AccordionContent>
            </AccordionItem>
          )}
          {/* Spec 057: Reconciled section — ALL reconciled bank transactions, info only */}
          {reconciledTxns.length > 0 && (
            <AccordionItem value="reconciled">
              <AccordionTrigger className="text-sm font-medium py-2 text-muted-foreground">
                Reconciled in Xero ({reconciledTxns.length})
              </AccordionTrigger>
              <AccordionContent>
                <BankTransactionTable transactions={reconciledTxns} />
              </AccordionContent>
            </AccordionItem>
          )}
        </Accordion>
      </div>

      {/* All resolved message */}
      {pending.length === 0 && !hasApprovedNotApplied && unreconciledTxns.length === 0 && (
        <div className="flex items-center gap-2 p-3 bg-status-success/10 text-status-success text-sm rounded-lg border border-status-success/20">
          <CheckCircle2 className="w-4 h-4" />
          All excluded transactions resolved. BAS is ready for approval.
        </div>
      )}

      {/* Unreconciled transactions warning */}
      {pending.length === 0 && !hasApprovedNotApplied && unreconciledTxns.length > 0 && (
        <div className="flex items-center gap-2 p-3 bg-status-warning/10 text-status-warning text-sm rounded-lg border border-status-warning/20">
          <CheckCircle2 className="w-4 h-4" />
          All suggestions resolved, but {unreconciledTxns.length} bank transaction{unreconciledTxns.length !== 1 ? 's are' : ' is'} still unreconciled in Xero. Reconcile before approving BAS.
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Internal helper — unified suggestion table with optional Client Said column
// ---------------------------------------------------------------------------

interface SuggestionTableProps {
  suggestions: TaxCodeSuggestion[];
  classifMap: Map<string, string | null>;
  xeroSyncBadgeFor?: (s: TaxCodeSuggestion) => React.ReactNode;
  onApprove: (id: string) => Promise<void>;
  onOverride: (id: string, taxType: string) => Promise<void>;
  onDismiss: (id: string) => Promise<void>;
  onUnpark?: (id: string) => Promise<void>;
  getToken?: () => Promise<string | null>;
  connectionId?: string;
  sessionId?: string;
  completedWritebackJobId?: string | null;
  syncMap?: Map<string, { status: string; skip_reason: string | null; error_detail: string | null }>;
  onSplitsChanged?: () => void;
  onNoteChanged?: () => void;
}

function SuggestionTable({
  suggestions,
  classifMap,
  xeroSyncBadgeFor,
  onApprove,
  onOverride,
  onDismiss,
  onUnpark,
  getToken,
  connectionId,
  sessionId,
  completedWritebackJobId,
  syncMap,
  onSplitsChanged,
  onNoteChanged,
}: SuggestionTableProps) {
  const hasClientSaid = classifMap.size > 0;
  const colCount = hasClientSaid ? 7 : 6;

  // Group suggestions by source_id to support multi-line-item bank transactions
  const grouped = new Map<string, TaxCodeSuggestion[]>();
  for (const s of suggestions) {
    const existing = grouped.get(s.source_id);
    if (existing) {
      existing.push(s);
    } else {
      grouped.set(s.source_id, [s]);
    }
  }

  return (
    <div className="border border-border rounded-lg overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-muted/50 text-xs text-muted-foreground uppercase tracking-wider">
            <th className="px-3 py-1.5 text-left font-medium">Date</th>
            <th className="px-3 py-1.5 text-right font-medium">Amount</th>
            <th className="px-3 py-1.5 text-left font-medium">Description</th>
            {hasClientSaid && <th className="px-3 py-1.5 text-left font-medium">Client Said</th>}
            <th className="px-3 py-1.5 text-left font-medium">Tax Code</th>
            <th className="px-3 py-1.5 text-right font-medium">Status</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {Array.from(grouped.values()).map((group) => {
            if (group.length === 0) return null;
            const first = group[0]!;
            const isBankTxn = first.source_type === 'bank_transaction';
            const isMultiLine = group.length > 1;

            // Use TransactionLineItemGroup for bank transactions or multi-line groups
            if ((isBankTxn || isMultiLine) && getToken && connectionId && sessionId) {
              const syncEntry = syncMap?.get(first.source_id);
              return (
                <TransactionLineItemGroup
                  key={first.source_id}
                  suggestions={group}
                  connectionId={connectionId}
                  sessionId={sessionId}
                  getToken={getToken}
                  onApprove={onApprove}

                  onOverride={onOverride}
                  onDismiss={onDismiss}
                  showClientSaidCol={hasClientSaid}
                  clientSaidMap={classifMap}
                  xeroSyncBadgeFor={xeroSyncBadgeFor}
                  colCount={colCount}
                  completedWritebackJobId={completedWritebackJobId}
                  syncSkipReason={syncEntry?.skip_reason ?? null}
                  onSplitsChanged={onSplitsChanged}
                  onNoteChanged={onNoteChanged}
                  onUnpark={onUnpark}
                />
              );
            }

            // Single non-bank suggestion — render directly
            return (
              <TaxCodeSuggestionCard
                key={first.id}
                suggestion={first}
                onApprove={onApprove}
                onOverride={onOverride}
                onDismiss={onDismiss}
                onUnpark={onUnpark}
                showClientSaidCol={hasClientSaid}
                clientSaid={classifMap.get(first.id) ?? null}
                xeroSyncBadge={xeroSyncBadgeFor?.(first)}
                getToken={getToken}
                connectionId={connectionId}
                sessionId={sessionId}
                onNoteChanged={onNoteChanged}
              />
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Spec 057: Read-only bank transaction table for period-level reconciliation view
// ---------------------------------------------------------------------------

function BankTransactionTable({ transactions }: { transactions: PeriodBankTransaction[] }) {
  return (
    <div className="border border-border rounded-lg overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-muted/50 text-xs text-muted-foreground uppercase tracking-wider">
            <th className="px-3 py-1.5 text-left font-medium">Date</th>
            <th className="px-3 py-1.5 text-right font-medium">Amount</th>
            <th className="px-3 py-1.5 text-left font-medium">Description</th>
            <th className="px-3 py-1.5 text-left font-medium">Tax Code</th>
            <th className="px-3 py-1.5 text-right font-medium">Status</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {transactions.map((txn) => (
            <tr key={txn.id} className="opacity-60">
              <td className="px-3 py-1.5 text-xs text-muted-foreground whitespace-nowrap tabular-nums">
                {txn.transaction_date ? formatDate(txn.transaction_date) : '—'}
              </td>
              <td className="px-3 py-1.5 text-right font-medium tabular-nums whitespace-nowrap text-sm">
                {formatCurrency(txn.total_amount)}
              </td>
              <td className="px-3 py-1.5 max-w-[220px]">
                <span className="truncate block text-xs">{txn.description || '—'}</span>
                {txn.contact_name && (
                  <span className="truncate block text-[10px] text-muted-foreground">{txn.contact_name}</span>
                )}
              </td>
              <td className="px-3 py-1.5 whitespace-nowrap text-xs text-muted-foreground">
                {txn.tax_types.length > 0 ? txn.tax_types.join(', ') : '—'}
              </td>
              <td className="px-3 py-1.5 text-right whitespace-nowrap">
                <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
                  {txn.is_reconciled ? 'Reconciled' : 'Unreconciled'}
                </Badge>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
