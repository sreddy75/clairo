'use client';

import { AlertCircle, CheckCircle2, Info, RefreshCw, X } from 'lucide-react';
import { useState } from 'react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import type { XeroBASCrossCheckResponse } from '@/lib/bas';
import { formatCurrency } from '@/lib/formatters';
import { cn } from '@/lib/utils';

interface XeroBASCrossCheckProps {
  data: XeroBASCrossCheckResponse;
  onRefresh?: () => Promise<void>;
}

export function XeroBASCrossCheck({ data, onRefresh }: XeroBASCrossCheckProps) {
  const [dismissed, setDismissed] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  async function handleRefresh() {
    if (!onRefresh || refreshing) return;
    setRefreshing(true);
    try {
      await onRefresh();
    } finally {
      setRefreshing(false);
    }
  }

  if (dismissed) return null;

  // Xero error or unavailable — show inline error with Refresh button
  if (data.xero_report_found === null) {
    return (
      <Card className="mb-4 border-status-danger/20 bg-status-danger/5">
        <CardContent className="py-2 px-4 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-xs text-status-danger">
            <AlertCircle className="w-3.5 h-3.5 shrink-0" />
            <span>
              {data.xero_error
                ? `Could not connect to Xero — cross-check unavailable. ${data.xero_error}`
                : 'Could not connect to Xero — cross-check unavailable.'}
              {' '}Try refreshing or check the Xero connection.
            </span>
          </div>
          <div className="flex items-center gap-1 shrink-0">
            {onRefresh && (
              <Button
                variant="ghost"
                size="sm"
                className="h-5 px-2 text-xs"
                onClick={handleRefresh}
                disabled={refreshing}
              >
                <RefreshCw className={`w-3 h-3 mr-1 ${refreshing ? 'animate-spin' : ''}`} />
                Refresh
              </Button>
            )}
            <Button variant="ghost" size="sm" className="h-5 w-5 p-0" onClick={() => setDismissed(true)}>
              <X className="w-3 h-3" />
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  // No report found
  if (!data.xero_report_found) {
    return (
      <Card className="mb-4 border-stone-200 bg-stone-50">
        <CardContent className="py-2 px-4 flex items-center justify-between">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Info className="w-3.5 h-3.5" />
            <span>No BAS report found in Xero for {data.period_label}</span>
          </div>
          <Button variant="ghost" size="sm" className="h-5 w-5 p-0" onClick={() => setDismissed(true)}>
            <X className="w-3 h-3" />
          </Button>
        </CardContent>
      </Card>
    );
  }

  // Report found — show comparison
  const hasDiffs = data.differences && Object.keys(data.differences).length > 0;

  const labels: { key: string; label: string }[] = [
    { key: 'g1_total_sales', label: 'G1 — Total sales' },
    { key: 'g10_capital_purchases', label: 'G10 — Capital purchases' },
    { key: 'g11_non_capital_purchases', label: 'G11 — Non-capital purchases' },
    { key: 'label_1a_gst_on_sales', label: '1A — GST on sales' },
    { key: 'label_1b_gst_on_purchases', label: '1B — GST on purchases' },
    { key: 'net_gst', label: 'Net GST' },
  ];

  return (
    <Card className={cn('mb-4', hasDiffs ? 'border-amber-300 bg-amber-50/50' : 'border-emerald-200 bg-emerald-50/30')}>
      <CardHeader className="py-2 px-4 flex flex-row items-center justify-between">
        <div className="flex items-center gap-2 text-xs font-medium">
          {hasDiffs ? (
            <AlertCircle className="w-3.5 h-3.5 text-amber-600" />
          ) : (
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
          )}
          <span>Xero BAS data found for {data.period_label}</span>
          {hasDiffs && <span className="text-amber-600 font-normal">— figures differ</span>}
        </div>
        <div className="flex items-center gap-1">
          {onRefresh && (
            <Button
              variant="ghost"
              size="sm"
              className="h-5 w-5 p-0"
              onClick={handleRefresh}
              disabled={refreshing}
              title="Refresh from Xero"
            >
              <RefreshCw className={cn('w-3 h-3', refreshing && 'animate-spin')} />
            </Button>
          )}
          <Button variant="ghost" size="sm" className="h-5 w-5 p-0" onClick={() => setDismissed(true)}>
            <X className="w-3 h-3" />
          </Button>
        </div>
      </CardHeader>
      <CardContent className="py-0 px-4 pb-3">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-muted-foreground">
              <th className="text-left font-medium py-1">Field</th>
              <th className="text-right font-medium py-1">Xero</th>
              <th className="text-right font-medium py-1">Clairo</th>
              <th className="text-right font-medium py-1">Diff</th>
            </tr>
          </thead>
          <tbody>
            {labels.map(({ key, label }) => {
              const diff = data.differences?.[key];
              const xeroVal = data.xero_figures?.[key as keyof typeof data.xero_figures];
              const clairoVal = data.clairo_figures?.[key as keyof typeof data.clairo_figures];
              const isMaterial = diff?.material;

              return (
                <tr key={key} className={cn(isMaterial && 'bg-amber-100/60')}>
                  <td className="py-0.5">{label}</td>
                  <td className="text-right tabular-nums">{xeroVal != null ? formatCurrency(Number(xeroVal)) : '—'}</td>
                  <td className="text-right tabular-nums">{clairoVal != null ? formatCurrency(Number(clairoVal)) : '—'}</td>
                  <td className={cn('text-right tabular-nums', isMaterial && 'text-amber-700 font-medium')}>
                    {diff ? formatCurrency(Number(diff.delta)) : '—'}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}
