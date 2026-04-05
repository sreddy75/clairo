'use client';

import Link from 'next/link';
import type { ReactNode } from 'react';

import { ClairoLogo } from '@/components/brand';
import { ThemeToggle } from '@/components/theme';

interface AuthLayoutProps {
  children: ReactNode;
}

/**
 * Layout for authentication pages (sign-in, sign-up).
 * Centers the auth card on the page with a branded background.
 */
export default function AuthLayout({ children }: AuthLayoutProps) {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-background">
      {/* Theme Toggle - positioned in top right */}
      <div className="absolute top-4 right-4">
        <ThemeToggle />
      </div>

      {/* Header */}
      <div className="mb-8 text-center flex flex-col items-center">
        <ClairoLogo size="xl" variant="light" className="dark:hidden" />
        <ClairoLogo size="xl" variant="dark" className="hidden dark:flex" />
        <p className="text-muted-foreground mt-2">
          AI-Powered Tax & Advisory Platform
        </p>
      </div>

      {/* Auth Card */}
      <div className="w-full max-w-md px-4">
        {children}
      </div>

      {/* Footer */}
      <div className="mt-8 text-center text-sm text-muted-foreground space-y-2">
        <div className="flex items-center justify-center gap-4">
          <Link href="/terms" className="hover:text-foreground transition-colors">Terms</Link>
          <Link href="/privacy" className="hover:text-foreground transition-colors">Privacy</Link>
          <Link href="/acceptable-use" className="hover:text-foreground transition-colors">Acceptable Use</Link>
        </div>
        <p>
          © {new Date().getFullYear()} Clairo. Designed for Australian Accounting Practices.
        </p>
      </div>
    </div>
  );
}
