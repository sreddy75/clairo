'use client';

/**
 * Admin Tenant Detail Page
 *
 * Displays comprehensive information about a single tenant.
 *
 * Spec 022: Admin Dashboard (Internal)
 */

import {
  AlertTriangle,
  ArrowLeft,
  CreditCard,
  RefreshCw,
  Settings,
  User,
} from 'lucide-react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useState } from 'react';

import { useTenant } from '@/hooks/useAdminDashboard';

import { CreditModal } from '../../components/CreditModal';
import { FeatureFlagOverrides } from '../../components/FeatureFlagOverrides';
import { SubscriptionHistory } from '../../components/SubscriptionHistory';
import { TenantDetailCard } from '../../components/TenantDetailCard';
import { TierChangeModal } from '../../components/TierChangeModal';

/**
 * Action button component.
 */
function ActionButton({
  label,
  icon: Icon,
  onClick,
  variant = 'default',
  disabled = false,
}: {
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  onClick: () => void;
  variant?: 'default' | 'primary' | 'danger';
  disabled?: boolean;
}) {
  const variantStyles = {
    default: 'bg-muted text-foreground hover:bg-muted/80',
    primary: 'bg-primary text-primary-foreground hover:bg-primary/90',
    danger: 'bg-status-danger/10 text-status-danger hover:bg-status-danger/20',
  };

  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${variantStyles[variant]}`}
    >
      <Icon className="w-4 h-4" />
      {label}
    </button>
  );
}

/**
 * Tenant detail page.
 */
export default function TenantDetailPage() {
  const params = useParams();
  const tenantId = params.id as string;

  const { data: tenant, isLoading, error, refetch, isFetching } = useTenant(tenantId);

  const [showTierModal, setShowTierModal] = useState(false);
  const [showCreditModal, setShowCreditModal] = useState(false);

  // Handle not found
  if (!isLoading && !tenant && !error) {
    return (
      <div className="flex flex-col items-center justify-center h-64">
        <AlertTriangle className="w-12 h-12 text-status-warning mb-4" />
        <h2 className="text-xl font-bold text-foreground mb-2">Tenant Not Found</h2>
        <p className="text-muted-foreground mb-4">
          The tenant you&apos;re looking for doesn&apos;t exist or has been removed.
        </p>
        <Link
          href="/internal/admin/customers"
          className="flex items-center gap-2 text-primary hover:text-primary/80"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Customers
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <Link
            href="/internal/admin/customers"
            className="flex items-center gap-2 text-muted-foreground hover:text-foreground mb-2 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Customers
          </Link>
          <h1 className="text-2xl font-bold text-foreground flex items-center gap-3">
            <User className="w-7 h-7 text-primary" />
            {isLoading ? (
              <span className="h-8 w-48 bg-muted rounded animate-pulse" />
            ) : (
              tenant?.name ?? 'Tenant Details'
            )}
          </h1>
        </div>

        {/* Actions */}
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
          <ActionButton
            label="Change Tier"
            icon={Settings}
            onClick={() => setShowTierModal(true)}
            variant="primary"
            disabled={isLoading}
          />
          <ActionButton
            label="Apply Credit"
            icon={CreditCard}
            onClick={() => setShowCreditModal(true)}
            disabled={isLoading}
          />
        </div>
      </div>

      {/* Error state */}
      {error && (
        <div className="bg-status-danger/10 border border-status-danger/20 rounded-lg p-4 flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 text-status-danger" />
          <div>
            <p className="text-status-danger font-medium">Failed to load tenant</p>
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

      {/* Tenant details */}
      <TenantDetailCard tenant={tenant ?? null} isLoading={isLoading} />

      {/* Feature flags */}
      {!isLoading && tenant && (
        <FeatureFlagOverrides tenantId={tenantId} />
      )}

      {/* Subscription history */}
      <SubscriptionHistory
        events={tenant?.subscription_history ?? []}
        activity={tenant?.recent_activity ?? []}
        isLoading={isLoading}
      />

      {/* Modals */}
      {tenant && (
        <>
          <TierChangeModal
            isOpen={showTierModal}
            onClose={() => setShowTierModal(false)}
            tenantId={tenantId}
            tenantName={tenant.name}
            currentTier={tenant.tier}
            clientCount={tenant.client_count}
            onSuccess={() => refetch()}
          />

          <CreditModal
            isOpen={showCreditModal}
            onClose={() => setShowCreditModal(false)}
            tenantId={tenantId}
            tenantName={tenant.name}
            onSuccess={() => refetch()}
          />
        </>
      )}
    </div>
  );
}
