'use client';

/**
 * Bulk Import Configuration Page (Phase 035 - T017)
 *
 * Post-OAuth configuration screen where the accountant can:
 * - See all authorized Xero organizations
 * - Select which orgs to import
 * - Assign team members to each client
 * - Set connection type (practice/client)
 * - See plan limit warnings
 */

import { useAuth } from '@clerk/nextjs';
import {
  AlertTriangle,
  ArrowLeft,
  Check,
  CheckCircle2,
  Link2,
  Loader2,
  XCircle,
} from 'lucide-react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense, useCallback, useEffect, useRef, useState } from 'react';

import { useBulkImportApi } from '@/lib/api/bulk-import';
import { listTenantUsers, type TenantUser } from '@/lib/api/users';
import type {
  BulkImportCallbackResponse,
  ImportOrgSelection,
} from '@/types/bulk-import';

function ImportConfigContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { getToken } = useAuth();
  const bulkImportApi = useBulkImportApi();
  const processedRef = useRef(false);

  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [callbackData, setCallbackData] = useState<BulkImportCallbackResponse | null>(null);
  const [oauthState, setOauthState] = useState<string | null>(null);
  const [teamMembers, setTeamMembers] = useState<TenantUser[]>([]);

  // Per-org selection state
  const [selections, setSelections] = useState<
    Map<string, ImportOrgSelection>
  >(new Map());

  // Process OAuth callback
  const processCallback = useCallback(async () => {
    const code = searchParams.get('code');
    const state = searchParams.get('state');
    const errorParam = searchParams.get('error');

    if (errorParam) {
      setError('Xero connection was cancelled or failed. Please try again.');
      setIsLoading(false);
      return;
    }

    if (!code || !state) {
      setError('Invalid callback parameters. Please try connecting again.');
      setIsLoading(false);
      return;
    }

    try {
      // Fetch team members in parallel
      const token = await getToken();
      const [callbackResult, usersResult] = await Promise.all([
        bulkImportApi.handleBulkCallback(code, state),
        token ? listTenantUsers(token) : Promise.resolve({ users: [], total: 0 }),
      ]);

      setCallbackData(callbackResult);
      setOauthState(state);
      setTeamMembers(usersResult.users.filter((u) => u.is_active));

      // Initialize selections - all new orgs selected, already-connected deselected
      const initial = new Map<string, ImportOrgSelection>();
      for (const org of callbackResult.organizations) {
        initial.set(org.xero_tenant_id, {
          xero_tenant_id: org.xero_tenant_id,
          selected: !org.already_connected,
          connection_type: 'client',
          assigned_user_id: null,
        });
      }
      setSelections(initial);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to process callback');
    } finally {
      setIsLoading(false);
    }
  }, [searchParams, getToken, bulkImportApi]);

  useEffect(() => {
    if (processedRef.current) return;
    processedRef.current = true;
    processCallback();
  }, [processCallback]);

  const updateSelection = (
    xeroTenantId: string,
    updates: Partial<ImportOrgSelection>
  ) => {
    setSelections((prev) => {
      const next = new Map(prev);
      const existing = next.get(xeroTenantId);
      if (existing) {
        next.set(xeroTenantId, { ...existing, ...updates });
      }
      return next;
    });
  };

  const selectedCount = Array.from(selections.values()).filter(
    (s) => s.selected
  ).length;

  const newSelectedCount = callbackData
    ? callbackData.organizations.filter(
        (org) =>
          !org.already_connected &&
          selections.get(org.xero_tenant_id)?.selected
      ).length
    : 0;

  const exceedsLimit = callbackData
    ? newSelectedCount > callbackData.available_slots
    : false;

  const handleConfirm = async () => {
    if (!callbackData || !oauthState || exceedsLimit) return;

    setIsSubmitting(true);
    setError(null);

    try {
      const orgSelections = callbackData.organizations.map((org) => {
        const sel = selections.get(org.xero_tenant_id);
        return {
          xero_tenant_id: org.xero_tenant_id,
          organization_name: org.organization_name,
          selected: sel?.selected ?? false,
          connection_type: sel?.connection_type ?? 'client',
          assigned_user_id: sel?.assigned_user_id ?? null,
          already_connected: org.already_connected,
        };
      });

      const result = await bulkImportApi.confirmBulkImport(
        {
          auth_event_id: callbackData.auth_event_id,
          organizations: orgSelections,
        },
        oauthState
      );

      router.push(`/clients/import/progress/${result.job_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to confirm import');
      setIsSubmitting(false);
    }
  };

  const selectAll = () => {
    setSelections((prev) => {
      const next = new Map(prev);
      next.forEach((sel, id) => {
        const org = callbackData?.organizations.find(
          (o) => o.xero_tenant_id === id
        );
        if (org && !org.already_connected) {
          next.set(id, { ...sel, selected: true });
        }
      });
      return next;
    });
  };

  const deselectAll = () => {
    setSelections((prev) => {
      const next = new Map(prev);
      next.forEach((sel, id) => {
        next.set(id, { ...sel, selected: false });
      });
      return next;
    });
  };

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-24">
        <Loader2 className="w-8 h-8 animate-spin text-primary mb-4" />
        <p className="text-muted-foreground">
          Processing Xero authorization...
        </p>
      </div>
    );
  }

  if (error && !callbackData) {
    return (
      <div className="max-w-xl mx-auto py-12">
        <div className="bg-status-danger/10 border border-status-danger/20 rounded-xl p-6 text-center">
          <XCircle className="w-12 h-12 text-status-danger mx-auto mb-4" />
          <h2 className="text-lg font-semibold text-status-danger mb-2">
            Authorization Failed
          </h2>
          <p className="text-status-danger mb-4">{error}</p>
          <button
            onClick={() => router.push('/clients')}
            className="text-status-danger hover:text-status-danger/80 underline"
          >
            Return to Clients
          </button>
        </div>
      </div>
    );
  }

  if (!callbackData) return null;

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <button
          onClick={() => router.push('/clients')}
          className="flex items-center gap-1 text-muted-foreground hover:text-foreground mb-4 text-sm"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Clients
        </button>
        <h1 className="text-2xl font-bold text-foreground">
          Configure Client Import
        </h1>
        <p className="text-muted-foreground mt-1">
          Select which Xero organizations to import as clients.
        </p>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-card rounded-xl border border-border p-4">
          <p className="text-sm text-muted-foreground">New Organizations</p>
          <p className="text-2xl font-bold text-primary">
            {callbackData.new_count}
          </p>
        </div>
        <div className="bg-card rounded-xl border border-border p-4">
          <p className="text-sm text-muted-foreground">Already Connected</p>
          <p className="text-2xl font-bold text-muted-foreground">
            {callbackData.already_connected_count}
          </p>
        </div>
        <div className="bg-card rounded-xl border border-border p-4">
          <p className="text-sm text-muted-foreground">Available Slots</p>
          <p className="text-2xl font-bold text-status-success">
            {callbackData.available_slots >= 999999
              ? 'Unlimited'
              : callbackData.available_slots}
          </p>
        </div>
      </div>

      {/* Plan Limit Warning */}
      {exceedsLimit && (
        <div className="bg-status-warning/10 border border-status-warning/20 rounded-xl p-4 flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-status-warning mt-0.5 shrink-0" />
          <div>
            <p className="font-medium text-status-warning">
              Plan limit exceeded
            </p>
            <p className="text-sm text-status-warning mt-1">
              You have {callbackData.available_slots} available client
              {callbackData.available_slots === 1 ? ' slot' : ' slots'} but
              selected {newSelectedCount} new organizations. Please deselect
              some or upgrade your plan.
            </p>
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="bg-status-danger/10 border border-status-danger/20 rounded-xl p-4">
          <p className="text-status-danger">{error}</p>
        </div>
      )}

      {/* Organization List */}
      <div className="bg-card rounded-xl border border-border overflow-hidden">
        {/* Toolbar */}
        <div className="px-6 py-3 border-b border-border flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={selectAll}
              className="text-sm text-primary hover:text-primary/80"
            >
              Select All
            </button>
            <button
              onClick={deselectAll}
              className="text-sm text-muted-foreground hover:text-foreground"
            >
              Deselect All
            </button>
          </div>
          <p className="text-sm text-muted-foreground">
            {selectedCount} of {callbackData.organizations.length} selected
          </p>
        </div>

        {/* Table */}
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-muted border-b border-border">
              <tr>
                <th className="w-12 px-6 py-3" />
                <th className="text-left px-4 py-3 text-sm font-medium text-muted-foreground">
                  Organization
                </th>
                <th className="text-left px-4 py-3 text-sm font-medium text-muted-foreground">
                  Status
                </th>
                <th className="text-left px-4 py-3 text-sm font-medium text-muted-foreground">
                  Type
                </th>
                <th className="text-left px-4 py-3 text-sm font-medium text-muted-foreground">
                  Assign To
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {callbackData.organizations.map((org) => {
                const sel = selections.get(org.xero_tenant_id);
                const isDisabled = org.already_connected;

                return (
                  <tr
                    key={org.xero_tenant_id}
                    className={
                      isDisabled
                        ? 'opacity-60'
                        : 'hover:bg-muted'
                    }
                  >
                    <td className="px-6 py-4">
                      <input
                        type="checkbox"
                        checked={sel?.selected ?? false}
                        disabled={isDisabled}
                        onChange={(e) =>
                          updateSelection(org.xero_tenant_id, {
                            selected: e.target.checked,
                          })
                        }
                        className="w-4 h-4 rounded border-border text-primary focus:ring-primary/20 disabled:opacity-50"
                      />
                    </td>
                    <td className="px-4 py-4">
                      <p className="font-medium text-foreground">
                        {org.organization_name}
                      </p>
                      {org.match_status === 'matched' && org.matched_client_name && (
                        <span className="inline-flex items-center gap-1 text-xs text-status-success mt-1">
                          <CheckCircle2 className="w-3 h-3" />
                          Matched: {org.matched_client_name}
                        </span>
                      )}
                      {org.match_status === 'suggested' && org.matched_client_name && (
                        <span className="inline-flex items-center gap-1 text-xs text-status-warning mt-1">
                          <Link2 className="w-3 h-3" />
                          Suggested: {org.matched_client_name}
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-4">
                      {org.already_connected ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-muted text-muted-foreground">
                          <Check className="w-3 h-3" />
                          Connected
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-primary/10 text-primary">
                          New
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-4">
                      <select
                        value={sel?.connection_type ?? 'client'}
                        disabled={isDisabled}
                        onChange={(e) =>
                          updateSelection(org.xero_tenant_id, {
                            connection_type: e.target.value as
                              | 'practice'
                              | 'client',
                          })
                        }
                        className="text-sm border border-border bg-card text-foreground rounded-lg px-2 py-1 focus:outline-none focus:ring-1 focus:ring-primary/20 disabled:opacity-50"
                      >
                        <option value="client">Client</option>
                        <option value="practice">Practice</option>
                      </select>
                    </td>
                    <td className="px-4 py-4">
                      <select
                        value={sel?.assigned_user_id ?? ''}
                        disabled={isDisabled}
                        onChange={(e) =>
                          updateSelection(org.xero_tenant_id, {
                            assigned_user_id: e.target.value || null,
                          })
                        }
                        className="text-sm border border-border bg-card text-foreground rounded-lg px-2 py-1 focus:outline-none focus:ring-1 focus:ring-primary/20 disabled:opacity-50"
                      >
                        <option value="">Unassigned</option>
                        {teamMembers.map((user) => (
                          <option key={user.id} value={user.id}>
                            {user.email}
                          </option>
                        ))}
                      </select>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Action Bar */}
      <div className="flex items-center justify-between">
        <button
          onClick={() => router.push('/clients')}
          className="px-4 py-2 text-muted-foreground hover:text-foreground transition-colors"
        >
          Cancel
        </button>
        <button
          onClick={handleConfirm}
          disabled={isSubmitting || selectedCount === 0 || exceedsLimit}
          className="inline-flex items-center gap-2 px-6 py-2 bg-primary hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed text-primary-foreground rounded-lg font-medium transition-colors"
        >
          {isSubmitting ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Check className="w-4 h-4" />
          )}
          Import {selectedCount} Organization{selectedCount !== 1 ? 's' : ''}
        </button>
      </div>
    </div>
  );
}

export default function ImportConfigPage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center py-24">
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
        </div>
      }
    >
      <ImportConfigContent />
    </Suspense>
  );
}
