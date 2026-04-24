'use client';

import { AlertTriangle } from 'lucide-react';
import { useState } from 'react';

import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { apiClient } from '@/lib/api-client';

interface GSTBasisModalProps {
  open: boolean;
  connectionId: string;
  getToken: () => Promise<string | null>;
  /** Current saved basis — null means first-time setup, non-null means change */
  currentBasis: string | null;
  /** Whether the current BAS session is already lodged */
  isLodged?: boolean;
  onClose: () => void;
  onSaved: (basis: string) => void;
}

export function GSTBasisModal({
  open,
  connectionId,
  getToken,
  currentBasis,
  isLodged = false,
  onClose,
  onSaved,
}: GSTBasisModalProps) {
  const [selectedBasis, setSelectedBasis] = useState<'cash' | 'accrual' | null>(
    currentBasis as 'cash' | 'accrual' | null
  );
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isChanging = currentBasis !== null;

  const handleSave = async () => {
    if (!selectedBasis) return;
    setIsSaving(true);
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error('Not authenticated');
      const response = await apiClient.patch(
        `/api/v1/clients/${connectionId}/gst-basis`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ gst_reporting_basis: selectedBasis }),
        }
      );
      await apiClient.handleResponse(response);
      onSaved(selectedBasis);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save GST basis');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>
            {isChanging ? 'Change GST Reporting Basis' : 'Select GST Reporting Basis'}
          </DialogTitle>
          <DialogDescription>
            {isChanging
              ? 'Changing the basis will reload all figures. Any manual adjustments will be lost.'
              : 'This determines how Xero data is filtered when calculating BAS figures.'}
          </DialogDescription>
        </DialogHeader>

        {isLodged && (
          <div className="flex items-start gap-2 rounded-lg bg-status-warning/10 border border-status-warning/20 p-3 text-sm text-status-warning">
            <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
            <span>
              This period has been lodged with the ATO. Changing the basis will require you to lodge an amended BAS.
            </span>
          </div>
        )}

        <div className="space-y-3">
          <button
            type="button"
            onClick={() => setSelectedBasis('accrual')}
            className={`w-full text-left rounded-xl border p-4 transition-colors ${
              selectedBasis === 'accrual'
                ? 'border-primary bg-primary/5'
                : 'border-border hover:border-primary/50'
            }`}
          >
            <p className="font-semibold text-sm">Accrual basis</p>
            <p className="text-xs text-muted-foreground mt-1">
              GST is reported when invoices are issued, regardless of payment.
            </p>
          </button>

          <button
            type="button"
            onClick={() => setSelectedBasis('cash')}
            className={`w-full text-left rounded-xl border p-4 transition-colors ${
              selectedBasis === 'cash'
                ? 'border-primary bg-primary/5'
                : 'border-border hover:border-primary/50'
            }`}
          >
            <p className="font-semibold text-sm">Cash basis</p>
            <p className="text-xs text-muted-foreground mt-1">
              GST is reported when payment is received or made.
            </p>
          </button>
        </div>

        {error && (
          <p className="text-sm text-status-danger">{error}</p>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={isSaving}>
            Cancel
          </Button>
          <Button
            onClick={handleSave}
            disabled={!selectedBasis || isSaving}
          >
            {isSaving ? 'Saving...' : isChanging ? 'Change basis' : 'Confirm basis'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
