'use client';

import { ClerkProvider } from '@clerk/nextjs';
import { QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { type ReactNode } from 'react';
import { Toaster } from 'sonner';

import { ThemeProvider } from '@/components/theme';
import { AnalyticsUserSync } from '@/lib/analytics';
import { queryClient } from '@/lib/query-client';

interface ProvidersProps {
  children: ReactNode;
}

export function Providers({ children }: ProvidersProps) {
  return (
    <ThemeProvider
      attribute="class"
      defaultTheme="light"
      enableSystem
      disableTransitionOnChange
    >
      <ClerkProvider
        proxyUrl={process.env.NEXT_PUBLIC_CLERK_PROXY_URL}
        appearance={{
          baseTheme: undefined,
          variables: {
            colorPrimary: 'hsl(12, 80%, 55%)',
            colorTextOnPrimaryBackground: 'hsl(0, 0%, 100%)',
            colorBackground: 'hsl(0, 0%, 100%)',
            colorInputBackground: 'hsl(40, 15%, 94%)',
            colorInputText: 'hsl(222, 47%, 11%)',
            borderRadius: '0.5rem',
          },
          elements: {
            formButtonPrimary:
              'bg-primary hover:bg-primary/90 text-primary-foreground font-medium py-2 px-4 rounded-lg transition-colors',
            card: 'shadow-sm rounded-xl border border-border',
            headerTitle: 'text-2xl font-bold text-foreground',
            headerSubtitle: 'text-muted-foreground',
            socialButtonsBlockButton:
              'border border-border hover:bg-muted transition-colors',
            formFieldLabel: 'text-sm font-medium text-muted-foreground',
            formFieldInput:
              'border-input focus:border-primary focus:ring-primary rounded-lg',
            footerActionLink: 'text-primary hover:text-primary/80',
          },
        }}
      >
        <QueryClientProvider client={queryClient}>
          <AnalyticsUserSync />
          {children}
          <Toaster
            position="top-right"
            toastOptions={{
              style: {
                background: 'hsl(var(--card))',
                border: '1px solid hsl(var(--border))',
                borderRadius: '0.5rem',
              },
            }}
          />
          <ReactQueryDevtools initialIsOpen={false} />
        </QueryClientProvider>
      </ClerkProvider>
    </ThemeProvider>
  );
}
