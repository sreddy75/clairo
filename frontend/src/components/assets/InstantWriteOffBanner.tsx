'use client';

import { useAuth } from '@clerk/nextjs';
import {
  AlertCircle,
  AlertTriangle,
  Calculator,
  ChevronDown,
  ChevronUp,
  DollarSign,
  Loader2,
  Sparkles,
} from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import { formatCurrency, formatDate } from '@/lib/api/assets';
import { apiClient } from '@/lib/api-client';

// =============================================================================
// Types
// =============================================================================

interface WriteOffEligibleAsset {
  asset_id: string;
  xero_asset_id: string;
  asset_name: string;
  asset_number: string | null;
  purchase_date: string | null;
  purchase_price: number;
  asset_type_name: string | null;
  status: string;
}

interface WriteOffSummary {
  is_eligible_business: boolean;
  ineligibility_reason: string | null;
  write_off_threshold: number;
  threshold_type: string;
  financial_year_start: string;
  financial_year_end: string;
  eligible_assets: WriteOffEligibleAsset[];
  total_eligible_amount: number;
  asset_count: number;
}

// =============================================================================
// Component Props
// =============================================================================

interface InstantWriteOffBannerProps {
  /** Connection ID for the Xero connection */
  connectionId: string;
  /** Whether the business is GST registered */
  isGstRegistered?: boolean;
  /** Optional estimated annual turnover */
  estimatedTurnover?: number;
  /** Callback when eligibility data is loaded */
  onDataLoaded?: (data: WriteOffSummary) => void;
}

// =============================================================================
// Component
// =============================================================================

/**
 * Displays a banner showing instant asset write-off eligibility and summary.
 *
 * Shows eligible assets under the ATO threshold purchased in the current FY.
 */
export function InstantWriteOffBanner({
  connectionId,
  isGstRegistered = true,
  estimatedTurnover,
  onDataLoaded,
}: InstantWriteOffBannerProps) {
  const { getToken } = useAuth();
  const [data, setData] = useState<WriteOffSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isExpanded, setIsExpanded] = useState(false);

  const fetchWriteOffData = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const token = await getToken();
      if (!token) return;

      const params = new URLSearchParams();
      params.set('is_gst_registered', String(isGstRegistered));
      if (estimatedTurnover !== undefined) {
        params.set('estimated_turnover', String(estimatedTurnover));
      }

      const response = await apiClient.get(
        `/api/v1/integrations/xero/connections/${connectionId}/assets/instant-write-off?${params.toString()}`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      const result = await apiClient.handleResponse<WriteOffSummary>(response);
      setData(result);
      onDataLoaded?.(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load write-off data');
    } finally {
      setIsLoading(false);
    }
  }, [getToken, connectionId, isGstRegistered, estimatedTurnover, onDataLoaded]);

  useEffect(() => {
    fetchWriteOffData();
  }, [fetchWriteOffData]);

  // Loading state
  if (isLoading) {
    return (
      <div className="bg-primary/10 border border-primary/20 rounded-lg p-4">
        <div className="flex items-center gap-2 text-primary">
          <Loader2 className="w-5 h-5 animate-spin" />
          <span className="text-sm">Checking instant write-off eligibility...</span>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="bg-status-danger/10 border border-status-danger/20 rounded-lg p-4">
        <div className="flex items-center gap-2 text-status-danger">
          <AlertCircle className="w-5 h-5" />
          <span className="text-sm">{error}</span>
        </div>
      </div>
    );
  }

  // No data
  if (!data) {
    return null;
  }

  // Not eligible business
  if (!data.is_eligible_business) {
    return (
      <div className="bg-status-warning/10 border border-status-warning/20 rounded-lg p-4">
        <div className="flex items-center gap-3">
          <div className="flex-shrink-0">
            <AlertTriangle className="w-6 h-6 text-status-warning" />
          </div>
          <div>
            <h3 className="text-sm font-medium text-status-warning">
              Instant Asset Write-Off Not Available
            </h3>
            <p className="text-sm text-status-warning mt-1">
              {data.ineligibility_reason ||
                'This business does not meet the eligibility criteria for instant asset write-off.'}
            </p>
          </div>
        </div>
      </div>
    );
  }

  // No eligible assets
  if (data.asset_count === 0) {
    return (
      <div className="bg-muted border border-border rounded-lg p-4">
        <div className="flex items-center gap-3">
          <div className="flex-shrink-0">
            <Calculator className="w-6 h-6 text-muted-foreground" />
          </div>
          <div>
            <h3 className="text-sm font-medium text-foreground">
              No Eligible Assets for Instant Write-Off
            </h3>
            <p className="text-sm text-muted-foreground mt-1">
              No assets under {formatCurrency(data.write_off_threshold)} were purchased in FY{' '}
              {new Date(data.financial_year_start).getFullYear()}/
              {new Date(data.financial_year_end).getFullYear()}.
            </p>
          </div>
        </div>
      </div>
    );
  }

  // Eligible assets found
  return (
    <div className="bg-status-success/10 border border-status-success/20 rounded-lg overflow-hidden">
      {/* Header */}
      <div
        className="p-4 cursor-pointer hover:bg-status-success/20 transition-colors"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex-shrink-0">
              <div className="w-10 h-10 bg-status-success/20 rounded-full flex items-center justify-center">
                <Sparkles className="w-5 h-5 text-status-success" />
              </div>
            </div>
            <div>
              <h3 className="text-sm font-medium text-status-success flex items-center gap-2">
                Instant Asset Write-Off Available
                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-status-success/20 text-status-success">
                  {data.asset_count} asset{data.asset_count !== 1 ? 's' : ''}
                </span>
              </h3>
              <p className="text-sm text-status-success mt-0.5">
                <span className="font-medium">{formatCurrency(data.total_eligible_amount)}</span>{' '}
                potential deduction for FY{' '}
                {new Date(data.financial_year_start).getFullYear()}/
                {new Date(data.financial_year_end).getFullYear()}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <div className="text-right hidden sm:block">
              <div className="text-xs text-status-success">Threshold</div>
              <div className="text-sm font-medium text-status-success">
                {formatCurrency(data.write_off_threshold)}
                <span className="text-xs text-status-success ml-1">
                  ({data.threshold_type === 'gst_exclusive' ? 'excl. GST' : 'incl. GST'})
                </span>
              </div>
            </div>
            {isExpanded ? (
              <ChevronUp className="w-5 h-5 text-status-success" />
            ) : (
              <ChevronDown className="w-5 h-5 text-status-success" />
            )}
          </div>
        </div>
      </div>

      {/* Expanded asset list */}
      {isExpanded && (
        <div className="border-t border-status-success/20 bg-card">
          <div className="p-4">
            <h4 className="text-sm font-medium text-foreground mb-3">
              Eligible Assets for Instant Write-Off
            </h4>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-border">
                <thead>
                  <tr>
                    <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground uppercase">
                      Asset
                    </th>
                    <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground uppercase">
                      Type
                    </th>
                    <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground uppercase">
                      Purchase Date
                    </th>
                    <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground uppercase">
                      Purchase Price
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {data.eligible_assets.map((asset) => (
                    <tr key={asset.asset_id} className="hover:bg-muted">
                      <td className="px-3 py-2 text-sm text-foreground">
                        <div className="font-medium">{asset.asset_name}</div>
                        {asset.asset_number && (
                          <div className="text-xs text-muted-foreground">{asset.asset_number}</div>
                        )}
                      </td>
                      <td className="px-3 py-2 text-sm text-muted-foreground">
                        {asset.asset_type_name || '-'}
                      </td>
                      <td className="px-3 py-2 text-sm text-muted-foreground">
                        {formatDate(asset.purchase_date)}
                      </td>
                      <td className="px-3 py-2 text-sm text-foreground text-right font-medium">
                        <span className="inline-flex items-center gap-1">
                          <DollarSign className="w-3 h-3 text-status-success" />
                          {formatCurrency(asset.purchase_price).replace('$', '')}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr className="bg-status-success/10">
                    <td
                      colSpan={3}
                      className="px-3 py-2 text-sm font-medium text-status-success"
                    >
                      Total Potential Deduction
                    </td>
                    <td className="px-3 py-2 text-sm font-bold text-status-success text-right">
                      {formatCurrency(data.total_eligible_amount)}
                    </td>
                  </tr>
                </tfoot>
              </table>
            </div>
            <p className="text-xs text-muted-foreground mt-4">
              Assets purchased for less than {formatCurrency(data.write_off_threshold)} in the
              current financial year may be immediately deducted. Consult with a tax professional
              for specific advice.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

export default InstantWriteOffBanner;
