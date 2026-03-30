'use client';

/**
 * TenantTable Component
 *
 * Displays a paginated, sortable, filterable table of tenants.
 *
 * Spec 022: Admin Dashboard (Internal)
 */

import {
  ArrowUpDown,
  ChevronLeft,
  ChevronRight,
  Search,
  X,
} from 'lucide-react';
import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';

import type {
  SortOrder,
  SubscriptionTierType,
  TenantListParams,
  TenantSortField,
  TenantStatusFilter,
  TenantSummary,
} from '@/types/admin';

interface TenantTableProps {
  tenants: TenantSummary[];
  total: number;
  page: number;
  limit: number;
  hasMore: boolean;
  isLoading: boolean;
  onParamsChange: (params: TenantListParams) => void;
  params: TenantListParams;
}

/**
 * Format cents to currency string.
 */
function formatCurrency(cents: number): string {
  return new Intl.NumberFormat('en-AU', {
    style: 'currency',
    currency: 'AUD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(cents / 100);
}

/**
 * Format date to readable string.
 */
function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('en-AU', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

/**
 * Tier badge component.
 */
function TierBadge({ tier }: { tier: SubscriptionTierType }) {
  const colors: Record<SubscriptionTierType, string> = {
    starter: 'bg-muted text-foreground',
    professional: 'bg-primary/10 text-primary',
    growth: 'bg-purple-500/10 text-purple-700',
    enterprise: 'bg-status-warning/10 text-status-warning',
  };

  return (
    <span
      className={`text-xs font-medium px-2 py-1 rounded ${colors[tier] || colors.starter}`}
    >
      {tier.charAt(0).toUpperCase() + tier.slice(1)}
    </span>
  );
}

/**
 * Status indicator component.
 */
function StatusIndicator({ isActive }: { isActive: boolean }) {
  return (
    <span className="flex items-center gap-2">
      <span
        className={`w-2 h-2 rounded-full ${
          isActive ? 'bg-status-success' : 'bg-status-danger'
        }`}
      />
      <span className={`text-sm ${isActive ? 'text-status-success' : 'text-status-danger'}`}>
        {isActive ? 'Active' : 'Inactive'}
      </span>
    </span>
  );
}

/**
 * Sortable column header.
 */
function SortableHeader({
  label,
  field,
  currentSortBy,
  currentSortOrder,
  onSort,
}: {
  label: string;
  field: TenantSortField;
  currentSortBy: TenantSortField;
  currentSortOrder: SortOrder;
  onSort: (field: TenantSortField) => void;
}) {
  const isActive = currentSortBy === field;

  return (
    <button
      onClick={() => onSort(field)}
      className="flex items-center gap-1 text-xs font-medium text-muted-foreground uppercase tracking-wider hover:text-foreground transition-colors"
    >
      {label}
      <ArrowUpDown
        className={`w-3 h-3 ${isActive ? 'text-foreground' : 'text-muted-foreground'}`}
      />
      {isActive && (
        <span className="text-muted-foreground">
          {currentSortOrder === 'asc' ? '(A-Z)' : '(Z-A)'}
        </span>
      )}
    </button>
  );
}

/**
 * Main TenantTable component.
 */
export function TenantTable({
  tenants,
  total,
  page,
  limit,
  hasMore,
  isLoading,
  onParamsChange,
  params,
}: TenantTableProps) {
  const [searchInput, setSearchInput] = useState(params.search || '');

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(() => {
      if (searchInput !== (params.search || '')) {
        onParamsChange({ ...params, search: searchInput || undefined, page: 1 });
      }
    }, 300);

    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- intentionally excluding params/onParamsChange to avoid infinite loop
  }, [searchInput]);

  const handleSort = useCallback(
    (field: TenantSortField) => {
      const newOrder: SortOrder =
        params.sort_by === field && params.sort_order === 'asc' ? 'desc' : 'asc';
      onParamsChange({ ...params, sort_by: field, sort_order: newOrder });
    },
    [params, onParamsChange]
  );

  const handleTierFilter = useCallback(
    (tier: SubscriptionTierType | '') => {
      onParamsChange({
        ...params,
        tier: tier || undefined,
        page: 1,
      });
    },
    [params, onParamsChange]
  );

  const handleStatusFilter = useCallback(
    (status: TenantStatusFilter) => {
      onParamsChange({ ...params, status, page: 1 });
    },
    [params, onParamsChange]
  );

  const handlePageChange = useCallback(
    (newPage: number) => {
      onParamsChange({ ...params, page: newPage });
    },
    [params, onParamsChange]
  );

  const clearSearch = useCallback(() => {
    setSearchInput('');
    onParamsChange({ ...params, search: undefined, page: 1 });
  }, [params, onParamsChange]);

  const startItem = (page - 1) * limit + 1;
  const endItem = Math.min(page * limit, total);

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-4">
        {/* Search */}
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input
            type="text"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            placeholder="Search tenants..."
            className="w-full pl-10 pr-10 py-2 bg-card border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/20"
          />
          {searchInput && (
            <button
              onClick={clearSearch}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* Tier filter */}
        <select
          value={params.tier || ''}
          onChange={(e) =>
            handleTierFilter(e.target.value as SubscriptionTierType | '')
          }
          className="px-4 py-2 bg-card border border-border rounded-lg text-foreground focus:outline-none focus:ring-2 focus:ring-primary/20"
        >
          <option value="">All Tiers</option>
          <option value="starter">Starter</option>
          <option value="professional">Professional</option>
          <option value="growth">Growth</option>
          <option value="enterprise">Enterprise</option>
        </select>

        {/* Status filter */}
        <select
          value={params.status || 'all'}
          onChange={(e) => handleStatusFilter(e.target.value as TenantStatusFilter)}
          className="px-4 py-2 bg-card border border-border rounded-lg text-foreground focus:outline-none focus:ring-2 focus:ring-primary/20"
        >
          <option value="all">All Status</option>
          <option value="active">Active</option>
          <option value="inactive">Inactive</option>
        </select>
      </div>

      {/* Table */}
      <div className="bg-card border border-border rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-muted">
              <tr>
                <th className="px-6 py-3 text-left">
                  <SortableHeader
                    label="Name"
                    field="name"
                    currentSortBy={params.sort_by || 'created_at'}
                    currentSortOrder={params.sort_order || 'desc'}
                    onSort={handleSort}
                  />
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Email
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Tier
                </th>
                <th className="px-6 py-3 text-left">
                  <SortableHeader
                    label="Clients"
                    field="client_count"
                    currentSortBy={params.sort_by || 'created_at'}
                    currentSortOrder={params.sort_order || 'desc'}
                    onSort={handleSort}
                  />
                </th>
                <th className="px-6 py-3 text-left">
                  <SortableHeader
                    label="MRR"
                    field="mrr"
                    currentSortBy={params.sort_by || 'created_at'}
                    currentSortOrder={params.sort_order || 'desc'}
                    onSort={handleSort}
                  />
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left">
                  <SortableHeader
                    label="Created"
                    field="created_at"
                    currentSortBy={params.sort_by || 'created_at'}
                    currentSortOrder={params.sort_order || 'desc'}
                    onSort={handleSort}
                  />
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {isLoading ? (
                // Loading skeleton
                Array.from({ length: 5 }).map((_, i) => (
                  <tr key={i} className="animate-pulse">
                    <td className="px-6 py-4">
                      <div className="h-4 bg-muted rounded w-32" />
                    </td>
                    <td className="px-6 py-4">
                      <div className="h-4 bg-muted rounded w-40" />
                    </td>
                    <td className="px-6 py-4">
                      <div className="h-4 bg-muted rounded w-20" />
                    </td>
                    <td className="px-6 py-4">
                      <div className="h-4 bg-muted rounded w-16" />
                    </td>
                    <td className="px-6 py-4">
                      <div className="h-4 bg-muted rounded w-16" />
                    </td>
                    <td className="px-6 py-4">
                      <div className="h-4 bg-muted rounded w-16" />
                    </td>
                    <td className="px-6 py-4">
                      <div className="h-4 bg-muted rounded w-24" />
                    </td>
                  </tr>
                ))
              ) : tenants.length === 0 ? (
                <tr>
                  <td
                    colSpan={7}
                    className="px-6 py-12 text-center text-muted-foreground"
                  >
                    No tenants found
                  </td>
                </tr>
              ) : (
                tenants.map((tenant) => (
                  <tr
                    key={tenant.id}
                    className="hover:bg-muted transition-colors"
                  >
                    <td className="px-6 py-4">
                      <Link
                        href={`/internal/admin/customers/${tenant.id}`}
                        className="text-sm font-medium text-foreground hover:text-primary transition-colors"
                      >
                        {tenant.name}
                      </Link>
                    </td>
                    <td className="px-6 py-4 text-sm text-muted-foreground">
                      {tenant.owner_email || '-'}
                    </td>
                    <td className="px-6 py-4">
                      <TierBadge tier={tenant.tier} />
                    </td>
                    <td className="px-6 py-4 text-sm text-foreground">
                      {tenant.client_count}
                      {tenant.client_limit && (
                        <span className="text-muted-foreground">
                          {' '}/ {tenant.client_limit}
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-sm text-foreground">
                      {formatCurrency(tenant.mrr_cents)}
                    </td>
                    <td className="px-6 py-4">
                      <StatusIndicator isActive={tenant.is_active} />
                    </td>
                    <td className="px-6 py-4 text-sm text-muted-foreground">
                      {formatDate(tenant.created_at)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div className="px-6 py-4 border-t border-border flex items-center justify-between">
          <div className="text-sm text-muted-foreground">
            Showing {startItem} to {endItem} of {total} tenants
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => handlePageChange(page - 1)}
              disabled={page <= 1}
              className="p-2 rounded-lg bg-muted text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="text-sm text-muted-foreground">
              Page {page} of {Math.ceil(total / limit)}
            </span>
            <button
              onClick={() => handlePageChange(page + 1)}
              disabled={!hasMore}
              className="p-2 rounded-lg bg-muted text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default TenantTable;
