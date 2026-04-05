'use client';

import { useCallback, useEffect, useState } from 'react';

type ConsentStatus = 'accepted' | 'declined' | null;

const STORAGE_KEY = 'clairo_cookie_consent';

interface ConsentData {
  status: 'accepted' | 'declined';
  timestamp: string;
  version: string;
}

export function useCookieConsent() {
  const [consent, setConsent] = useState<ConsentStatus>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const data: ConsentData = JSON.parse(stored);
        setConsent(data.status);
      }
    } catch {
      // ignore
    }
    setLoaded(true);
  }, []);

  const accept = useCallback(() => {
    const data: ConsentData = {
      status: 'accepted',
      timestamp: new Date().toISOString(),
      version: '1.0',
    };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
    setConsent('accepted');
    window.dispatchEvent(new Event('cookie-consent-changed'));
  }, []);

  const decline = useCallback(() => {
    const data: ConsentData = {
      status: 'declined',
      timestamp: new Date().toISOString(),
      version: '1.0',
    };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
    setConsent('declined');
    window.dispatchEvent(new Event('cookie-consent-changed'));
  }, []);

  return { consent, loaded, accept, decline };
}
