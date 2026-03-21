'use client';

import { useAuth } from '@clerk/nextjs';
import { ExternalLink, Loader2 } from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';

import { apiClient } from '@/lib/api-client';

interface XeroConnectButtonProps {
  onConnected?: () => void;
  className?: string;
}

interface XeroAuthUrlResponse {
  auth_url: string;
  state: string;
}

/**
 * Button component to initiate Xero OAuth connection.
 * Calls the backend to get an auth URL and redirects to Xero.
 */
export function XeroConnectButton({ onConnected: _onConnected, className = '' }: XeroConnectButtonProps) {
  const { getToken } = useAuth();
  const [isConnecting, setIsConnecting] = useState(false);

  const handleConnect = async () => {
    setIsConnecting(true);

    try {
      const token = await getToken();
      if (!token) {
        throw new Error('Authentication required');
      }

      // Get the callback URL for this environment
      const callbackUrl = `${window.location.origin}/settings/integrations/xero/callback`;

      const response = await apiClient.post('/api/v1/integrations/xero/connect', {
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          redirect_uri: callbackUrl,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData?.error?.message || 'Failed to initiate Xero connection');
      }

      const data: XeroAuthUrlResponse = await response.json();

      // Store state for callback validation (optional client-side check)
      sessionStorage.setItem('xero_oauth_state', data.state);

      // Redirect to Xero authorization page
      window.location.href = data.auth_url;
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : 'Failed to connect to Xero'
      );
      setIsConnecting(false);
    }
  };

  return (
    <button
      onClick={handleConnect}
      disabled={isConnecting}
      className={`inline-flex items-center gap-2 px-4 py-2 bg-[#13B5EA] hover:bg-[#0A9FD4] text-white font-medium rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${className}`}
    >
      {isConnecting ? (
        <>
          <Loader2 className="w-5 h-5 animate-spin" />
          Connecting...
        </>
      ) : (
        <>
          <svg
            className="w-5 h-5"
            viewBox="0 0 24 24"
            fill="currentColor"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm0 21.75c-5.385 0-9.75-4.365-9.75-9.75S6.615 2.25 12 2.25s9.75 4.365 9.75 9.75-4.365 9.75-9.75 9.75z" />
            <path d="M16.5 8.25L12 12.75 7.5 8.25M12 4.5v8.25" />
          </svg>
          Connect Xero
          <ExternalLink className="w-4 h-4" />
        </>
      )}
    </button>
  );
}

export default XeroConnectButton;
