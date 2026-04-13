'use client';

import { ArrowRight, Ban, Check, ChevronDown, Sparkles } from 'lucide-react';
import { useState } from 'react';

import { SuggestionNoteEditor } from '@/components/bas/SuggestionNoteEditor';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import type { TaxCodeSuggestion } from '@/lib/bas';
import { VALID_TAX_TYPES, fetchOrgTaxTypes } from '@/lib/bas';
import { formatCurrency, formatDate } from '@/lib/formatters';
import { cn } from '@/lib/utils';

interface TaxCodeSuggestionCardProps {
  suggestion: TaxCodeSuggestion;
  onApprove: (id: string) => Promise<void>;
  onOverride: (id: string, taxType: string) => Promise<void>;
  onDismiss: (id: string) => Promise<void>;
  onUnpark?: (id: string) => Promise<void>;
  disabled?: boolean;
  /** Optional badge rendered after the status pill (used to show Xero sync state in Resolved rows). */
  xeroSyncBadge?: React.ReactNode;
  /** When true, renders a "Client Said" cell (4th column). Pass clientSaid text or null for empty cell. */
  showClientSaidCol?: boolean;
  clientSaid?: string | null;
  /** Token + connectionId used to fetch org-specific valid tax types for the override dropdown. */
  getToken?: () => Promise<string | null>;
  connectionId?: string;
  sessionId?: string;
  onNoteChanged?: () => void;
}

/**
 * Compact table row for a tax code suggestion.
 * Renders as a <tr> — must be inside a <tbody>.
 */
export function TaxCodeSuggestionCard({
  suggestion,
  onApprove,
  onOverride,
  onDismiss,
  onUnpark,
  disabled = false,
  xeroSyncBadge,
  showClientSaidCol = false,
  clientSaid,
  getToken,
  connectionId,
  sessionId,
  onNoteChanged,
}: TaxCodeSuggestionCardProps) {
  const [showOverride, setShowOverride] = useState(false);
  const [overrideType, setOverrideType] = useState<string>('');
  const [isLoading, setIsLoading] = useState<string | null>(null);
  const [orgTaxTypes, setOrgTaxTypes] = useState<{ value: string; label: string }[] | null>(null);
  const [isLoadingTaxTypes, setIsLoadingTaxTypes] = useState(false);

  const isPending = suggestion.status === 'pending';
  const isParked = suggestion.status === 'dismissed' || suggestion.status === 'rejected';
  const isResolved = !isPending && !isParked;
  const canReOverride = suggestion.status === 'approved' || suggestion.status === 'overridden';

  async function handleAction(action: string, fn: () => Promise<void>) {
    setIsLoading(action);
    try {
      await fn();
    } finally {
      setIsLoading(null);
    }
  }

  async function openOverride() {
    setShowOverride((prev) => !prev);
    if (orgTaxTypes !== null || isLoadingTaxTypes) return;
    if (!getToken || !connectionId) return;
    setIsLoadingTaxTypes(true);
    try {
      const token = await getToken();
      if (!token) return;
      const fetched = await fetchOrgTaxTypes(token, connectionId);
      if (fetched.length > 0) {
        // Map fetched org types to labels from VALID_TAX_TYPES where available
        const labelMap = new Map<string, string>(VALID_TAX_TYPES.map((t) => [t.value, t.label]));
        setOrgTaxTypes(
          fetched.map((t) => ({ value: t.tax_type, label: labelMap.get(t.tax_type) ?? t.name }))
        );
      }
      // If fetched is empty, leave orgTaxTypes null so we fall back to VALID_TAX_TYPES
    } finally {
      setIsLoadingTaxTypes(false);
    }
  }

  return (
    <>
      <tr
        className={cn(
          'hover:bg-muted/30 transition-colors',
          isResolved && 'opacity-60',
          suggestion.status === 'approved' && 'bg-emerald-50/50',
          (suggestion.status === 'rejected' || suggestion.status === 'dismissed') && 'bg-amber-50/30',
        )}
      >
        {/* Date */}
        <td className="px-3 py-1.5 text-xs text-muted-foreground whitespace-nowrap tabular-nums">
          {suggestion.transaction_date ? formatDate(suggestion.transaction_date) : '—'}
        </td>

        {/* Amount */}
        <td className="px-3 py-1.5 text-right font-medium tabular-nums whitespace-nowrap text-sm">
          {suggestion.line_amount !== null ? formatCurrency(suggestion.line_amount) : '—'}
        </td>

        {/* Description */}
        <td className="px-3 py-1.5 max-w-[220px]">
          <span className="truncate block text-xs">{suggestion.description || '—'}</span>
          {suggestion.contact_name && (
            <span className="truncate block text-[10px] text-muted-foreground">{suggestion.contact_name}</span>
          )}
        </td>

        {/* Client Said (optional column) */}
        {showClientSaidCol && (
          <td className="px-3 py-1.5 max-w-[140px]">
            {clientSaid ? (
              <span className="truncate block text-xs text-primary font-medium">{clientSaid}</span>
            ) : (
              <span className="text-xs text-muted-foreground">—</span>
            )}
          </td>
        )}

        {/* Current → Suggested */}
        <td className="px-3 py-1.5 whitespace-nowrap">
          {isPending && suggestion.suggested_tax_type ? (
            <div className="flex items-center gap-1 text-xs">
              <span className="text-muted-foreground">{suggestion.original_tax_type}</span>
              <ArrowRight className="w-3 h-3 text-muted-foreground" />
              <span className="font-semibold">{suggestion.suggested_tax_type}</span>
              {suggestion.confidence_score !== null && suggestion.confidence_score >= 0.9 && (
                <span className="text-emerald-600 text-[10px]">{Math.round(suggestion.confidence_score * 100)}%</span>
              )}
              {suggestion.confidence_score !== null && suggestion.confidence_score >= 0.7 && suggestion.confidence_score < 0.9 && (
                <span className="text-amber-600 text-[10px]">{Math.round(suggestion.confidence_score * 100)}%</span>
              )}
              {suggestion.confidence_score !== null && suggestion.confidence_score < 0.7 && (
                <span className="text-red-600 text-[10px]">{Math.round(suggestion.confidence_score * 100)}%</span>
              )}
              {suggestion.confidence_tier === 'llm_classification' && (
                <Sparkles className="w-3 h-3 text-primary" />
              )}
            </div>
          ) : suggestion.status === 'approved' ? (
            <span className="text-xs text-emerald-600 flex items-center gap-1 flex-wrap">
              <span className="flex items-center gap-1"><Check className="w-3 h-3" />{suggestion.applied_tax_type}</span>
              {suggestion.source_type === 'bank_transaction' && suggestion.is_reconciled === false && (
                <span className="px-1 py-0.5 text-[10px] font-medium rounded border border-amber-300 text-amber-600 leading-none">
                  Unreconciled in Xero
                </span>
              )}
              {suggestion.source_type === 'bank_transaction' && suggestion.is_reconciled === true && (
                <span className="px-1 py-0.5 text-[10px] font-medium rounded border border-emerald-300 text-emerald-600 leading-none">
                  Reconciled in Xero
                </span>
              )}
            </span>
          ) : suggestion.status === 'overridden' ? (
            <span className="text-xs text-primary flex items-center gap-1">{suggestion.applied_tax_type && <ArrowRight className="w-3 h-3" />}{suggestion.applied_tax_type}</span>
          ) : (suggestion.status === 'rejected' || suggestion.status === 'dismissed') ? (
            <span className="text-xs text-amber-600 flex items-center gap-1">
              <Ban className="w-3 h-3" />Parked
              {(suggestion.auto_park_reason === 'unreconciled_in_xero' || suggestion.is_reconciled === false) && (
                <span className="ml-1 px-1 py-0.5 text-[10px] font-medium rounded border border-amber-300 text-amber-600 leading-none">
                  Unreconciled in Xero
                </span>
              )}
            </span>
          ) : (
            <span className="text-xs text-muted-foreground">—</span>
          )}
        </td>

        {/* Note */}
        <td className="px-1 py-1.5 w-8">
          {getToken && connectionId && sessionId && onNoteChanged && (
            <SuggestionNoteEditor
              suggestion={suggestion}
              getToken={getToken}
              connectionId={connectionId}
              sessionId={sessionId}
              onNoteChanged={onNoteChanged}
            />
          )}
        </td>

        {/* Actions */}
        <td className="px-3 py-1.5 text-right whitespace-nowrap">
          {isPending && (
            <div className="flex items-center justify-end gap-1">
              {suggestion.suggested_tax_type && (
                <Button
                  size="sm"
                  variant="outline"
                  className="text-[10px] h-6 px-2 text-emerald-700 border-emerald-300 hover:bg-emerald-50"
                  disabled={disabled || isLoading !== null}
                  onClick={() => handleAction('approve', () => onApprove(suggestion.id))}
                >
                  {isLoading === 'approve' ? '...' : 'Approve'}
                </Button>
              )}
              <Button
                size="sm"
                variant="outline"
                className="text-[10px] h-6 px-2"
                disabled={disabled || isLoading !== null}
                onClick={openOverride}
              >
                Override <ChevronDown className="w-2.5 h-2.5 ml-0.5" />
              </Button>
              <Button
                size="sm"
                variant="ghost"
                className="text-[10px] h-6 px-1.5 text-muted-foreground"
                disabled={disabled || isLoading !== null}
                onClick={() => handleAction('dismiss', () => onDismiss(suggestion.id))}
              >
                {isLoading === 'dismiss' ? '...' : 'Park it'}
              </Button>
            </div>
          )}
          {isParked && (
            <div className="flex items-center justify-end gap-1">
              {suggestion.suggested_tax_type && (
                <Button
                  size="sm"
                  variant="outline"
                  className="text-[10px] h-6 px-2 text-emerald-700 border-emerald-300 hover:bg-emerald-50"
                  disabled={disabled || isLoading !== null}
                  onClick={() => handleAction('approve', () => onApprove(suggestion.id))}
                >
                  {isLoading === 'approve' ? '...' : 'Approve'}
                </Button>
              )}
              {onUnpark && (
                <Button
                  size="sm"
                  variant="ghost"
                  className="text-[10px] h-6 px-1.5 text-muted-foreground"
                  disabled={disabled || isLoading !== null}
                  onClick={() => handleAction('unpark', () => onUnpark(suggestion.id))}
                >
                  {isLoading === 'unpark' ? '...' : 'Back to Manual'}
                </Button>
              )}
            </div>
          )}
          {isResolved && (
            <div className="flex items-center justify-end gap-1 flex-wrap">
              <Badge
                variant="secondary"
                className={cn(
                  'text-[10px] px-1.5 py-0',
                  suggestion.status === 'approved' && 'bg-emerald-100 text-emerald-700',
                )}
              >
                {suggestion.status}
              </Badge>
              {xeroSyncBadge}
              {canReOverride && (
                <Button
                  size="sm"
                  variant="ghost"
                  className="text-[10px] h-6 px-1.5 text-muted-foreground"
                  disabled={disabled || isLoading !== null}
                  onClick={openOverride}
                >
                  Override <ChevronDown className="w-2.5 h-2.5 ml-0.5" />
                </Button>
              )}
            </div>
          )}
        </td>
      </tr>

      {/* Override row (spans all columns) */}
      {showOverride && (isPending || canReOverride) && (
        <tr className="bg-muted/20">
          <td colSpan={showClientSaidCol ? 6 : 5} className="px-3 py-1.5">
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground">Override to:</span>
              <Select value={overrideType} onValueChange={setOverrideType}>
                <SelectTrigger className="h-6 text-xs w-48">
                  <SelectValue placeholder={isLoadingTaxTypes ? 'Loading...' : 'Select tax code...'} />
                </SelectTrigger>
                <SelectContent>
                  {(orgTaxTypes ?? VALID_TAX_TYPES).map((t) => (
                    <SelectItem key={t.value} value={t.value} className="text-xs">
                      {t.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button
                size="sm"
                disabled={!overrideType || disabled || isLoading !== null}
                onClick={() => handleAction('override', () => onOverride(suggestion.id, overrideType))}
                className="h-6 text-xs px-2"
              >
                {isLoading === 'override' ? '...' : 'Apply'}
              </Button>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
