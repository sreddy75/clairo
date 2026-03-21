'use client';

/**
 * A2UI Badge Component
 * Displays status badges with variants
 */

import { Badge as ShadcnBadge } from '@/components/ui/badge';
import type { BadgeProps } from '@/lib/a2ui/types';


// =============================================================================
// Types
// =============================================================================

interface A2UIBadgeProps extends BadgeProps {
  id: string;
  dataBinding?: string;
}

// =============================================================================
// Component
// =============================================================================

export function A2UIBadge({
  id,
  label,
  variant = 'default',
}: A2UIBadgeProps) {
  // Map A2UI variants to shadcn badge variants
  const badgeVariant = {
    default: 'default',
    secondary: 'secondary',
    destructive: 'destructive',
    outline: 'outline',
  }[variant] as 'default' | 'secondary' | 'destructive' | 'outline';

  return (
    <ShadcnBadge
      id={id}
      variant={badgeVariant}
      className="whitespace-nowrap"
    >
      {label}
    </ShadcnBadge>
  );
}
