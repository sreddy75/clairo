'use client';

import { useAuth } from '@clerk/nextjs';
import {
  AlertCircle,
  Building2,
  ChevronLeft,
  ChevronRight,
  FileText,
  Loader2,
  Package,
  RefreshCw,
} from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import type {
  Asset,
  AssetStatus} from '@/lib/api/assets';
import {
  formatCurrency,
  formatDate,
  getAssets,
  getDepreciationMethodDisplayName,
  getStatusColor,
  syncAssets,
} from '@/lib/api/assets';

interface AssetsListProps {
  /** Connection ID for the Xero connection */
  connectionId: string;
  /** Number of items per page */
  pageSize?: number;
  /** Optional filter by asset status */
  statusFilter?: AssetStatus;
  /** Optional filter by asset type ID */
  assetTypeId?: string;
}

/**
 * Displays a paginated list of fixed assets with depreciation information.
 */
export function AssetsList({
  connectionId,
  pageSize = 25,
  statusFilter,
  assetTypeId,
}: AssetsListProps) {
  const { getToken } = useAuth();
  const [assets, setAssets] = useState<Asset[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchAssets = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const token = await getToken();
      if (!token) return;

      const response = await getAssets(token, connectionId, {
        limit: pageSize,
        offset: page * pageSize,
        status: statusFilter,
        assetTypeId,
      });

      setAssets(response.assets);
      setTotal(response.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load assets');
    } finally {
      setIsLoading(false);
    }
  }, [getToken, connectionId, pageSize, page, statusFilter, assetTypeId]);

  const handleSync = async () => {
    setIsSyncing(true);
    try {
      const token = await getToken();
      if (!token) return;

      await syncAssets(token, connectionId);
      await fetchAssets();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to sync assets');
    } finally {
      setIsSyncing(false);
    }
  };

  useEffect(() => {
    fetchAssets();
  }, [fetchAssets]);

  const totalPages = Math.ceil(total / pageSize);

  // Loading state
  if (isLoading && assets.length === 0) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="text-center py-12">
        <AlertCircle className="w-10 h-10 text-status-danger mx-auto mb-3" />
        <p className="text-status-danger mb-2">{error}</p>
        <button
          onClick={fetchAssets}
          className="text-sm text-primary hover:text-primary/80 font-medium"
        >
          Try again
        </button>
      </div>
    );
  }

  // Empty state
  if (assets.length === 0) {
    return (
      <div className="text-center py-12">
        <Package className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
        <h3 className="text-lg font-medium text-foreground mb-2">No fixed assets</h3>
        <p className="text-muted-foreground mb-4">
          {statusFilter
            ? `No ${statusFilter.toLowerCase()} assets found.`
            : 'No fixed assets have been synced yet.'}
        </p>
        <button
          onClick={handleSync}
          disabled={isSyncing}
          className="inline-flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 disabled:opacity-50"
        >
          {isSyncing ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <RefreshCw className="w-4 h-4" />
          )}
          Sync Assets from Xero
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header with sync button */}
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-medium text-foreground">
          Fixed Assets ({total})
        </h3>
        <button
          onClick={handleSync}
          disabled={isSyncing}
          className="inline-flex items-center gap-2 px-3 py-1.5 text-sm border border-border rounded-lg hover:bg-muted disabled:opacity-50"
        >
          {isSyncing ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <RefreshCw className="w-4 h-4" />
          )}
          Sync
        </button>
      </div>

      {/* Assets table */}
      <div className="overflow-hidden bg-card border border-border rounded-lg">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-border">
            <thead className="bg-muted">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Asset
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Status
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Purchase Date
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Purchase Price
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Book Value
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Depreciation (YTD)
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Method
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {assets.map((asset) => (
                <tr key={asset.id} className="hover:bg-muted">
                  <td className="px-4 py-3 whitespace-nowrap">
                    <div className="flex items-center gap-3">
                      <div className="flex-shrink-0">
                        {asset.asset_type_name?.toLowerCase().includes('building') ? (
                          <Building2 className="w-5 h-5 text-muted-foreground" />
                        ) : asset.asset_type_name?.toLowerCase().includes('vehicle') ? (
                          <FileText className="w-5 h-5 text-muted-foreground" />
                        ) : (
                          <Package className="w-5 h-5 text-muted-foreground" />
                        )}
                      </div>
                      <div>
                        <div className="text-sm font-medium text-foreground">
                          {asset.asset_name}
                        </div>
                        <div className="text-xs text-muted-foreground">
                          {asset.asset_number || asset.asset_type_name || 'No type'}
                        </div>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap">
                    <span
                      className={`inline-flex px-2 py-0.5 text-xs font-medium rounded-full ${getStatusColor(
                        asset.status
                      )}`}
                    >
                      {asset.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-sm text-muted-foreground">
                    {formatDate(asset.purchase_date)}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-sm text-foreground text-right">
                    {formatCurrency(asset.purchase_price)}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-sm text-foreground text-right font-medium">
                    {formatCurrency(asset.book_value)}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-sm text-right">
                    <span className={asset.book_depreciation_this_year && asset.book_depreciation_this_year > 0 ? 'text-status-warning' : 'text-muted-foreground'}>
                      {formatCurrency(asset.book_depreciation_this_year)}
                    </span>
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-sm text-muted-foreground">
                    {getDepreciationMethodDisplayName(asset.book_depreciation_method)}
                    {asset.book_depreciation_rate && (
                      <span className="text-xs text-muted-foreground ml-1">
                        ({asset.book_depreciation_rate}%)
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <div className="text-sm text-muted-foreground">
            Showing {page * pageSize + 1} to{' '}
            {Math.min((page + 1) * pageSize, total)} of {total} assets
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
              className="p-2 text-muted-foreground hover:text-foreground hover:bg-muted rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <ChevronLeft className="w-5 h-5" />
            </button>
            <span className="text-sm text-muted-foreground">
              Page {page + 1} of {totalPages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
              disabled={page >= totalPages - 1}
              className="p-2 text-muted-foreground hover:text-foreground hover:bg-muted rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <ChevronRight className="w-5 h-5" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default AssetsList;
