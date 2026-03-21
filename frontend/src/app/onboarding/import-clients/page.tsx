'use client';

import { useAuth } from '@clerk/nextjs';
import { useRouter } from 'next/navigation';
import { useCallback, useEffect, useState } from 'react';

import { ConnectAllRemainingFlow } from '@/components/onboarding/ConnectAllRemainingFlow';
import { ConnectClientXeroModal } from '@/components/onboarding/ConnectClientXeroModal';
import { UnmatchedConnectionsManager } from '@/components/onboarding/UnmatchedConnectionsManager';
import { useClientXeroConnection } from '@/hooks/useClientXeroConnection';
import { useImportJob } from '@/hooks/useImportJob';
import {
  getAvailableClients,
  startBulkImport,
  retryFailedImports,
  setAuthToken,
  type AvailableClient,
  type BulkImportJob,
  type XpmClient,
} from '@/lib/api/onboarding';

export default function ImportClientsPage() {
  const router = useRouter();
  const { getToken } = useAuth();

  // Client list state
  const [clients, setClients] = useState<AvailableClient[]>([]);
  const [isLoadingClients, setIsLoadingClients] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [searchTerm, setSearchTerm] = useState('');

  // Pagination
  const [page, setPage] = useState(1);
  const [totalClients, setTotalClients] = useState(0);
  const pageSize = 50;

  // Tier limits
  const [tierLimit, setTierLimit] = useState(100);
  const [currentCount, setCurrentCount] = useState(0);
  const [sourceType, setSourceType] = useState<'xpm' | 'xero_accounting'>('xpm');

  // Import state
  const [isStartingImport, setIsStartingImport] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);
  const { job, isPolling, startPolling, stopPolling, error: pollError } = useImportJob();

  // Xero connection state
  const {
    progress: xeroProgress,
    fetchProgress: fetchXeroProgress,
    connectClient,
    startConnectAll,
    connectNext,
    skipClient,
    pauseConnectAll,
    currentClient: connectingClient,
    isConnectAllActive,
    connectAllProgress,
    connectError,
  } = useClientXeroConnection();

  const [showConnectModal, setShowConnectModal] = useState(false);
  const [selectedClientForConnect, setSelectedClientForConnect] = useState<XpmClient | null>(null);
  const [showConnectAllModal, setShowConnectAllModal] = useState(false);

  const availableSlots = tierLimit - currentCount;
  const unconnectedCount = xeroProgress?.not_connected ?? 0;

  // Fetch available clients
  const fetchClients = useCallback(async (searchQuery?: string, pageNum: number = 1) => {
    try {
      setIsLoadingClients(true);
      setLoadError(null);

      const token = await getToken();
      if (token) {
        setAuthToken(token);
      }

      const response = await getAvailableClients(searchQuery, pageNum, pageSize);
      setClients(response.clients);
      setTotalClients(response.total);
      setTierLimit(response.tier_limit);
      setCurrentCount(response.current_count);
      setSourceType(response.source_type);
      setPage(response.page);
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : 'Failed to load clients');
    } finally {
      setIsLoadingClients(false);
    }
  }, [getToken]);

  // Initial load
  useEffect(() => {
    fetchClients();
    fetchXeroProgress();
  }, [fetchClients, fetchXeroProgress]);

  // Convert AvailableClient to XpmClient for modal
  const toXpmClient = (client: AvailableClient): XpmClient => ({
    id: client.id,
    name: client.name,
    email: client.email,
    abn: null,
    xero_contact_id: '',
    is_active: client.already_imported ? false : true,
    connection_status: client.xero_org_status,
    xero_connection_id: client.xero_connection_id,
    xero_org_name: null,
    connected_at: null,
  });

  const handleOpenConnectModal = (client: AvailableClient) => {
    setSelectedClientForConnect(toXpmClient(client));
    setShowConnectModal(true);
  };

  const handleCloseConnectModal = () => {
    setShowConnectModal(false);
    setSelectedClientForConnect(null);
  };

  const handleConnectClient = async (client: XpmClient) => {
    await connectClient(client);
  };

  // Search with debounce
  useEffect(() => {
    const timer = setTimeout(() => {
      fetchClients(searchTerm || undefined, 1);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchTerm, fetchClients]);

  const toggleSelect = (id: string) => {
    const newSelected = new Set(selectedIds);
    if (newSelected.has(id)) {
      newSelected.delete(id);
    } else if (newSelected.size < availableSlots) {
      newSelected.add(id);
    }
    setSelectedIds(newSelected);
  };

  const selectAll = () => {
    const available = clients
      .filter((c) => !c.already_imported)
      .slice(0, availableSlots)
      .map((c) => c.id);
    setSelectedIds(new Set(available));
  };

  const clearSelection = () => {
    setSelectedIds(new Set());
  };

  const handleImport = async () => {
    if (selectedIds.size === 0) return;

    setIsStartingImport(true);
    setImportError(null);

    try {
      const token = await getToken();
      if (token) {
        setAuthToken(token);
      }

      const importJob = await startBulkImport(Array.from(selectedIds), sourceType);

      // Start polling for job status
      startPolling(importJob.id);
    } catch (err) {
      setImportError(err instanceof Error ? err.message : 'Failed to start import');
      setIsStartingImport(false);
    }
  };

  const handleRetry = async () => {
    if (!job) return;

    setImportError(null);
    try {
      const token = await getToken();
      if (token) {
        setAuthToken(token);
      }

      const retryJob = await retryFailedImports(job.id);
      startPolling(retryJob.id);
    } catch (err) {
      setImportError(err instanceof Error ? err.message : 'Failed to retry import');
    }
  };

  const handleSkip = () => {
    router.push('/dashboard');
  };

  const handleContinue = () => {
    stopPolling();
    router.push('/dashboard');
  };

  // Render import progress/results screen
  if (isStartingImport || isPolling || job) {
    return <ImportProgressView
      job={job}
      isStarting={isStartingImport}
      pollError={pollError}
      importError={importError}
      onRetry={handleRetry}
      onContinue={handleContinue}
    />;
  }

  // Loading state
  if (isLoadingClients && clients.length === 0) {
    return (
      <div className="max-w-2xl mx-auto text-center space-y-6 py-12">
        <div className="mx-auto w-16 h-16 bg-primary/10 rounded-full flex items-center justify-center">
          <svg
            className="w-8 h-8 text-primary animate-spin"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            />
          </svg>
        </div>
        <h2 className="text-xl font-semibold text-foreground">
          Loading your clients...
        </h2>
        <p className="text-muted-foreground">
          Fetching client list from {sourceType === 'xpm' ? 'Xero Practice Manager' : 'Xero'}.
        </p>
      </div>
    );
  }

  // Error state
  if (loadError) {
    return (
      <div className="max-w-2xl mx-auto text-center space-y-6 py-12">
        <div className="mx-auto w-16 h-16 bg-status-danger/10 rounded-full flex items-center justify-center">
          <svg
            className="w-8 h-8 text-status-danger"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
            />
          </svg>
        </div>
        <h2 className="text-xl font-semibold text-foreground">
          Failed to load clients
        </h2>
        <p className="text-muted-foreground">{loadError}</p>
        <div className="flex justify-center gap-4">
          <button
            onClick={() => fetchClients()}
            className="px-6 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90"
          >
            Try again
          </button>
          <button
            onClick={handleSkip}
            className="px-6 py-2 text-muted-foreground hover:text-foreground"
          >
            Skip for now
          </button>
        </div>
      </div>
    );
  }

  // Empty state
  if (clients.length === 0 && !searchTerm) {
    return (
      <div className="max-w-2xl mx-auto text-center space-y-6 py-12">
        <div className="mx-auto w-16 h-16 bg-muted rounded-full flex items-center justify-center">
          <svg
            className="w-8 h-8 text-muted-foreground"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"
            />
          </svg>
        </div>
        <h2 className="text-xl font-semibold text-foreground">
          No clients found
        </h2>
        <p className="text-muted-foreground">
          We couldn&apos;t find any clients in your {sourceType === 'xpm' ? 'Xero Practice Manager' : 'Xero'} account.
          You can add clients manually later.
        </p>
        <button
          onClick={handleSkip}
          className="px-6 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90"
        >
          Continue to Dashboard
        </button>
      </div>
    );
  }

  const totalPages = Math.ceil(totalClients / pageSize);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="text-center">
        <h1 className="text-3xl font-bold text-foreground">
          Import your clients
        </h1>
        <p className="mt-2 text-lg text-muted-foreground">
          Select the clients you want to import from {sourceType === 'xpm' ? 'Xero Practice Manager' : 'Xero'}
        </p>
      </div>

      {/* Tier limit warning */}
      {selectedIds.size >= availableSlots && (
        <div className="bg-status-warning/10 border border-status-warning/20 rounded-lg p-4">
          <div className="flex items-center">
            <svg
              className="w-5 h-5 text-status-warning mr-2"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path
                fillRule="evenodd"
                d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"
                clipRule="evenodd"
              />
            </svg>
            <span className="text-status-warning">
              You have reached your plan limit ({tierLimit} clients).{' '}
              <a href="/billing" className="underline">
                Upgrade your plan
              </a>{' '}
              to import more clients.
            </span>
          </div>
        </div>
      )}

      {/* Current count info */}
      {currentCount > 0 && (
        <div className="bg-primary/10 border border-primary/20 rounded-lg p-4">
          <p className="text-primary">
            You already have {currentCount} client{currentCount !== 1 ? 's' : ''} imported.
            You can import up to {availableSlots} more.
          </p>
        </div>
      )}

      {/* Xero Connection Progress */}
      {xeroProgress && xeroProgress.total_clients > 0 && (
        <div className="bg-card border border-border rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-foreground">
                Xero Organization Connections
              </p>
              <p className="text-sm text-muted-foreground">
                {xeroProgress.connected} of {xeroProgress.total_clients} clients connected to their Xero
              </p>
            </div>
            {unconnectedCount > 0 && (
              <button
                onClick={() => setShowConnectAllModal(true)}
                className="px-4 py-2 text-sm font-medium text-primary-foreground bg-primary hover:bg-primary/90 rounded-lg transition-colors"
              >
                Connect All ({unconnectedCount})
              </button>
            )}
          </div>
          <div className="mt-3 h-2 rounded-full bg-muted">
            <div
              className="h-2 rounded-full bg-status-success transition-all"
              style={{ width: `${xeroProgress.connection_rate_percent}%` }}
            />
          </div>
        </div>
      )}

      {/* Unmatched Connections Manager */}
      <UnmatchedConnectionsManager
        onConnectionLinked={() => {
          // Refresh client list and progress after linking
          fetchClients();
          fetchXeroProgress();
        }}
      />

      {/* Search and actions */}
      <div className="flex flex-col sm:flex-row gap-4 items-center justify-between">
        <div className="relative flex-1 w-full">
          <svg
            className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
            />
          </svg>
          <input
            type="text"
            placeholder="Search by name or email..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border border-border rounded-lg focus:ring-2 focus:ring-primary/20 focus:border-primary"
          />
        </div>
        <div className="flex gap-2">
          <button
            onClick={selectAll}
            className="px-4 py-2 text-sm text-primary hover:bg-primary/10 rounded-lg"
          >
            Select all
          </button>
          <button
            onClick={clearSelection}
            className="px-4 py-2 text-sm text-muted-foreground hover:bg-muted rounded-lg"
          >
            Clear
          </button>
        </div>
      </div>

      {/* Client list */}
      <div className="bg-card border border-border rounded-xl divide-y divide-border">
        {isLoadingClients ? (
          <div className="p-8 text-center text-muted-foreground">
            Loading...
          </div>
        ) : clients.length === 0 ? (
          <div className="p-8 text-center text-muted-foreground">
            No clients match your search.
          </div>
        ) : (
          clients.map((client) => (
            <div
              key={client.id}
              className={`flex items-center p-4 hover:bg-muted ${
                client.already_imported ? 'opacity-50' : ''
              }`}
            >
              <label className="flex items-center flex-1 cursor-pointer">
                <input
                  type="checkbox"
                  checked={selectedIds.has(client.id)}
                  onChange={() => toggleSelect(client.id)}
                  disabled={client.already_imported}
                  className="w-5 h-5 text-primary rounded border-border focus:ring-primary/20"
                />
                <div className="ml-4 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-foreground">{client.name}</span>
                    {/* Xero connection status badge */}
                    {client.xero_org_status === 'connected' ? (
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-status-success/10 text-status-success">
                        Xero Connected
                      </span>
                    ) : client.xero_org_status === 'disconnected' ? (
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-status-warning/10 text-status-warning">
                        Xero Disconnected
                      </span>
                    ) : client.xero_org_status === 'no_access' ? (
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-status-danger/10 text-status-danger">
                        No Xero Access
                      </span>
                    ) : (
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-muted text-muted-foreground">
                        Xero Not Connected
                      </span>
                    )}
                  </div>
                  <div className="text-sm text-muted-foreground">
                    {client.email && <span>{client.email}</span>}
                  </div>
                </div>
              </label>
              <div className="flex items-center gap-2">
                {client.already_imported ? (
                  <span className="text-sm text-muted-foreground">Already imported</span>
                ) : client.xero_org_status !== 'connected' ? (
                  <button
                    onClick={(e) => {
                      e.preventDefault();
                      handleOpenConnectModal(client);
                    }}
                    className="px-3 py-1 text-sm text-primary hover:bg-primary/10 rounded-lg transition-colors"
                  >
                    Connect Xero
                  </button>
                ) : null}
              </div>
            </div>
          ))
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex justify-center items-center gap-2">
          <button
            onClick={() => fetchClients(searchTerm || undefined, page - 1)}
            disabled={page <= 1 || isLoadingClients}
            className="px-3 py-1 text-sm border border-border rounded hover:bg-muted disabled:opacity-50"
          >
            Previous
          </button>
          <span className="text-sm text-muted-foreground">
            Page {page} of {totalPages}
          </span>
          <button
            onClick={() => fetchClients(searchTerm || undefined, page + 1)}
            disabled={page >= totalPages || isLoadingClients}
            className="px-3 py-1 text-sm border border-border rounded hover:bg-muted disabled:opacity-50"
          >
            Next
          </button>
        </div>
      )}

      {/* Selection summary and actions */}
      <div className="sticky bottom-0 bg-card border-t border-border -mx-4 px-4 py-4 sm:mx-0 sm:px-0 sm:border-0">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="text-sm text-muted-foreground">
            {selectedIds.size} of {availableSlots} available slots selected
            {totalClients > 0 && ` (${totalClients} total clients in ${sourceType === 'xpm' ? 'XPM' : 'Xero'})`}
          </div>
          <div className="flex gap-4">
            <button
              onClick={handleSkip}
              className="px-6 py-2 text-muted-foreground hover:text-foreground"
            >
              Skip for now
            </button>
            <button
              onClick={handleImport}
              disabled={selectedIds.size === 0}
              className="px-6 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Import {selectedIds.size} client{selectedIds.size !== 1 ? 's' : ''}
            </button>
          </div>
        </div>
      </div>

      {/* Connect Client Xero Modal */}
      {selectedClientForConnect && (
        <ConnectClientXeroModal
          client={selectedClientForConnect}
          isOpen={showConnectModal}
          onClose={handleCloseConnectModal}
          onConnect={handleConnectClient}
        />
      )}

      {/* Connect All Remaining Flow Modal */}
      <ConnectAllRemainingFlow
        isOpen={showConnectAllModal}
        onClose={() => setShowConnectAllModal(false)}
        progress={xeroProgress}
        currentClient={connectingClient}
        isActive={isConnectAllActive}
        connectAllProgress={connectAllProgress}
        onStartConnectAll={startConnectAll}
        onConnectNext={connectNext}
        onSkipClient={skipClient}
        onPause={pauseConnectAll}
        error={connectError}
      />
    </div>
  );
}

// Import progress component
interface ImportProgressViewProps {
  job: BulkImportJob | null;
  isStarting: boolean;
  pollError: string | null;
  importError: string | null;
  onRetry: () => void;
  onContinue: () => void;
}

function ImportProgressView({
  job,
  isStarting,
  pollError,
  importError,
  onRetry,
  onContinue,
}: ImportProgressViewProps) {
  const error = pollError || importError;
  const isFailed = job?.status === 'failed' || job?.status === 'cancelled';
  const isInProgress = !job || job.status === 'pending' || job.status === 'in_progress';

  // Show error state
  if (error && !job) {
    return (
      <div className="max-w-2xl mx-auto text-center space-y-6 py-12">
        <div className="mx-auto w-16 h-16 bg-status-danger/10 rounded-full flex items-center justify-center">
          <svg
            className="w-8 h-8 text-status-danger"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </div>
        <h2 className="text-2xl font-bold text-foreground">Import Failed</h2>
        <p className="text-muted-foreground">{error}</p>
        <button
          onClick={onContinue}
          className="px-6 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90"
        >
          Go to Dashboard
        </button>
      </div>
    );
  }

  // Show loading/progress state
  if (isStarting || isInProgress) {
    return (
      <div className="max-w-2xl mx-auto text-center space-y-6 py-12">
        <div className="mx-auto w-16 h-16 bg-primary/10 rounded-full flex items-center justify-center">
          <svg
            className="w-8 h-8 text-primary animate-spin"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            />
          </svg>
        </div>
        <h2 className="text-2xl font-bold text-foreground">
          {isStarting ? 'Starting import...' : 'Importing your clients...'}
        </h2>
        <p className="text-muted-foreground">
          This may take a few minutes. Please don&apos;t close this page.
        </p>
        {job && (
          <>
            <div className="w-full bg-muted rounded-full h-3">
              <div
                className="bg-primary h-3 rounded-full transition-all duration-300"
                style={{ width: `${job.progress_percent}%` }}
              />
            </div>
            <p className="text-sm text-muted-foreground">
              {job.imported_count} of {job.total_clients} clients imported ({job.progress_percent}%)
            </p>
          </>
        )}
      </div>
    );
  }

  // Show failed state
  if (isFailed) {
    return (
      <div className="max-w-2xl mx-auto text-center space-y-6 py-12">
        <div className="mx-auto w-16 h-16 bg-status-danger/10 rounded-full flex items-center justify-center">
          <svg
            className="w-8 h-8 text-status-danger"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </div>
        <h2 className="text-2xl font-bold text-foreground">Import Failed</h2>
        <p className="text-muted-foreground">
          {job?.error_message || 'The import could not be completed. Please try again.'}
        </p>
        <div className="flex justify-center gap-4">
          <button
            onClick={onRetry}
            className="px-6 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90"
          >
            Try Again
          </button>
          <button
            onClick={onContinue}
            className="px-6 py-2 text-muted-foreground hover:text-foreground"
          >
            Continue to Dashboard
          </button>
        </div>
      </div>
    );
  }

  // Show complete state (success or partial success)
  return (
    <div className="max-w-2xl mx-auto space-y-6 py-12">
      <div className="text-center space-y-4">
        <div className={`mx-auto w-16 h-16 rounded-full flex items-center justify-center ${
          job?.status === 'partial_failure' ? 'bg-status-warning/10' : 'bg-status-success/10'
        }`}>
          <svg
            className={`w-8 h-8 ${job?.status === 'partial_failure' ? 'text-status-warning' : 'text-status-success'}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M5 13l4 4L19 7"
            />
          </svg>
        </div>
        <h2 className="text-2xl font-bold text-foreground">
          {job?.status === 'partial_failure' ? 'Import Partially Complete' : 'Import Complete!'}
        </h2>
        <p className="text-muted-foreground">
          Successfully imported {job?.imported_count} of {job?.total_clients} clients.
        </p>
      </div>

      {/* Successfully imported clients */}
      {job && job.imported_clients.length > 0 && (
        <div className="bg-card border border-border rounded-xl p-4">
          <h3 className="font-medium text-foreground mb-3">
            Imported Clients ({job.imported_clients.length})
          </h3>
          <ul className="divide-y divide-border">
            {job.imported_clients.slice(0, 10).map((client) => (
              <li key={client.clairo_id} className="py-2 flex items-center">
                <svg
                  className="w-4 h-4 text-status-success mr-2"
                  fill="currentColor"
                  viewBox="0 0 20 20"
                >
                  <path
                    fillRule="evenodd"
                    d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                    clipRule="evenodd"
                  />
                </svg>
                <span>{client.name}</span>
              </li>
            ))}
            {job.imported_clients.length > 10 && (
              <li className="py-2 text-muted-foreground text-sm">
                And {job.imported_clients.length - 10} more...
              </li>
            )}
          </ul>
        </div>
      )}

      {/* Failed clients */}
      {job && job.failed_clients.length > 0 && (
        <div className="bg-status-danger/10 border border-status-danger/20 rounded-xl p-4">
          <h3 className="font-medium text-status-danger mb-3">
            Failed to Import ({job.failed_clients.length})
          </h3>
          <ul className="divide-y divide-status-danger/20">
            {job.failed_clients.map((client) => (
              <li key={client.source_id} className="py-2">
                <div className="flex items-center">
                  <svg
                    className="w-4 h-4 text-status-danger mr-2"
                    fill="currentColor"
                    viewBox="0 0 20 20"
                  >
                    <path
                      fillRule="evenodd"
                      d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                      clipRule="evenodd"
                    />
                  </svg>
                  <span className="font-medium">{client.name}</span>
                </div>
                <p className="text-sm text-status-danger ml-6">{client.error}</p>
              </li>
            ))}
          </ul>
          <button
            onClick={onRetry}
            className="mt-4 w-full px-4 py-2 bg-status-danger text-white rounded-lg hover:bg-status-danger/90"
          >
            Retry Failed Imports
          </button>
        </div>
      )}

      {/* Continue button */}
      <div className="text-center">
        <button
          onClick={onContinue}
          className="px-8 py-3 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 font-medium"
        >
          Continue to Dashboard
        </button>
      </div>
    </div>
  );
}
