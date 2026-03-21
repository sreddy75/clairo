'use client';

import dynamic from 'next/dynamic';
import { usePathname } from 'next/navigation';
import type { ReactNode } from 'react';

import { ClairoLogo } from '@/components/brand';
import { ThemeToggle } from '@/components/theme';
import { Toaster } from '@/components/ui/sonner';

// Dynamically import PWA components to prevent SSR issues
const InstallPrompt = dynamic(
  () => import('@/components/pwa/InstallPrompt').then((mod) => mod.InstallPrompt),
  { ssr: false }
);
const OfflineIndicator = dynamic(
  () => import('@/components/pwa/OfflineIndicator').then((mod) => mod.OfflineIndicator),
  { ssr: false }
);

interface PortalLayoutProps {
  children: ReactNode;
}

/**
 * Layout for client portal pages.
 *
 * - Auth pages (login, verify): Centered minimal layout
 * - Dashboard pages: Full-width with navigation header
 */
export default function PortalLayout({ children }: PortalLayoutProps) {
  const pathname = usePathname();

  // Auth pages use centered layout
  const isAuthPage = pathname === '/portal/login' ||
                     pathname === '/portal/verify' ||
                     pathname?.startsWith('/portal/verify/');

  if (isAuthPage) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-background">
        {/* Offline Indicator */}
        <div className="fixed top-0 left-0 right-0 z-50">
          <OfflineIndicator variant="banner" />
        </div>

        {/* Theme Toggle */}
        <div className="absolute top-4 right-4">
          <ThemeToggle />
        </div>

        {/* Header */}
        <div className="mb-8 text-center flex flex-col items-center">
          <ClairoLogo size="lg" variant="light" className="dark:hidden" />
          <ClairoLogo size="lg" variant="dark" className="hidden dark:flex" />
          <p className="text-muted-foreground mt-2 text-sm">
            Client Portal
          </p>
        </div>

        {/* Content */}
        <div className="w-full max-w-md px-4">
          {children}
        </div>

        {/* Footer */}
        <div className="mt-8 text-center text-sm text-muted-foreground">
          <p>Secure access provided by your accountant</p>
          <p className="mt-1 text-xs">
            &copy; {new Date().getFullYear()} Clairo. Powered by AI.
          </p>
        </div>
        <Toaster />

        {/* PWA Install Prompt */}
        <InstallPrompt minVisits={2} />
      </div>
    );
  }

  // Dashboard pages use full-width layout with header
  // Note: PortalHeader is rendered by individual dashboard pages that need session data
  return (
    <div className="min-h-screen flex flex-col bg-background">
      {/* Offline Indicator */}
      <div className="fixed top-0 left-0 right-0 z-50">
        <OfflineIndicator variant="banner" />
      </div>

      {/* Content */}
      <main className="flex-1">
        {children}
      </main>

      {/* Footer */}
      <footer className="border-t bg-card py-4">
        <div className="container mx-auto px-4">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-2 text-sm text-muted-foreground">
            <p>Secure document portal powered by Clairo</p>
            <div className="flex items-center gap-4">
              <a href="/portal/help" className="hover:text-foreground transition-colors">
                Help
              </a>
              <a href="/portal/privacy" className="hover:text-foreground transition-colors">
                Privacy
              </a>
              <div className="ml-2">
                <ThemeToggle />
              </div>
            </div>
          </div>
        </div>
      </footer>
      <Toaster />

      {/* PWA Install Prompt */}
      <InstallPrompt minVisits={2} />
    </div>
  );
}
