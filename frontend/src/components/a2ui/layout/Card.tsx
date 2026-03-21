'use client';

/**
 * A2UI Card Component
 * Container card with optional title and description
 */

import {
  Card as ShadcnCard,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import type { CardProps } from '@/lib/a2ui/types';
import { cn } from '@/lib/utils';


// =============================================================================
// Types
// =============================================================================

interface A2UICardProps extends CardProps {
  id: string;
  dataBinding?: string;
  children?: React.ReactNode;
  className?: string;
}

// =============================================================================
// Component
// =============================================================================

export function A2UICard({
  id,
  title,
  description,
  footer,
  children,
  className,
}: A2UICardProps) {
  const hasHeader = title || description;

  return (
    <ShadcnCard id={id} className={cn('overflow-hidden', className)}>
      {hasHeader && (
        <CardHeader>
          {title && <CardTitle className="text-lg">{title}</CardTitle>}
          {description && (
            <CardDescription>{description}</CardDescription>
          )}
        </CardHeader>
      )}
      {children && (
        <CardContent className={cn(!hasHeader && 'pt-6')}>
          {children}
        </CardContent>
      )}
      {footer && footer.length > 0 && (
        <CardFooter className="flex justify-end gap-2 border-t bg-muted/50 px-6 py-4">
          {/* Footer components would be rendered by parent A2UIRenderer */}
        </CardFooter>
      )}
    </ShadcnCard>
  );
}
