'use client';

/**
 * Analytics and Error Tracking Integration
 *
 * This module provides lightweight analytics and error tracking before
 * the full observability spec is implemented.
 *
 * Features:
 * - PostHog for product analytics (when configured)
 * - Sentry for error tracking (when configured)
 * - Standardized event tracking API
 *
 * Configuration:
 * Set these environment variables:
 * - NEXT_PUBLIC_POSTHOG_KEY: PostHog project API key
 * - NEXT_PUBLIC_POSTHOG_HOST: PostHog host (default: https://app.posthog.com)
 * - NEXT_PUBLIC_SENTRY_DSN: Sentry DSN for error tracking
 */

import { useUser } from '@clerk/nextjs';
import { useEffect, useState, type ReactNode } from 'react';

// PostHog types (inline to avoid dependency until package is added)
interface PostHogLike {
  identify: (distinctId: string, properties?: Record<string, unknown>) => void;
  capture: (event: string, properties?: Record<string, unknown>) => void;
  reset: () => void;
}

// Global PostHog instance (set by script)
declare global {
  interface Window {
    posthog?: PostHogLike;
  }
}

// Environment configuration
const POSTHOG_KEY = process.env.NEXT_PUBLIC_POSTHOG_KEY || '';
const POSTHOG_HOST = process.env.NEXT_PUBLIC_POSTHOG_HOST || 'https://app.posthog.com';
const SENTRY_DSN = process.env.NEXT_PUBLIC_SENTRY_DSN || '';

/**
 * Track a custom event in PostHog
 */
export function trackEvent(
  event: string,
  properties?: Record<string, unknown>
): void {
  if (typeof window !== 'undefined' && window.posthog) {
    window.posthog.capture(event, properties);
  }
}

/**
 * Identify the current user in PostHog
 */
export function identifyUser(
  userId: string,
  properties?: Record<string, unknown>
): void {
  if (typeof window !== 'undefined' && window.posthog) {
    window.posthog.identify(userId, properties);
  }
}

/**
 * Reset user identity (on logout)
 */
export function resetAnalytics(): void {
  if (typeof window !== 'undefined' && window.posthog) {
    window.posthog.reset();
  }
}

// Standard event names following our taxonomy
export const AnalyticsEvents = {
  // Onboarding
  ONBOARDING_STARTED: 'onboarding.started',
  ONBOARDING_STEP_COMPLETED: 'onboarding.step_completed',
  ONBOARDING_COMPLETED: 'onboarding.completed',
  ONBOARDING_ABANDONED: 'onboarding.abandoned',

  // Authentication
  AUTH_SIGNUP: 'auth.signup',
  AUTH_LOGIN: 'auth.login',
  AUTH_LOGOUT: 'auth.logout',

  // Client Management
  CLIENT_VIEWED: 'client.viewed',
  CLIENT_CREATED: 'client.created',
  CLIENT_XERO_CONNECTED: 'client.xero_connected',
  CLIENT_XERO_SYNCED: 'client.xero_synced',

  // BAS Preparation
  BAS_PREP_STARTED: 'bas.prep_started',
  BAS_CHECKLIST_COMPLETED: 'bas.checklist_item_completed',
  BAS_PREP_COMPLETED: 'bas.prep_completed',
  BAS_LODGED: 'bas.lodged',

  // Insights
  INSIGHT_VIEWED: 'insight.viewed',
  INSIGHT_ACTIONED: 'insight.actioned',
  INSIGHT_DISMISSED: 'insight.dismissed',

  // AI Chat
  CHAT_OPENED: 'chat.opened',
  CHAT_MESSAGE_SENT: 'chat.message_sent',
  CHAT_FEEDBACK_GIVEN: 'chat.feedback_given',

  // Magic Zone
  MAGIC_ZONE_OPENED: 'magic_zone.opened',
  MAGIC_ZONE_QUERY_SUBMITTED: 'magic_zone.query_submitted',
  MAGIC_ZONE_ACTION_TAKEN: 'magic_zone.action_taken',

  // Subscription
  SUBSCRIPTION_UPGRADED: 'subscription.upgraded',
  SUBSCRIPTION_DOWNGRADED: 'subscription.downgraded',
  SUBSCRIPTION_CANCELLED: 'subscription.cancelled',

  // Feature interaction
  FEATURE_USED: 'feature.used',
  PAGE_VIEWED: 'page.viewed',
} as const;

/**
 * PostHog Script Loader Component
 *
 * Loads PostHog via script tag (more reliable than npm package for Next.js)
 */
function PostHogScript(): ReactNode {
  if (!POSTHOG_KEY) {
    return null;
  }

  return (
    <script
      dangerouslySetInnerHTML={{
        __html: `
          !function(t,e){var o,n,p,r;e.__SV||(window.posthog=e,e._i=[],e.init=function(i,s,a){function g(t,e){var o=e.split(".");2==o.length&&(t=t[o[0]],e=o[1]),t[e]=function(){t.push([e].concat(Array.prototype.slice.call(arguments,0)))}}(p=t.createElement("script")).type="text/javascript",p.async=!0,p.src=s.api_host+"/static/array.js",(r=t.getElementsByTagName("script")[0]).parentNode.insertBefore(p,r);var u=e;for(void 0!==a?u=e[a]=[]:a="posthog",u.people=u.people||[],u.toString=function(t){var e="posthog";return"posthog"!==a&&(e+="."+a),t||(e+=" (stub)"),e},u.people.toString=function(){return u.toString(1)+".people (stub)"},o="capture identify alias people.set people.set_once set_config register register_once unregister opt_out_capturing has_opted_out_capturing opt_in_capturing reset isFeatureEnabled onFeatureFlags getFeatureFlag getFeatureFlagPayload reloadFeatureFlags group updateEarlyAccessFeatureEnrollment getEarlyAccessFeatures getActiveMatchingSurveys getSurveys".split(" "),n=0;n<o.length;n++)g(u,o[n]);e._i.push([i,s,a])},e.__SV=1)}(document,window.posthog||[]);
          posthog.init('${POSTHOG_KEY}', {
            api_host: '${POSTHOG_HOST}',
            loaded: function(posthog) {
              if (window.location.hostname === 'localhost') {
                posthog.opt_out_capturing();
              }
            },
            capture_pageview: true,
            capture_pageleave: true,
            autocapture: false,
          });
        `,
      }}
    />
  );
}

/**
 * Sentry Script Loader Component
 *
 * Loads Sentry via script tag for error tracking
 */
function SentryScript(): ReactNode {
  if (!SENTRY_DSN) {
    return null;
  }

  return (
    <script
      dangerouslySetInnerHTML={{
        __html: `
          (function() {
            var script = document.createElement('script');
            script.src = 'https://js.sentry-cdn.com/${SENTRY_DSN.split('/').pop()}.min.js';
            script.crossOrigin = 'anonymous';
            script.onload = function() {
              if (window.Sentry) {
                window.Sentry.init({
                  dsn: '${SENTRY_DSN}',
                  environment: '${process.env.NODE_ENV}',
                  tracesSampleRate: 0.1,
                  replaysSessionSampleRate: 0,
                  replaysOnErrorSampleRate: 1.0,
                });
              }
            };
            document.head.appendChild(script);
          })();
        `,
      }}
    />
  );
}

/**
 * User Identity Sync Component
 *
 * Syncs Clerk user identity to PostHog when user signs in
 */
function UserIdentitySync(): null {
  const { user, isSignedIn } = useUser();

  useEffect(() => {
    if (isSignedIn && user) {
      identifyUser(user.id, {
        email: user.primaryEmailAddress?.emailAddress,
        name: user.fullName,
        created_at: user.createdAt,
      });
    } else if (!isSignedIn) {
      resetAnalytics();
    }
  }, [isSignedIn, user]);

  return null;
}

/**
 * Analytics Provider Component
 *
 * Add this to your root layout to enable analytics and error tracking.
 *
 * Usage:
 * ```tsx
 * import { AnalyticsProvider } from '@/lib/analytics';
 *
 * export default function RootLayout({ children }) {
 *   return (
 *     <html>
 *       <head>
 *         <AnalyticsProvider />
 *       </head>
 *       <body>{children}</body>
 *     </html>
 *   );
 * }
 * ```
 */
export function AnalyticsProvider(): ReactNode {
  return (
    <>
      <ConsentGatedPostHog />
      <SentryScript />
    </>
  );
}

/**
 * Consent-gated PostHog loader.
 * Only loads PostHog after the user has explicitly accepted cookies.
 * Sentry is loaded unconditionally (legitimate interest for error tracking).
 */
function ConsentGatedPostHog(): ReactNode {
  const [shouldLoad, setShouldLoad] = useState(false);

  useEffect(() => {
    try {
      const stored = localStorage.getItem('clairo_cookie_consent');
      if (stored) {
        const data = JSON.parse(stored);
        if (data.status === 'accepted') {
          setShouldLoad(true);
        }
      }
    } catch {
      // ignore
    }

    // Listen for consent changes (from CookieConsentBanner)
    const handler = () => {
      try {
        const stored = localStorage.getItem('clairo_cookie_consent');
        if (stored) {
          const data = JSON.parse(stored);
          setShouldLoad(data.status === 'accepted');
        }
      } catch {
        // ignore
      }
    };
    window.addEventListener('storage', handler);
    // Custom event for same-tab updates
    window.addEventListener('cookie-consent-changed', handler);
    return () => {
      window.removeEventListener('storage', handler);
      window.removeEventListener('cookie-consent-changed', handler);
    };
  }, []);

  if (!shouldLoad) return null;
  return <PostHogScript />;
}

/**
 * Analytics User Sync Component
 *
 * Add this inside your Providers to sync user identity.
 * Must be inside ClerkProvider.
 */
export function AnalyticsUserSync(): ReactNode {
  return <UserIdentitySync />;
}
