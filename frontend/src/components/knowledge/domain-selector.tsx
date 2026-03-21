'use client';

/**
 * DomainSelector Component
 *
 * Fetches specialist tax domains from the API and displays them as
 * clickable chips/cards. Users can select a domain to scope knowledge
 * base queries, or choose "All Topics" to clear the filter.
 */

import { useEffect, useState } from 'react';

import { cn } from '@/lib/utils';

// =============================================================================
// Types
// =============================================================================

/** Tax domain as returned by GET /api/v1/knowledge/domains */
interface TaxDomain {
  slug: string;
  name: string;
  description: string;
  icon: string | null;
  display_order: number;
  is_active: boolean;
}

interface DomainSelectorProps {
  /** Currently selected domain slug, or null for "All Topics" */
  selectedDomain: string | null;
  /** Callback when a domain is selected or cleared */
  onSelect: (slug: string | null) => void;
  /** Auth token for API requests */
  token: string;
  /** Additional CSS classes */
  className?: string;
}

// =============================================================================
// Default domain icons (fallback when icon field is null)
// =============================================================================

const DEFAULT_DOMAIN_ICONS: Record<string, string> = {
  gst: 'G',
  division_7a: '7A',
  cgt: 'CGT',
  fbt: 'FBT',
  smsf: 'SMSF',
  trusts: 'T',
  superannuation: 'S',
  payroll: 'P',
  international_tax: 'INT',
};

// =============================================================================
// Component
// =============================================================================

export function DomainSelector({
  selectedDomain,
  onSelect,
  token,
  className,
}: DomainSelectorProps) {
  const [domains, setDomains] = useState<TaxDomain[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchDomains() {
      try {
        setLoading(true);
        setError(null);

        const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
        const response = await fetch(`${baseUrl}/api/v1/knowledge/domains`, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        if (!response.ok) {
          throw new Error(`Failed to fetch domains: ${response.statusText}`);
        }

        const data = await response.json();
        // API may return { domains: [...] } or a bare array
        const domainList: TaxDomain[] = Array.isArray(data) ? data : data.domains ?? [];
        setDomains(domainList.sort((a, b) => a.display_order - b.display_order));
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load domains');
      } finally {
        setLoading(false);
      }
    }

    if (token) {
      fetchDomains();
    }
  }, [token]);

  if (loading) {
    return (
      <div className={cn('flex gap-2 overflow-x-auto pb-1', className)}>
        {/* Skeleton chips */}
        {Array.from({ length: 5 }).map((_, i) => (
          <div
            key={i}
            className="h-8 w-20 rounded-full bg-muted animate-pulse shrink-0"
          />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className={cn('text-xs text-status-danger', className)}>
        {error}
      </div>
    );
  }

  return (
    <div
      className={cn(
        'flex flex-wrap gap-2',
        className,
      )}
      role="listbox"
      aria-label="Select tax domain"
    >
      {/* "All Topics" chip */}
      <button
        type="button"
        role="option"
        aria-selected={selectedDomain === null}
        onClick={() => onSelect(null)}
        className={cn(
          'inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition-all',
          'border cursor-pointer',
          selectedDomain === null
            ? 'bg-foreground text-background border-foreground'
            : 'bg-card text-muted-foreground border-border hover:bg-muted',
        )}
      >
        All Topics
      </button>

      {/* Domain chips */}
      {domains.map((domain) => {
        const isSelected = selectedDomain === domain.slug;
        const iconChar = domain.icon || DEFAULT_DOMAIN_ICONS[domain.slug] || domain.name.charAt(0);

        return (
          <button
            key={domain.slug}
            type="button"
            role="option"
            aria-selected={isSelected}
            onClick={() => onSelect(isSelected ? null : domain.slug)}
            title={domain.description}
            className={cn(
              'inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition-all',
              'border cursor-pointer',
              isSelected
                ? 'bg-primary text-primary-foreground border-primary'
                : 'bg-card text-muted-foreground border-border hover:bg-muted',
            )}
          >
            <span
              className={cn(
                'inline-flex items-center justify-center w-5 h-5 rounded-full text-[10px] font-bold shrink-0',
                isSelected
                  ? 'bg-white/20 text-white'
                  : 'bg-muted text-muted-foreground',
              )}
            >
              {iconChar}
            </span>
            <span>{domain.name}</span>
          </button>
        );
      })}
    </div>
  );
}

export default DomainSelector;
