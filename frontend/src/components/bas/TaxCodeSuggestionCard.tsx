'use client';

import { ArrowRight, Ban, Check, ChevronDown, Sparkles, X } from 'lucide-react';
import { useState } from 'react';

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
import { VALID_TAX_TYPES } from '@/lib/bas';
import { formatCurrency, formatDate } from '@/lib/formatters';
import { cn } from '@/lib/utils';

interface TaxCodeSuggestionCardProps {
  suggestion: TaxCodeSuggestion;
  onApprove: (id: string) => Promise<void>;
  onReject: (id: string) => Promise<void>;
  onOverride: (id: string, taxType: string) => Promise<void>;
  onDismiss: (id: string) => Promise<void>;
  disabled?: boolean;
}

/**
 * Compact table row for a tax code suggestion.
 * Renders as a <tr> — must be inside a <tbody>.
 */
export function TaxCodeSuggestionCard({
  suggestion,
  onApprove,
  onReject,
  onOverride,
  onDismiss,
  disabled = false,
}: TaxCodeSuggestionCardProps) {
  const [showOverride, setShowOverride] = useState(false);
  const [overrideType, setOverrideType] = useState<string>('');
  const [isLoading, setIsLoading] = useState<string | null>(null);

  const isPending = suggestion.status === 'pending';
  const isResolved = !isPending;

  async function handleAction(action: string, fn: () => Promise<void>) {
    setIsLoading(action);
    try {
      await fn();
    } finally {
      setIsLoading(null);
    }
  }

  return (
    <>
      <tr
        className={cn(
          'hover:bg-muted/30 transition-colors',
          isResolved && 'opacity-60',
          suggestion.status === 'approved' && 'bg-emerald-50/50',
          suggestion.status === 'rejected' && 'bg-red-50/30',
          suggestion.status === 'dismissed' && 'bg-muted/30',
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
            <span className="text-xs text-emerald-600 flex items-center gap-1"><Check className="w-3 h-3" />{suggestion.applied_tax_type}</span>
          ) : suggestion.status === 'overridden' ? (
            <span className="text-xs text-primary flex items-center gap-1"><ArrowRight className="w-3 h-3" />{suggestion.applied_tax_type}</span>
          ) : suggestion.status === 'rejected' ? (
            <span className="text-xs text-red-600 flex items-center gap-1"><X className="w-3 h-3" />Rejected</span>
          ) : suggestion.status === 'dismissed' ? (
            <span className="text-xs text-muted-foreground flex items-center gap-1"><Ban className="w-3 h-3" />Excluded</span>
          ) : (
            <span className="text-xs text-muted-foreground">—</span>
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
                onClick={() => setShowOverride(!showOverride)}
              >
                Override <ChevronDown className="w-2.5 h-2.5 ml-0.5" />
              </Button>
              <Button
                size="sm"
                variant="ghost"
                className="text-[10px] h-6 px-1.5 text-muted-foreground"
                disabled={disabled || isLoading !== null}
                onClick={() => handleAction('reject', () => onReject(suggestion.id))}
              >
                {isLoading === 'reject' ? '...' : 'Reject'}
              </Button>
              <Button
                size="sm"
                variant="ghost"
                className="text-[10px] h-6 px-1.5 text-muted-foreground"
                disabled={disabled || isLoading !== null}
                onClick={() => handleAction('dismiss', () => onDismiss(suggestion.id))}
              >
                {isLoading === 'dismiss' ? '...' : 'Dismiss'}
              </Button>
            </div>
          )}
          {isResolved && (
            <Badge
              variant="secondary"
              className={cn(
                'text-[10px] px-1.5 py-0',
                suggestion.status === 'approved' && 'bg-emerald-100 text-emerald-700',
              )}
            >
              {suggestion.status}
            </Badge>
          )}
        </td>
      </tr>

      {/* Override row (spans all columns) */}
      {showOverride && isPending && (
        <tr className="bg-muted/20">
          <td colSpan={5} className="px-3 py-1.5">
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground">Override to:</span>
              <Select value={overrideType} onValueChange={setOverrideType}>
                <SelectTrigger className="h-6 text-xs w-48">
                  <SelectValue placeholder="Select tax code..." />
                </SelectTrigger>
                <SelectContent>
                  {VALID_TAX_TYPES.map((t) => (
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
