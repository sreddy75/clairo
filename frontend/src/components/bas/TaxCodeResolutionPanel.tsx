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
import { Button } from '@/components/ui/button';
import type {
  TaxCodeSuggestion,
  TaxCodeSuggestionSummary,
} from '@/lib/bas';
import {
  approveSuggestion,
  bulkApproveSuggestions,
  dismissSuggestion,
  generateTaxCodeSuggestions,
  listTaxCodeSuggestions,
  overrideSuggestion,
  recalculateBASWithSuggestions,
  rejectSuggestion,
} from '@/lib/bas';

import { ClassificationRequestButton } from './ClassificationRequestButton';
import { ClassificationReview } from './ClassificationReview';
import { TaxCodeBulkActions } from './TaxCodeBulkActions';
import { TaxCodeSuggestionCard } from './TaxCodeSuggestionCard';

interface TaxCodeResolutionPanelProps {
  connectionId: string;
  sessionId: string;
  getToken: () => Promise<string | null>;
  onSummaryChange?: (summary: TaxCodeSuggestionSummary) => void;
  onRecalculated?: () => void;
}

export function TaxCodeResolutionPanel({
  connectionId,
  sessionId,
  getToken,
  onSummaryChange,
  onRecalculated,
}: TaxCodeResolutionPanelProps) {
  const [suggestions, setSuggestions] = useState<TaxCodeSuggestion[]>([]);
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

  // Use refs for callbacks to avoid dependency loops
  const onSummaryChangeRef = useRef(onSummaryChange);
  onSummaryChangeRef.current = onSummaryChange;

  const loadSuggestions = useCallback(async () => {
    try {
      const token = await getToken();
      if (!token) return;
      const data = await listTaxCodeSuggestions(token, connectionId, sessionId);
      setSuggestions(data.suggestions);
      setSummary(data.summary);
      onSummaryChangeRef.current?.(data.summary);

      // Check for pending classification request
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
  }

  async function handleReject(id: string) {
    const token = await getToken();
    if (!token) return;
    await rejectSuggestion(token, connectionId, sessionId, id);
    await loadSuggestions();
  }

  async function handleOverride(id: string, taxType: string) {
    const token = await getToken();
    if (!token) return;
    await overrideSuggestion(token, connectionId, sessionId, id, taxType);
    await loadSuggestions();
  }

  async function handleDismiss(id: string) {
    const token = await getToken();
    if (!token) return;
    await dismissSuggestion(token, connectionId, sessionId, id);
    await loadSuggestions();
  }

  async function handleBulkApprove() {
    const token = await getToken();
    if (!token) return;
    await bulkApproveSuggestions(token, connectionId, sessionId, 0.9);
    await loadSuggestions();
  }

  async function handleRecalculate() {
    const token = await getToken();
    if (!token) return;
    await recalculateBASWithSuggestions(token, connectionId, sessionId);
    await loadSuggestions();
    onRecalculated?.();
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

  if (!summary || suggestions.length === 0) {
    return (
      <div className="flex items-center gap-2 p-4 text-status-success text-sm">
        <CheckCircle2 className="w-4 h-4" />
        All transactions have valid tax codes.
      </div>
    );
  }

  // Group by status
  const pending = suggestions.filter((s) => s.status === 'pending');
  const highConfidence = pending.filter((s) => (s.confidence_score ?? 0) >= 0.9);
  const needsReview = pending.filter(
    (s) => (s.confidence_score ?? 0) >= 0.7 && (s.confidence_score ?? 0) < 0.9
  );
  const manual = pending.filter(
    (s) => s.confidence_score === null || (s.confidence_score ?? 0) < 0.7
  );
  const resolved = suggestions.filter((s) => s.status !== 'pending');

  // Check if there are approved items not yet applied (no recalculation done)
  const hasApprovedNotApplied =
    suggestions.some((s) => s.status === 'approved' || s.status === 'overridden');

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

      {/* Client classification review */}
      {showReview && (
        <ClassificationReview
          connectionId={connectionId}
          sessionId={sessionId}
          getToken={getToken}
          onComplete={() => {
            setShowReview(false);
            loadSuggestions();
          }}
        />
      )}

      {/* Bulk actions bar */}
      {pending.length > 0 && (
        <TaxCodeBulkActions
          summary={summary}
          onBulkApprove={handleBulkApprove}
          onRecalculate={handleRecalculate}
          hasApprovedNotApplied={hasApprovedNotApplied}
        />
      )}

      {/* Recalculate prompt when all resolved */}
      {pending.length === 0 && hasApprovedNotApplied && (
        <TaxCodeBulkActions
          summary={summary}
          onBulkApprove={handleBulkApprove}
          onRecalculate={handleRecalculate}
          hasApprovedNotApplied={hasApprovedNotApplied}
        />
      )}

      <div className="max-h-[600px] overflow-y-auto">
        <Accordion type="multiple" defaultValue={['high', 'review', 'manual']}>
          {highConfidence.length > 0 && (
            <AccordionItem value="high">
              <AccordionTrigger className="text-sm font-medium py-2">
                High Confidence ({highConfidence.length})
              </AccordionTrigger>
              <AccordionContent>
                <div className="border border-border rounded-lg overflow-hidden">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-muted/50 text-xs text-muted-foreground uppercase tracking-wider">
                        <th className="px-3 py-1.5 text-left font-medium">Date</th>
                        <th className="px-3 py-1.5 text-right font-medium">Amount</th>
                        <th className="px-3 py-1.5 text-left font-medium">Description</th>
                        <th className="px-3 py-1.5 text-left font-medium">Suggestion</th>
                        <th className="px-3 py-1.5 text-right font-medium">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {highConfidence.map((s) => (
                        <TaxCodeSuggestionCard key={s.id} suggestion={s} onApprove={handleApprove} onReject={handleReject} onOverride={handleOverride} onDismiss={handleDismiss} />
                      ))}
                    </tbody>
                  </table>
                </div>
              </AccordionContent>
            </AccordionItem>
          )}

          {needsReview.length > 0 && (
            <AccordionItem value="review">
              <AccordionTrigger className="text-sm font-medium py-2">
                Needs Review ({needsReview.length})
              </AccordionTrigger>
              <AccordionContent>
                <div className="border border-border rounded-lg overflow-hidden">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-muted/50 text-xs text-muted-foreground uppercase tracking-wider">
                        <th className="px-3 py-1.5 text-left font-medium">Date</th>
                        <th className="px-3 py-1.5 text-right font-medium">Amount</th>
                        <th className="px-3 py-1.5 text-left font-medium">Description</th>
                        <th className="px-3 py-1.5 text-left font-medium">Suggestion</th>
                        <th className="px-3 py-1.5 text-right font-medium">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {needsReview.map((s) => (
                        <TaxCodeSuggestionCard key={s.id} suggestion={s} onApprove={handleApprove} onReject={handleReject} onOverride={handleOverride} onDismiss={handleDismiss} />
                      ))}
                    </tbody>
                  </table>
                </div>
              </AccordionContent>
            </AccordionItem>
          )}

          {manual.length > 0 && (
            <AccordionItem value="manual">
              <AccordionTrigger className="text-sm font-medium py-2">
                Manual Required ({manual.length})
              </AccordionTrigger>
              <AccordionContent>
                <div className="border border-border rounded-lg overflow-hidden">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-muted/50 text-xs text-muted-foreground uppercase tracking-wider">
                        <th className="px-3 py-1.5 text-left font-medium">Date</th>
                        <th className="px-3 py-1.5 text-right font-medium">Amount</th>
                        <th className="px-3 py-1.5 text-left font-medium">Description</th>
                        <th className="px-3 py-1.5 text-left font-medium">Suggestion</th>
                        <th className="px-3 py-1.5 text-right font-medium">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {manual.map((s) => (
                        <TaxCodeSuggestionCard key={s.id} suggestion={s} onApprove={handleApprove} onReject={handleReject} onOverride={handleOverride} onDismiss={handleDismiss} />
                      ))}
                    </tbody>
                  </table>
                </div>
              </AccordionContent>
            </AccordionItem>
          )}

          {resolved.length > 0 && (
            <AccordionItem value="resolved">
              <AccordionTrigger className="text-sm font-medium py-2 text-muted-foreground">
                Resolved ({resolved.length})
              </AccordionTrigger>
              <AccordionContent>
                <div className="border border-border rounded-lg overflow-hidden">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-muted/50 text-xs text-muted-foreground uppercase tracking-wider">
                        <th className="px-3 py-1.5 text-left font-medium">Date</th>
                        <th className="px-3 py-1.5 text-right font-medium">Amount</th>
                        <th className="px-3 py-1.5 text-left font-medium">Description</th>
                        <th className="px-3 py-1.5 text-left font-medium">Result</th>
                        <th className="px-3 py-1.5 text-right font-medium">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {resolved.map((s) => (
                        <TaxCodeSuggestionCard key={s.id} suggestion={s} onApprove={handleApprove} onReject={handleReject} onOverride={handleOverride} onDismiss={handleDismiss} />
                      ))}
                    </tbody>
                  </table>
                </div>
              </AccordionContent>
            </AccordionItem>
          )}
        </Accordion>
      </div>

      {/* All resolved message */}
      {pending.length === 0 && !hasApprovedNotApplied && (
        <div className="flex items-center gap-2 p-3 bg-status-success/10 text-status-success text-sm rounded-lg border border-status-success/20">
          <CheckCircle2 className="w-4 h-4" />
          All excluded transactions resolved. BAS is ready for approval.
        </div>
      )}
    </div>
  );
}
