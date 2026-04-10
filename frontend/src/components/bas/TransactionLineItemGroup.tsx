'use client';

import { ChevronDown, ChevronRight, Layers } from 'lucide-react';
import { useEffect, useState } from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import type { TaxCodeOverrideWithSplit, TaxCodeSuggestion, XeroLineItemView } from '@/lib/bas';
import { listTransactionSplits } from '@/lib/bas';
import { formatCurrency } from '@/lib/formatters';
import { cn } from '@/lib/utils';

import { SplitBalanceIndicator } from './SplitBalanceIndicator';
import { SplitCreationForm } from './SplitCreationForm';
import { TaxCodeSuggestionCard } from './TaxCodeSuggestionCard';

interface TransactionLineItemGroupProps {
  /** All suggestions sharing the same source_id */
  suggestions: TaxCodeSuggestion[];
  connectionId: string;
  sessionId: string;
  getToken: () => Promise<string | null>;
  onApprove: (id: string) => Promise<void>;
  onOverride: (id: string, taxType: string) => Promise<void>;
  onDismiss: (id: string) => Promise<void>;
  disabled?: boolean;
  showClientSaidCol?: boolean;
  clientSaidMap?: Map<string, string | null>;
  xeroSyncBadgeFor?: (suggestion: TaxCodeSuggestion) => React.ReactNode;
  /** Total number of columns in the parent table (for colSpan) */
  colCount?: number;
  /** When this changes (non-null), reload split data to reflect post-sync amounts */
  completedWritebackJobId?: string | null;
  /** skip_reason from last sync, if any — used to auto-open splits on invalid_tax_type */
  syncSkipReason?: string | null;
  /** Called after any split is added, edited, or deleted — lets parent reset recalculation state */
  onSplitsChanged?: () => void;
  onNoteChanged?: () => void;
  onUnpark?: (id: string) => Promise<void>;
}

/**
 * Groups all line-item suggestions for a single bank transaction into one expandable
 * group. Shows a header row with the transaction summary, individual suggestion rows
 * beneath, and — for bank transactions — a Splits section for creating/editing split
 * overrides.
 *
 * Renders as a fragment of <tr> elements — must be inside a <tbody>.
 */
export function TransactionLineItemGroup({
  suggestions,
  connectionId,
  sessionId,
  getToken,
  onApprove,
  onOverride,
  onDismiss,
  disabled = false,
  showClientSaidCol = false,
  clientSaidMap,
  xeroSyncBadgeFor,
  colCount = 5,
  completedWritebackJobId,
  syncSkipReason,
  onSplitsChanged,
  onNoteChanged,
  onUnpark,
}: TransactionLineItemGroupProps) {
  const first = suggestions[0] ?? null;
  const isBankTransaction = first?.source_type === 'bank_transaction';
  const multiLine = suggestions.length > 1;

  const [expanded, setExpanded] = useState(true);
  const [showSplits, setShowSplits] = useState(false);
  const [originalLineItems, setOriginalLineItems] = useState<XeroLineItemView[]>([]);
  const [splits, setSplits] = useState<TaxCodeOverrideWithSplit[]>([]);
  const [splitsLoaded, setSplitsLoaded] = useState(false);

  // Aggregate display values
  const totalAmount = suggestions.reduce((acc, s) => acc + Number(s.line_amount ?? 0), 0);
  const contactName = first?.contact_name ?? null;
  const date = first?.transaction_date ?? null;

  // When split data is loaded, compute the effective total from live data:
  // non-deleted originals + active new splits. Falls back to suggestion total otherwise.
  const effectiveTotal = splitsLoaded
    ? originalLineItems
        .filter((li) => !splits.some(
          (s) => !s.is_new_split && s.line_item_index === li.index && s.is_deleted && s.is_active,
        ))
        .reduce((acc, li) => acc + Number(li.line_amount ?? 0), 0)
      + splits
          .filter((s) => s.is_new_split && s.is_active)
          .reduce((acc, s) => acc + Number(s.line_amount ?? 0), 0)
    : totalAmount;

  // Pending-split aggregate: any split with pending_sync status
  const hasPendingSplit = splits.some((s) => s.writeback_status === 'pending_sync' && s.is_active);

  async function loadSplits() {
    if (!isBankTransaction || !first) return;
    const token = await getToken();
    if (!token) return;
    const data = await listTransactionSplits(token, connectionId, sessionId, first.source_id);
    setOriginalLineItems(data.original_line_items);
    setSplits(data.overrides);
    setSplitsLoaded(true);
  }

  // Eagerly load split data for bank transactions so the header total is always accurate.
  useEffect(() => {
    if (isBankTransaction) {
      loadSplits();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (showSplits && !splitsLoaded) {
      loadSplits();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showSplits]);

  // Reload split data after a sync completes so displayed amounts match Xero
  useEffect(() => {
    if (isBankTransaction && completedWritebackJobId) {
      loadSplits();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [completedWritebackJobId]);

  // Auto-open splits panel when sync fails with invalid_tax_type so user can see which row is invalid
  useEffect(() => {
    if (isBankTransaction && syncSkipReason === 'invalid_tax_type') {
      setShowSplits(true);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [syncSkipReason]);

  async function handleSplitsChanged() {
    await loadSplits();
    onSplitsChanged?.();
  }

  if (!first || suggestions.length === 0) return null;

  // If only one suggestion and not bank transaction, render without group header
  if (!multiLine && !isBankTransaction) {
    return (
      <TaxCodeSuggestionCard
        suggestion={first}
        onApprove={onApprove}

        onOverride={onOverride}
        onDismiss={onDismiss}
        disabled={disabled}
        showClientSaidCol={showClientSaidCol}
        clientSaid={clientSaidMap?.get(first.id)}
        xeroSyncBadge={xeroSyncBadgeFor?.(first)}
        getToken={getToken}
        connectionId={connectionId}
        sessionId={sessionId}
        onNoteChanged={onNoteChanged}
        onUnpark={onUnpark}
      />
    );
  }

  return (
    <>
      {/* Group header row */}
      <tr className="bg-muted/20 hover:bg-muted/30 transition-colors border-b border-border/40">
        <td
          colSpan={showClientSaidCol ? colCount + 1 : colCount}
          className="px-2 py-1"
        >
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              className="h-5 w-5 p-0 text-muted-foreground"
              onClick={() => setExpanded((v) => !v)}
            >
              {expanded ? (
                <ChevronDown className="w-3.5 h-3.5" />
              ) : (
                <ChevronRight className="w-3.5 h-3.5" />
              )}
            </Button>

            {multiLine && <Layers className="w-3 h-3 text-muted-foreground" />}

            {date && (
              <span className="text-[10px] text-muted-foreground tabular-nums">
                {new Date(date).toLocaleDateString('en-AU', {
                  day: '2-digit',
                  month: 'short',
                })}
              </span>
            )}

            {contactName && (
              <span className="text-xs font-medium truncate max-w-[200px]">{contactName}</span>
            )}

            <span className="text-xs font-mono tabular-nums text-right ml-1">
              {formatCurrency(effectiveTotal, { fractionDigits: 2 })}
            </span>

            {multiLine && (
              <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
                {suggestions.length} lines
              </Badge>
            )}

            {hasPendingSplit && (
              <Badge className="text-[10px] px-1.5 py-0 bg-amber-100 text-amber-700 border-amber-200">
                Pending split
              </Badge>
            )}

            {isBankTransaction && (
              <Button
                variant="ghost"
                size="sm"
                className={cn(
                  'ml-auto h-5 text-[10px] px-2 gap-1',
                  showSplits ? 'text-primary' : 'text-muted-foreground',
                )}
                onClick={() => setShowSplits((v) => !v)}
                disabled={disabled}
              >
                <Layers className="w-3 h-3" />
                {showSplits ? 'Hide splits' : 'Splits'}
              </Button>
            )}
          </div>
        </td>
      </tr>

      {/* Line item suggestion rows */}
      {expanded &&
        suggestions.map((s) => {
          // If a non-deleted edit override exists for this line item, reflect its amount in the card.
          const editOverride = splitsLoaded
            ? splits.find(
                (o) =>
                  !o.is_new_split &&
                  !o.is_deleted &&
                  o.is_active &&
                  o.line_item_index === s.line_item_index &&
                  o.line_amount !== null,
              )
            : undefined;
          const displaySuggestion =
            editOverride
              ? { ...s, line_amount: Number(editOverride.line_amount) }
              : s;
          return (
            <TaxCodeSuggestionCard
              key={s.id}
              suggestion={displaySuggestion}
              onApprove={onApprove}
      
              onOverride={onOverride}
              onDismiss={onDismiss}
              disabled={disabled}
              showClientSaidCol={showClientSaidCol}
              clientSaid={clientSaidMap?.get(s.id)}
              xeroSyncBadge={xeroSyncBadgeFor?.(s)}
              getToken={getToken}
              connectionId={connectionId}
              sessionId={sessionId}
              onNoteChanged={onNoteChanged}
              onUnpark={onUnpark}
            />
          );
        })}

      {/* Splits panel (bank transactions only) */}
      {showSplits && isBankTransaction && (
        <tr>
          <td
            colSpan={showClientSaidCol ? colCount + 1 : colCount}
            className="px-2 py-2 bg-primary/5 border-b border-border/30"
          >
            <SplitBalanceIndicator
              splits={splits}
              originalLineItems={originalLineItems}
              transactionTotal={effectiveTotal}
              className="mb-2"
            />
            <SplitCreationForm
              connectionId={connectionId}
              sessionId={sessionId}
              sourceId={first.source_id}
              originalLineItems={originalLineItems}
              splits={splits}
              transactionTotal={effectiveTotal}
              getToken={getToken}
              onChanged={handleSplitsChanged}
              disabled={disabled}
            />
          </td>
        </tr>
      )}
    </>
  );
}
