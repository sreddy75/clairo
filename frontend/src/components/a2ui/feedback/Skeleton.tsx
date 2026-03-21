'use client';

/**
 * A2UI Skeleton Component
 * Loading placeholder animation
 */

import { Skeleton as ShadcnSkeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';


// =============================================================================
// Types
// =============================================================================

interface A2UISkeletonProps {
  id: string;
  variant?: 'text' | 'circular' | 'rectangular';
  width?: string | number;
  height?: string | number;
  count?: number;
  dataBinding?: string;
}

// =============================================================================
// Component
// =============================================================================

export function A2UISkeleton({
  id,
  variant = 'text',
  width,
  height,
  count = 1,
}: A2UISkeletonProps) {
  const getVariantClass = () => {
    switch (variant) {
      case 'circular':
        return 'rounded-full';
      case 'rectangular':
        return 'rounded-none';
      case 'text':
      default:
        return 'rounded';
    }
  };

  const getDefaultDimensions = () => {
    switch (variant) {
      case 'circular':
        return { width: width || '40px', height: height || '40px' };
      case 'rectangular':
        return { width: width || '100%', height: height || '100px' };
      case 'text':
      default:
        return { width: width || '100%', height: height || '16px' };
    }
  };

  const dimensions = getDefaultDimensions();

  const skeletons = Array.from({ length: count }, (_, i) => (
    <ShadcnSkeleton
      key={i}
      className={cn(getVariantClass())}
      style={{
        width: dimensions.width,
        height: dimensions.height,
      }}
    />
  ));

  return (
    <div id={id} className="space-y-2">
      {skeletons}
    </div>
  );
}
