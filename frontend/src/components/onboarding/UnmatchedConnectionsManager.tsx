'use client';

/**
 * Component for managing Xero connections that couldn't be auto-matched to XPM clients.
 *
 * Shows:
 * - List of unmatched Xero organizations
 * - Dropdown to select which XPM client to link to
 * - Success/error feedback for linking operations
 */

import { useAuth } from '@clerk/nextjs';
import { useCallback, useEffect, useState } from 'react';

import {
  getUnmatchedConnections,
  getXpmClients,
  linkClientByTenantId,
  setAuthToken,
  type XeroConnection,
  type XpmClient,
} from '@/lib/api/onboarding';

interface UnmatchedConnectionsManagerProps {
  onConnectionLinked?: () => void;
}

export function UnmatchedConnectionsManager({
  onConnectionLinked,
}: UnmatchedConnectionsManagerProps) {
  const { getToken } = useAuth();

  // State
  const [unmatchedConnections, setUnmatchedConnections] = useState<XeroConnection[]>([]);
  const [availableClients, setAvailableClients] = useState<XpmClient[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [linkingConnectionId, setLinkingConnectionId] = useState<string | null>(null);
  const [selectedClients, setSelectedClients] = useState<Record<string, string>>({});
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Fetch data
  const fetchData = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);

      const token = await getToken();
      if (token) {
        setAuthToken(token);
      }

      const [connections, clientsResponse] = await Promise.all([
        getUnmatchedConnections(),
        getXpmClients(undefined, 'not_connected', 1, 1000), // Get all unconnected clients
      ]);

      setUnmatchedConnections(connections);
      setAvailableClients(clientsResponse.clients);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load data');
    } finally {
      setIsLoading(false);
    }
  }, [getToken]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Handle client selection for a connection
  const handleClientSelect = (connectionId: string, clientId: string) => {
    setSelectedClients((prev) => ({
      ...prev,
      [connectionId]: clientId,
    }));
  };

  // Link a connection to a client
  const handleLinkConnection = async (connection: XeroConnection) => {
    const selectedClientId = selectedClients[connection.id];
    if (!selectedClientId) {
      setError('Please select a client to link this organization to');
      return;
    }

    try {
      setLinkingConnectionId(connection.id);
      setError(null);

      const token = await getToken();
      if (token) {
        setAuthToken(token);
      }

      const client = await linkClientByTenantId(selectedClientId, connection.xero_tenant_id);

      // Show success message
      setSuccessMessage(`Successfully linked ${connection.organization_name} to ${client.name}`);
      setTimeout(() => setSuccessMessage(null), 3000);

      // Remove the linked connection from the list
      setUnmatchedConnections((prev) =>
        prev.filter((c) => c.id !== connection.id)
      );

      // Remove the linked client from available clients
      setAvailableClients((prev) =>
        prev.filter((c) => c.id !== selectedClientId)
      );

      // Clear selection
      setSelectedClients((prev) => {
        const newState = { ...prev };
        delete newState[connection.id];
        return newState;
      });

      // Notify parent
      onConnectionLinked?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to link connection');
    } finally {
      setLinkingConnectionId(null);
    }
  };

  // Loading state
  if (isLoading) {
    return (
      <div className="bg-white border border-border rounded-lg p-6">
        <div className="flex items-center justify-center">
          <svg
            className="animate-spin h-6 w-6 text-primary mr-2"
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
          <span className="text-muted-foreground">Loading unmatched connections...</span>
        </div>
      </div>
    );
  }

  // No unmatched connections
  if (unmatchedConnections.length === 0) {
    return (
      <div className="bg-white border border-border rounded-lg p-6">
        <div className="text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-green-100">
            <svg
              className="h-6 w-6 text-green-600"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M5 13l4 4L19 7"
              />
            </svg>
          </div>
          <h3 className="mt-3 text-sm font-medium text-foreground">
            All connections matched
          </h3>
          <p className="mt-1 text-sm text-muted-foreground">
            All authorized Xero organizations have been matched to clients.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white border border-border rounded-lg">
      {/* Header */}
      <div className="border-b border-border px-4 py-3">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-medium text-foreground">
              Unmatched Xero Organizations
            </h3>
            <p className="text-xs text-muted-foreground">
              {unmatchedConnections.length} organization{unmatchedConnections.length !== 1 ? 's' : ''} need
              manual matching
            </p>
          </div>
          <button
            onClick={fetchData}
            className="text-sm text-primary hover:text-primary/80"
          >
            Refresh
          </button>
        </div>
      </div>

      {/* Success message */}
      {successMessage && (
        <div className="mx-4 mt-4 rounded-lg bg-green-50 p-3">
          <div className="flex items-center">
            <svg
              className="h-5 w-5 text-green-500 mr-2"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path
                fillRule="evenodd"
                d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                clipRule="evenodd"
              />
            </svg>
            <span className="text-sm text-green-700">{successMessage}</span>
          </div>
        </div>
      )}

      {/* Error message */}
      {error && (
        <div className="mx-4 mt-4 rounded-lg bg-red-50 p-3">
          <div className="flex items-center">
            <svg
              className="h-5 w-5 text-red-500 mr-2"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path
                fillRule="evenodd"
                d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                clipRule="evenodd"
              />
            </svg>
            <span className="text-sm text-red-700">{error}</span>
          </div>
        </div>
      )}

      {/* Connection list */}
      <ul className="divide-y divide-border">
        {unmatchedConnections.map((connection) => (
          <li key={connection.id} className="px-4 py-4">
            <div className="flex items-center justify-between gap-4">
              {/* Connection info */}
              <div className="min-w-0 flex-1">
                <p className="font-medium text-foreground truncate">
                  {connection.organization_name || 'Unnamed Organization'}
                </p>
                <p className="text-xs text-muted-foreground truncate">
                  Tenant ID: {connection.xero_tenant_id}
                </p>
                {connection.connected_at && (
                  <p className="text-xs text-muted-foreground">
                    Connected {new Date(connection.connected_at).toLocaleDateString()}
                  </p>
                )}
              </div>

              {/* Client selector */}
              <div className="flex items-center gap-2">
                <select
                  value={selectedClients[connection.id] || ''}
                  onChange={(e) => handleClientSelect(connection.id, e.target.value)}
                  disabled={linkingConnectionId === connection.id}
                  className="block w-48 rounded-lg border border-input px-3 py-2 text-sm focus:border-ring focus:ring-ring disabled:opacity-50"
                >
                  <option value="">Select client...</option>
                  {availableClients.map((client) => (
                    <option key={client.id} value={client.id}>
                      {client.name}
                    </option>
                  ))}
                </select>

                <button
                  onClick={() => handleLinkConnection(connection)}
                  disabled={
                    !selectedClients[connection.id] ||
                    linkingConnectionId === connection.id
                  }
                  className="rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {linkingConnectionId === connection.id ? (
                    <svg
                      className="h-4 w-4 animate-spin"
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
                  ) : (
                    'Link'
                  )}
                </button>
              </div>
            </div>
          </li>
        ))}
      </ul>

      {/* No available clients warning */}
      {availableClients.length === 0 && unmatchedConnections.length > 0 && (
        <div className="border-t border-border px-4 py-3 bg-amber-50">
          <p className="text-sm text-amber-700">
            <strong>Note:</strong> All clients are already connected to Xero organizations.
            Import more clients from XPM to link these organizations.
          </p>
        </div>
      )}
    </div>
  );
}
