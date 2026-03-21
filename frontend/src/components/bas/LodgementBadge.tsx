'use client';

/**
 * Lodgement Badge Component
 *
 * Displays lodgement status indicator and summary information.
 * Spec 011: Interim Lodgement
 */

import {
  Building2,
  Calendar,
  CheckCircle2,
  Clock,
  ExternalLink,
  FileText,
  PencilLine,
} from 'lucide-react';

import {
  type BASSession,
  type LodgementMethod,
  getLodgementMethodLabel,
} from '@/lib/bas';

interface LodgementBadgeProps {
  session: BASSession;
  variant?: 'compact' | 'detailed';
  onEditClick?: () => void;
}

export function LodgementBadge({
  session,
  variant = 'compact',
  onEditClick,
}: LodgementBadgeProps) {
  const isLodged = session.status === 'lodged' || !!session.lodged_at;
  const isPending = session.status === 'approved' && !session.lodged_at;

  const formatDateTime = (dateStr: string | null) => {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleDateString('en-AU', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const getMethodIcon = (method: LodgementMethod | null) => {
    switch (method) {
      case 'ATO_PORTAL':
        return Building2;
      case 'XERO':
        return ExternalLink;
      case 'OTHER':
        return FileText;
      default:
        return FileText;
    }
  };

  if (!isLodged && !isPending) {
    return null;
  }

  // Compact variant - just a small badge
  if (variant === 'compact') {
    if (isLodged) {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-emerald-100 text-emerald-700 text-[10px] font-bold uppercase tracking-wide rounded-md">
          <CheckCircle2 className="w-3 h-3" />
          Lodged
        </span>
      );
    }

    if (isPending) {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-amber-100 text-amber-700 text-[10px] font-bold uppercase tracking-wide rounded-md">
          <Clock className="w-3 h-3" />
          Pending
        </span>
      );
    }

    return null;
  }

  // Detailed variant - full lodgement info card
  if (isLodged) {
    const MethodIcon = getMethodIcon(session.lodgement_method);

    return (
      <div className="bg-emerald-50/50 border border-emerald-200/50 rounded-xl p-4">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-emerald-100 rounded-xl flex items-center justify-center">
              <CheckCircle2 className="w-5 h-5 text-emerald-600" />
            </div>
            <div>
              <h5 className="font-semibold text-emerald-900 text-sm">Lodged with ATO</h5>
              <div className="flex items-center gap-2 mt-0.5">
                <Calendar className="w-3 h-3 text-emerald-600" />
                <span className="text-emerald-700 text-xs">
                  {formatDateTime(session.lodged_at)}
                </span>
              </div>
            </div>
          </div>
          {onEditClick && (
            <button
              onClick={onEditClick}
              className="p-2 text-emerald-600 hover:text-emerald-800 hover:bg-emerald-100 rounded-lg transition-all"
              title="Edit lodgement details"
            >
              <PencilLine className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* Lodgement Details */}
        <div className="mt-4 grid grid-cols-2 gap-3">
          <div className="bg-white/60 rounded-lg p-3">
            <div className="flex items-center gap-2 text-emerald-600 mb-1">
              <MethodIcon className="w-3.5 h-3.5" />
              <span className="text-[10px] font-semibold uppercase tracking-wide">Method</span>
            </div>
            <p className="text-sm text-foreground font-medium">
              {getLodgementMethodLabel(session.lodgement_method)}
            </p>
            {session.lodgement_method_description && (
              <p className="text-xs text-muted-foreground mt-0.5">
                {session.lodgement_method_description}
              </p>
            )}
          </div>

          {session.ato_reference_number && (
            <div className="bg-white/60 rounded-lg p-3">
              <div className="flex items-center gap-2 text-emerald-600 mb-1">
                <FileText className="w-3.5 h-3.5" />
                <span className="text-[10px] font-semibold uppercase tracking-wide">ATO Reference</span>
              </div>
              <p className="text-sm text-foreground font-mono font-medium">
                {session.ato_reference_number}
              </p>
            </div>
          )}

          {session.lodged_by_name && (
            <div className="bg-white/60 rounded-lg p-3">
              <span className="text-[10px] font-semibold uppercase tracking-wide text-emerald-600">
                Lodged by
              </span>
              <p className="text-sm text-foreground font-medium mt-1">
                {session.lodged_by_name}
              </p>
            </div>
          )}
        </div>

        {/* Notes */}
        {session.lodgement_notes && (
          <div className="mt-3 pt-3 border-t border-emerald-200/50">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-emerald-600 mb-1">
              Notes
            </p>
            <p className="text-sm text-muted-foreground">
              {session.lodgement_notes}
            </p>
          </div>
        )}
      </div>
    );
  }

  // Pending lodgement state
  if (isPending) {
    return (
      <div className="bg-amber-50/50 border border-amber-200/50 rounded-xl p-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-amber-100 rounded-xl flex items-center justify-center">
            <Clock className="w-5 h-5 text-amber-600" />
          </div>
          <div className="flex-1">
            <h5 className="font-semibold text-amber-900 text-sm">Approved - Pending Lodgement</h5>
            <p className="text-amber-700/70 text-xs mt-0.5">
              Record lodgement details once submitted to the ATO
            </p>
          </div>
        </div>
      </div>
    );
  }

  return null;
}

export default LodgementBadge;
