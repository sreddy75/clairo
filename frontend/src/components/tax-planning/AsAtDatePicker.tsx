'use client';

import { useAuth } from '@clerk/nextjs';
import { Calendar, ChevronDown, Loader2 } from 'lucide-react';
import { useMemo, useState } from 'react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { pullXeroFinancials } from '@/lib/api/tax-planning';
import { cn } from '@/lib/utils';

interface AsAtDatePickerProps {
  planId: string;
  // Current persisted anchor. Null means "following the reconciliation date".
  asAtDate: string | null;
  // Latest reconciliation date reported by the plan (from
  // financials_data.last_reconciliation_date). Surfaced as the default
  // option's label so the accountant can see what "Latest reconciled" is.
  reconDate: string | null;
  // Financial year in `YYYY-YY` shape — used to derive BAS quarter presets.
  financialYear: string;
  onRefreshed: () => void | Promise<void>;
  disabled?: boolean;
}

/**
 * Spec 059.1 — anchor the projection to a user-chosen "as at" date.
 *
 * Accountants flagged that projecting off the latest Xero reconciliation
 * date (e.g. 13 Apr for a March-quarter client) mixes a partial month into
 * a monthly-average × 12 calculation. BAS quarter ends are known-clean
 * checkpoints, so the picker surfaces them as one-click presets.
 *
 * Changing the date calls the existing refresh endpoint with the new
 * anchor — a single round-trip that persists the choice AND re-pulls Xero
 * data scoped to the new date.
 */
export function AsAtDatePicker({
  planId,
  asAtDate,
  reconDate,
  financialYear,
  onRefreshed,
  disabled = false,
}: AsAtDatePickerProps) {
  const { getToken } = useAuth();
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [customDraft, setCustomDraft] = useState<string>(asAtDate ?? '');

  const fyStartYear = useMemo(() => {
    const parsed = parseInt(financialYear.slice(0, 4), 10);
    return Number.isFinite(parsed) ? parsed : new Date().getFullYear();
  }, [financialYear]);

  // BAS quarter ends for this FY — dates only (no time), ISO format.
  const basQuarterOptions = useMemo(
    () => [
      { date: `${fyStartYear}-09-30`, label: `30 Sep ${fyStartYear}` },
      { date: `${fyStartYear}-12-31`, label: `31 Dec ${fyStartYear}` },
      { date: `${fyStartYear + 1}-03-31`, label: `31 Mar ${fyStartYear + 1}` },
      { date: `${fyStartYear + 1}-06-30`, label: `30 Jun ${fyStartYear + 1}` },
    ],
    [fyStartYear],
  );

  const currentLabel = useMemo(() => {
    if (asAtDate) {
      return formatDateLabel(asAtDate);
    }
    if (reconDate) {
      return `Reconciled to ${formatDateLabel(reconDate)}`;
    }
    return 'Latest available';
  }, [asAtDate, reconDate]);

  const apply = async (nextDate: string | null) => {
    setSaving(true);
    try {
      const token = await getToken();
      if (!token) throw new Error('not authenticated');
      await pullXeroFinancials(token, planId, false, nextDate);
      await onRefreshed();
      setOpen(false);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          disabled={disabled || saving}
          className="h-8 gap-1.5 text-xs"
        >
          {saving ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Calendar className="h-3.5 w-3.5" />
          )}
          <span>As at: {currentLabel}</span>
          <ChevronDown className="h-3 w-3 opacity-60" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-72 space-y-2 p-3">
        <div className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          Projection basis
        </div>
        <button
          type="button"
          onClick={() => apply(null)}
          disabled={saving}
          className={cn(
            'flex w-full items-center justify-between rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted',
            asAtDate === null && 'bg-muted font-medium',
          )}
        >
          <span>Follow Xero reconciliation</span>
          {reconDate && (
            <span className="text-xs text-muted-foreground">
              {formatDateLabel(reconDate)}
            </span>
          )}
        </button>
        <div className="border-t pt-2">
          <div className="mb-1 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
            BAS quarter ends
          </div>
          {basQuarterOptions.map((opt) => (
            <button
              key={opt.date}
              type="button"
              onClick={() => apply(opt.date)}
              disabled={saving}
              className={cn(
                'block w-full rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted',
                asAtDate === opt.date && 'bg-muted font-medium',
              )}
            >
              {opt.label}
            </button>
          ))}
        </div>
        <div className="border-t pt-2 space-y-1.5">
          <Label
            htmlFor="as-at-custom"
            className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground"
          >
            Custom date
          </Label>
          <div className="flex gap-1.5">
            <Input
              id="as-at-custom"
              type="date"
              value={customDraft}
              onChange={(e) => setCustomDraft(e.target.value)}
              disabled={saving}
              className="h-8 text-sm"
            />
            <Button
              size="sm"
              onClick={() => customDraft && apply(customDraft)}
              disabled={saving || !customDraft}
              className="h-8"
            >
              Apply
            </Button>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}

function formatDateLabel(iso: string): string {
  const [y, m, d] = iso.split('-').map(Number);
  if (!y || !m || !d) return iso;
  const months = [
    'Jan',
    'Feb',
    'Mar',
    'Apr',
    'May',
    'Jun',
    'Jul',
    'Aug',
    'Sep',
    'Oct',
    'Nov',
    'Dec',
  ];
  return `${d} ${months[m - 1]} ${y}`;
}
