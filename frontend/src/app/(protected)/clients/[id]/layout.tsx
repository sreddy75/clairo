import { type ReactNode } from 'react';

/**
 * Client Detail Layout
 *
 * Passthrough layout for client detail pages.
 * Navigation is handled within the main page component.
 *
 * Sub-pages (assets, purchase-orders, reports) are accessed via
 * the main page's grouped navigation or direct links.
 */

interface ClientLayoutProps {
  children: ReactNode;
}

export default function ClientLayout({ children }: ClientLayoutProps) {
  return <>{children}</>;
}
