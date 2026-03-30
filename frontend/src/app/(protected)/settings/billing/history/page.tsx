'use client';

import { useAuth } from '@clerk/nextjs';
import { ArrowLeft, Loader2, TrendingUp, Calendar } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

import { getUsageHistory, setAuthToken } from '@/lib/api/billing';
import type { UsageHistoryResponse, UsageSnapshot } from '@/types/billing';

/**
 * Usage history page showing historical usage trends.
 */
export default function UsageHistoryPage() {
  const router = useRouter();
  const { getToken, isLoaded } = useAuth();
  const [history, setHistory] = useState<UsageHistoryResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [months, setMonths] = useState(3);

  const fetchHistory = async (monthsToFetch: number) => {
    try {
      setIsLoading(true);
      const token = await getToken();
      setAuthToken(token);
      const data = await getUsageHistory(monthsToFetch);
      setHistory(data);
    } catch (err) {
      setError('Failed to load usage history');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (isLoaded) {
      fetchHistory(months);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- fetchHistory depends on getToken which is stable
  }, [isLoaded, months]);

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-AU', {
      day: 'numeric',
      month: 'short',
    });
  };

  const formatFullDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-AU', {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
    });
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="mb-8">
        <button
          onClick={() => router.back()}
          className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground mb-4"
        >
          <ArrowLeft className="h-4 w-4 mr-1" />
          Back to Billing
        </button>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-foreground">Usage History</h1>
            <p className="mt-1 text-muted-foreground">
              Track your usage trends over time.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <label htmlFor="months" className="text-sm text-muted-foreground">
              Show:
            </label>
            <select
              id="months"
              value={months}
              onChange={(e) => setMonths(Number(e.target.value))}
              className="rounded-lg border border-border px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
            >
              <option value={1}>Last month</option>
              <option value={3}>Last 3 months</option>
              <option value={6}>Last 6 months</option>
              <option value={12}>Last 12 months</option>
            </select>
          </div>
        </div>
      </div>

      {/* Error message */}
      {error && (
        <div className="mb-6 p-4 bg-status-danger/10 border border-status-danger/20 rounded-lg text-status-danger">
          {error}
        </div>
      )}

      {/* Loading state */}
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : history ? (
        <>
          {/* Period Info */}
          <div className="mb-6 p-4 bg-primary/10 border border-primary/20 rounded-lg">
            <div className="flex items-center gap-2 text-primary">
              <Calendar className="h-5 w-5" />
              <span className="font-medium">
                {formatFullDate(history.period_start)} - {formatFullDate(history.period_end)}
              </span>
            </div>
          </div>

          {/* Snapshots */}
          {history.snapshots.length === 0 ? (
            <div className="bg-card rounded-lg border p-8 text-center">
              <TrendingUp className="h-12 w-12 text-muted-foreground/50 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-foreground mb-2">
                No history yet
              </h3>
              <p className="text-muted-foreground">
                Usage snapshots are captured daily. Check back tomorrow to see your usage trends.
              </p>
            </div>
          ) : (
            <div className="bg-card rounded-lg border shadow-sm overflow-hidden">
              <div className="px-6 py-4 border-b">
                <h3 className="text-lg font-semibold text-foreground">
                  Daily Snapshots
                </h3>
                <p className="text-sm text-muted-foreground">
                  {history.snapshots.length} snapshots
                </p>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="bg-muted">
                      <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                        Date
                      </th>
                      <th className="px-6 py-3 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider">
                        Clients
                      </th>
                      <th className="px-6 py-3 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider">
                        AI Queries
                      </th>
                      <th className="px-6 py-3 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider">
                        Documents
                      </th>
                      <th className="px-6 py-3 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider">
                        Tier
                      </th>
                      <th className="px-6 py-3 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider">
                        Limit
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {history.snapshots.map((snapshot: UsageSnapshot) => (
                      <tr key={snapshot.id} className="hover:bg-muted">
                        <td className="px-6 py-4 text-sm text-foreground">
                          {formatDate(snapshot.captured_at)}
                        </td>
                        <td className="px-6 py-4 text-sm text-foreground text-right">
                          {snapshot.client_count}
                        </td>
                        <td className="px-6 py-4 text-sm text-foreground text-right">
                          {snapshot.ai_queries_count}
                        </td>
                        <td className="px-6 py-4 text-sm text-foreground text-right">
                          {snapshot.documents_count}
                        </td>
                        <td className="px-6 py-4 text-sm text-right">
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-primary/10 text-primary capitalize">
                            {snapshot.tier}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-sm text-muted-foreground text-right">
                          {snapshot.client_limit ?? 'Unlimited'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      ) : null}
    </div>
  );
}
