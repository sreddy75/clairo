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

import { useAuth, useUser } from '@clerk/nextjs';
import {
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  Building2,
  ChevronLeft,
  ChevronRight,
  Download,
  Loader2,
  MoreHorizontal,
  Plus,
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
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
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
import type { TenantUser } from '@/lib/api/users';
import { listTenantUsers } from '@/lib/api/users';
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

interface TeamMemberSummary {
  id: string | null;
  name: string;
  client_count: number;
}

interface DashboardSummary {
  total_clients: number;
  active_clients: number;
  excluded_count: number;
  total_sales: string;
  total_purchases: string;
  gst_collected: string;
  gst_paid: string;
  net_gst: string;
  status_counts: StatusCounts;
  quality: QualitySummary;
  team_members: TeamMemberSummary[];
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
  assigned_user_id: string | null;
  assigned_user_name: string | null;
  accounting_software: string;
  has_xero_connection: boolean;
  xero_connection_id: string | null;
  notes_preview: string | null;
  unreconciled_count: number;
  manual_status: string | null;
  exclusion: { id: string; reason: string | null; excluded_by_name: string | null; excluded_at: string } | null;
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
  { value: 'needs_attention', label: 'Needs Review' },
  { value: 'ready', label: 'Ready' },
  { value: 'no_activity', label: 'No Activity' },
  { value: 'excluded', label: 'Excluded' },
] as const;

// ─── Component ──────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const { getToken, userId } = useAuth();
  const { user: clerkUser } = useUser();
  const userRole = clerkUser?.publicMetadata?.role as string | undefined;
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
  const [selectedAssignee, setSelectedAssignee] = useState<string>('');
  const [teamMembers, setTeamMembers] = useState<TenantUser[]>([]);
  const [assigningClient, setAssigningClient] = useState<string | null>(null);
  const [showAddClient, setShowAddClient] = useState(false);
  const [addClientName, setAddClientName] = useState('');
  const [addClientAbn, setAddClientAbn] = useState('');
  const [addClientSoftware, setAddClientSoftware] = useState('quickbooks');
  const [addingClient, setAddingClient] = useState(false);
  const [insightsExpanded, setInsightsExpanded] = useState(false);
  const [excludeClientId, setExcludeClientId] = useState<string | null>(null);
  const [excludeReason, setExcludeReason] = useState('dormant');
  const [excluding, setExcluding] = useState(false);
  const [selectedRows, setSelectedRows] = useState<Set<string>>(new Set());
  const [bulkAssigning, setBulkAssigning] = useState(false);

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
      if (selectedStatus === 'excluded') {
        params.set('show_excluded', 'true');
      } else if (selectedStatus) {
        params.set('status', selectedStatus);
      }
      if (search) params.set('search', search);
      if (selectedAssignee && selectedAssignee !== 'unassigned') {
        params.set('assigned_user_id', selectedAssignee);
      }
      if (selectedAssignee === 'unassigned') {
        params.set('show_unassigned', 'true');
      }

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
  }, [page, sortBy, sortOrder, selectedStatus, search, selectedAssignee]);

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
          await Promise.all([
            fetchSummary(token, quarter),
            fetchClients(token, quarter),
            listTenantUsers(token).then((r) => {
              const active = r.users.filter((u) => u.is_active);
              setTeamMembers(active);
              // Default to "My Clients" for non-admin users
              if (userRole && userRole !== 'admin' && userRole !== 'super_admin' && userId) {
                const me = active.find((u) => u.clerk_id === userId);
                if (me) setSelectedAssignee(me.id);
              }
            }).catch(() => {}),
          ]);
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

  const handleAssign = async (clientId: string, userId: string | null) => {
    setAssigningClient(clientId);
    try {
      const token = await getToken();
      if (!token) return;
      const response = await apiClient.patch(`/api/v1/clients/${clientId}/assign`, {
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ assigned_user_id: userId || null }),
      });
      if (response.ok && selectedQuarter) {
        await fetchClients(token, selectedQuarter);
      }
    } catch {
      // Could add toast
    } finally {
      setAssigningClient(null);
    }
  };

  const handleAddClient = async () => {
    if (!addClientName.trim()) return;
    setAddingClient(true);
    try {
      const token = await getToken();
      if (!token) return;
      const response = await apiClient.post('/api/v1/clients/manual', {
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: addClientName.trim(),
          abn: addClientAbn.trim() || undefined,
          accounting_software: addClientSoftware,
        }),
      });
      if (response.ok && selectedQuarter) {
        setShowAddClient(false);
        setAddClientName('');
        setAddClientAbn('');
        setAddClientSoftware('quickbooks');
        await fetchClients(token, selectedQuarter);
      }
    } catch {
      // Could add toast
    } finally {
      setAddingClient(false);
    }
  };

  const handleExcludeConfirm = async () => {
    if (!excludeClientId || !selectedQuarter) return;
    setExcluding(true);
    try {
      const token = await getToken();
      if (!token) return;
      const fyYearStr = `${selectedQuarter.fy_year - 1}-${String(selectedQuarter.fy_year).slice(-2)}`;
      const resp = await apiClient.post(`/api/v1/clients/${excludeClientId}/exclusions`, {
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          quarter: selectedQuarter.quarter,
          fy_year: fyYearStr,
          reason: excludeReason,
        }),
      });
      if (resp.ok || resp.status === 409) {
        setExcludeClientId(null);
        await Promise.all([fetchSummary(token, selectedQuarter), fetchClients(token, selectedQuarter)]);
      }
    } finally {
      setExcluding(false);
    }
  };

  const handleInclude = async (clientId: string, exclusionId: string) => {
    const token = await getToken();
    if (!token || !selectedQuarter) return;
    await apiClient.delete(`/api/v1/clients/${clientId}/exclusions/${exclusionId}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    await Promise.all([fetchSummary(token, selectedQuarter), fetchClients(token, selectedQuarter)]);
  };

  const handleBulkAssign = async (assigneeId: string | null) => {
    if (selectedRows.size === 0) return;
    setBulkAssigning(true);
    try {
      const token = await getToken();
      if (!token || !selectedQuarter) return;
      await apiClient.post('/api/v1/clients/bulk-assign', {
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          client_ids: Array.from(selectedRows),
          assigned_user_id: assigneeId || null,
        }),
      });
      setSelectedRows(new Set());
      await fetchClients(token, selectedQuarter);
    } catch {
      // silent
    } finally {
      setBulkAssigning(false);
    }
  };

  const toggleRow = (id: string) => {
    setSelectedRows((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const toggleAllRows = () => {
    if (selectedRows.size === clients.length) {
      setSelectedRows(new Set());
    } else {
      setSelectedRows(new Set(clients.map((c) => c.id)));
    }
  };

  const handleManualStatus = async (clientId: string, newStatus: string) => {
    try {
      const token = await getToken();
      if (!token || !selectedQuarter) return;
      await apiClient.patch(`/api/v1/clients/${clientId}/manual-status`, {
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ manual_status: newStatus }),
      });
      await fetchClients(token, selectedQuarter);
    } catch {
      // silent
    }
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

          <Button size="sm" onClick={() => setShowAddClient(true)}>
            <Plus className="h-4 w-4" />
            <span className="hidden sm:inline ml-1.5">Add Client</span>
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
                {summary.status_counts.ready}
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                All items ready
              </p>
            </CardContent>
          </Card>

          {/* Needs Attention */}
          <Card
            className="cursor-pointer shadow-sm transition-shadow hover:shadow-md"
            onClick={() => { setSelectedStatus('needs_attention'); setPage(1); }}
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

      {/* ── Insights — Attention Items (collapsible) ────────────────── */}
      <div>
        <button
          onClick={() => setInsightsExpanded(!insightsExpanded)}
          className="flex items-center gap-2 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors mb-2"
        >
          <ChevronRight className={cn('h-3.5 w-3.5 transition-transform', insightsExpanded && 'rotate-90')} />
          Attention Needed
        </button>
        {insightsExpanded && <InsightsWidget />}
      </div>

      {/* Bulk Action Bar */}
      {selectedRows.size > 0 && (
        <div className="flex items-center gap-3 rounded-lg border bg-muted/50 px-4 py-2">
          <span className="text-sm font-medium">{selectedRows.size} selected</span>
          <span className="text-muted-foreground">|</span>
          <span className="text-xs text-muted-foreground">Assign to:</span>
          <select
            onChange={(e) => { handleBulkAssign(e.target.value || null); e.target.value = ''; }}
            disabled={bulkAssigning}
            className="h-7 rounded border border-input bg-background px-2 text-xs"
            defaultValue=""
          >
            <option value="" disabled>Select member...</option>
            <option value="">Unassign all</option>
            {teamMembers.map((tm) => (
              <option key={tm.id} value={tm.id}>{tm.display_name || tm.email}</option>
            ))}
          </select>
          {bulkAssigning && <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />}
          <button
            onClick={() => setSelectedRows(new Set())}
            className="ml-auto text-xs text-muted-foreground hover:text-foreground"
          >
            Clear selection
          </button>
        </div>
      )}

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
                  : tab.value === 'needs_attention'
                    ? (summary?.status_counts.needs_review ?? 0) + (summary?.status_counts.missing_data ?? 0)
                    : tab.value === 'excluded'
                      ? (summary?.excluded_count ?? 0)
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

            {/* Team Filter */}
            <select
              value={selectedAssignee}
              onChange={(e) => { setSelectedAssignee(e.target.value); setPage(1); }}
              className="h-8 rounded-md border border-input bg-background px-2 text-xs text-foreground"
            >
              <option value="">All Members</option>
              {summary?.team_members?.filter((tm: { id: string | null }) => tm.id).map((tm: { id: string | null; name: string; client_count: number }) => (
                <option key={tm.id} value={tm.id!}>
                  {tm.name} ({tm.client_count})
                </option>
              ))}
              <option value="unassigned">Unassigned</option>
            </select>

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
                  <TableHead className="w-[32px]">
                    <input
                      type="checkbox"
                      checked={selectedRows.size > 0 && selectedRows.size === clients.length}
                      onChange={toggleAllRows}
                      className="accent-primary"
                    />
                  </TableHead>
                  <SortableHead column="organization_name" label="Client" sortBy={sortBy} onSort={handleSort}>
                    <SortIcon column="organization_name" />
                  </SortableHead>
                  <TableHead className="hidden md:table-cell">Assigned</TableHead>
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
                  <TableHead className="hidden text-center lg:table-cell">Unrec.</TableHead>
                  <TableHead className="text-center">Status</TableHead>
                  <TableHead className="hidden text-right md:table-cell">Synced</TableHead>
                  <TableHead className="w-[40px]"></TableHead>
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
                      <TableRow key={client.id} className={cn(isInactive && 'opacity-50', selectedRows.has(client.id) && 'bg-primary/5')}>
                        <TableCell className="w-[32px]">
                          <input
                            type="checkbox"
                            checked={selectedRows.has(client.id)}
                            onChange={() => toggleRow(client.id)}
                            className="accent-primary"
                          />
                        </TableCell>
                        <TableCell className="font-medium">
                          <div className="flex items-center gap-1.5">
                            <Link
                              href={`/clients/${client.xero_connection_id || client.id}`}
                              className="hover:text-primary transition-colors"
                            >
                              {client.organization_name}
                            </Link>
                            {(() => {
                              const sw = client.accounting_software;
                              const softwareConfig: Record<string, { label: string; className: string }> = {
                                xero: { label: 'Xero', className: 'bg-[#13B5EA]/10 text-[#13B5EA] border border-[#13B5EA]/20' },
                                quickbooks: { label: 'QB', className: 'bg-emerald-50 text-emerald-700 border border-emerald-200' },
                                myob: { label: 'MYOB', className: 'bg-purple-50 text-purple-700 border border-purple-200' },
                                email: { label: 'Email', className: 'bg-amber-50 text-amber-700 border border-amber-200' },
                                other: { label: 'Other', className: 'bg-stone-100 text-stone-600 border border-stone-200' },
                                unknown: { label: '?', className: 'bg-stone-100 text-stone-500 border border-stone-200' },
                              };
                              const cfg = softwareConfig[sw] ?? softwareConfig['unknown']!;
                              return (
                                <span className={cn('rounded-full px-1.5 py-0.5 text-[10px] font-semibold', cfg.className)}>
                                  {cfg.label}
                                </span>
                              );
                            })()}
                          </div>
                        </TableCell>
                        <TableCell className="hidden md:table-cell">
                          <select
                            value={client.assigned_user_id || ''}
                            onChange={(e) => handleAssign(client.id, e.target.value || null)}
                            disabled={assigningClient === client.id}
                            className="h-7 w-[120px] rounded border border-input bg-background px-1.5 text-xs text-foreground disabled:opacity-50"
                          >
                            <option value="">Unassigned</option>
                            {teamMembers.map((tm) => (
                              <option key={tm.id} value={tm.id}>
                                {tm.display_name || tm.email}
                              </option>
                            ))}
                          </select>
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
                        <TableCell className={cn(
                          'hidden text-center tabular-nums text-xs lg:table-cell',
                          client.unreconciled_count > 5 ? 'text-amber-600 font-medium' : 'text-muted-foreground'
                        )}>
                          {client.has_xero_connection ? client.unreconciled_count : '—'}
                        </TableCell>
                        <TableCell className="text-center">
                          {!client.has_xero_connection ? (
                            <select
                              value={client.manual_status || 'not_started'}
                              onChange={(e) => handleManualStatus(client.id, e.target.value)}
                              className="h-6 rounded border border-input bg-background px-1 text-[11px] text-foreground"
                            >
                              <option value="not_started">Not Started</option>
                              <option value="in_progress">In Progress</option>
                              <option value="completed">Completed</option>
                              <option value="lodged">Lodged</option>
                            </select>
                          ) : (
                            <span className="inline-flex items-center gap-1.5 text-xs">
                              <span className={cn('h-1.5 w-1.5 rounded-full', status.dotColor)} />
                              <span className="text-muted-foreground">{status.label}</span>
                            </span>
                          )}
                        </TableCell>
                        <TableCell className="hidden text-right text-xs text-muted-foreground md:table-cell">
                          {formatRelativeTime(client.last_synced_at)}
                        </TableCell>
                        <TableCell>
                          {selectedStatus === 'excluded' && client.exclusion ? (
                            <button
                              onClick={() => handleInclude(client.id, client.exclusion!.id)}
                              className="text-xs text-primary hover:underline"
                            >
                              Include
                            </button>
                          ) : selectedStatus !== 'excluded' ? (
                            <button
                              onClick={() => { setExcludeClientId(client.id); setExcludeReason('dormant'); }}
                              className="text-xs text-muted-foreground hover:text-foreground"
                              title="Exclude from this quarter"
                            >
                              <MoreHorizontal className="h-4 w-4" />
                            </button>
                          ) : null}
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

      {/* Add Client Dialog */}
      <Dialog open={showAddClient} onOpenChange={setShowAddClient}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Add Client</DialogTitle>
            <DialogDescription>Add a non-Xero client to your practice.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label htmlFor="client-name">Business name</Label>
              <Input
                id="client-name"
                placeholder="Smith & Co Pty Ltd"
                value={addClientName}
                onChange={(e) => setAddClientName(e.target.value)}
                disabled={addingClient}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="client-abn">ABN (optional)</Label>
              <Input
                id="client-abn"
                placeholder="12345678901"
                value={addClientAbn}
                onChange={(e) => setAddClientAbn(e.target.value)}
                disabled={addingClient}
                maxLength={11}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="client-software">Accounting software</Label>
              <select
                id="client-software"
                value={addClientSoftware}
                onChange={(e) => setAddClientSoftware(e.target.value)}
                disabled={addingClient}
                className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
              >
                <option value="quickbooks">QuickBooks</option>
                <option value="myob">MYOB</option>
                <option value="email">Email-based</option>
                <option value="other">Other</option>
              </select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowAddClient(false)} disabled={addingClient}>
              Cancel
            </Button>
            <Button onClick={handleAddClient} disabled={addingClient || !addClientName.trim()}>
              {addingClient ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Plus className="mr-2 h-4 w-4" />}
              Add Client
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Exclude Client Dialog */}
      <Dialog open={!!excludeClientId} onOpenChange={(open) => { if (!open) setExcludeClientId(null); }}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>Exclude from Quarter</DialogTitle>
            <DialogDescription>
              This client won&apos;t appear in the active list for this quarter.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <Label>Reason</Label>
            <div className="space-y-2">
              {[
                { value: 'dormant', label: 'Dormant entity' },
                { value: 'lodged_externally', label: 'Lodged externally' },
                { value: 'gst_cancelled', label: 'GST cancelled' },
                { value: 'left_practice', label: 'Left practice' },
                { value: 'other', label: 'Other' },
              ].map((opt) => (
                <label key={opt.value} className="flex items-center gap-2 text-sm cursor-pointer">
                  <input
                    type="radio"
                    name="exclude-reason"
                    value={opt.value}
                    checked={excludeReason === opt.value}
                    onChange={() => setExcludeReason(opt.value)}
                    className="accent-primary"
                  />
                  {opt.label}
                </label>
              ))}
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setExcludeClientId(null)} disabled={excluding}>
              Cancel
            </Button>
            <Button onClick={handleExcludeConfirm} disabled={excluding}>
              {excluding && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Exclude
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
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
