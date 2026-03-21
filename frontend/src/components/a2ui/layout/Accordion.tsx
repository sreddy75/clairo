'use client';

/**
 * A2UI Accordion Component
 * Collapsible content sections
 */

import {
  Accordion as RadixAccordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import type { AccordionProps } from '@/lib/a2ui/types';


// =============================================================================
// Types
// =============================================================================

interface A2UIAccordionProps extends AccordionProps {
  id: string;
  dataBinding?: string;
  children?: React.ReactNode;
}

// =============================================================================
// Component
// =============================================================================

export function A2UIAccordion({
  id,
  items,
  defaultOpen,
  children,
}: A2UIAccordionProps) {
  // If no items but children provided, render children directly
  if (!items?.length && children) {
    return (
      <RadixAccordion
        id={id}
        type="multiple"
        defaultValue={defaultOpen}
        className="w-full"
      >
        {children}
      </RadixAccordion>
    );
  }

  if (!items?.length) {
    return null;
  }

  return (
    <RadixAccordion
      id={id}
      type="multiple"
      defaultValue={defaultOpen}
      className="w-full"
    >
      {items.map((item) => (
        <AccordionItem key={item.id} value={item.id}>
          <AccordionTrigger className="text-left">
            {item.title}
          </AccordionTrigger>
          <AccordionContent>
            {/* Render nested A2UI components if provided */}
            {item.content && (
              <div className="space-y-4">
                {/* Content would be rendered by parent A2UIRenderer */}
                <div className="text-sm text-muted-foreground">
                  {/* Placeholder - actual nested rendering handled by renderer */}
                </div>
              </div>
            )}
          </AccordionContent>
        </AccordionItem>
      ))}
    </RadixAccordion>
  );
}

// =============================================================================
// Sub-components for direct child usage
// =============================================================================

export function A2UIAccordionItem({
  id,
  title,
  children,
  className,
}: {
  id: string;
  title: string;
  children?: React.ReactNode;
  className?: string;
}) {
  return (
    <AccordionItem value={id} className={className}>
      <AccordionTrigger className="text-left">{title}</AccordionTrigger>
      <AccordionContent>{children}</AccordionContent>
    </AccordionItem>
  );
}
