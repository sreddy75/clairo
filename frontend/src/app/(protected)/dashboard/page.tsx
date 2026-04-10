'use client';

/**
 * Dashboard — Portfolio Triage View
 *
 * Information hierarchy (per UX patterns):
 * 1. Portfolio stat cards (triage at a glance, clickable to filter)
 * 2. Attention items (insights requiring action)
 * 3. Client table (sortable, filterable, full portfolio)
 *
 * Each row = one XeroConnection = one client business = one BAS to lodge.
 */

import { useAuth } from '@clerk/nextjs';
import {
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  Building2,
  ChevronLeft,
  ChevronRight,
  Download,
  Loader2,
  RefreshCw,
  Search,
} from 'lucide-react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { useCallback, useEffect, useRef, useState } from 'react';

import { DashboardA2UI } from '@/components/dashboard/DashboardA2UI';
import { InsightsWidget } from '@/components/insights/InsightsWidget';
import { QualityBadge } from '@/components/quality';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
} from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { apiClient } from '@/lib/api-client';
import { getStatusConfig } from '@/lib/constants/status';
import { formatCurrency, formatRelativeTime } from '@/lib/formatters';
import { cn } from '@/lib/utils';

// ─── Types ──────────────────────────────────────────────────────────────────

interface StatusCounts {
  ready: number;
  needs_review: number;
  no_activity: number;
  missing_data: number;
}

interface QualitySummary {
  avg_score: string;
  good_count: number;
  fair_count: number;
  poor_count: number;
  total_critical_issues: number;
}

interface DashboardSummary {
  total_clients: number;
  active_clients: number;
  total_sales: string;
  total_purchases: string;
  gst_collected: string;
  gst_paid: string;
  net_gst: string;
  status_counts: StatusCounts;
  quality: QualitySummary;
  quarter_label: string;
  quarter: number;
  fy_year: number;
  quarter_start: string;
  quarter_end: string;
  last_sync_at: string | null;
}

interface ClientPortfolioItem {
  id: string;
  organization_name: string;
  total_sales: string;
  total_purchases: string;
  gst_collected: string;
  gst_paid: string;
  net_gst: string;
  invoice_count: number;
  transaction_count: number;
  activity_count: number;
  bas_status: string;
  quality_score: string | null;
  critical_issues: number;
  last_synced_at: string | null;
}

interface ClientPortfolioResponse {
  clients: ClientPortfolioItem[];
  total: number;
  page: number;
  limit: number;
}

interface QuarterInfo {
  quarter: number;
  fy_year: number;
  label: string;
  start_date: string;
  end_date: string;
  is_current: boolean;
}

interface AvailableQuartersResponse {
  quarters: QuarterInfo[];
  current: QuarterInfo;
}

// ─── Status Filter Tabs ─────────────────────────────────────────────────────

const STATUS_TABS = [
  { value: '', label: 'All' },
  { value: 'needs_review', label: 'Needs Review' },
  { value: 'ready', label: 'Ready' },
  { value: 'no_activity', label: 'No Activity' },
] as const;

// ─── Component ──────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const { getToken } = useAuth();
  const searchParams = useSearchParams();
  const isDemo = searchParams.get('demo') === 'true';

  // State
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [clients, setClients] = useState<ClientPortfolioItem[]>([]);
  const [quarters, setQuarters] = useState<QuarterInfo[]>([]);
  const [_currentQuarter, setCurrentQuarter] = useState<QuarterInfo | null>(null);

  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [selectedQuarter, setSelectedQuarter] = useState<{ quarter: number; fy_year: number } | null>(null);
  const [selectedStatus, setSelectedStatus] = useState<string>('');
  const [search, setSearch] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [sortBy, setSortBy] = useState('organization_name');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const limit = 25;

  // ─── Data Fetching ──────────────────────────────────────────────────────

  const fetchSummary = useCallback(async (token: string, quarter: { quarter: number; fy_year: number }) => {
    try {
      const params = new URLSearchParams();
      params.set('quarter', quarter.quarter.toString());
      params.set('fy_year', quarter.fy_year.toString());
      const response = await apiClient.get(`/api/v1/dashboard/summary?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (response.ok) {
        setSummary(await response.json());
      }
    } catch {
      // Silently fail
    }
  }, []);

  const fetchClients = useCallback(async (token: string, quarter: { quarter: number; fy_year: number }) => {
    try {
      setIsLoading(true);
      setError(null);
      const params = new URLSearchParams({
        page: page.toString(),
        limit: limit.toString(),
        sort_by: sortBy,
        sort_order: sortOrder,
      });
      params.set('quarter', quarter.quarter.toString());
      params.set('fy_year', quarter.fy_year.toString());
      if (selectedStatus) params.set('status', selectedStatus);
      if (search) params.set('search', search);

      const response = await apiClient.get(`/api/v1/dashboard/clients?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) throw new Error('Failed to fetch clients');

      const data: ClientPortfolioResponse = await response.json();
      setClients(data.clients);
      setTotal(data.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setIsLoading(false);
    }
  }, [page, sortBy, sortOrder, selectedStatus, search]);

  // Initial load
  useEffect(() => {
    let cancelled = false;
    async function loadDashboard() {
      const token = await getToken();
      if (!token || cancelled) return;
      try {
        const response = await apiClient.get('/api/v1/integrations/xero/quarters', {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (response.ok && !cancelled) {
          const data: AvailableQuartersResponse = await response.json();
          setQuarters(data.quarters);
          setCurrentQuarter(data.current);
          const quarter = { quarter: data.current.quarter, fy_year: data.current.fy_year };
          setSelectedQuarter(quarter);
          await Promise.all([fetchSummary(token, quarter), fetchClients(token, quarter)]);
        }
      } catch {
        // Silently fail
      }
    }
    loadDashboard();
    return () => { cancelled = true; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Re-fetch on filter/sort/pagination changes
  const isInitialLoad = useRef(true);
  useEffect(() => {
    if (isInitialLoad.current) {
      isInitialLoad.current = false;
      return;
    }
    if (!selectedQuarter) return;
    let cancelled = false;
    async function refetchData() {
      const token = await getToken();
      if (!token || cancelled) return;
      await Promise.all([fetchSummary(token, selectedQuarter!), fetchClients(token, selectedQuarter!)]);
    }
    refetchData();
    return () => { cancelled = true; };
  }, [getToken, selectedQuarter, fetchSummary, fetchClients]);

  // ─── Handlers ───────────────────────────────────────────────────────────

  const handleRefresh = async () => {
    if (!selectedQuarter) return;
    setIsRefreshing(true);
    try {
      const token = await getToken();
      if (!token) return;
      await Promise.all([fetchSummary(token, selectedQuarter), fetchClients(token, selectedQuarter)]);
    } finally {
      setIsRefreshing(false);
    }
  };

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSearch(searchInput);
    setPage(1);
  };

  const handleSort = (column: string) => {
    if (sortBy === column) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(column);
      setSortOrder('asc');
    }
    setPage(1);
  };

  const handleExport = () => {
    if (clients.length === 0) return;
    const headers = ['Organization', 'Sales', 'Purchases', 'GST Collected', 'GST Paid', 'Net GST', 'Activity', 'Quality', 'Status', 'Last Synced'];
    const rows = clients.map(c => [
      c.organization_name,
      c.total_sales,
      c.total_purchases,
      c.gst_collected,
      c.gst_paid,
      c.net_gst,
      c.activity_count.toString(),
      c.quality_score ? `${parseFloat(c.quality_score).toFixed(0)}%` : 'N/A',
      getStatusConfig(c.bas_status).label,
      c.last_synced_at || 'Never',
    ]);
    const csv = [headers, ...rows].map(row => row.join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `bas-clients-${summary?.quarter_label?.replace(' ', '-').toLowerCase() || 'export'}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // ─── Computed ───────────────────────────────────────────────────────────

  const totalPages = Math.ceil(total / limit);
  const needsAttentionCount = summary
    ? summary.quality.fair_count + summary.quality.poor_count +
      summary.status_counts.needs_review + summary.status_counts.missing_data
    : 0;
  const hasCritical = summary
    ? summary.quality.poor_count > 0 || summary.status_counts.missing_data > 0
    : false;

  // ─── Sort Icon ──────────────────────────────────────────────────────────

  const SortIcon = ({ column }: { column: string }) => {
    if (sortBy !== column) return <ArrowUpDown className="h-3.5 w-3.5 text-muted-foreground/50" />;
    return sortOrder === 'asc' ? (
      <ArrowUp className="h-3.5 w-3.5 text-primary" />
    ) : (
      <ArrowDown className="h-3.5 w-3.5 text-primary" />
    );
  };

  // ─── Render ─────────────────────────────────────────────────────────────

  return (
    <div className="space-y-5">

      {/* ── Page Header ──────────────────────────────────────────────── */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Dashboard</h1>
          <p className="text-sm text-muted-foreground">
            Portfolio overview for {summary?.quarter_label || 'current quarter'}
          </p>
        </div>

        <div className="flex items-center gap-2">
          {quarters.length > 0 && (
            <Select
              value={selectedQuarter ? `${selectedQuarter.quarter}-${selectedQuarter.fy_year}` : undefined}
              onValueChange={(val) => {
                const parts = val.split('-');
                if (parts.length === 2 && parts[0] && parts[1]) {
                  setSelectedQuarter({ quarter: parseInt(parts[0], 10), fy_year: parseInt(parts[1], 10) });
                  setPage(1);
                }
              }}
            >
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Select quarter" />
              </SelectTrigger>
              <SelectContent>
                {quarters.map((q) => (
                  <SelectItem key={`${q.quarter}-${q.fy_year}`} value={`${q.quarter}-${q.fy_year}`}>
                    {q.label}{q.is_current ? ' (Current)' : ''}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}

          <Button variant="outline" size="sm" onClick={handleRefresh} disabled={isRefreshing}>
            <RefreshCw className={cn('h-4 w-4', isRefreshing && 'animate-spin')} />
            <span className="hidden sm:inline ml-1.5">Refresh</span>
          </Button>

          <Button variant="outline" size="sm" onClick={handleExport} disabled={clients.length === 0}>
            <Download className="h-4 w-4" />
            <span className="hidden sm:inline ml-1.5">Export</span>
          </Button>
        </div>
      </div>

      {/* ── Stat Cards ───────────────────────────────────────────────── */}
      {summary && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {/* Portfolio Health */}
          <Card className="shadow-sm">
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Portfolio Health
                </span>
                <span className="text-xs text-muted-foreground">
                  {summary.total_clients} client{summary.total_clients !== 1 ? 's' : ''}
                </span>
              </div>
              <p className="mt-2 text-2xl font-bold tracking-tight tabular-nums">
                {parseFloat(summary.quality.avg_score).toFixed(0)}%
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                Avg quality · {summary.active_clients} active
              </p>
            </CardContent>
          </Card>

          {/* Ready to Lodge */}
          <Card
            className="cursor-pointer shadow-sm transition-shadow hover:shadow-md"
            onClick={() => { setSelectedStatus('ready'); setPage(1); }}
          >
            <CardContent className="p-4">
              <div className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-status-success" />
                <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Ready to Lodge
                </span>
              </div>
              <p className="mt-2 text-2xl font-bold tracking-tight tabular-nums text-status-success">
                {summary.quality.good_count}
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                Quality ≥80% · Data current
              </p>
            </CardContent>
          </Card>

          {/* Needs Attention */}
          <Card
            className="cursor-pointer shadow-sm transition-shadow hover:shadow-md"
            onClick={() => { setSelectedStatus('needs_review'); setPage(1); }}
          >
            <CardContent className="p-4">
              <div className="flex items-center gap-2">
                <span className={cn(
                  'h-2 w-2 rounded-full',
                  hasCritical ? 'bg-status-danger' : 'bg-status-warning'
                )} />
                <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Needs Attention
                </span>
              </div>
              <p className={cn(
                'mt-2 text-2xl font-bold tracking-tight tabular-nums',
                hasCritical ? 'text-status-danger' : 'text-status-warning'
              )}>
                {needsAttentionCount}
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                {needsAttentionCount === 0 ? 'All clients ready' : 'Review before lodging'}
              </p>
            </CardContent>
          </Card>

          {/* No Activity */}
          <Card
            className="cursor-pointer shadow-sm transition-shadow hover:shadow-md"
            onClick={() => { setSelectedStatus('no_activity'); setPage(1); }}
          >
            <CardContent className="p-4">
              <div className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-status-neutral" />
                <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  No Activity
                </span>
              </div>
              <p className="mt-2 text-2xl font-bold tracking-tight tabular-nums text-muted-foreground">
                {summary.status_counts.no_activity}
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                No transactions this quarter
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* ── A2UI Demo (gated) ────────────────────────────────────────── */}
      {isDemo && selectedQuarter && (
        <Card className="shadow-sm">
          <CardContent className="p-4">
            <DashboardA2UI quarter={selectedQuarter.quarter} fyYear={selectedQuarter.fy_year} />
          </CardContent>
        </Card>
      )}

      {/* ── Insights — Attention Items ───────────────────────────────── */}
      <InsightsWidget />

      {/* ── Client Table ─────────────────────────────────────────────── */}
      <Card className="shadow-sm">
        {/* Filter Bar */}
        <CardHeader className="pb-3">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            {/* Status Tabs */}
            <div className="flex gap-1">
              {STATUS_TABS.map((tab) => {
                const count = tab.value === ''
                  ? total
                  : tab.value === 'needs_review'
                    ? (summary?.status_counts.needs_review ?? 0) + (summary?.status_counts.missing_data ?? 0)
                    : summary?.status_counts[tab.value as keyof StatusCounts] ?? 0;
                return (
                  <button
                    key={tab.value}
                    onClick={() => { setSelectedStatus(tab.value); setPage(1); }}
                    className={cn(
                      'rounded-md px-3 py-1.5 text-xs font-medium transition-colors',
                      selectedStatus === tab.value
                        ? 'bg-primary text-primary-foreground'
                        : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                    )}
                  >
                    {tab.label}
                    {count > 0 && (
                      <span className={cn(
                        'ml-1.5 tabular-nums',
                        selectedStatus === tab.value ? 'text-primary-foreground/70' : 'text-muted-foreground'
                      )}>
                        {count}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>

            {/* Search */}
            <form onSubmit={handleSearchSubmit} className="relative w-full sm:max-w-xs">
              <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                type="text"
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                placeholder="Search clients..."
                className="pl-9"
              />
            </form>
          </div>
        </CardHeader>

        {/* Table Content */}
        <CardContent className="p-0">
          {/* Error State */}
          {error && (
            <div className="flex items-center gap-3 border-b px-4 py-2.5 text-sm">
              <span className="h-2 w-2 rounded-full bg-status-danger" />
              <span className="text-status-danger">{error}</span>
              <Button variant="link" size="sm" className="ml-auto p-0 text-xs" onClick={handleRefresh}>
                Retry
              </Button>
            </div>
          )}

          {/* Loading State */}
          {isLoading && (
            <div className="flex flex-col items-center justify-center py-16">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              <p className="mt-2 text-sm text-muted-foreground">Loading clients...</p>
            </div>
          )}

          {/* Table */}
          {!isLoading && !error && (
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <SortableHead column="organization_name" label="Client" sortBy={sortBy} onSort={handleSort}>
                    <SortIcon column="organization_name" />
                  </SortableHead>
                  <SortableHead column="net_gst" label="Net GST" sortBy={sortBy} onSort={handleSort} className="text-right">
                    <SortIcon column="net_gst" />
                  </SortableHead>
                  <SortableHead column="total_sales" label="Sales" sortBy={sortBy} onSort={handleSort} className="hidden text-right lg:table-cell">
                    <SortIcon column="total_sales" />
                  </SortableHead>
                  <SortableHead column="activity_count" label="Activity" sortBy={sortBy} onSort={handleSort} className="hidden text-right md:table-cell">
                    <SortIcon column="activity_count" />
                  </SortableHead>
                  <SortableHead column="quality_score" label="Quality" sortBy={sortBy} onSort={handleSort} className="text-center">
                    <SortIcon column="quality_score" />
                  </SortableHead>
                  <TableHead className="text-center">Status</TableHead>
                  <TableHead className="hidden text-right md:table-cell">Synced</TableHead>
                </TableRow>
              </TableHeader>

              <TableBody>
                {clients.length === 0 ? (
                  <TableRow className="hover:bg-transparent">
                    <TableCell colSpan={7} className="py-16 text-center">
                      {search || selectedStatus ? (
                        <div>
                          <p className="font-medium text-foreground">No clients match your filters</p>
                          <Button
                            variant="link"
                            size="sm"
                            className="mt-1"
                            onClick={() => {
                              setSelectedStatus('');
                              setSearch('');
                              setSearchInput('');
                              setPage(1);
                            }}
                          >
                            Clear filters
                          </Button>
                        </div>
                      ) : (
                        <div>
                          <Building2 className="mx-auto h-10 w-10 text-muted-foreground/30" />
                          <p className="mt-3 font-medium text-foreground">No client businesses found</p>
                          <p className="mt-1 text-sm text-muted-foreground">
                            Connect a Xero organization to see your clients
                          </p>
                          <Button variant="outline" size="sm" className="mt-3" asChild>
                            <Link href="/integrations">Connect Xero</Link>
                          </Button>
                        </div>
                      )}
                    </TableCell>
                  </TableRow>
                ) : (
                  clients.map((client) => {
                    const status = getStatusConfig(client.bas_status);
                    const isInactive = client.bas_status === 'no_activity';

                    return (
                      <TableRow key={client.id} className={cn(isInactive && 'opacity-50')}>
                        <TableCell className="font-medium">
                          <Link
                            href={`/clients/${client.id}`}
                            className="hover:text-primary transition-colors"
                          >
                            {client.organization_name}
                          </Link>
                        </TableCell>
                        <TableCell className={cn(
                          'text-right tabular-nums font-medium',
                          !isInactive && parseFloat(client.net_gst) < 0 && 'text-status-danger'
                        )}>
                          {formatCurrency(client.net_gst)}
                        </TableCell>
                        <TableCell className="hidden text-right tabular-nums lg:table-cell">
                          {formatCurrency(client.total_sales)}
                        </TableCell>
                        <TableCell className="hidden text-right tabular-nums md:table-cell">
                          {client.activity_count}
                        </TableCell>
                        <TableCell className="text-center">
                          <QualityBadge
                            score={client.quality_score ? parseFloat(client.quality_score) : null}
                            size="sm"
                          />
                        </TableCell>
                        <TableCell className="text-center">
                          <span className="inline-flex items-center gap-1.5 text-xs">
                            <span className={cn('h-1.5 w-1.5 rounded-full', status.dotColor)} />
                            <span className="text-muted-foreground">{status.label}</span>
                          </span>
                        </TableCell>
                        <TableCell className="hidden text-right text-xs text-muted-foreground md:table-cell">
                          {formatRelativeTime(client.last_synced_at)}
                        </TableCell>
                      </TableRow>
                    );
                  })
                )}
              </TableBody>
            </Table>
          )}
        </CardContent>

        {/* Pagination */}
        {totalPages > 1 && (
          <CardFooter className="flex-wrap justify-between gap-2 border-t px-3 sm:px-6 py-3">
            <span className="text-xs text-muted-foreground">
              {(page - 1) * limit + 1}–{Math.min(page * limit, total)} of {total}
            </span>
            <div className="flex items-center gap-1">
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                onClick={() => setPage(page - 1)}
                disabled={page === 1}
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <span className="px-2 text-xs text-muted-foreground tabular-nums">
                {page} / {totalPages}
              </span>
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                onClick={() => setPage(page + 1)}
                disabled={page === totalPages}
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </CardFooter>
        )}
      </Card>
    </div>
  );
}

// ─── Sortable Table Head ────────────────────────────────────────────────────

function SortableHead({
  column,
  label,
  onSort,
  className,
  children,
}: {
  column: string;
  label: string;
  sortBy?: string;
  onSort: (column: string) => void;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <TableHead
      className={cn('cursor-pointer select-none transition-colors hover:text-foreground', className)}
      onClick={() => onSort(column)}
    >
      <div className={cn('flex items-center gap-1', className?.includes('text-right') && 'justify-end', className?.includes('text-center') && 'justify-center')}>
        {label}
        {children}
      </div>
    </TableHead>
  );
}
