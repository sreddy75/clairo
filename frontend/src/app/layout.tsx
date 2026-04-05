import { SpeedInsights } from '@vercel/speed-insights/next';
import type { Metadata, Viewport } from 'next';
import { Sora, Plus_Jakarta_Sans } from 'next/font/google';

import { CookieConsentBanner } from '@/components/CookieConsentBanner';
import { AnalyticsProvider } from '@/lib/analytics';

import { Providers } from './providers';
import './globals.css';

const sora = Sora({
  subsets: ['latin'],
  variable: '--font-heading',
  display: 'swap',
});

const jakarta = Plus_Jakarta_Sans({
  subsets: ['latin'],
  variable: '--font-sans',
  display: 'swap',
});

export const metadata: Metadata = {
  title: {
    default: 'Clairo',
    template: '%s | Clairo',
  },
  description:
    'AI-Powered Tax & Advisory Platform for Australian Accounting Practices',
  keywords: [
    'Tax',
    'BAS',
    'Business Activity Statement',
    'Australian Tax',
    'Accounting',
    'AI Advisory',
    'Xero',
    'MYOB',
  ],
  manifest: '/manifest.json',
  appleWebApp: {
    capable: true,
    statusBarStyle: 'default',
    title: 'Clairo',
  },
  formatDetection: {
    telephone: false,
  },
  openGraph: {
    type: 'website',
    locale: 'en_AU',
    siteName: 'Clairo',
    title: 'Clairo — AI-Powered Tax & Advisory Platform',
    description:
      'Decision support for Australian accounting practices. BAS preparation, tax planning, and compliance — powered by AI.',
    images: [
      {
        url: '/og-image.png',
        width: 1200,
        height: 630,
        alt: 'Clairo — AI-Powered Tax & Advisory Platform',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Clairo — AI-Powered Tax & Advisory Platform',
    description:
      'Decision support for Australian accounting practices. BAS preparation, tax planning, and compliance — powered by AI.',
    images: ['/og-image.png'],
  },
  other: {
    'mobile-web-app-capable': 'yes',
  },
};

export const viewport: Viewport = {
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: '#ffffff' },
    { media: '(prefers-color-scheme: dark)', color: '#0c0a09' },
  ],
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
  viewportFit: 'cover',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <AnalyticsProvider />
      </head>
      <body className={`${sora.variable} ${jakarta.variable} font-sans antialiased`}>
        <Providers>{children}</Providers>
        <CookieConsentBanner />
        <SpeedInsights />
      </body>
    </html>
  );
}
