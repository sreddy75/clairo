'use client';

/**
 * FeatureFlagOverrides Component
 *
 * Table for viewing and managing tenant feature flag overrides.
 *
 * Spec 022: Admin Dashboard (Internal)
 */

import { AlertTriangle, Loader2, RotateCcw, X } from 'lucide-react';
import { useState } from 'react';

import {
  useDeleteFeatureFlagOverride,
  useSetFeatureFlagOverride,
  useTenantFeatureFlags,
} from '@/hooks/useAdminDashboard';
import type { FeatureFlagStatus, FeatureKeyType } from '@/types/admin';

interface FeatureFlagOverridesProps {
  tenantId: string;
}

/**
 * Feature display names and descriptions.
 */
const FEATURE_INFO: Record<FeatureKeyType, { name: string; description: string }> = {
  ai_insights: {
    name: 'AI Insights',
    description: 'Access to AI-powered BAS analysis and recommendations',
  },
  client_portal: {
    name: 'Client Portal',
    description: 'Enable business owner self-service portal access',
  },
  custom_triggers: {
    name: 'Custom Triggers',
    description: 'Create automated alerts and notifications',
  },
  api_access: {
    name: 'API Access',
    description: 'Enable REST API access for integrations',
  },
  knowledge_base: {
    name: 'Knowledge Base',
    description: 'Access to ATO guidelines and compliance RAG',
  },
  magic_zone: {
    name: 'Magic Zone',
    description: 'Advanced BAS automation features',
  },
};

/**
 * Toggle switch component.
 */
function Toggle({
  enabled,
  onChange,
  disabled = false,
  loading = false,
}: {
  enabled: boolean;
  onChange: () => void;
  disabled?: boolean;
  loading?: boolean;
}) {
  return (
    <button
      onClick={onChange}
      disabled={disabled || loading}
      className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-primary/20 focus:ring-offset-2 ${
        enabled ? 'bg-primary' : 'bg-muted'
      } ${(disabled || loading) ? 'opacity-50 cursor-not-allowed' : ''}`}
    >
      <span
        className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
          enabled ? 'translate-x-6' : 'translate-x-1'
        }`}
      />
      {loading && (
        <span className="absolute inset-0 flex items-center justify-center">
          <Loader2 className="w-3 h-3 animate-spin text-white" />
        </span>
      )}
    </button>
  );
}

/**
 * Reason input modal.
 */
function ReasonModal({
  isOpen,
  onClose,
  onConfirm,
  featureName,
  newValue,
  isLoading,
}: {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (reason: string) => void;
  featureName: string;
  newValue: boolean;
  isLoading: boolean;
}) {
  const [reason, setReason] = useState('');

  if (!isOpen) return null;

  const handleSubmit = () => {
    if (reason.trim().length >= 5) {
      onConfirm(reason.trim());
      setReason('');
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-card rounded-xl max-w-md w-full mx-4 border border-border shadow-xl">
        <div className="flex items-center justify-between p-6 border-b border-border">
          <h2 className="text-lg font-bold text-foreground">
            {newValue ? 'Enable' : 'Disable'} Feature
          </h2>
          <button
            onClick={onClose}
            disabled={isLoading}
            className="text-muted-foreground hover:text-foreground transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="p-6 space-y-4">
          <p className="text-foreground">
            You are about to <strong>{newValue ? 'enable' : 'disable'}</strong>{' '}
            <strong>{featureName}</strong> for this tenant.
          </p>
          <div>
            <label className="block text-sm font-medium text-muted-foreground mb-2">
              Reason <span className="text-status-danger">*</span>
            </label>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Enter reason for this override..."
              rows={3}
              className="w-full px-4 py-2 bg-card border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/20 resize-none"
            />
            <p className="text-xs text-muted-foreground mt-1">
              {reason.length}/5 characters minimum
            </p>
          </div>
        </div>
        <div className="flex justify-end gap-3 p-6 border-t border-border">
          <button
            onClick={onClose}
            disabled={isLoading}
            className="px-4 py-2 bg-muted text-foreground rounded-lg hover:bg-muted transition-colors disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={reason.trim().length < 5 || isLoading}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isLoading && <Loader2 className="w-4 h-4 animate-spin" />}
            Confirm
          </button>
        </div>
      </div>
    </div>
  );
}

/**
 * Main FeatureFlagOverrides component.
 */
export function FeatureFlagOverrides({ tenantId }: FeatureFlagOverridesProps) {
  const { data, isLoading, error, refetch } = useTenantFeatureFlags(tenantId);
  const setOverride = useSetFeatureFlagOverride();
  const deleteOverride = useDeleteFeatureFlagOverride();

  const [pendingToggle, setPendingToggle] = useState<{
    featureKey: FeatureKeyType;
    newValue: boolean;
  } | null>(null);

  const handleToggle = (flag: FeatureFlagStatus) => {
    setPendingToggle({
      featureKey: flag.feature_key,
      newValue: !flag.effective_value,
    });
  };

  const handleConfirmToggle = async (reason: string) => {
    if (!pendingToggle) return;

    try {
      await setOverride.mutateAsync({
        tenantId,
        featureKey: pendingToggle.featureKey,
        request: {
          value: pendingToggle.newValue,
          reason,
        },
      });
      refetch();
    } finally {
      setPendingToggle(null);
    }
  };

  const handleRevertOverride = async (featureKey: FeatureKeyType) => {
    try {
      await deleteOverride.mutateAsync({ tenantId, featureKey });
      refetch();
    } catch (error) {
      console.error('Failed to revert override:', error);
    }
  };

  if (isLoading) {
    return (
      <div className="bg-card rounded-xl border border-border">
        <div className="px-6 py-4 border-b border-border">
          <div className="h-5 bg-muted rounded w-40 animate-pulse" />
        </div>
        <div className="p-6 space-y-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="flex justify-between animate-pulse">
              <div className="h-4 bg-muted rounded w-32" />
              <div className="h-6 bg-muted rounded w-11" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-card rounded-xl border border-border p-6">
        <div className="flex items-center gap-3 text-status-danger">
          <AlertTriangle className="w-5 h-5" />
          <span>Failed to load feature flags</span>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-card rounded-xl border border-border">
      <div className="px-6 py-4 border-b border-border">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-foreground">Feature Flags</h3>
          <span className="text-sm text-muted-foreground">
            Tier: {data?.tier?.charAt(0).toUpperCase()}{data?.tier?.slice(1)}
          </span>
        </div>
      </div>

      <div className="divide-y divide-border">
        {data?.flags.map((flag) => {
          const info = FEATURE_INFO[flag.feature_key];
          const isDeleting = deleteOverride.isPending &&
            deleteOverride.variables?.featureKey === flag.feature_key;

          return (
            <div
              key={flag.feature_key}
              className={`px-6 py-4 ${
                flag.is_overridden ? 'bg-primary/10' : ''
              }`}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-foreground">
                      {info?.name ?? flag.feature_key}
                    </span>
                    {flag.is_overridden && (
                      <span className="text-xs bg-primary/10 text-primary px-2 py-0.5 rounded">
                        Overridden
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-muted-foreground mt-1">
                    {info?.description ?? 'Feature flag'}
                  </p>
                  {flag.is_overridden && flag.override_reason && (
                    <p className="text-xs text-muted-foreground mt-2">
                      Reason: {flag.override_reason}
                    </p>
                  )}
                </div>

                <div className="flex items-center gap-3">
                  {/* Tier default indicator */}
                  <div className="text-right">
                    <span className="text-xs text-muted-foreground block">
                      Tier default
                    </span>
                    <span
                      className={`text-xs ${
                        flag.tier_default ? 'text-status-success' : 'text-muted-foreground'
                      }`}
                    >
                      {flag.tier_default ? 'On' : 'Off'}
                    </span>
                  </div>

                  {/* Toggle */}
                  <Toggle
                    enabled={flag.effective_value}
                    onChange={() => handleToggle(flag)}
                    loading={
                      (setOverride.isPending &&
                        pendingToggle?.featureKey === flag.feature_key) ||
                      isDeleting
                    }
                  />

                  {/* Revert button */}
                  {flag.is_overridden && (
                    <button
                      onClick={() => handleRevertOverride(flag.feature_key)}
                      disabled={isDeleting}
                      className="p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted rounded transition-colors disabled:opacity-50"
                      title="Revert to tier default"
                    >
                      {isDeleting ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <RotateCcw className="w-4 h-4" />
                      )}
                    </button>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Reason modal */}
      {pendingToggle && (
        <ReasonModal
          isOpen={true}
          onClose={() => setPendingToggle(null)}
          onConfirm={handleConfirmToggle}
          featureName={
            FEATURE_INFO[pendingToggle.featureKey]?.name ?? pendingToggle.featureKey
          }
          newValue={pendingToggle.newValue}
          isLoading={setOverride.isPending}
        />
      )}
    </div>
  );
}

export default FeatureFlagOverrides;
