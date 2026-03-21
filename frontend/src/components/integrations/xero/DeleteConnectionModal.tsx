'use client';

import { useAuth } from '@clerk/nextjs';
import { AlertTriangle, Loader2, Trash2 } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { toast } from 'sonner';

import { apiClient } from '@/lib/api-client';

interface DataCounts {
  clients: number;
  invoices: number;
  bank_transactions: number;
  payments: number;
  credit_notes: number;
  journals: number;
  accounts: number;
  employees: number;
  bas_periods: number;
  quality_scores: number;
  sync_jobs: number;
}

interface DeleteConnectionModalProps {
  connectionId: string;
  organizationName: string;
  onDeleted: () => void;
  onClose: () => void;
}

/**
 * Confirmation modal for permanently deleting a Xero connection and all data.
 * Requires the user to type the organization name to confirm.
 */
export function DeleteConnectionModal({
  connectionId,
  organizationName,
  onDeleted,
  onClose,
}: DeleteConnectionModalProps) {
  const { getToken } = useAuth();
  const [counts, setCounts] = useState<DataCounts | null>(null);
  const [isLoadingCounts, setIsLoadingCounts] = useState(true);
  const [confirmationText, setConfirmationText] = useState('');
  const [reason, setReason] = useState('');
  const [isDeleting, setIsDeleting] = useState(false);

  const isConfirmed = confirmationText.trim() === organizationName.trim();

  const fetchCounts = useCallback(async () => {
    try {
      const token = await getToken();
      if (!token) return;

      const response = await apiClient.get(
        `/api/v1/integrations/xero/connections/${connectionId}/data-counts`,
        { headers: { Authorization: `Bearer ${token}` } }
      );

      if (response.ok) {
        setCounts(await response.json());
      }
    } catch {
      // If counts fail to load, still allow deletion
    } finally {
      setIsLoadingCounts(false);
    }
  }, [getToken, connectionId]);

  useEffect(() => {
    fetchCounts();
  }, [fetchCounts]);

  const totalRecords = counts
    ? Object.values(counts).reduce((sum, n) => sum + n, 0)
    : 0;

  const handleDelete = async () => {
    if (!isConfirmed) return;

    setIsDeleting(true);
    try {
      const token = await getToken();
      if (!token) throw new Error('Authentication required');

      const response = await apiClient.delete(
        `/api/v1/integrations/xero/connections/${connectionId}/all-data`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            confirmation_name: confirmationText.trim(),
            reason: reason.trim() || null,
          }),
        }
      );

      if (!response.ok) {
        const data = await response.json().catch(() => null);
        throw new Error(
          data?.error?.message || `Failed to delete (${response.status})`
        );
      }

      toast.success(`Deleted ${organizationName} and all associated data`);
      onDeleted();
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : 'Failed to delete connection'
      );
    } finally {
      setIsDeleting(false);
    }
  };

  const countRows: { label: string; key: keyof DataCounts }[] = [
    { label: 'Clients / Contacts', key: 'clients' },
    { label: 'Invoices', key: 'invoices' },
    { label: 'Bank Transactions', key: 'bank_transactions' },
    { label: 'Payments', key: 'payments' },
    { label: 'Credit Notes', key: 'credit_notes' },
    { label: 'Journals', key: 'journals' },
    { label: 'Chart of Accounts', key: 'accounts' },
    { label: 'Employees', key: 'employees' },
    { label: 'BAS Periods', key: 'bas_periods' },
    { label: 'Quality Scores', key: 'quality_scores' },
    { label: 'Sync Jobs', key: 'sync_jobs' },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50"
        onClick={isDeleting ? undefined : onClose}
      />

      {/* Modal */}
      <div className="relative bg-card rounded-xl shadow-2xl w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="p-6 border-b border-status-danger/20 bg-status-danger/10 rounded-t-xl">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-status-danger/20 rounded-full flex items-center justify-center">
              <AlertTriangle className="w-5 h-5 text-status-danger" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-status-danger">
                Delete Connection & All Data
              </h3>
              <p className="text-sm text-status-danger/80">
                This action is permanent and cannot be undone.
              </p>
            </div>
          </div>
        </div>

        {/* Body */}
        <div className="p-6 space-y-5">
          {/* What will be deleted */}
          <div>
            <p className="text-sm text-foreground mb-3">
              This will permanently delete{' '}
              <span className="font-semibold text-foreground">
                {organizationName}
              </span>{' '}
              and all associated data:
            </p>

            {isLoadingCounts ? (
              <div className="flex items-center justify-center py-4">
                <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
              </div>
            ) : counts ? (
              <div className="bg-muted rounded-lg border border-border overflow-hidden">
                <div className="divide-y divide-border">
                  {countRows
                    .filter((row) => (counts[row.key] ?? 0) > 0)
                    .map((row) => (
                      <div
                        key={row.key}
                        className="flex items-center justify-between px-4 py-2"
                      >
                        <span className="text-sm text-muted-foreground">
                          {row.label}
                        </span>
                        <span className="text-sm font-medium text-foreground">
                          {counts[row.key].toLocaleString()}
                        </span>
                      </div>
                    ))}
                </div>
                <div className="border-t-2 border-border px-4 py-2 bg-muted">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-semibold text-foreground">
                      Total records
                    </span>
                    <span className="text-sm font-bold text-status-danger">
                      {totalRecords.toLocaleString()}
                    </span>
                  </div>
                </div>
              </div>
            ) : null}
          </div>

          {/* Type to confirm */}
          <div>
            <label className="block text-sm font-medium text-foreground mb-1.5">
              Type{' '}
              <span className="font-mono bg-muted px-1.5 py-0.5 rounded text-status-danger">
                {organizationName}
              </span>{' '}
              to confirm
            </label>
            <input
              type="text"
              value={confirmationText}
              onChange={(e) => setConfirmationText(e.target.value)}
              placeholder={organizationName}
              disabled={isDeleting}
              className="w-full px-3 py-2 text-sm border border-border rounded-lg bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-status-danger focus:border-status-danger disabled:opacity-50"
              autoComplete="off"
              spellCheck={false}
            />
          </div>

          {/* Optional reason */}
          <div>
            <label className="block text-sm font-medium text-foreground mb-1.5">
              Reason{' '}
              <span className="text-muted-foreground font-normal">
                (optional)
              </span>
            </label>
            <input
              type="text"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="e.g. Client no longer managed"
              disabled={isDeleting}
              className="w-full px-3 py-2 text-sm border border-border rounded-lg bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary disabled:opacity-50"
              maxLength={500}
            />
          </div>
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-border flex items-center justify-end gap-3">
          <button
            onClick={onClose}
            disabled={isDeleting}
            className="px-4 py-2 text-sm font-medium text-foreground hover:bg-muted rounded-lg transition-colors disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={handleDelete}
            disabled={!isConfirmed || isDeleting}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-status-danger hover:bg-status-danger/90 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isDeleting ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Trash2 className="w-4 h-4" />
            )}
            Delete Everything
          </button>
        </div>
      </div>
    </div>
  );
}

export default DeleteConnectionModal;
