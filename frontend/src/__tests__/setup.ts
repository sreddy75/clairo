/**
 * Vitest test setup file.
 *
 * Configures testing environment for React components.
 */

import '@testing-library/jest-dom';
import type { ReactNode } from 'react';
import { vi } from 'vitest';

// Mock Next.js router
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
    back: vi.fn(),
  }),
  usePathname: () => '/',
  useSearchParams: () => new URLSearchParams(),
}));

// Mock Next.js Link component
vi.mock('next/link', () => ({
  default: ({
    children: _children,
    href,
    ...props
  }: {
    children: ReactNode;
    href: string;
  }) => {
    // eslint-disable-next-line @next/next/no-html-link-for-pages
    const anchor = document.createElement('a');
    anchor.href = href;
    Object.assign(anchor, props);
    return anchor;
  },
}));

// Mock Clerk
vi.mock('@clerk/nextjs', () => ({
  useAuth: () => ({
    isLoaded: true,
    isSignedIn: true,
    userId: 'test-user-id',
    getToken: vi.fn().mockResolvedValue('test-token'),
  }),
  useUser: () => ({
    isLoaded: true,
    user: {
      id: 'test-user-id',
      firstName: 'Test',
      primaryEmailAddress: { emailAddress: 'test@example.com' },
    },
  }),
  ClerkProvider: ({ children }: { children: React.ReactNode }) => children,
}));
