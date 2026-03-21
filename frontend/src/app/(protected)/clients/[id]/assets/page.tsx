'use client';

/**
 * Client Fixed Assets Page
 *
 * Displays fixed assets synced from Xero Assets API with depreciation information.
 * Supports filtering by status and displays depreciation summary.
 *
 * Spec 025: Fixed Assets & Enhanced Analysis
 */

import { useAuth } from '@clerk/nextjs';
import {
  AlertCircle,
  ArrowLeft,
  Loader2,
  Package,
} from 'lucide-react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useCallback, useEffect, useState } from 'react';

import { AssetsList } from '@/components/assets/AssetsList';
import { DepreciationSummary } from '@/components/assets/DepreciationSummary';
import { InstantWriteOffBanner } from '@/components/assets/InstantWriteOffBanner';
import type { AssetStatus } from '@/lib/api/assets';

// =============================================================================
// Types
// =============================================================================

interface ClientBasic {
  id: string;
  organization_name: string;
}

// =============================================================================
// Status Filter Options
// =============================================================================

const STATUS_OPTIONS: { value: AssetStatus | 'all'; label: string }[] = [
  { value: 'all', label: 'All Assets' },
  { value: 'Registered', label: 'Registered' },
  { value: 'Draft', label: 'Draft' },
  { value: 'Disposed', label: 'Disposed' },
];

// =============================================================================
// Page Component
// =============================================================================

export default function ClientAssetsPage() {
  const { getToken } = useAuth();
  const params = useParams();
  const clientId = params.id as string;

  // State
  const [client, setClient] = useState<ClientBasic | null>(null);
  const [statusFilter, setStatusFilter] = useState<AssetStatus | 'all'>('all');

  // Loading states
  const [isLoadingClient, setIsLoadingClient] = useState(true);

  // Error states
  const [clientError, setClientError] = useState<string | null>(null);

  // Fetch client basic info
  const fetchClient = useCallback(async () => {
    try {
      setIsLoadingClient(true);
      setClientError(null);

      const token = await getToken();
      if (!token) {
        throw new Error('Not authenticated');
      }

      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/v1/integrations/xero/connections/${clientId}`,
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      );

      if (!response.ok) {
        throw new Error('Failed to load client');
      }

      const data = await response.json();
      setClient({
        id: data.id,
        organization_name: data.organization_name,
      });
    } catch (err) {
      setClientError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setIsLoadingClient(false);
    }
  }, [clientId, getToken]);

  // Load client on mount
  useEffect(() => {
    fetchClient();
  }, [fetchClient]);

  // =============================================================================
  // Render
  // =============================================================================

  if (isLoadingClient) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (clientError) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen gap-4">
        <AlertCircle className="h-12 w-12 text-status-danger" />
        <p className="text-status-danger">{clientError}</p>
        <Link
          href="/clients"
          className="text-primary hover:underline flex items-center gap-1"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Clients
        </Link>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background pb-12">
      {/* Header */}
      <div className="bg-card border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center gap-4">
            <Link
              href={`/clients/${clientId}`}
              className="text-muted-foreground hover:text-foreground"
            >
              <ArrowLeft className="h-5 w-5" />
            </Link>
            <div>
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Link href="/clients" className="hover:underline">
                  Clients
                </Link>
                <span>/</span>
                <Link href={`/clients/${clientId}`} className="hover:underline">
                  {client?.organization_name || 'Client'}
                </Link>
                <span>/</span>
                <span>Assets</span>
              </div>
              <h1 className="text-2xl font-bold text-foreground flex items-center gap-2">
                <Package className="h-6 w-6" />
                Fixed Assets
              </h1>
            </div>
          </div>
        </div>
      </div>

      {/* Instant Write-Off Banner */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <InstantWriteOffBanner connectionId={clientId} isGstRegistered={true} />
      </div>

      {/* Depreciation Summary */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pb-6">
        <DepreciationSummary connectionId={clientId} />
      </div>

      {/* Status Filter */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div className="bg-card rounded-lg shadow-sm border p-4">
          <div className="flex flex-wrap items-center gap-4">
            <span className="text-sm text-muted-foreground">Filter by status:</span>
            <div className="flex flex-wrap gap-2">
              {STATUS_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  onClick={() => setStatusFilter(option.value)}
                  className={`px-3 py-1.5 text-sm rounded-full border transition-colors ${
                    statusFilter === option.value
                      ? 'bg-primary text-primary-foreground border-primary'
                      : 'bg-card text-foreground border-border hover:border-foreground/30'
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Assets List */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="bg-card rounded-lg shadow-sm border p-6">
          <AssetsList
            connectionId={clientId}
            statusFilter={statusFilter === 'all' ? undefined : statusFilter}
            pageSize={25}
          />
        </div>
      </div>
    </div>
  );
}
