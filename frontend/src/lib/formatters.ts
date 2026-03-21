/**
 * Shared formatting utilities for Clairo.
 * ALWAYS import from here — never define formatters locally.
 */

/**
 * Format a currency value for display (AUD).
 * Accepts both string and number inputs.
 */
export function formatCurrency(
  value: string | number | null | undefined,
  options?: { fractionDigits?: number; currency?: string }
): string {
  if (value == null) return '-';
  const num = typeof value === 'string' ? parseFloat(value) : value;
  if (isNaN(num)) return '-';
  return new Intl.NumberFormat('en-AU', {
    style: 'currency',
    currency: options?.currency ?? 'AUD',
    minimumFractionDigits: options?.fractionDigits ?? 0,
    maximumFractionDigits: options?.fractionDigits ?? 0,
  }).format(num);
}

/**
 * Format a date for display. Returns '-' for null/undefined.
 */
export function formatDate(
  date: Date | string | null | undefined,
  options?: Intl.DateTimeFormatOptions
): string {
  if (!date) return '-';
  const defaultOptions: Intl.DateTimeFormatOptions = {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  };
  return new Intl.DateTimeFormat('en-AU', options || defaultOptions).format(
    typeof date === 'string' ? new Date(date) : date
  );
}

/**
 * Format a date with time for display. Returns '-' for null/undefined.
 */
export function formatDateTime(
  date: Date | string | null | undefined
): string {
  if (!date) return '-';
  return new Intl.DateTimeFormat('en-AU', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(typeof date === 'string' ? new Date(date) : date);
}

/**
 * Format a percentage value. Returns '-' for null/undefined.
 */
export function formatPercentage(
  value: number | string | null | undefined,
  fractionDigits = 0
): string {
  if (value == null) return '-';
  const num = typeof value === 'string' ? parseFloat(value) : value;
  if (isNaN(num)) return '-';
  return `${num.toFixed(fractionDigits)}%`;
}

/**
 * Format relative time (e.g., "2d ago", "just now").
 */
export function formatRelativeTime(
  date: Date | string | null | undefined
): string {
  if (!date) return '-';
  const d = typeof date === 'string' ? new Date(date) : date;
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays === 0) {
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    if (diffHours === 0) return 'just now';
    return `${diffHours}h ago`;
  }
  if (diffDays === 1) return 'yesterday';
  if (diffDays < 7) return `${diffDays}d ago`;
  if (diffDays < 30) return `${Math.floor(diffDays / 7)}w ago`;
  return formatDate(d);
}
