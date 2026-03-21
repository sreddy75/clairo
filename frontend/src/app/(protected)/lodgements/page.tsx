'use client';

/**
 * BAS Lodgement Workboard
 *
 * UX: List layout with summary stat cards + filterable table.
 * JTBD: #2 Review & Lodge Compliance — deadline countdown, client count by readiness.
 * Information priority: Deadline countdown → Readiness counts → Table with status.
 */

import { useAuth } from '@clerk/nextjs';
import {
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock,
  FileText,
  Loader2,
  Search,
  XCircle,
} from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useCallback, useEffect, useState } from 'react';

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
import { getLodgementStatusConfig, getUrgencyConfig } from '@/lib/constants/status';
import { formatDate } from '@/lib/formatters';
import { cn } from '@/lib/utils';

// ─── Types ──────────────────────────────────────────────────────────────────

interface WorkboardSummary {
  total_periods: number;
  overdue: number;
  due_this_week: number;
  due_this_month: number;
  lodged: number;
  not_started: number;
}

interface WorkboardItem {
  connection_id: string;
  client_name: string;
  period_id: string;
  period_display_name: string;
  quarter: number | null;
  financial_year: string;
  due_date: string;
  days_remaining: number;
  session_id: string | null;
  session_status: string | null;
  is_lodged: boolean;
  lodged_at: string | null;
  urgency: 'overdue' | 'critical' | 'warning' | 'normal';
}

interface WorkboardResponse {
  items: WorkboardItem[];
  total: number;
  page: number;
  limit: number;
  total_pages: number;
}

// ─── Status Filter Tabs ─────────────────────────────────────────────────────

const STATUS_TABS = [
  { value: 'all', label: 'All' },
  { value: 'overdue', label: 'Overdue' },
  { value: 'due_this_week', label: 'Due This Week' },
  { value: 'upcoming', label: 'Upcoming' },
  { value: 'lodged', label: 'Lodged' },
] as const;

// ─── Days Remaining Badge ───────────────────────────────────────────────────

function DaysRemainingBadge({ days, isLodged }: { days: number; isLodged: boolean }) {
  if (isLodged) {
    return (
      <span className="inline-flex items-center gap-1 text-xs font-medium text-status-success">
        <CheckCircle2 className="h-3 w-3" /> Lodged
      </span>
    );
  }
  if (days < 0) {
    return (
      <span className="inline-flex items-center gap-1 text-xs font-semibold text-status-danger">
        <XCircle className="h-3 w-3" /> {Math.abs(days)}d overdue
      </span>
    );
  }
  if (days === 0) {
    return (
      <span className="inline-flex items-center gap-1 text-xs font-semibold text-status-danger animate-pulse">
        <AlertTriangle className="h-3 w-3" /> Due today
      </span>
    );
  }
  if (days === 1) {
    return (
      <span className="inline-flex items-center gap-1 text-xs font-semibold text-status-warning">
        <Clock className="h-3 w-3" /> Due tomorrow
      </span>
    );
  }
  if (days <= 7) {
    return <span className="text-xs font-medium text-status-warning tabular-nums">{days}d left</span>;
  }
  return <span className="text-xs text-muted-foreground tabular-nums">{days}d</span>;
}

// ─── Financial Year Options ─────────────────────────────────────────────────

function getFinancialYearOptions(): string[] {
  const currentYear = new Date().getFullYear();
  const currentMonth = new Date().getMonth();
  const currentFY = currentMonth >= 6 ? currentYear : currentYear - 1;
  return [
    `${currentFY}-${(currentFY + 1).toString().slice(2)}`,
    `${currentFY - 1}-${currentFY.toString().slice(2)}`,
    `${currentFY - 2}-${(currentFY - 1).toString().slice(2)}`,
  ];
}

// ─── Component ──────────────────────────────────────────────────────────────

export default function LodgementsPage() {
  const { getToken } = useAuth();
  const router = useRouter();

  // State
  const [summary, setSummary] = useState<WorkboardSummary | null>(null);
  const [items, setItems] = useState<WorkboardItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSummaryLoading, setIsSummaryLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [search, setSearch] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [quarterFilter, setQuarterFilter] = useState<string>('all');
  const [fyFilter, setFyFilter] = useState<string>('');

  // Sorting
  const [sortBy, setSortBy] = useState<'due_date' | 'client_name' | 'status' | 'days_remaining'>('due_date');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');

  // Pagination
  const [page, setPage] = useState(1);
  const [limit, setLimit] = useState(25);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);

  const fyOptions = getFinancialYearOptions();

  // ─── Data Fetching ──────────────────────────────────────────────────────

  const fetchSummary = useCallback(async () => {
    try {
      setIsSummaryLoading(true);
      const token = await getToken();
      if (!token) return;
      const response = await apiClient.get('/api/v1/bas/workboard/summary', {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (response.ok) setSummary(await response.json());
    } catch {
      // Silently fail
    } finally {
      setIsSummaryLoading(false);
    }
  }, [getToken]);

  const fetchWorkboard = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const token = await getToken();
      if (!token) { setError('Not authenticated'); return; }

      const params = new URLSearchParams({
        page: page.toString(),
        limit: limit.toString(),
        sort_by: sortBy,
        sort_order: sortOrder,
      });
      if (statusFilter !== 'all') params.set('status', statusFilter);
      if (quarterFilter !== 'all') params.set('quarter', quarterFilter);
      if (fyFilter) params.set('fy', fyFilter);
      if (search) params.set('search', search);

      const response = await apiClient.get(`/api/v1/bas/workboard?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) throw new Error('Failed to fetch workboard data');

      const data: WorkboardResponse = await response.json();
      setItems(data.items);
      setTotal(data.total);
      setTotalPages(data.total_pages);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setIsLoading(false);
    }
  }, [getToken, page, limit, sortBy, sortOrder, statusFilter, quarterFilter, fyFilter, search]);

  useEffect(() => { fetchSummary(); fetchWorkboard(); }, [fetchSummary, fetchWorkboard]);

  // ─── Handlers ───────────────────────────────────────────────────────────

  const handleSearchSubmit = (e: React.FormEvent) => { e.preventDefault(); setSearch(searchInput); setPage(1); };

  const handleSort = (column: typeof sortBy) => {
    if (sortBy === column) { setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc'); }
    else { setSortBy(column); setSortOrder(column === 'due_date' || column === 'days_remaining' ? 'asc' : 'desc'); }
    setPage(1);
  };

  const clearFilters = () => {
    setStatusFilter('all'); setQuarterFilter('all'); setFyFilter('');
    setSearch(''); setSearchInput(''); setPage(1);
  };

  const handleRowClick = (item: WorkboardItem) => {
    router.push(`/clients/${item.connection_id}?tab=bas`);
  };

  const SortIcon = ({ column }: { column: typeof sortBy }) => {
    if (sortBy !== column) return <ArrowUpDown className="h-3.5 w-3.5 text-muted-foreground/50" />;
    return sortOrder === 'asc'
      ? <ArrowUp className="h-3.5 w-3.5 text-primary" />
      : <ArrowDown className="h-3.5 w-3.5 text-primary" />;
  };

  // ─── Render ─────────────────────────────────────────────────────────────

  return (
    <div className="space-y-5">
      {/* Page Header */}
      <div>
        <h1 className="text-xl font-semibold tracking-tight">BAS Lodgements</h1>
        <p className="text-sm text-muted-foreground">
          Track and manage BAS deadlines across all clients
        </p>
      </div>

      {/* Summary Stat Cards */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        {[
          { label: 'Overdue', value: summary?.overdue, color: 'text-status-danger', dot: 'bg-status-danger', filter: 'overdue' },
          { label: 'Due This Week', value: summary?.due_this_week, color: 'text-status-warning', dot: 'bg-status-warning', filter: 'due_this_week' },
          { label: 'Due This Month', value: summary?.due_this_month, color: 'text-status-info', dot: 'bg-status-info', filter: 'upcoming' },
          { label: 'Lodged', value: summary?.lodged, color: 'text-status-success', dot: 'bg-status-success', filter: 'lodged' },
          { label: 'Not Started', value: summary?.not_started, color: 'text-muted-foreground', dot: 'bg-status-neutral', filter: 'all' },
        ].map((card) => (
          <Card
            key={card.label}
            className="cursor-pointer shadow-sm transition-shadow hover:shadow-md"
            onClick={() => { setStatusFilter(card.filter); setPage(1); }}
          >
            <CardContent className="p-4">
              <div className="flex items-center gap-2">
                <span className={cn('h-2 w-2 rounded-full', card.dot)} />
                <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  {card.label}
                </span>
              </div>
              {isSummaryLoading ? (
                <div className="mt-2 h-8 w-12 animate-pulse rounded bg-muted" />
              ) : (
                <p className={cn('mt-2 text-2xl font-bold tracking-tight tabular-nums', card.color)}>
                  {card.value ?? 0}
                </p>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Workboard Table Card */}
      <Card className="shadow-sm">
        {/* Filter Bar */}
        <CardHeader className="pb-3">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            {/* Status Tabs */}
            <div className="flex gap-1">
              {STATUS_TABS.map((tab) => (
                <button
                  key={tab.value}
                  onClick={() => { setStatusFilter(tab.value); setPage(1); }}
                  className={cn(
                    'rounded-md px-3 py-1.5 text-xs font-medium transition-colors',
                    statusFilter === tab.value
                      ? 'bg-primary text-primary-foreground'
                      : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                  )}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            <div className="flex items-center gap-2">
              {/* Quarter Filter */}
              <Select value={quarterFilter} onValueChange={(v) => { setQuarterFilter(v); setPage(1); }}>
                <SelectTrigger className="w-[130px]">
                  <SelectValue placeholder="Quarter" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Quarters</SelectItem>
                  <SelectItem value="Q1">Q1 (Jul-Sep)</SelectItem>
                  <SelectItem value="Q2">Q2 (Oct-Dec)</SelectItem>
                  <SelectItem value="Q3">Q3 (Jan-Mar)</SelectItem>
                  <SelectItem value="Q4">Q4 (Apr-Jun)</SelectItem>
                </SelectContent>
              </Select>

              {/* FY Filter */}
              <Select value={fyFilter || 'all'} onValueChange={(v) => { setFyFilter(v === 'all' ? '' : v); setPage(1); }}>
                <SelectTrigger className="w-[130px]">
                  <SelectValue placeholder="FY" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Years</SelectItem>
                  {fyOptions.map((fy) => (
                    <SelectItem key={fy} value={fy}>FY {fy}</SelectItem>
                  ))}
                </SelectContent>
              </Select>

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
          </div>
        </CardHeader>

        {/* Table Content */}
        <CardContent className="p-0">
          {/* Error */}
          {error && (
            <div className="flex items-center gap-3 border-b px-4 py-2.5 text-sm">
              <span className="h-2 w-2 rounded-full bg-status-danger" />
              <span className="text-status-danger">{error}</span>
              <Button variant="link" size="sm" className="ml-auto p-0 text-xs" onClick={() => { fetchWorkboard(); fetchSummary(); }}>
                Retry
              </Button>
            </div>
          )}

          {/* Loading */}
          {isLoading && (
            <div className="flex flex-col items-center justify-center py-16">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              <p className="mt-2 text-sm text-muted-foreground">Loading workboard...</p>
            </div>
          )}

          {/* Table */}
          {!isLoading && !error && (
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead className="cursor-pointer select-none" onClick={() => handleSort('client_name')}>
                    <div className="flex items-center gap-1">Client <SortIcon column="client_name" /></div>
                  </TableHead>
                  <TableHead className="hidden md:table-cell">Period</TableHead>
                  <TableHead className="cursor-pointer select-none" onClick={() => handleSort('due_date')}>
                    <div className="flex items-center gap-1">Due Date <SortIcon column="due_date" /></div>
                  </TableHead>
                  <TableHead className="cursor-pointer select-none" onClick={() => handleSort('days_remaining')}>
                    <div className="flex items-center gap-1">Days Left <SortIcon column="days_remaining" /></div>
                  </TableHead>
                  <TableHead className="cursor-pointer select-none text-center" onClick={() => handleSort('status')}>
                    <div className="flex items-center justify-center gap-1">Status <SortIcon column="status" /></div>
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.length === 0 ? (
                  <TableRow className="hover:bg-transparent">
                    <TableCell colSpan={5} className="py-16 text-center">
                      {statusFilter !== 'all' || search ? (
                        <div>
                          <p className="font-medium">No lodgements match your filters</p>
                          <Button variant="link" size="sm" className="mt-1" onClick={clearFilters}>Clear filters</Button>
                        </div>
                      ) : (
                        <div>
                          <FileText className="mx-auto h-10 w-10 text-muted-foreground/30" />
                          <p className="mt-3 font-medium">No BAS periods found</p>
                          <p className="mt-1 text-sm text-muted-foreground">
                            BAS periods will appear here when clients are synced
                          </p>
                        </div>
                      )}
                    </TableCell>
                  </TableRow>
                ) : (
                  items.map((item) => {
                    const urgency = getUrgencyConfig(item.urgency);
                    const sessionStatus = item.session_status ? getLodgementStatusConfig(item.session_status) : null;

                    return (
                      <TableRow
                        key={`${item.period_id}-${item.connection_id}`}
                        className={cn(
                          'cursor-pointer',
                          item.urgency === 'overdue' && 'bg-status-danger/5',
                          item.urgency === 'critical' && 'bg-status-warning/5'
                        )}
                        onClick={() => handleRowClick(item)}
                      >
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <span className={cn('h-1.5 w-1.5 rounded-full', urgency.dotColor)} />
                            <span className="font-medium">{item.client_name}</span>
                          </div>
                        </TableCell>
                        <TableCell className="hidden text-muted-foreground md:table-cell">
                          {item.period_display_name}
                          {item.quarter && <span className="ml-1.5 text-xs">Q{item.quarter}</span>}
                        </TableCell>
                        <TableCell className="tabular-nums">
                          {formatDate(item.due_date)}
                        </TableCell>
                        <TableCell>
                          <DaysRemainingBadge days={item.days_remaining} isLodged={item.is_lodged} />
                        </TableCell>
                        <TableCell className="text-center">
                          {sessionStatus ? (
                            <span className="inline-flex items-center gap-1.5 text-xs">
                              <span className={cn('h-1.5 w-1.5 rounded-full', sessionStatus.dotColor)} />
                              <span className="text-muted-foreground">{sessionStatus.label}</span>
                            </span>
                          ) : (
                            <span className="text-xs text-muted-foreground">Not Started</span>
                          )}
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
          <CardFooter className="justify-between border-t px-6 py-3">
            <div className="flex items-center gap-4">
              <span className="text-xs text-muted-foreground">
                {(page - 1) * limit + 1}–{Math.min(page * limit, total)} of {total}
              </span>
              <Select value={limit.toString()} onValueChange={(v) => { setLimit(Number(v)); setPage(1); }}>
                <SelectTrigger className="h-7 w-[70px] text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="25">25</SelectItem>
                  <SelectItem value="50">50</SelectItem>
                  <SelectItem value="100">100</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-center gap-1">
              <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => setPage(page - 1)} disabled={page === 1}>
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <span className="px-2 text-xs text-muted-foreground tabular-nums">{page} / {totalPages}</span>
              <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => setPage(page + 1)} disabled={page >= totalPages}>
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </CardFooter>
        )}
      </Card>
    </div>
  );
}
