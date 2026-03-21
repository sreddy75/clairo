'use client';

/**
 * Client List Page
 *
 * CRITICAL: In Clairo, "client" = XeroConnection = one business = one BAS to lodge.
 * This page lists client BUSINESSES (XeroConnections), NOT contacts.
 *
 * UX: List layout — filter tabs + search + table in one Card.
 * JTBD: #1 Triage (subset) — name + status dot + key metric + data freshness.
 */

import { useAuth } from '@clerk/nextjs';
import {
  Building2,
  ChevronLeft,
  ChevronRight,
  Download,
  Loader2,
  Search,
} from 'lucide-react';
import Link from 'next/link';
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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useBulkImportApi } from '@/lib/api/bulk-import';
import { apiClient } from '@/lib/api-client';
import { getStatusConfig } from '@/lib/constants/status';
import { formatCurrency, formatRelativeTime } from '@/lib/formatters';
import { cn } from '@/lib/utils';

// ─── Types ──────────────────────────────────────────────────────────────────

interface ClientBusiness {
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
  last_synced_at: string | null;
}

interface ClientListResponse {
  clients: ClientBusiness[];
  total: number;
  page: number;
  limit: number;
}

// ─── Status Filter Tabs ─────────────────────────────────────────────────────

const STATUS_TABS = [
  { value: '', label: 'All' },
  { value: 'needs_review', label: 'Needs Review' },
  { value: 'ready', label: 'Ready' },
  { value: 'no_activity', label: 'No Activity' },
] as const;

// ─── Component ──────────────────────────────────────────────────────────────

export default function ClientsPage() {
  const { getToken } = useAuth();
  const bulkImportApi = useBulkImportApi();
  const [clients, setClients] = useState<ClientBusiness[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isImporting, setIsImporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const limit = 25;

  const handleBulkImport = async () => {
    try {
      setIsImporting(true);
      setError(null);
      const redirectUri = `${window.location.origin}/clients/import`;
      const result = await bulkImportApi.initiateBulkImport(redirectUri);
      window.location.href = result.auth_url;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start bulk import');
      setIsImporting(false);
    }
  };

  const fetchClients = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const token = await getToken();
      if (!token) { setError('Not authenticated'); return; }

      const params = new URLSearchParams({ page: page.toString(), limit: limit.toString() });
      if (search) params.set('search', search);
      if (statusFilter) params.set('status', statusFilter);

      const response = await apiClient.get(`/api/v1/clients?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) throw new Error('Failed to fetch clients');

      const data: ClientListResponse = await response.json();
      setClients(data.clients);
      setTotal(data.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setIsLoading(false);
    }
  }, [getToken, page, search, statusFilter]);

  useEffect(() => { fetchClients(); }, [fetchClients]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setSearch(searchInput);
    setPage(1);
  };

  const totalPages = Math.ceil(total / limit);

  // ─── Render ─────────────────────────────────────────────────────────────

  return (
    <div className="space-y-5">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Clients</h1>
          <p className="text-sm text-muted-foreground">
            {total > 0
              ? `${total} client business${total !== 1 ? 'es' : ''} connected`
              : 'View and manage your client businesses'}
          </p>
        </div>
        <Button onClick={handleBulkImport} disabled={isImporting} size="sm">
          {isImporting ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" /> : <Download className="mr-1.5 h-4 w-4" />}
          Import from Xero
        </Button>
      </div>

      {/* Client Table Card */}
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

            {/* Search */}
            <form onSubmit={handleSearch} className="relative w-full sm:max-w-xs">
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
          {/* Error */}
          {error && (
            <div className="flex items-center gap-3 border-b px-6 py-4 text-sm">
              <span className="h-2 w-2 rounded-full bg-status-danger" />
              <span className="text-status-danger">{error}</span>
              <Button variant="link" size="sm" className="ml-auto p-0 text-xs" onClick={fetchClients}>
                Retry
              </Button>
            </div>
          )}

          {/* Loading */}
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
                  <TableHead>Client</TableHead>
                  <TableHead className="text-center">Status</TableHead>
                  <TableHead className="text-right">Net GST</TableHead>
                  <TableHead className="hidden text-center md:table-cell">Activity</TableHead>
                  <TableHead className="hidden text-right md:table-cell">Synced</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {clients.length === 0 ? (
                  <TableRow className="hover:bg-transparent">
                    <TableCell colSpan={5} className="py-16 text-center">
                      {search || statusFilter ? (
                        <div>
                          <p className="font-medium">No clients match your filters</p>
                          <Button
                            variant="link" size="sm" className="mt-1"
                            onClick={() => { setSearch(''); setSearchInput(''); setStatusFilter(''); setPage(1); }}
                          >
                            Clear filters
                          </Button>
                        </div>
                      ) : (
                        <div>
                          <Building2 className="mx-auto h-10 w-10 text-muted-foreground/30" />
                          <p className="mt-3 font-medium">No client businesses found</p>
                          <p className="mt-1 text-sm text-muted-foreground">
                            Connect a Xero organization to see your clients
                          </p>
                          <Button variant="outline" size="sm" className="mt-3" asChild>
                            <Link href="/settings/integrations">Connect Xero</Link>
                          </Button>
                        </div>
                      )}
                    </TableCell>
                  </TableRow>
                ) : (
                  clients.map((client) => {
                    const status = getStatusConfig(client.bas_status);
                    const isInactive = client.bas_status === 'no_activity';
                    const netGst = parseFloat(client.net_gst);

                    return (
                      <TableRow key={client.id} className={cn(isInactive && 'opacity-50')}>
                        <TableCell>
                          <Link href={`/clients/${client.id}`} className="group">
                            <p className="font-medium group-hover:text-primary transition-colors">
                              {client.organization_name}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              {client.invoice_count} invoices, {client.transaction_count} txns
                            </p>
                          </Link>
                        </TableCell>
                        <TableCell className="text-center">
                          <span className="inline-flex items-center gap-1.5 text-xs">
                            <span className={cn('h-1.5 w-1.5 rounded-full', status.dotColor)} />
                            <span className="text-muted-foreground">{status.label}</span>
                          </span>
                        </TableCell>
                        <TableCell className="text-right">
                          <span className={cn(
                            'tabular-nums font-medium',
                            !isInactive && netGst < 0 && 'text-status-danger'
                          )}>
                            {formatCurrency(client.net_gst)}
                          </span>
                        </TableCell>
                        <TableCell className="hidden text-center tabular-nums md:table-cell">
                          {client.activity_count}
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
          <CardFooter className="justify-between border-t px-6 py-3">
            <span className="text-xs text-muted-foreground">
              {(page - 1) * limit + 1}–{Math.min(page * limit, total)} of {total}
            </span>
            <div className="flex items-center gap-1">
              <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}>
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <span className="px-2 text-xs text-muted-foreground tabular-nums">{page} / {totalPages}</span>
              <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page >= totalPages}>
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </CardFooter>
        )}
      </Card>
    </div>
  );
}
