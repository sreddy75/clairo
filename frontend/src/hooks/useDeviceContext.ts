'use client';

/**
 * useDeviceContext Hook
 * Detects device context for A2UI rendering
 */

import { useState, useEffect, useMemo } from 'react';

import type { DeviceContext } from '@/lib/a2ui/types';

// =============================================================================
// Types
// =============================================================================

export interface UseDeviceContextOptions {
  /** Override mobile detection */
  forceMobile?: boolean;
  /** Override tablet detection */
  forceTablet?: boolean;
  /** SSR-safe default context */
  ssrDefault?: DeviceContext;
}

// =============================================================================
// Constants
// =============================================================================

const DEFAULT_CONTEXT: DeviceContext = {
  isMobile: false,
  isTablet: false,
  platform: undefined,
  browser: undefined,
};

// Breakpoints (matching Tailwind defaults)
const MOBILE_BREAKPOINT = 640; // sm
const TABLET_BREAKPOINT = 1024; // lg

// =============================================================================
// Platform Detection
// =============================================================================

function detectPlatform(): DeviceContext['platform'] {
  if (typeof window === 'undefined' || typeof navigator === 'undefined') {
    return undefined;
  }

  const userAgent = navigator.userAgent.toLowerCase();
  const platform = navigator.platform?.toLowerCase() || '';

  if (/iphone|ipad|ipod/.test(userAgent) || /mac/.test(platform) && 'ontouchend' in document) {
    return 'ios';
  }
  if (/android/.test(userAgent)) {
    return 'android';
  }
  if (/win/.test(platform)) {
    return 'windows';
  }
  if (/mac/.test(platform)) {
    return 'macos';
  }
  if (/linux/.test(platform)) {
    return 'linux';
  }

  return undefined;
}

// =============================================================================
// Browser Detection
// =============================================================================

function detectBrowser(): string | undefined {
  if (typeof window === 'undefined' || typeof navigator === 'undefined') {
    return undefined;
  }

  const userAgent = navigator.userAgent;

  if (userAgent.includes('Firefox')) {
    return 'firefox';
  }
  if (userAgent.includes('SamsungBrowser')) {
    return 'samsung';
  }
  if (userAgent.includes('Opera') || userAgent.includes('OPR')) {
    return 'opera';
  }
  if (userAgent.includes('Edg')) {
    return 'edge';
  }
  if (userAgent.includes('Chrome')) {
    return 'chrome';
  }
  if (userAgent.includes('Safari')) {
    return 'safari';
  }

  return undefined;
}

// =============================================================================
// Device Type Detection
// =============================================================================

function detectDeviceType(): { isMobile: boolean; isTablet: boolean } {
  if (typeof window === 'undefined') {
    return { isMobile: false, isTablet: false };
  }

  const width = window.innerWidth;
  const userAgent = navigator.userAgent.toLowerCase();

  // Check for tablet-specific keywords
  const isTabletUA =
    /ipad|tablet|playbook|silk/.test(userAgent) ||
    (/android/.test(userAgent) && !/mobile/.test(userAgent));

  // Check for mobile-specific keywords
  const isMobileUA = /mobile|iphone|ipod|android.*mobile|blackberry|opera mini|opera mobi/.test(
    userAgent
  );

  // Combine UA detection with viewport width
  const isMobile = isMobileUA || width < MOBILE_BREAKPOINT;
  const isTablet = isTabletUA || (width >= MOBILE_BREAKPOINT && width < TABLET_BREAKPOINT);

  return { isMobile, isTablet };
}

// =============================================================================
// Hook Implementation
// =============================================================================

export function useDeviceContext(
  options: UseDeviceContextOptions = {}
): DeviceContext {
  const { forceMobile, forceTablet, ssrDefault } = options;

  const [context, setContext] = useState<DeviceContext>(
    ssrDefault || DEFAULT_CONTEXT
  );

  useEffect(() => {
    // Initial detection
    const updateContext = () => {
      const { isMobile, isTablet } = detectDeviceType();
      const platform = detectPlatform();
      const browser = detectBrowser();

      setContext({
        isMobile: forceMobile ?? isMobile,
        isTablet: forceTablet ?? isTablet,
        platform,
        browser,
      });
    };

    updateContext();

    // Listen for resize events
    const handleResize = () => {
      updateContext();
    };

    window.addEventListener('resize', handleResize);
    window.addEventListener('orientationchange', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      window.removeEventListener('orientationchange', handleResize);
    };
  }, [forceMobile, forceTablet]);

  return context;
}

// =============================================================================
// SSR-Safe Hook
// =============================================================================

export function useDeviceContextSSR(
  serverContext?: DeviceContext
): DeviceContext {
  const [isClient, setIsClient] = useState(false);
  const clientContext = useDeviceContext({
    ssrDefault: serverContext || DEFAULT_CONTEXT,
  });

  useEffect(() => {
    setIsClient(true);
  }, []);

  return isClient ? clientContext : (serverContext || DEFAULT_CONTEXT);
}

// =============================================================================
// Media Query Hooks
// =============================================================================

export function useIsMobile(): boolean {
  const { isMobile } = useDeviceContext();
  return isMobile;
}

export function useIsTablet(): boolean {
  const { isTablet } = useDeviceContext();
  return isTablet;
}

export function useIsDesktop(): boolean {
  const { isMobile, isTablet } = useDeviceContext();
  return !isMobile && !isTablet;
}

// =============================================================================
// Header Generation (for API calls)
// =============================================================================

export function useDeviceHeader(): string {
  const { isMobile, isTablet } = useDeviceContext();

  return useMemo(() => {
    if (isMobile) return 'mobile';
    if (isTablet) return 'tablet';
    return 'desktop';
  }, [isMobile, isTablet]);
}
