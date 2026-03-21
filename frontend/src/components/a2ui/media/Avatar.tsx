'use client';

/**
 * A2UI Avatar Component
 * User avatar with fallback initials
 */

import {
  Avatar as ShadcnAvatar,
  AvatarFallback,
  AvatarImage,
} from '@/components/ui/avatar';
import { cn } from '@/lib/utils';

// =============================================================================
// Types
// =============================================================================

interface A2UIAvatarProps {
  id: string;
  src?: string;
  alt?: string;
  name?: string;
  size?: 'sm' | 'md' | 'lg' | 'xl';
  dataBinding?: string;
}

// =============================================================================
// Helpers
// =============================================================================

function getInitials(name: string): string {
  const parts = name.split(' ').filter(Boolean);
  if (parts.length === 0) return '?';
  const first = parts[0];
  const last = parts[parts.length - 1];
  if (!first) return '?';
  if (parts.length === 1) return first.charAt(0).toUpperCase();
  if (!last) return first.charAt(0).toUpperCase();
  return (first.charAt(0) + last.charAt(0)).toUpperCase();
}

function getSizeClass(size: string): string {
  switch (size) {
    case 'sm':
      return 'h-8 w-8 text-xs';
    case 'lg':
      return 'h-12 w-12 text-lg';
    case 'xl':
      return 'h-16 w-16 text-xl';
    case 'md':
    default:
      return 'h-10 w-10 text-sm';
  }
}

// =============================================================================
// Component
// =============================================================================

export function A2UIAvatar({
  id,
  src,
  alt,
  name,
  size = 'md',
}: A2UIAvatarProps) {
  const initials = name ? getInitials(name) : alt ? getInitials(alt) : '?';
  const sizeClass = getSizeClass(size);

  return (
    <ShadcnAvatar id={id} className={cn(sizeClass)}>
      {src && <AvatarImage src={src} alt={alt || name || 'Avatar'} />}
      <AvatarFallback className="bg-primary/10 text-primary font-medium">
        {initials}
      </AvatarFallback>
    </ShadcnAvatar>
  );
}
