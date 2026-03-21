'use client';

/**
 * Notifications & Actions Dashboard
 *
 * UX: List layout with summary stat cards + sortable table.
 * JTBD: #6 Stay Ahead of Changes — triage notifications by priority & deadline.
 */

import { useAuth } from '@clerk/nextjs';
import {
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  Bell,
  Check,
  CheckCheck,
  ChevronLeft,
  ChevronRight,
  Loader2,
  Search,
  Trash2,
  X,
} from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useCallback, useEffect, useState } from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
} from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { apiClient } from '@/lib/api-client';
import { getPriorityConfig } from '@/lib/constants/status';
import { formatDate, formatRelativeTime } from '@/lib/formatters';
import { cn } from '@/lib/utils';

// ─── Types ──────────────────────────────────────────────────────────────────

interface NotificationSummary {
  total_unread: number;
  high_priority: number;
  overdue: number;
  due_this_week: number;
}

interface Notification {
  id: string;
  notification_type: string;
  title: string;
  message: string | null;
  entity_type: string | null;
  entity_id: string | null;
  entity_context: Record<string, unknown> | null;
  is_read: boolean;
  read_at: string | null;
  created_at: string;
  priority: 'high' | 'medium' | 'low';
  due_date: string | null;
  days_remaining: number | null;
  client_name: string | null;
  connection_id: string | null;
}

interface NotificationListResponse {
  notifications: Notification[];
  total: number;
  unread_count: number;
  page: number;
  limit: number;
  has_more: boolean;
}

// ─── Filter Tabs ────────────────────────────────────────────────────────────

const STATUS_TABS = [
  { value: 'all', label: 'All' },
  { value: 'unread', label: 'Unread' },
  { value: 'read', label: 'Read' },
] as const;

const PRIORITY_TABS = [
  { value: 'all', label: 'All' },
  { value: 'high', label: 'High' },
  { value: 'medium', label: 'Medium' },
  { value: 'low', label: 'Low' },
] as const;

// ─── Days Remaining ─────────────────────────────────────────────────────────

function DaysRemainingBadge({ days }: { days: number | null }) {
  if (days === null) return <span className="text-muted-foreground">-</span>;
  if (days < 0) return <span className="text-xs font-semibold text-status-danger">{Math.abs(days)}d overdue</span>;
  if (days === 0) return <span className="text-xs font-semibold text-status-danger">Due today</span>;
  if (days === 1) return <span className="text-xs font-semibold text-status-warning">Due tomorrow</span>;
  if (days <= 7) return <span className="text-xs font-medium text-status-warning">{days}d left</span>;
  return <span className="text-xs text-muted-foreground">{days}d</span>;
}

// ─── Component ──────────────────────────────────────────────────────────────

export default function NotificationsPage() {
  const { getToken } = useAuth();
  const router = useRouter();

  const [summary, setSummary] = useState<NotificationSummary | null>(null);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSummaryLoading, setIsSummaryLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [search, setSearch] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [priorityFilter, setPriorityFilter] = useState<string>('all');

  const [sortBy, setSortBy] = useState<'priority' | 'due_date' | 'created_at' | 'client_name'>('created_at');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');

  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const limit = 25;

  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [isBulkActioning, setIsBulkActioning] = useState(false);

  // ─── Data Fetching ──────────────────────────────────────────────────────

  const fetchSummary = useCallback(async () => {
    try {
      setIsSummaryLoading(true);
      const token = await getToken();
      if (!token) return;
      const response = await apiClient.get('/api/v1/notifications/summary', {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (response.ok) setSummary(await response.json());
    } catch { /* silently fail */ } finally { setIsSummaryLoading(false); }
  }, [getToken]);

  const fetchNotifications = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const token = await getToken();
      if (!token) { setError('Not authenticated'); return; }

      const params = new URLSearchParams({
        page: page.toString(), limit: limit.toString(),
        sort_by: sortBy, sort_order: sortOrder,
      });
      if (statusFilter !== 'all') params.set('status', statusFilter);
      if (priorityFilter !== 'all') params.set('priority', priorityFilter);
      if (search) params.set('search', search);

      const response = await apiClient.get(`/api/v1/notifications/dashboard?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) throw new Error('Failed to fetch notifications');

      const data: NotificationListResponse = await response.json();
      setNotifications(data.notifications);
      setTotal(data.total);
      setHasMore(data.has_more);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally { setIsLoading(false); }
  }, [getToken, page, sortBy, sortOrder, statusFilter, priorityFilter, search]);

  useEffect(() => { fetchSummary(); fetchNotifications(); }, [fetchSummary, fetchNotifications]);

  // ─── Handlers ───────────────────────────────────────────────────────────

  const handleSearchSubmit = (e: React.FormEvent) => { e.preventDefault(); setSearch(searchInput); setPage(1); setSelectedIds(new Set()); };

  const handleSort = (column: typeof sortBy) => {
    if (sortBy === column) setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    else { setSortBy(column); setSortOrder('desc'); }
    setPage(1); setSelectedIds(new Set());
  };

  const clearFilters = () => {
    setStatusFilter('all'); setPriorityFilter('all');
    setSearch(''); setSearchInput(''); setPage(1); setSelectedIds(new Set());
  };

  const toggleSelectAll = () => {
    setSelectedIds(selectedIds.size === notifications.length ? new Set() : new Set(notifications.map(n => n.id)));
  };

  const toggleSelect = (id: string) => {
    const s = new Set(selectedIds);
    if (s.has(id)) s.delete(id); else s.add(id);
    setSelectedIds(s);
  };

  const handleBulkAction = async (action: 'read' | 'dismiss') => {
    if (selectedIds.size === 0) return;
    try {
      setIsBulkActioning(true);
      const token = await getToken();
      if (!token) return;
      const response = await apiClient.post(`/api/v1/notifications/bulk/${action}`, {
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ notification_ids: Array.from(selectedIds) }),
      });
      if (response.ok) { setSelectedIds(new Set()); fetchNotifications(); fetchSummary(); }
    } catch { /* silently fail */ } finally { setIsBulkActioning(false); }
  };

  const handleNotificationClick = (n: Notification) => {
    if (n.entity_type === 'bas_session' && n.connection_id) router.push(`/clients/${n.connection_id}?tab=bas`);
  };

  const totalPages = Math.ceil(total / limit);
  const hasFilters = statusFilter !== 'all' || priorityFilter !== 'all' || search;

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
        <h1 className="text-xl font-semibold tracking-tight">Notifications</h1>
        <p className="text-sm text-muted-foreground">
          Manage actions and deadlines across your client portfolio
        </p>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {[
          { label: 'Unread', value: summary?.total_unread, color: 'text-foreground', dot: 'bg-status-info', onClick: () => { setStatusFilter('unread'); setPage(1); } },
          { label: 'High Priority', value: summary?.high_priority, color: 'text-status-danger', dot: 'bg-status-danger', onClick: () => { setPriorityFilter('high'); setPage(1); } },
          { label: 'Overdue', value: summary?.overdue, color: 'text-status-danger', dot: 'bg-status-danger', onClick: () => { setPriorityFilter('high'); setPage(1); } },
          { label: 'Due This Week', value: summary?.due_this_week, color: 'text-status-warning', dot: 'bg-status-warning', onClick: () => { setPriorityFilter('medium'); setPage(1); } },
        ].map((card) => (
          <Card key={card.label} className="cursor-pointer shadow-sm transition-shadow hover:shadow-md" onClick={card.onClick}>
            <CardContent className="p-4">
              <div className="flex items-center gap-2">
                <span className={cn('h-2 w-2 rounded-full', card.dot)} />
                <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{card.label}</span>
              </div>
              {isSummaryLoading ? (
                <div className="mt-2 h-8 w-12 animate-pulse rounded bg-muted" />
              ) : (
                <p className={cn('mt-2 text-2xl font-bold tracking-tight tabular-nums', card.color)}>{card.value ?? 0}</p>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Bulk Action Bar */}
      {selectedIds.size > 0 && (
        <div className="flex items-center justify-between rounded-lg bg-foreground px-4 py-3 text-background">
          <span className="text-sm font-medium">{selectedIds.size} selected</span>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" className="text-background hover:bg-background/10" onClick={() => handleBulkAction('read')} disabled={isBulkActioning}>
              {isBulkActioning ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" /> : <CheckCheck className="mr-1.5 h-4 w-4" />}
              Mark Read
            </Button>
            <Button variant="ghost" size="sm" className="text-background hover:bg-background/10" onClick={() => handleBulkAction('dismiss')} disabled={isBulkActioning}>
              {isBulkActioning ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" /> : <Trash2 className="mr-1.5 h-4 w-4" />}
              Dismiss
            </Button>
            <Button variant="ghost" size="icon" className="h-7 w-7 text-background hover:bg-background/10" onClick={() => setSelectedIds(new Set())}>
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}

      {/* Notifications Table Card */}
      <Card className="shadow-sm">
        <CardHeader className="pb-3">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex gap-3">
              {/* Status Tabs */}
              <div className="flex gap-1">
                {STATUS_TABS.map((tab) => (
                  <Button key={tab.value} variant="ghost" size="sm"
                    onClick={() => { setStatusFilter(tab.value); setPage(1); }}
                    className={cn('h-auto rounded-md px-3 py-1.5 text-xs font-medium',
                      statusFilter === tab.value ? 'bg-primary text-primary-foreground hover:bg-primary/90' : 'text-muted-foreground hover:bg-muted hover:text-foreground')}>
                    {tab.label}
                  </Button>
                ))}
              </div>
              <span className="w-px bg-border" />
              {/* Priority Tabs */}
              <div className="flex gap-1">
                {PRIORITY_TABS.map((tab) => (
                  <Button key={tab.value} variant="ghost" size="sm"
                    onClick={() => { setPriorityFilter(tab.value); setPage(1); }}
                    className={cn('h-auto rounded-md px-3 py-1.5 text-xs font-medium',
                      priorityFilter === tab.value ? 'bg-primary text-primary-foreground hover:bg-primary/90' : 'text-muted-foreground hover:bg-muted hover:text-foreground')}>
                    {tab.label}
                  </Button>
                ))}
              </div>
            </div>

            <form onSubmit={handleSearchSubmit} className="relative w-full sm:max-w-xs">
              <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input value={searchInput} onChange={(e) => setSearchInput(e.target.value)} placeholder="Search notifications..." className="pl-9" />
            </form>
          </div>
        </CardHeader>

        <CardContent className="p-0">
          {error && (
            <div className="flex items-center gap-3 border-b px-6 py-4 text-sm">
              <span className="h-2 w-2 rounded-full bg-status-danger" />
              <span className="text-status-danger">{error}</span>
              <Button variant="link" size="sm" className="ml-auto p-0 text-xs" onClick={() => { fetchNotifications(); fetchSummary(); }}>Retry</Button>
            </div>
          )}

          {isLoading && (
            <div className="flex flex-col items-center justify-center py-16">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              <p className="mt-2 text-sm text-muted-foreground">Loading notifications...</p>
            </div>
          )}

          {!isLoading && !error && (
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead className="w-10">
                    <Checkbox
                      checked={notifications.length > 0 && selectedIds.size === notifications.length}
                      onCheckedChange={toggleSelectAll}
                    />
                  </TableHead>
                  <TableHead className="cursor-pointer select-none" onClick={() => handleSort('priority')}>
                    <div className="flex items-center gap-1">Priority <SortIcon column="priority" /></div>
                  </TableHead>
                  <TableHead>Notification</TableHead>
                  <TableHead className="hidden cursor-pointer select-none md:table-cell" onClick={() => handleSort('client_name')}>
                    <div className="flex items-center gap-1">Client <SortIcon column="client_name" /></div>
                  </TableHead>
                  <TableHead className="hidden cursor-pointer select-none md:table-cell" onClick={() => handleSort('due_date')}>
                    <div className="flex items-center gap-1">Due <SortIcon column="due_date" /></div>
                  </TableHead>
                  <TableHead className="text-center">Status</TableHead>
                  <TableHead className="cursor-pointer select-none text-right" onClick={() => handleSort('created_at')}>
                    <div className="flex items-center justify-end gap-1">Created <SortIcon column="created_at" /></div>
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {notifications.length === 0 ? (
                  <TableRow className="hover:bg-transparent">
                    <TableCell colSpan={7} className="py-16 text-center">
                      {hasFilters ? (
                        <div>
                          <p className="font-medium">No notifications match your filters</p>
                          <Button variant="link" size="sm" className="mt-1" onClick={clearFilters}>Clear filters</Button>
                        </div>
                      ) : (
                        <div>
                          <Bell className="mx-auto h-10 w-10 text-muted-foreground/30" />
                          <p className="mt-3 font-medium">All caught up!</p>
                          <p className="mt-1 text-sm text-muted-foreground">No notifications to display</p>
                        </div>
                      )}
                    </TableCell>
                  </TableRow>
                ) : (
                  notifications.map((n) => {
                    const priority = getPriorityConfig(n.priority);
                    const isSelected = selectedIds.has(n.id);

                    return (
                      <TableRow
                        key={n.id}
                        className={cn(
                          isSelected && 'bg-muted/50',
                          !n.is_read && 'bg-status-info/5'
                        )}
                      >
                        <TableCell>
                          <Checkbox checked={isSelected} onCheckedChange={() => toggleSelect(n.id)} />
                        </TableCell>
                        <TableCell>
                          <span className="inline-flex items-center gap-1.5 text-xs">
                            <span className={cn('h-1.5 w-1.5 rounded-full', priority.dotColor)} />
                            <span className={priority.textColor}>{priority.label}</span>
                          </span>
                        </TableCell>
                        <TableCell>
                          <Button variant="ghost" onClick={() => handleNotificationClick(n)} className="h-auto w-full justify-start p-0 text-left group hover:bg-transparent">
                            <div>
                              <p className={cn('text-sm group-hover:text-primary transition-colors', !n.is_read && 'font-semibold')}>
                                {n.title}
                              </p>
                              {n.message && <p className="text-xs text-muted-foreground mt-0.5 line-clamp-1">{n.message}</p>}
                            </div>
                          </Button>
                        </TableCell>
                        <TableCell className="hidden text-sm text-muted-foreground md:table-cell">
                          {n.client_name || '-'}
                        </TableCell>
                        <TableCell className="hidden md:table-cell">
                          <div>
                            <p className="text-xs text-muted-foreground">{formatDate(n.due_date)}</p>
                            <DaysRemainingBadge days={n.days_remaining} />
                          </div>
                        </TableCell>
                        <TableCell className="text-center">
                          {n.is_read ? (
                            <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                              <Check className="h-3 w-3" /> Read
                            </span>
                          ) : (
                            <Badge variant="secondary" className="text-[10px]">New</Badge>
                          )}
                        </TableCell>
                        <TableCell className="text-right text-xs text-muted-foreground">
                          {formatRelativeTime(n.created_at)}
                        </TableCell>
                      </TableRow>
                    );
                  })
                )}
              </TableBody>
            </Table>
          )}
        </CardContent>

        {totalPages > 1 && (
          <CardFooter className="justify-between border-t px-6 py-3">
            <span className="text-xs text-muted-foreground">
              {(page - 1) * limit + 1}–{Math.min(page * limit, total)} of {total}
            </span>
            <div className="flex items-center gap-1">
              <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => { setPage(page - 1); setSelectedIds(new Set()); }} disabled={page === 1}>
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <span className="px-2 text-xs text-muted-foreground tabular-nums">{page} / {totalPages}</span>
              <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => { setPage(page + 1); setSelectedIds(new Set()); }} disabled={!hasMore}>
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </CardFooter>
        )}
      </Card>
    </div>
  );
}
