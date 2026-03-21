'use client';

import { useAuth } from '@clerk/nextjs';
import {
  AlertCircle,
  AlertTriangle,
  Calculator,
  ChevronDown,
  ChevronUp,
  Info,
  Lightbulb,
  Loader2,
  TrendingDown,
} from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import { formatCurrency } from '@/lib/api/assets';
import { apiClient } from '@/lib/api-client';

// =============================================================================
// Types
// =============================================================================

interface DepreciationByType {
  asset_type_name: string;
  asset_count: number;
  total_purchase_price: number;
  total_book_value: number;
  total_depreciation_this_year: number;
  total_accumulated_depreciation: number;
}

interface DepreciationByMethod {
  method: string;
  method_display_name: string;
  asset_count: number;
  total_book_value: number;
  total_depreciation_this_year: number;
}

interface TaxPlanningInsight {
  insight_type: 'opportunity' | 'warning' | 'info';
  title: string;
  description: string;
  impact_amount: number | null;
  affected_assets: string[];
}

interface FullyDepreciatedAsset {
  asset_id: string;
  asset_name: string;
  asset_number: string | null;
  asset_type_name: string | null;
  purchase_date: string | null;
  purchase_price: number;
  book_value: number;
}

interface DepreciationSummaryData {
  total_assets: number;
  total_purchase_price: number;
  total_book_value: number;
  total_book_depreciation_this_year: number;
  total_book_accumulated_depreciation: number;
  total_tax_depreciation_this_year: number | null;
  by_asset_type: DepreciationByType[];
  by_method: DepreciationByMethod[];
  fully_depreciated_count: number;
  fully_depreciated_assets: FullyDepreciatedAsset[];
  insights: TaxPlanningInsight[];
  financial_year_start: string;
  financial_year_end: string;
}

// =============================================================================
// Component Props
// =============================================================================

interface DepreciationSummaryProps {
  /** Connection ID for the Xero connection */
  connectionId: string;
  /** Callback when data is loaded */
  onDataLoaded?: (data: DepreciationSummaryData) => void;
}

// =============================================================================
// Component
// =============================================================================

/**
 * Comprehensive depreciation summary with tax planning insights.
 */
export function DepreciationSummary({
  connectionId,
  onDataLoaded,
}: DepreciationSummaryProps) {
  const { getToken } = useAuth();
  const [data, setData] = useState<DepreciationSummaryData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showByType, setShowByType] = useState(false);
  const [showByMethod, setShowByMethod] = useState(false);
  const [showFullyDepreciated, setShowFullyDepreciated] = useState(false);

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const token = await getToken();
      if (!token) return;

      const response = await apiClient.get(
        `/api/v1/integrations/xero/connections/${connectionId}/assets/depreciation-summary`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      const result = await apiClient.handleResponse<DepreciationSummaryData>(response);
      setData(result);
      onDataLoaded?.(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load depreciation data');
    } finally {
      setIsLoading(false);
    }
  }, [getToken, connectionId, onDataLoaded]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const getInsightIcon = (type: string) => {
    switch (type) {
      case 'opportunity':
        return <Lightbulb className="w-5 h-5 text-status-success" />;
      case 'warning':
        return <AlertTriangle className="w-5 h-5 text-status-warning" />;
      default:
        return <Info className="w-5 h-5 text-primary" />;
    }
  };

  const getInsightBgColor = (type: string) => {
    switch (type) {
      case 'opportunity':
        return 'bg-status-success/10 border-status-success/20';
      case 'warning':
        return 'bg-status-warning/10 border-status-warning/20';
      default:
        return 'bg-primary/10 border-primary/20';
    }
  };

  // Loading state
  if (isLoading) {
    return (
      <div className="bg-card rounded-lg shadow-sm border border-border p-6">
        <div className="flex items-center justify-center py-8">
          <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="bg-card rounded-lg shadow-sm border border-border p-6">
        <div className="flex items-center gap-2 text-status-danger">
          <AlertCircle className="w-5 h-5" />
          <span>{error}</span>
        </div>
      </div>
    );
  }

  // No data
  if (!data || data.total_assets === 0) {
    return (
      <div className="bg-card rounded-lg shadow-sm border border-border p-6">
        <div className="flex items-center gap-2 text-muted-foreground">
          <Calculator className="w-5 h-5" />
          <span>No registered assets to show depreciation summary.</span>
        </div>
      </div>
    );
  }

  const fyStartYear = new Date(data.financial_year_start).getFullYear();
  const fyEndYear = new Date(data.financial_year_end).getFullYear();

  return (
    <div className="space-y-6">
      {/* Main Summary Card */}
      <div className="bg-card rounded-lg shadow-sm border border-border p-6">
        <div className="flex items-center gap-2 mb-4">
          <Calculator className="h-5 w-5 text-muted-foreground" />
          <h2 className="text-lg font-medium text-foreground">
            Depreciation Summary - FY{fyStartYear}/{fyEndYear}
          </h2>
        </div>

        {/* Summary Stats */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <div className="bg-muted rounded-lg p-4">
            <div className="text-sm text-muted-foreground">Registered Assets</div>
            <div className="text-2xl font-bold text-foreground">{data.total_assets}</div>
          </div>
          <div className="bg-muted rounded-lg p-4">
            <div className="text-sm text-muted-foreground">Total Purchase Price</div>
            <div className="text-2xl font-bold text-foreground">
              {formatCurrency(data.total_purchase_price)}
            </div>
          </div>
          <div className="bg-muted rounded-lg p-4">
            <div className="text-sm text-muted-foreground">Current Book Value</div>
            <div className="text-2xl font-bold text-foreground">
              {formatCurrency(data.total_book_value)}
            </div>
          </div>
          <div className="bg-status-warning/10 rounded-lg p-4">
            <div className="text-sm text-status-warning flex items-center gap-1">
              <TrendingDown className="w-4 h-4" />
              Depreciation (This Year)
            </div>
            <div className="text-2xl font-bold text-status-warning">
              {formatCurrency(data.total_book_depreciation_this_year)}
            </div>
          </div>
        </div>

        {/* Tax vs Book Comparison */}
        {data.total_tax_depreciation_this_year !== null && (
          <div className="bg-primary/10 rounded-lg p-4 mb-6">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm text-primary">Book Depreciation</div>
                <div className="text-lg font-bold text-primary">
                  {formatCurrency(data.total_book_depreciation_this_year)}
                </div>
              </div>
              <div className="text-right">
                <div className="text-sm text-primary">Tax Depreciation</div>
                <div className="text-lg font-bold text-primary">
                  {formatCurrency(data.total_tax_depreciation_this_year)}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* By Asset Type */}
        {data.by_asset_type.length > 0 && (
          <div className="border-t border-border pt-4">
            <button
              onClick={() => setShowByType(!showByType)}
              className="flex items-center justify-between w-full text-left"
            >
              <span className="text-sm font-medium text-foreground">
                Breakdown by Asset Type ({data.by_asset_type.length})
              </span>
              {showByType ? (
                <ChevronUp className="w-5 h-5 text-muted-foreground" />
              ) : (
                <ChevronDown className="w-5 h-5 text-muted-foreground" />
              )}
            </button>
            {showByType && (
              <div className="mt-3 overflow-x-auto">
                <table className="min-w-full divide-y divide-border">
                  <thead>
                    <tr>
                      <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground uppercase">
                        Type
                      </th>
                      <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground uppercase">
                        Count
                      </th>
                      <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground uppercase">
                        Book Value
                      </th>
                      <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground uppercase">
                        Depreciation (YTD)
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {data.by_asset_type.map((type, idx) => (
                      <tr key={idx}>
                        <td className="px-3 py-2 text-sm text-foreground">{type.asset_type_name}</td>
                        <td className="px-3 py-2 text-sm text-muted-foreground text-right">{type.asset_count}</td>
                        <td className="px-3 py-2 text-sm text-foreground text-right">
                          {formatCurrency(type.total_book_value)}
                        </td>
                        <td className="px-3 py-2 text-sm text-status-warning text-right">
                          {formatCurrency(type.total_depreciation_this_year)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* By Method */}
        {data.by_method.length > 0 && (
          <div className="border-t border-border pt-4 mt-4">
            <button
              onClick={() => setShowByMethod(!showByMethod)}
              className="flex items-center justify-between w-full text-left"
            >
              <span className="text-sm font-medium text-foreground">
                Breakdown by Method ({data.by_method.length})
              </span>
              {showByMethod ? (
                <ChevronUp className="w-5 h-5 text-muted-foreground" />
              ) : (
                <ChevronDown className="w-5 h-5 text-muted-foreground" />
              )}
            </button>
            {showByMethod && (
              <div className="mt-3 overflow-x-auto">
                <table className="min-w-full divide-y divide-border">
                  <thead>
                    <tr>
                      <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground uppercase">
                        Method
                      </th>
                      <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground uppercase">
                        Count
                      </th>
                      <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground uppercase">
                        Book Value
                      </th>
                      <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground uppercase">
                        Depreciation (YTD)
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {data.by_method.map((method, idx) => (
                      <tr key={idx}>
                        <td className="px-3 py-2 text-sm text-foreground">{method.method_display_name}</td>
                        <td className="px-3 py-2 text-sm text-muted-foreground text-right">{method.asset_count}</td>
                        <td className="px-3 py-2 text-sm text-foreground text-right">
                          {formatCurrency(method.total_book_value)}
                        </td>
                        <td className="px-3 py-2 text-sm text-status-warning text-right">
                          {formatCurrency(method.total_depreciation_this_year)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* Fully Depreciated Assets */}
        {data.fully_depreciated_count > 0 && (
          <div className="border-t border-border pt-4 mt-4">
            <button
              onClick={() => setShowFullyDepreciated(!showFullyDepreciated)}
              className="flex items-center justify-between w-full text-left"
            >
              <span className="text-sm font-medium text-foreground">
                Fully Depreciated Assets ({data.fully_depreciated_count})
              </span>
              {showFullyDepreciated ? (
                <ChevronUp className="w-5 h-5 text-muted-foreground" />
              ) : (
                <ChevronDown className="w-5 h-5 text-muted-foreground" />
              )}
            </button>
            {showFullyDepreciated && (
              <div className="mt-3 overflow-x-auto">
                <table className="min-w-full divide-y divide-border">
                  <thead>
                    <tr>
                      <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground uppercase">
                        Asset
                      </th>
                      <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground uppercase">
                        Type
                      </th>
                      <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground uppercase">
                        Purchase Price
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {data.fully_depreciated_assets.map((asset) => (
                      <tr key={asset.asset_id}>
                        <td className="px-3 py-2 text-sm text-foreground">{asset.asset_name}</td>
                        <td className="px-3 py-2 text-sm text-muted-foreground">{asset.asset_type_name || '-'}</td>
                        <td className="px-3 py-2 text-sm text-foreground text-right">
                          {formatCurrency(asset.purchase_price)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Tax Planning Insights */}
      {data.insights.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-sm font-medium text-foreground flex items-center gap-2">
            <Lightbulb className="w-4 h-4" />
            Tax Planning Insights
          </h3>
          {data.insights.map((insight, idx) => (
            <div
              key={idx}
              className={`rounded-lg border p-4 ${getInsightBgColor(insight.insight_type)}`}
            >
              <div className="flex items-start gap-3">
                {getInsightIcon(insight.insight_type)}
                <div className="flex-1">
                  <h4 className="text-sm font-medium text-foreground">{insight.title}</h4>
                  <p className="text-sm text-muted-foreground mt-1">{insight.description}</p>
                  {insight.affected_assets.length > 0 && (
                    <div className="mt-2 text-xs text-muted-foreground">
                      Affected: {insight.affected_assets.join(', ')}
                    </div>
                  )}
                </div>
                {insight.impact_amount !== null && (
                  <div className="text-right">
                    <div className="text-sm font-bold text-foreground">
                      {formatCurrency(insight.impact_amount)}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default DepreciationSummary;
