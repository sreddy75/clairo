'use client';

/**
 * TierChangeModal Component
 *
 * Modal for changing a tenant's subscription tier.
 *
 * Spec 022: Admin Dashboard (Internal)
 */

import { AlertTriangle, Loader2, X } from 'lucide-react';
import { useState } from 'react';

import { useTierChange } from '@/hooks/useAdminDashboard';
import type { SubscriptionTierType } from '@/types/admin';

interface TierChangeModalProps {
  isOpen: boolean;
  onClose: () => void;
  tenantId: string;
  tenantName: string;
  currentTier: SubscriptionTierType;
  clientCount: number;
  onSuccess?: () => void;
}

/**
 * Tier limits for validation.
 */
const TIER_LIMITS: Record<SubscriptionTierType, number | null> = {
  starter: 25,
  professional: 100,
  growth: 250,
  enterprise: null, // Unlimited
};

/**
 * Tier display names and colors.
 */
const TIER_INFO: Record<
  SubscriptionTierType,
  { name: string; color: string; price: string }
> = {
  starter: { name: 'Starter', color: 'bg-muted-foreground', price: '$99/mo' },
  professional: { name: 'Professional', color: 'bg-primary', price: '$299/mo' },
  growth: { name: 'Growth', color: 'bg-purple-500', price: '$599/mo' },
  enterprise: { name: 'Enterprise', color: 'bg-status-warning', price: 'Custom' },
};

const TIERS: SubscriptionTierType[] = ['starter', 'professional', 'growth', 'enterprise'];

/**
 * Main TierChangeModal component.
 */
export function TierChangeModal({
  isOpen,
  onClose,
  tenantId,
  tenantName,
  currentTier,
  clientCount,
  onSuccess,
}: TierChangeModalProps) {
  const [newTier, setNewTier] = useState<SubscriptionTierType>(currentTier);
  const [reason, setReason] = useState('');
  const [forceDowngrade, setForceDowngrade] = useState(false);

  const tierChange = useTierChange();

  if (!isOpen) return null;

  const isDowngrade = TIERS.indexOf(newTier) < TIERS.indexOf(currentTier);
  const newLimit = TIER_LIMITS[newTier];
  const hasExcessClients = newLimit !== null && clientCount > newLimit;
  const canSubmit =
    newTier !== currentTier &&
    reason.trim().length >= 10 &&
    (!hasExcessClients || forceDowngrade);

  const handleSubmit = async () => {
    if (!canSubmit) return;

    try {
      await tierChange.mutateAsync({
        tenantId,
        request: {
          new_tier: newTier,
          reason: reason.trim(),
          force_downgrade: forceDowngrade,
        },
      });
      onSuccess?.();
      onClose();
    } catch (error) {
      // Error is handled by TanStack Query
      console.error('Tier change failed:', error);
    }
  };

  const handleClose = () => {
    if (!tierChange.isPending) {
      setNewTier(currentTier);
      setReason('');
      setForceDowngrade(false);
      onClose();
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-card rounded-xl max-w-lg w-full mx-4 border border-border shadow-xl">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-border">
          <h2 className="text-lg font-bold text-foreground">Change Subscription Tier</h2>
          <button
            onClick={handleClose}
            disabled={tierChange.isPending}
            className="text-muted-foreground hover:text-foreground transition-colors disabled:opacity-50"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Tenant info */}
          <div className="bg-muted rounded-lg p-4">
            <p className="text-sm text-muted-foreground">Changing tier for</p>
            <p className="text-lg font-medium text-foreground">{tenantName}</p>
            <p className="text-sm text-muted-foreground mt-1">
              Currently: {clientCount} clients
            </p>
          </div>

          {/* Current tier */}
          <div>
            <label className="block text-sm font-medium text-muted-foreground mb-2">
              Current Tier
            </label>
            <div className="flex items-center gap-3">
              <span
                className={`px-3 py-1.5 rounded-full text-sm font-medium text-white ${TIER_INFO[currentTier].color}`}
              >
                {TIER_INFO[currentTier].name}
              </span>
              <span className="text-muted-foreground">{TIER_INFO[currentTier].price}</span>
            </div>
          </div>

          {/* New tier selector */}
          <div>
            <label className="block text-sm font-medium text-muted-foreground mb-2">
              New Tier
            </label>
            <div className="grid grid-cols-2 gap-3">
              {TIERS.map((tier) => {
                const info = TIER_INFO[tier];
                const limit = TIER_LIMITS[tier];
                const isSelected = tier === newTier;
                const wouldExceedLimit = limit !== null && clientCount > limit;

                return (
                  <button
                    key={tier}
                    onClick={() => setNewTier(tier)}
                    disabled={tier === currentTier}
                    className={`p-3 rounded-lg border transition-all ${
                      isSelected
                        ? 'border-primary bg-primary/10'
                        : tier === currentTier
                          ? 'border-border bg-muted opacity-50 cursor-not-allowed'
                          : 'border-border hover:border-border'
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <span
                        className={`w-3 h-3 rounded-full ${info.color}`}
                      />
                      <span className="text-sm font-medium text-foreground">
                        {info.name}
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground">{info.price}</p>
                    <p className="text-xs text-muted-foreground">
                      {limit ? `${limit} clients` : 'Unlimited clients'}
                    </p>
                    {wouldExceedLimit && (
                      <p className="text-xs text-status-warning mt-1">
                        Exceeds limit
                      </p>
                    )}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Warning for downgrade with excess clients */}
          {isDowngrade && hasExcessClients && (
            <div className="bg-status-warning/10 border border-status-warning/20 rounded-lg p-4">
              <div className="flex items-start gap-3">
                <AlertTriangle className="w-5 h-5 text-status-warning flex-shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm font-medium text-status-warning">
                    Downgrade Warning
                  </p>
                  <p className="text-sm text-status-warning mt-1">
                    This tenant has {clientCount} clients, but the{' '}
                    {TIER_INFO[newTier].name} tier only allows {newLimit} clients.
                    They will need to reduce their client count or be blocked from adding new clients.
                  </p>
                  <label className="flex items-center gap-2 mt-3">
                    <input
                      type="checkbox"
                      checked={forceDowngrade}
                      onChange={(e) => setForceDowngrade(e.target.checked)}
                      className="w-4 h-4 rounded border-border text-status-warning focus:ring-status-warning/20"
                    />
                    <span className="text-sm text-status-warning">
                      I understand and want to proceed
                    </span>
                  </label>
                </div>
              </div>
            </div>
          )}

          {/* Reason */}
          <div>
            <label className="block text-sm font-medium text-muted-foreground mb-2">
              Reason for Change <span className="text-status-danger">*</span>
            </label>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Enter the reason for this tier change (minimum 10 characters)..."
              rows={3}
              className="w-full px-4 py-2 bg-card border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/20 resize-none"
            />
            <p className="text-xs text-muted-foreground mt-1">
              {reason.length}/10 characters minimum
            </p>
          </div>

          {/* Error message */}
          {tierChange.error && (
            <div className="bg-status-danger/10 border border-status-danger/20 rounded-lg p-3">
              <p className="text-sm text-status-danger">
                {tierChange.error instanceof Error
                  ? tierChange.error.message
                  : 'Failed to change tier. Please try again.'}
              </p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 p-6 border-t border-border">
          <button
            onClick={handleClose}
            disabled={tierChange.isPending}
            className="px-4 py-2 bg-muted text-foreground rounded-lg hover:bg-muted transition-colors disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={!canSubmit || tierChange.isPending}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {tierChange.isPending && (
              <Loader2 className="w-4 h-4 animate-spin" />
            )}
            {isDowngrade ? 'Downgrade Tier' : 'Upgrade Tier'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default TierChangeModal;
