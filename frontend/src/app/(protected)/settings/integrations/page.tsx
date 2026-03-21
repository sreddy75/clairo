'use client';

import { useAuth } from '@clerk/nextjs';
import {
  CheckCircle2,
  AlertCircle,
  Loader2,
  ArrowLeft,
  Unlink,
  History,
  MoreVertical,
  Trash2,
} from 'lucide-react';
import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { toast } from 'sonner';

import {
  DeleteConnectionModal,
  SyncHistoryView,
  SyncProgressDialog,
  SyncStatusDisplay,
  SyncTriggerButton,
} from '@/components/integrations/xero';
import { XeroConnectButton } from '@/components/integrations/XeroConnectButton';
import { apiClient } from '@/lib/api-client';

interface XeroConnectionSummary {
  id: string;
  organization_name: string;
  status: 'active' | 'needs_reauth' | 'disconnected';
  connected_at: string;
  last_full_sync_at?: string | null;
  sync_in_progress?: boolean;
}

interface XeroConnectionListResponse {
  connections: XeroConnectionSummary[];
  total: number;
}

/**
 * Integrations Settings Page
 * Lists all integrations and allows connecting/disconnecting them.
 */
export default function IntegrationsPage() {
  const { getToken } = useAuth();
  const [isLoading, setIsLoading] = useState(true);
  const [connections, setConnections] = useState<XeroConnectionSummary[]>([]);
  const [disconnecting, setDisconnecting] = useState<string | null>(null);
  const [activeSyncJob, setActiveSyncJob] = useState<{ connectionId: string; jobId: string } | null>(null);
  const [showHistoryFor, setShowHistoryFor] = useState<string | null>(null);
  const [syncingConnections, setSyncingConnections] = useState<Set<string>>(new Set());
  const [menuOpenFor, setMenuOpenFor] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<{ id: string; name: string } | null>(null);

  const fetchConnections = useCallback(async () => {
    try {
      const token = await getToken();
      if (!token) return;

      const response = await apiClient.get('/api/v1/integrations/xero/connections', {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (response.ok) {
        const data: XeroConnectionListResponse = await response.json();
        setConnections(data.connections);
      }
    } catch (error) {
      console.error('Failed to fetch connections:', error);
    } finally {
      setIsLoading(false);
    }
  }, [getToken]);

  useEffect(() => {
    fetchConnections();
  }, [fetchConnections]);

  const handleDisconnect = async (connectionId: string, orgName: string) => {
    if (!confirm(`Are you sure you want to disconnect ${orgName}?`)) {
      return;
    }

    setDisconnecting(connectionId);

    try {
      const token = await getToken();
      if (!token) throw new Error('Authentication required');

      const response = await apiClient.delete(
        `/api/v1/integrations/xero/connections/${connectionId}`,
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      );

      if (!response.ok) {
        throw new Error('Failed to disconnect');
      }

      toast.success(`Disconnected from ${orgName}`);
      setConnections((prev) => prev.filter((c) => c.id !== connectionId));
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : 'Failed to disconnect'
      );
    } finally {
      setDisconnecting(null);
    }
  };

  const getStatusBadge = (status: XeroConnectionSummary['status']) => {
    switch (status) {
      case 'active':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-status-success bg-status-success/10 rounded-full">
            <CheckCircle2 className="w-3 h-3" />
            Connected
          </span>
        );
      case 'needs_reauth':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-status-warning bg-status-warning/10 rounded-full">
            <AlertCircle className="w-3 h-3" />
            Needs Reconnection
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-muted-foreground bg-muted rounded-full">
            Disconnected
          </span>
        );
    }
  };

  return (
    <div className="max-w-4xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <Link
          href="/settings"
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-4"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Settings
        </Link>
        <h1 className="text-xl font-bold text-foreground">Integrations</h1>
        <p className="text-muted-foreground mt-1">
          Connect your accounting software to sync client data automatically.
        </p>
      </div>

      {/* Xero Integration */}
      <div className="bg-card rounded-xl border border-border">
        <div className="p-6 border-b border-border">
          <div className="flex items-center gap-4">
            {/* Xero Logo */}
            <div className="w-12 h-12 bg-[#13B5EA] rounded-xl flex items-center justify-center flex-shrink-0">
              <span className="text-white font-bold text-lg">X</span>
            </div>
            <div className="flex-1">
              <h2 className="text-lg font-semibold text-foreground">Xero</h2>
              <p className="text-sm text-muted-foreground">
                Connect to Xero to sync your clients, invoices, and financial data.
              </p>
            </div>
          </div>
        </div>

        <div className="p-6">
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
            </div>
          ) : connections.length === 0 ? (
            <div className="text-center py-8">
              <div className="w-16 h-16 bg-muted rounded-full flex items-center justify-center mx-auto mb-4">
                <svg
                  className="w-8 h-8 text-muted-foreground"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                >
                  <path d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                </svg>
              </div>
              <h3 className="text-lg font-medium text-foreground mb-2">
                No Xero accounts connected
              </h3>
              <p className="text-muted-foreground mb-6 max-w-sm mx-auto">
                Connect your Xero organization to start syncing your accounting data.
              </p>
              <XeroConnectButton onConnected={fetchConnections} />
            </div>
          ) : (
            <div className="space-y-4">
              {connections.map((connection) => {
                const isSyncing = syncingConnections.has(connection.id) || connection.sync_in_progress === true;

                return (
                  <div
                    key={connection.id}
                    className="bg-muted rounded-lg"
                  >
                    {/* Connection header */}
                    <div className="flex items-center justify-between p-4">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 bg-[#13B5EA] rounded-lg flex items-center justify-center">
                          <span className="text-white font-bold text-sm">X</span>
                        </div>
                        <div>
                          <p className="font-medium text-foreground">
                            {connection.organization_name}
                          </p>
                          <p className="text-sm text-muted-foreground">
                            Connected{' '}
                            {new Date(connection.connected_at).toLocaleDateString()}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        {getStatusBadge(connection.status)}
                        {connection.status === 'needs_reauth' && (
                          <XeroConnectButton
                            className="text-sm py-1.5 px-3"
                            onConnected={fetchConnections}
                          />
                        )}
                        <div className="relative">
                          <button
                            onClick={() => setMenuOpenFor(menuOpenFor === connection.id ? null : connection.id)}
                            disabled={disconnecting === connection.id}
                            className="p-2 text-muted-foreground hover:text-foreground hover:bg-muted rounded-lg transition-colors disabled:opacity-50"
                            title="Connection options"
                          >
                            {disconnecting === connection.id ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                              <MoreVertical className="w-4 h-4" />
                            )}
                          </button>
                          {menuOpenFor === connection.id && (
                            <>
                              <div className="fixed inset-0 z-10" onClick={() => setMenuOpenFor(null)} />
                              <div className="absolute right-0 mt-1 w-52 bg-card rounded-lg shadow-lg border border-border z-20 py-1">
                                <button
                                  onClick={() => {
                                    setMenuOpenFor(null);
                                    handleDisconnect(connection.id, connection.organization_name);
                                  }}
                                  className="w-full flex items-center gap-2.5 px-4 py-2.5 text-left text-sm text-foreground hover:bg-muted transition-colors"
                                >
                                  <Unlink className="w-4 h-4" />
                                  <div>
                                    <div className="font-medium">Disconnect</div>
                                    <div className="text-xs text-muted-foreground">Revoke access, keep data</div>
                                  </div>
                                </button>
                                <div className="border-t border-border my-1" />
                                <button
                                  onClick={() => {
                                    setMenuOpenFor(null);
                                    setDeleteTarget({ id: connection.id, name: connection.organization_name });
                                  }}
                                  className="w-full flex items-center gap-2.5 px-4 py-2.5 text-left text-sm text-status-danger hover:bg-status-danger/10 transition-colors"
                                >
                                  <Trash2 className="w-4 h-4" />
                                  <div>
                                    <div className="font-medium">Delete All Data</div>
                                    <div className="text-xs text-status-danger/70">Remove connection &amp; all records</div>
                                  </div>
                                </button>
                              </div>
                            </>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Sync section (only for active connections) */}
                    {connection.status === 'active' && (
                      <div className="border-t border-border p-4 bg-card">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-4">
                            <SyncStatusDisplay
                              status={isSyncing ? 'in_progress' : null}
                              lastSyncAt={connection.last_full_sync_at}
                              isSyncing={isSyncing}
                              compact
                            />
                          </div>
                          <div className="flex items-center gap-2">
                            <button
                              onClick={() => setShowHistoryFor(
                                showHistoryFor === connection.id ? null : connection.id
                              )}
                              className="p-2 text-muted-foreground hover:text-foreground hover:bg-muted rounded-lg transition-colors"
                              title="View sync history"
                            >
                              <History className="w-4 h-4" />
                            </button>
                            <SyncTriggerButton
                              connectionId={connection.id}
                              isSyncing={isSyncing}
                              onSyncStarted={(jobId) => {
                                setSyncingConnections((prev) => new Set(prev).add(connection.id));
                                setActiveSyncJob({ connectionId: connection.id, jobId });
                              }}
                              compact
                            />
                          </div>
                        </div>

                        {/* Sync history (expandable) */}
                        {showHistoryFor === connection.id && (
                          <div className="mt-4 pt-4 border-t border-border">
                            <h4 className="text-sm font-medium text-foreground mb-3">
                              Sync History
                            </h4>
                            <SyncHistoryView
                              connectionId={connection.id}
                              pageSize={5}
                            />
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}

              {/* Add another connection */}
              <div className="pt-4 border-t border-border">
                <p className="text-sm text-muted-foreground mb-3">
                  Connect additional Xero organizations:
                </p>
                <XeroConnectButton onConnected={fetchConnections} />
              </div>
            </div>
          )}
        </div>
      </div>

      {/* MYOB (Coming Soon) */}
      <div className="bg-card rounded-xl border border-border overflow-hidden mt-6 opacity-60">
        <div className="p-6">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-purple-600 rounded-xl flex items-center justify-center flex-shrink-0">
              <span className="text-white font-bold text-lg">M</span>
            </div>
            <div className="flex-1">
              <h2 className="text-lg font-semibold text-foreground">MYOB</h2>
              <p className="text-sm text-muted-foreground">
                Connect to MYOB to sync your accounting data.
              </p>
            </div>
            <span className="px-3 py-1 text-xs font-medium text-muted-foreground bg-muted rounded-full">
              Coming Soon
            </span>
          </div>
        </div>
      </div>

      {/* Sync Progress Dialog (SSE real-time + polling fallback) */}
      <SyncProgressDialog
        open={!!activeSyncJob}
        onOpenChange={(open) => { if (!open) setActiveSyncJob(null); }}
        connectionId={activeSyncJob?.connectionId ?? ''}
        jobId={activeSyncJob?.jobId ?? ''}
        onComplete={(_job) => {
          setSyncingConnections((prev) => {
            const next = new Set(prev);
            next.delete(activeSyncJob!.connectionId);
            return next;
          });
          fetchConnections();
        }}
      />

      {/* Delete Connection Modal */}
      {deleteTarget && (
        <DeleteConnectionModal
          connectionId={deleteTarget.id}
          organizationName={deleteTarget.name}
          onDeleted={() => {
            setDeleteTarget(null);
            setConnections((prev) => prev.filter((c) => c.id !== deleteTarget.id));
          }}
          onClose={() => setDeleteTarget(null)}
        />
      )}
    </div>
  );
}
