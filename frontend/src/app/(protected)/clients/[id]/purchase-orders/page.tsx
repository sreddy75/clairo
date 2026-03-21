'use client';

/**
 * Client Purchase Orders Page
 *
 * Displays purchase orders synced from Xero for a client connection.
 * Shows outstanding orders and upcoming deliveries for cash flow planning.
 *
 * Spec 025: Fixed Assets & Enhanced Analysis
 */

import { useAuth } from '@clerk/nextjs';
import { ArrowLeft, Loader2, ShoppingCart } from 'lucide-react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useCallback, useEffect, useState } from 'react';

import PurchaseOrdersList from '@/components/assets/PurchaseOrdersList';
import type { PurchaseOrderStatus } from '@/lib/api/assets';

interface ClientBasic {
  id: string;
  organization_name: string;
}

export default function PurchaseOrdersPage() {
  const params = useParams();
  const clientId = params.id as string;
  const { getToken } = useAuth();
  const [client, setClient] = useState<ClientBasic | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<PurchaseOrderStatus | undefined>(undefined);

  const fetchClient = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);

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
      setError(err instanceof Error ? err.message : 'Failed to load client');
    } finally {
      setIsLoading(false);
    }
  }, [getToken, clientId]);

  useEffect(() => {
    fetchClient();
  }, [fetchClient]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (error || !client) {
    return (
      <div className="text-center py-24">
        <ShoppingCart className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
        <h2 className="text-xl font-semibold text-foreground mb-2">
          {error || 'Client not found'}
        </h2>
        <p className="text-muted-foreground mb-4">
          Unable to load client details.
        </p>
        <Link
          href="/clients"
          className="text-primary hover:text-primary/80 text-sm"
        >
          Back to Clients
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link
            href={`/clients/${clientId}`}
            className="p-2 text-muted-foreground hover:text-foreground hover:bg-muted rounded-lg"
          >
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-foreground">Purchase Orders</h1>
            <p className="text-sm text-muted-foreground">{client.organization_name}</p>
          </div>
        </div>
      </div>

      {/* Status Filter */}
      <div className="flex gap-2 flex-wrap">
        <button
          onClick={() => setStatusFilter(undefined)}
          className={`px-3 py-1.5 text-sm rounded-full transition-colors ${
            statusFilter === undefined
              ? 'bg-primary text-primary-foreground'
              : 'bg-muted text-foreground hover:bg-muted/80'
          }`}
        >
          All
        </button>
        {(['DRAFT', 'SUBMITTED', 'AUTHORISED', 'BILLED'] as const).map((status) => (
          <button
            key={status}
            onClick={() => setStatusFilter(status)}
            className={`px-3 py-1.5 text-sm rounded-full transition-colors ${
              statusFilter === status
                ? 'bg-primary text-primary-foreground'
                : 'bg-muted text-foreground hover:bg-muted/80'
            }`}
          >
            {status.charAt(0) + status.slice(1).toLowerCase()}
          </button>
        ))}
      </div>

      {/* Purchase Orders List */}
      <PurchaseOrdersList
        connectionId={clientId}
        statusFilter={statusFilter}
        showSummary={true}
      />
    </div>
  );
}
