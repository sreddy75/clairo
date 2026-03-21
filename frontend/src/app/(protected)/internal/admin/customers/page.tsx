'use client';

/**
 * Admin Customers List Page
 *
 * Displays a paginated, searchable list of all tenants (customers).
 *
 * Spec 022: Admin Dashboard (Internal)
 */

import { AlertTriangle, Plus, RefreshCw, Users } from 'lucide-react';
import { useState } from 'react';

import { useTenants } from '@/hooks/useAdminDashboard';
import type { TenantListParams } from '@/types/admin';

import { TenantTable } from '../components/TenantTable';

/**
 * Customers list page.
 */
export default function CustomersPage() {
  const [params, setParams] = useState<TenantListParams>({
    page: 1,
    limit: 20,
    sort_by: 'created_at',
    sort_order: 'desc',
  });

  const { data, isLoading, error, refetch, isFetching } = useTenants(params);

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground flex items-center gap-3">
            <Users className="w-7 h-7 text-primary" />
            Customers
          </h1>
          <p className="text-muted-foreground mt-1">
            Manage all tenant accounts and subscriptions
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="flex items-center gap-2 px-4 py-2 bg-muted text-foreground rounded-lg hover:bg-muted/80 transition-colors disabled:opacity-50"
          >
            <RefreshCw
              className={`w-4 h-4 ${isFetching ? 'animate-spin' : ''}`}
            />
            Refresh
          </button>
          <button className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors">
            <Plus className="w-4 h-4" />
            Add Tenant
          </button>
        </div>
      </div>

      {/* Error state */}
      {error && (
        <div className="bg-status-danger/10 border border-status-danger/20 rounded-lg p-4 flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 text-status-danger" />
          <div>
            <p className="text-status-danger font-medium">Failed to load customers</p>
            <p className="text-sm text-status-danger/80">
              {error instanceof Error ? error.message : 'Unknown error'}
            </p>
          </div>
          <button
            onClick={() => refetch()}
            className="ml-auto px-3 py-1 text-sm bg-status-danger/10 text-status-danger rounded hover:bg-status-danger/20 transition-colors"
          >
            Retry
          </button>
        </div>
      )}

      {/* Summary cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-card border border-border rounded-xl p-4">
          <p className="text-sm text-muted-foreground">Total Customers</p>
          <p className="text-2xl font-bold text-foreground mt-1">
            {isLoading ? '-' : data?.total ?? 0}
          </p>
        </div>
        <div className="bg-card border border-border rounded-xl p-4">
          <p className="text-sm text-muted-foreground">Active</p>
          <p className="text-2xl font-bold text-status-success mt-1">
            {isLoading
              ? '-'
              : data?.tenants.filter((t) => t.is_active).length ?? 0}
          </p>
        </div>
        <div className="bg-card border border-border rounded-xl p-4">
          <p className="text-sm text-muted-foreground">Current Page</p>
          <p className="text-2xl font-bold text-foreground mt-1">
            {params.page} / {Math.ceil((data?.total ?? 0) / (params.limit ?? 20))}
          </p>
        </div>
        <div className="bg-card border border-border rounded-xl p-4">
          <p className="text-sm text-muted-foreground">Showing</p>
          <p className="text-2xl font-bold text-foreground mt-1">
            {isLoading ? '-' : data?.tenants.length ?? 0} tenants
          </p>
        </div>
      </div>

      {/* Tenant table */}
      <TenantTable
        tenants={data?.tenants ?? []}
        total={data?.total ?? 0}
        page={data?.page ?? 1}
        limit={data?.limit ?? 20}
        hasMore={data?.has_more ?? false}
        isLoading={isLoading}
        params={params}
        onParamsChange={setParams}
      />
    </div>
  );
}
