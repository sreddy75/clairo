'use client';

import { useAuth } from '@clerk/nextjs';
import {
  AlertCircle,
  Calendar,
  ChevronLeft,
  ChevronRight,
  Clock,
  Loader2,
  RefreshCw,
  ShoppingCart,
  Truck,
  User,
} from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import type {
  PurchaseOrder,
  PurchaseOrderStatus,
  PurchaseOrderSummary} from '@/lib/api/assets';
import {
  formatCurrency,
  formatDate,
  getPurchaseOrderStatusColor,
  getPurchaseOrders,
  getPurchaseOrderSummary,
  syncPurchaseOrders,
} from '@/lib/api/assets';

interface PurchaseOrdersListProps {
  /** Connection ID for the Xero connection */
  connectionId: string;
  /** Number of items per page */
  pageSize?: number;
  /** Optional filter by status */
  statusFilter?: PurchaseOrderStatus;
  /** Show summary card */
  showSummary?: boolean;
}

/**
 * Displays a paginated list of purchase orders with optional summary.
 */
export function PurchaseOrdersList({
  connectionId,
  pageSize = 25,
  statusFilter,
  showSummary = true,
}: PurchaseOrdersListProps) {
  const { getToken } = useAuth();
  const [orders, setOrders] = useState<PurchaseOrder[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<PurchaseOrderSummary | null>(null);

  const fetchOrders = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const token = await getToken();
      if (!token) return;

      const [ordersResponse, summaryResponse] = await Promise.all([
        getPurchaseOrders(token, connectionId, {
          limit: pageSize,
          offset: page * pageSize,
          status: statusFilter,
        }),
        showSummary ? getPurchaseOrderSummary(token, connectionId) : Promise.resolve(null),
      ]);

      setOrders(ordersResponse.orders);
      setTotal(ordersResponse.total);
      if (summaryResponse) {
        setSummary(summaryResponse);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load purchase orders');
    } finally {
      setIsLoading(false);
    }
  }, [getToken, connectionId, pageSize, page, statusFilter, showSummary]);

  const handleSync = async () => {
    setIsSyncing(true);
    try {
      const token = await getToken();
      if (!token) return;

      await syncPurchaseOrders(token, connectionId);
      await fetchOrders();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to sync purchase orders');
    } finally {
      setIsSyncing(false);
    }
  };

  useEffect(() => {
    fetchOrders();
  }, [fetchOrders]);

  const totalPages = Math.ceil(total / pageSize);

  // Loading state
  if (isLoading && orders.length === 0) {
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
          onClick={fetchOrders}
          className="text-sm text-primary hover:text-blue-800 font-medium"
        >
          Try again
        </button>
      </div>
    );
  }

  // Empty state
  if (orders.length === 0) {
    return (
      <div className="text-center py-12">
        <ShoppingCart className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
        <h3 className="text-lg font-medium text-foreground mb-2">No purchase orders</h3>
        <p className="text-muted-foreground mb-4">
          {statusFilter
            ? `No ${statusFilter.toLowerCase()} purchase orders found.`
            : 'No purchase orders have been synced yet.'}
        </p>
        <button
          onClick={handleSync}
          disabled={isSyncing}
          className="inline-flex items-center gap-2 px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary/90 disabled:opacity-50"
        >
          {isSyncing ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <RefreshCw className="w-4 h-4" />
          )}
          Sync Purchase Orders from Xero
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Summary Cards */}
      {showSummary && summary && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <div className="bg-white border border-border rounded-lg p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-orange-100 rounded-lg">
                <Clock className="w-5 h-5 text-orange-600" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Outstanding Orders</p>
                <p className="text-xl font-semibold text-foreground">
                  {summary.outstanding_count}
                </p>
              </div>
            </div>
          </div>
          <div className="bg-white border border-border rounded-lg p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-blue-100 rounded-lg">
                <ShoppingCart className="w-5 h-5 text-primary" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Outstanding Value</p>
                <p className="text-xl font-semibold text-foreground">
                  {formatCurrency(summary.outstanding_total)}
                </p>
              </div>
            </div>
          </div>
          <div className="bg-white border border-border rounded-lg p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-green-100 rounded-lg">
                <Truck className="w-5 h-5 text-green-600" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Upcoming Deliveries</p>
                <p className="text-xl font-semibold text-foreground">
                  {summary.upcoming_deliveries.length}
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Header with sync button */}
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-medium text-foreground">
          Purchase Orders ({total})
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

      {/* Purchase Orders table */}
      <div className="overflow-hidden bg-white border border-border rounded-lg">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-border">
            <thead className="bg-muted">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  PO Number
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Vendor
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Status
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Date
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Delivery
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Total
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {orders.map((order) => (
                <tr key={order.id} className="hover:bg-muted">
                  <td className="px-4 py-3 whitespace-nowrap">
                    <div className="flex items-center gap-3">
                      <ShoppingCart className="w-5 h-5 text-muted-foreground" />
                      <div>
                        <div className="text-sm font-medium text-foreground">
                          {order.purchase_order_number || 'No number'}
                        </div>
                        {order.reference && (
                          <div className="text-xs text-muted-foreground">
                            {order.reference}
                          </div>
                        )}
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap">
                    <div className="flex items-center gap-2">
                      <User className="w-4 h-4 text-muted-foreground" />
                      <span className="text-sm text-foreground">
                        {order.contact_name || 'Unknown'}
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap">
                    <span
                      className={`inline-flex px-2 py-0.5 text-xs font-medium rounded-full ${getPurchaseOrderStatusColor(
                        order.status
                      )}`}
                    >
                      {order.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap">
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      <Calendar className="w-4 h-4" />
                      {formatDate(order.date)}
                    </div>
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap">
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      <Truck className="w-4 h-4" />
                      {formatDate(order.expected_arrival_date || order.delivery_date)}
                    </div>
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-sm text-foreground text-right font-medium">
                    {formatCurrency(order.total)}
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
            {Math.min((page + 1) * pageSize, total)} of {total} orders
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

export default PurchaseOrdersList;
