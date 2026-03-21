'use client';

/**
 * Modal to initiate OAuth connection for a specific client's Xero organization.
 *
 * Shows:
 * - Client name and details
 * - Explanation of what will be authorized
 * - Connect button to initiate OAuth
 * - Current connection status
 */

import { useState } from 'react';

import type { XpmClient } from '@/lib/api/onboarding';

interface ConnectClientXeroModalProps {
  client: XpmClient;
  isOpen: boolean;
  onClose: () => void;
  onConnect: (client: XpmClient) => Promise<void>;
}

export function ConnectClientXeroModal({
  client,
  isOpen,
  onClose,
  onConnect,
}: ConnectClientXeroModalProps) {
  const [isConnecting, setIsConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleConnect = async () => {
    try {
      setIsConnecting(true);
      setError(null);
      await onConnect(client);
      // Note: onConnect redirects to Xero OAuth, so we won't reach here
    } catch (err) {
      setIsConnecting(false);
      setError(err instanceof Error ? err.message : 'Failed to connect');
    }
  };

  const getStatusBadge = () => {
    switch (client.connection_status) {
      case 'connected':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
            Connected
          </span>
        );
      case 'disconnected':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
            Disconnected
          </span>
        );
      case 'no_access':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
            No Access
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-muted text-foreground">
            Not Connected
          </span>
        );
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black bg-opacity-50 transition-opacity"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="flex min-h-full items-center justify-center p-4">
        <div className="relative w-full max-w-md transform rounded-xl bg-card p-6 shadow-2xl transition-all">
          {/* Close button */}
          <button
            onClick={onClose}
            className="absolute right-4 top-4 text-muted-foreground hover:text-muted-foreground"
          >
            <svg
              className="h-5 w-5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>

          {/* Xero logo */}
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
            <svg
              className="h-6 w-6 text-primary"
              viewBox="0 0 24 24"
              fill="currentColor"
            >
              <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z" />
            </svg>
          </div>

          {/* Title */}
          <h3 className="mt-4 text-center text-lg font-semibold text-foreground">
            Connect {client.name}&apos;s Xero
          </h3>

          {/* Client info */}
          <div className="mt-4 rounded-lg bg-muted p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium text-foreground">{client.name}</p>
                {client.email && (
                  <p className="text-sm text-muted-foreground">{client.email}</p>
                )}
                {client.abn && (
                  <p className="text-sm text-muted-foreground">ABN: {client.abn}</p>
                )}
              </div>
              {getStatusBadge()}
            </div>

            {client.xero_org_name && (
              <div className="mt-3 border-t border-border pt-3">
                <p className="text-sm text-muted-foreground">
                  Connected to: <span className="font-medium">{client.xero_org_name}</span>
                </p>
              </div>
            )}
          </div>

          {/* Explanation */}
          <div className="mt-4">
            <p className="text-sm text-muted-foreground">
              {client.connection_status === 'connected' ? (
                <>
                  This client&apos;s Xero organization is already connected. You can
                  reconnect to refresh the authorization if needed.
                </>
              ) : (
                <>
                  Connect to this client&apos;s Xero organization to access their
                  financial data for BAS preparation. You&apos;ll be redirected to
                  Xero to authorize access.
                </>
              )}
            </p>
          </div>

          {/* What we'll access */}
          <div className="mt-4">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Clairo will access:
            </p>
            <ul className="mt-2 space-y-1 text-sm text-muted-foreground">
              <li className="flex items-center">
                <svg
                  className="mr-2 h-4 w-4 text-green-500"
                  fill="currentColor"
                  viewBox="0 0 20 20"
                >
                  <path
                    fillRule="evenodd"
                    d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                    clipRule="evenodd"
                  />
                </svg>
                Bank transactions
              </li>
              <li className="flex items-center">
                <svg
                  className="mr-2 h-4 w-4 text-green-500"
                  fill="currentColor"
                  viewBox="0 0 20 20"
                >
                  <path
                    fillRule="evenodd"
                    d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                    clipRule="evenodd"
                  />
                </svg>
                Invoices and bills
              </li>
              <li className="flex items-center">
                <svg
                  className="mr-2 h-4 w-4 text-green-500"
                  fill="currentColor"
                  viewBox="0 0 20 20"
                >
                  <path
                    fillRule="evenodd"
                    d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                    clipRule="evenodd"
                  />
                </svg>
                Chart of accounts
              </li>
              <li className="flex items-center">
                <svg
                  className="mr-2 h-4 w-4 text-green-500"
                  fill="currentColor"
                  viewBox="0 0 20 20"
                >
                  <path
                    fillRule="evenodd"
                    d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                    clipRule="evenodd"
                  />
                </svg>
                GST reports
              </li>
            </ul>
          </div>

          {/* Error */}
          {error && (
            <div className="mt-4 rounded-lg bg-red-50 p-3">
              <p className="text-sm text-red-700">{error}</p>
            </div>
          )}

          {/* Actions */}
          <div className="mt-6 flex gap-3">
            <button
              onClick={onClose}
              className="flex-1 rounded-lg border border-border px-4 py-2 text-sm font-medium text-foreground hover:bg-muted"
            >
              Cancel
            </button>
            <button
              onClick={handleConnect}
              disabled={isConnecting}
              className="flex-1 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isConnecting ? (
                <span className="flex items-center justify-center">
                  <svg
                    className="mr-2 h-4 w-4 animate-spin"
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
                  Connecting...
                </span>
              ) : client.connection_status === 'connected' ? (
                'Reconnect to Xero'
              ) : (
                'Connect to Xero'
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
