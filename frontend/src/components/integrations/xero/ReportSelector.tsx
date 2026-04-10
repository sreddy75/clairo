'use client';

/**
 * ReportSelector Component
 *
 * A dropdown selector for choosing which Xero financial report to view.
 * Shows report types with sync status indicators.
 *
 * Spec 023: Xero Reports API Integration
 */

import { AlertCircle, Calculator, CheckCircle2, ChevronDown, Clock, RefreshCw } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

import type { ReportStatusItem, XeroReportType } from '@/lib/xero-reports';
import { getReportDisplayName, REPORT_TYPE_DISPLAY_NAMES } from '@/lib/xero-reports';

/**
 * Reports that are computed locally from synced invoice data
 * rather than fetched directly from Xero's Reports API
 */
const COMPUTED_REPORT_TYPES = new Set<XeroReportType>([
  'aged_receivables_by_contact',
  'aged_payables_by_contact',
]);

interface ReportSelectorProps {
  /** Currently selected report type */
  value: XeroReportType | null;
  /** Callback when selection changes */
  onChange: (reportType: XeroReportType) => void;
  /** Report status items from the API (optional) */
  reportStatuses?: ReportStatusItem[];
  /** Whether selector is disabled */
  disabled?: boolean;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Get status indicator for a report type
 */
function getStatusIndicator(status: ReportStatusItem | undefined, reportType?: XeroReportType) {
  // Computed reports always show as ready (computed from synced invoices)
  if (reportType && COMPUTED_REPORT_TYPES.has(reportType)) {
    return {
      icon: <Calculator className="h-3 w-3" />,
      color: 'text-purple-500',
      label: 'Computed',
    };
  }

  if (!status) {
    return { icon: null, color: 'text-muted-foreground', label: '' };
  }

  if (status.sync_status === 'in_progress') {
    return {
      icon: <RefreshCw className="h-3 w-3 animate-spin" />,
      color: 'text-blue-500',
      label: 'Syncing',
    };
  }

  if (status.is_stale) {
    return {
      icon: <AlertCircle className="h-3 w-3" />,
      color: 'text-amber-500',
      label: 'Stale',
    };
  }

  if (status.last_synced_at) {
    return {
      icon: <CheckCircle2 className="h-3 w-3" />,
      color: 'text-green-500',
      label: 'Fresh',
    };
  }

  return {
    icon: <Clock className="h-3 w-3" />,
    color: 'text-muted-foreground',
    label: 'Not synced',
  };
}

/**
 * Format relative time for last sync display
 */
function formatRelativeTime(dateString: string | null, reportType?: XeroReportType): string {
  // Computed reports show different status text
  if (reportType && COMPUTED_REPORT_TYPES.has(reportType)) {
    return 'From invoices';
  }

  if (!dateString) return 'Never synced';

  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / (1000 * 60));
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;

  return date.toLocaleDateString('en-AU');
}

export function ReportSelector({
  value,
  onChange,
  reportStatuses,
  disabled = false,
  className = '',
}: ReportSelectorProps) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Get all report types
  const reportTypes = Object.keys(REPORT_TYPE_DISPLAY_NAMES) as XeroReportType[];

  // Create status map for quick lookup
  const statusMap = new Map<XeroReportType, ReportStatusItem>();
  reportStatuses?.forEach((status) => {
    statusMap.set(status.report_type, status);
  });

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const selectedStatus = value ? statusMap.get(value) : undefined;
  const selectedStatusInfo = getStatusIndicator(selectedStatus, value ?? undefined);

  return (
    <div className={`relative ${className}`} ref={dropdownRef}>
      <button
        type="button"
        onClick={() => !disabled && setIsOpen(!isOpen)}
        disabled={disabled}
        className={`
          flex items-center justify-between w-full sm:w-[240px] px-3 py-2
          bg-white border border-input rounded-md shadow-sm
          text-sm text-left
          ${disabled ? 'opacity-50 cursor-not-allowed' : 'hover:bg-muted cursor-pointer'}
          focus:outline-none focus:ring-2 focus:ring-ring focus:border-ring
        `}
      >
        {value ? (
          <div className="flex items-center gap-2">
            {selectedStatusInfo.icon && (
              <span className={selectedStatusInfo.color}>
                {selectedStatusInfo.icon}
              </span>
            )}
            <span>{getReportDisplayName(value)}</span>
          </div>
        ) : (
          <span className="text-muted-foreground">Select a report</span>
        )}
        <ChevronDown className={`h-4 w-4 text-muted-foreground transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {isOpen && (
        <div className="absolute z-10 mt-1 w-full bg-white border border-border rounded-md shadow-lg max-h-60 overflow-auto">
          {reportTypes.map((reportType) => {
            const status = statusMap.get(reportType);
            const statusInfo = getStatusIndicator(status, reportType);
            const isComputed = COMPUTED_REPORT_TYPES.has(reportType);

            return (
              <button
                key={reportType}
                type="button"
                onClick={() => {
                  onChange(reportType);
                  setIsOpen(false);
                }}
                className={`
                  flex items-center justify-between w-full px-3 py-2 text-sm text-left
                  hover:bg-muted
                  ${value === reportType ? 'bg-accent' : ''}
                `}
              >
                <div className="flex items-center gap-2">
                  <span className={statusInfo.color}>{statusInfo.icon}</span>
                  <span>{getReportDisplayName(reportType)}</span>
                </div>
                <span className={`text-xs ${isComputed ? 'text-purple-500' : 'text-muted-foreground'}`}>
                  {formatRelativeTime(status?.last_synced_at ?? null, reportType)}
                </span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

// =============================================================================
// Period Selector Component
// =============================================================================

interface PeriodSelectorProps {
  /** Currently selected period */
  value: string;
  /** Callback when selection changes */
  onChange: (period: string) => void;
  /** Available periods from the API */
  availablePeriods?: string[];
  /** Report type (affects available period options) - reserved for future use */
  reportType?: XeroReportType;
  /** Whether selector is disabled */
  disabled?: boolean;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Generate period options based on report type
 */
function generatePeriodOptions(
  availablePeriods?: string[]
): Array<{ value: string; label: string }> {
  const now = new Date();
  const options: Array<{ value: string; label: string }> = [];

  // Current period is always first
  options.push({ value: 'current', label: 'Current Period' });

  // Use available periods from API if provided
  if (availablePeriods && availablePeriods.length > 0) {
    availablePeriods.forEach((period) => {
      // Skip if already added
      if (options.some((o) => o.value === period)) return;

      // Format the period for display
      let label = period;
      if (period.endsWith('-FY')) {
        const year = period.split('-')[0] || '2024';
        label = `FY ${year}/${parseInt(year) + 1}`;
      } else if (period.includes('-Q')) {
        const parts = period.split('-Q');
        const year = parts[0] || '2024';
        const q = parts[1] || '1';
        label = `Q${q} ${year}`;
      } else if (period.length === 7) {
        const parts = period.split('-');
        const year = parts[0] || '2024';
        const month = parts[1] || '01';
        const date = new Date(parseInt(year), parseInt(month) - 1);
        label = date.toLocaleDateString('en-AU', { month: 'short', year: 'numeric' });
      }

      options.push({ value: period, label });
    });
  } else {
    // Generate default options

    // Last 6 months
    for (let i = 0; i < 6; i++) {
      const date = new Date(now.getFullYear(), now.getMonth() - i, 1);
      const value = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
      const label = date.toLocaleDateString('en-AU', { month: 'short', year: 'numeric' });
      if (!options.some((o) => o.value === value)) {
        options.push({ value, label });
      }
    }

    // Last 4 quarters
    const currentQuarter = Math.floor(now.getMonth() / 3) + 1;
    for (let i = 0; i < 4; i++) {
      let quarter = currentQuarter - i;
      let year = now.getFullYear();
      while (quarter <= 0) {
        quarter += 4;
        year -= 1;
      }
      const value = `${year}-Q${quarter}`;
      const label = `Q${quarter} ${year}`;
      if (!options.some((o) => o.value === value)) {
        options.push({ value, label });
      }
    }

    // Last 2 financial years
    const currentFY = now.getMonth() >= 6 ? now.getFullYear() : now.getFullYear() - 1;
    for (let i = 0; i < 2; i++) {
      const fy = currentFY - i;
      const value = `${fy}-FY`;
      const label = `FY ${fy}/${fy + 1}`;
      if (!options.some((o) => o.value === value)) {
        options.push({ value, label });
      }
    }
  }

  return options;
}

export function PeriodSelector({
  value,
  onChange,
  availablePeriods,
  disabled = false,
  className = '',
}: PeriodSelectorProps) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const options = generatePeriodOptions(availablePeriods);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const selectedOption = options.find((o) => o.value === value);

  return (
    <div className={`relative ${className}`} ref={dropdownRef}>
      <button
        type="button"
        onClick={() => !disabled && setIsOpen(!isOpen)}
        disabled={disabled}
        className={`
          flex items-center justify-between w-full sm:w-[180px] px-3 py-2
          bg-white border border-input rounded-md shadow-sm
          text-sm text-left
          ${disabled ? 'opacity-50 cursor-not-allowed' : 'hover:bg-muted cursor-pointer'}
          focus:outline-none focus:ring-2 focus:ring-ring focus:border-ring
        `}
      >
        <span>{selectedOption?.label || 'Select period'}</span>
        <ChevronDown className={`h-4 w-4 text-muted-foreground transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {isOpen && (
        <div className="absolute z-10 mt-1 w-full bg-white border border-border rounded-md shadow-lg max-h-60 overflow-auto">
          {options.map((option) => (
            <button
              key={option.value}
              type="button"
              onClick={() => {
                onChange(option.value);
                setIsOpen(false);
              }}
              className={`
                w-full px-3 py-2 text-sm text-left
                hover:bg-muted
                ${value === option.value ? 'bg-accent' : ''}
              `}
            >
              {option.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default ReportSelector;
