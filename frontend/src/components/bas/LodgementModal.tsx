'use client';

/**
 * Lodgement Modal Component
 *
 * Modal for recording BAS lodgement details after approval.
 * Spec 011: Interim Lodgement
 */

import {
  Building2,
  CheckCircle2,
  ExternalLink,
  FileText,
  Loader2,
  X,
} from 'lucide-react';
import { useState } from 'react';

import {
  type BASSession,
  type LodgementMethod,
  type LodgementRecordRequest,
  type LodgementUpdateRequest,
  getLodgementMethodDescription,
  getLodgementMethodLabel,
  formatBASCurrency,
} from '@/lib/bas';

interface LodgementModalProps {
  session: BASSession;
  totalPayable: string;
  isRefund: boolean;
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (request: LodgementRecordRequest | LodgementUpdateRequest) => Promise<void>;
  isUpdate?: boolean;
}

const LODGEMENT_METHODS: LodgementMethod[] = ['ATO_PORTAL', 'XERO', 'OTHER'];

export function LodgementModal({
  session,
  totalPayable,
  isRefund,
  isOpen,
  onClose,
  onSubmit,
  isUpdate = false,
}: LodgementModalProps) {
  const [lodgementDate, setLodgementDate] = useState(
    new Date().toISOString().split('T')[0] // Default to today YYYY-MM-DD
  );
  const [selectedMethod, setSelectedMethod] = useState<LodgementMethod>(
    session.lodgement_method || 'ATO_PORTAL'
  );
  const [methodDescription, setMethodDescription] = useState(
    session.lodgement_method_description || ''
  );
  const [atoReference, setAtoReference] = useState(
    session.ato_reference_number || ''
  );
  const [notes, setNotes] = useState(session.lodgement_notes || '');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      let request: LodgementRecordRequest | LodgementUpdateRequest;

      if (isUpdate) {
        // Update only allows changing reference and notes
        request = {
          ato_reference_number: atoReference || undefined,
          lodgement_notes: notes || undefined,
        } as LodgementUpdateRequest;
      } else {
        // New lodgement record - include user-selected lodgement_date
        request = {
          lodgement_date: lodgementDate,
          lodgement_method: selectedMethod,
          lodgement_method_description: methodDescription || undefined,
          ato_reference_number: atoReference || undefined,
          lodgement_notes: notes || undefined,
        } as LodgementRecordRequest;
      }

      await onSubmit(request);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to record lodgement');
    } finally {
      setIsSubmitting(false);
    }
  };

  const getMethodIcon = (method: LodgementMethod) => {
    switch (method) {
      case 'ATO_PORTAL':
        return Building2;
      case 'XERO':
        return ExternalLink;
      case 'OTHER':
        return FileText;
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-lg mx-4 overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-border bg-gradient-to-r from-emerald-50 to-teal-50">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold text-foreground">
                {isUpdate ? 'Update Lodgement Details' : 'Record Lodgement'}
              </h3>
              <p className="text-sm text-muted-foreground">
                {session.period_display_name}
              </p>
            </div>
            <button
              onClick={onClose}
              className="p-2 text-muted-foreground hover:text-muted-foreground hover:bg-muted rounded-lg transition-all"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Summary Banner */}
        <div className={`px-6 py-4 ${isRefund ? 'bg-status-info/10' : 'bg-amber-50'}`}>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                {isRefund ? 'Refund from ATO' : 'Amount Payable to ATO'}
              </p>
              <p className={`text-2xl font-bold ${isRefund ? 'text-status-info' : 'text-amber-700'}`}>
                {formatBASCurrency(Math.abs(parseFloat(totalPayable)))}
              </p>
            </div>
            <CheckCircle2 className={`w-10 h-10 ${isRefund ? 'text-status-info/60' : 'text-amber-400'}`} />
          </div>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-6">
          {/* Lodgement Date - only show for new lodgements */}
          {!isUpdate && (
            <div>
              <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">
                Lodgement Date
              </label>
              <input
                type="date"
                value={lodgementDate}
                onChange={(e) => setLodgementDate(e.target.value)}
                max={new Date().toISOString().split('T')[0]} // Can't be in the future
                required
                className="w-full px-3 py-2.5 bg-white border border-border rounded-lg text-sm focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 outline-none transition-all"
              />
              <p className="text-xs text-muted-foreground mt-1">
                The date when the BAS was lodged with the ATO
              </p>
            </div>
          )}

          {/* Lodgement Method Selection - only for new lodgements */}
          {!isUpdate && (
            <div>
              <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3">
                Lodgement Method
              </label>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                {LODGEMENT_METHODS.map((method) => {
                  const Icon = getMethodIcon(method);
                  const isSelected = selectedMethod === method;

                  return (
                    <button
                      key={method}
                      type="button"
                      onClick={() => setSelectedMethod(method)}
                      className={`flex flex-col items-center gap-2 p-4 rounded-xl border-2 transition-all ${
                        isSelected
                          ? 'border-emerald-500 bg-emerald-50 text-emerald-700'
                          : 'border-border hover:border-border text-muted-foreground hover:bg-muted'
                      }`}
                    >
                      <Icon className={`w-6 h-6 ${isSelected ? 'text-emerald-600' : 'text-muted-foreground'}`} />
                      <span className="text-xs font-semibold text-center leading-tight">
                        {getLodgementMethodLabel(method)}
                      </span>
                    </button>
                  );
                })}
              </div>
              <p className="text-xs text-muted-foreground mt-2">
                {getLodgementMethodDescription(selectedMethod)}
              </p>
            </div>
          )}

          {/* Show current lodgement info when updating (read-only) */}
          {isUpdate && session.lodged_at && (
            <div className="bg-muted rounded-lg p-4 space-y-2">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                Lodgement Record (Read-only)
              </p>
              <div className="text-sm text-foreground">
                <p><span className="font-medium">Date:</span> {new Date(session.lodged_at).toLocaleDateString('en-AU', { day: 'numeric', month: 'short', year: 'numeric' })}</p>
                <p><span className="font-medium">Method:</span> {getLodgementMethodLabel(session.lodgement_method)}</p>
              </div>
            </div>
          )}

          {/* Additional Description (for OTHER method) - only for new lodgements */}
          {!isUpdate && selectedMethod === 'OTHER' && (
            <div>
              <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">
                Method Description
              </label>
              <input
                type="text"
                value={methodDescription}
                onChange={(e) => setMethodDescription(e.target.value)}
                placeholder="e.g., Tax agent portal, MYOB..."
                className="w-full px-3 py-2.5 bg-white border border-border rounded-lg text-sm focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 outline-none transition-all"
              />
            </div>
          )}

          {/* ATO Reference Number */}
          <div>
            <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">
              ATO Reference Number <span className="text-muted-foreground font-normal">(optional)</span>
            </label>
            <input
              type="text"
              value={atoReference}
              onChange={(e) => setAtoReference(e.target.value)}
              placeholder="e.g., REF-123456789"
              className="w-full px-3 py-2.5 bg-white border border-border rounded-lg text-sm focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 outline-none transition-all"
            />
            <p className="text-xs text-muted-foreground mt-1">
              Enter the confirmation or receipt number from the ATO
            </p>
          </div>

          {/* Notes */}
          <div>
            <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">
              Lodgement Notes <span className="text-muted-foreground font-normal">(optional)</span>
            </label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Any additional notes about this lodgement..."
              rows={3}
              className="w-full px-3 py-2.5 bg-white border border-border rounded-lg text-sm focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 outline-none transition-all resize-none"
            />
          </div>

          {/* Error */}
          {error && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
              {error}
            </div>
          )}

          {/* Actions */}
          <div className="flex items-center justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2.5 text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-muted rounded-lg transition-all"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="inline-flex items-center gap-2 px-5 py-2.5 bg-emerald-600 text-white text-sm font-semibold rounded-lg hover:bg-emerald-700 disabled:opacity-50 transition-all"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  {isUpdate ? 'Updating...' : 'Recording...'}
                </>
              ) : (
                <>
                  <CheckCircle2 className="w-4 h-4" />
                  {isUpdate ? 'Update Details' : 'Confirm Lodgement'}
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default LodgementModal;
