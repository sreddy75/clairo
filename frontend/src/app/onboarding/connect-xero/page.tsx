'use client';

import { useAuth } from '@clerk/nextjs';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

import { initiateXeroConnect, skipXero, setAuthToken, getProgress } from '@/lib/api/onboarding';

export default function ConnectXeroPage() {
  const router = useRouter();
  const { getToken } = useAuth();
  const [isLoading, setIsLoading] = useState(false);
  const [showSkipModal, setShowSkipModal] = useState(false);
  const [showTrialStarted, setShowTrialStarted] = useState(false);

  // Set auth token on mount and check if trial was started
  useEffect(() => {
    async function initAuth() {
      const token = await getToken();
      if (token) {
        setAuthToken(token);
      }

      // Check if status is payment_setup (trial started)
      if (token) {
        try {
          const progress = await getProgress();
          if (progress.status === 'payment_setup') {
            setShowTrialStarted(true);
          }
        } catch {
          // Ignore - non-critical check
        }
      }
    }
    initAuth();
  }, [getToken]);

  const handleConnectXero = async () => {
    setIsLoading(true);
    try {
      const token = await getToken();
      if (token) {
        setAuthToken(token);
      }

      const response = await initiateXeroConnect();
      // Redirect to Xero OAuth
      window.location.href = response.authorization_url;
    } catch (error) {
      console.error('Failed to connect Xero:', error);
      setIsLoading(false);
    }
  };

  const handleSkip = async () => {
    try {
      const token = await getToken();
      if (token) {
        setAuthToken(token);
      }

      await skipXero();
      router.push('/dashboard');
    } catch (error) {
      console.error('Failed to skip Xero:', error);
    }
  };

  return (
    <div className="max-w-2xl mx-auto space-y-8">
      {/* Trial started notification */}
      {showTrialStarted && (
        <div className="bg-status-success/10 border border-status-success/20 rounded-lg p-4 flex items-center gap-3">
          <svg
            className="w-5 h-5 text-status-success flex-shrink-0"
            fill="currentColor"
            viewBox="0 0 20 20"
          >
            <path
              fillRule="evenodd"
              d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
              clipRule="evenodd"
            />
          </svg>
          <div>
            <p className="font-medium text-status-success">
              Your 14-day free trial has started!
            </p>
            <p className="text-sm text-status-success">
              No credit card required. You can add a payment method later from Settings.
            </p>
          </div>
        </div>
      )}

      {/* Header */}
      <div className="text-center">
        <div className="mx-auto w-16 h-16 bg-primary/10 rounded-full flex items-center justify-center mb-4">
          <svg
            className="w-8 h-8 text-primary"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"
            />
          </svg>
        </div>
        <h1 className="text-3xl font-bold text-foreground">
          Connect your Xero account
        </h1>
        <p className="mt-2 text-lg text-muted-foreground">
          Import your clients and sync financial data automatically
        </p>
      </div>

      {/* Benefits */}
      <div className="bg-card rounded-xl border border-border p-6">
        <h2 className="text-lg font-semibold text-foreground mb-4">
          Why connect Xero?
        </h2>
        <ul className="space-y-4">
          {[
            {
              title: 'Import all your clients',
              description:
                'Bulk import your practice clients from Xero Practice Manager',
            },
            {
              title: 'Automatic data sync',
              description:
                'Keep financial data up-to-date with real-time synchronization',
            },
            {
              title: 'Smart BAS preparation',
              description:
                'AI-powered insights based on actual transaction data',
            },
            {
              title: 'Data quality scoring',
              description:
                'Identify and fix data issues before they become problems',
            },
          ].map((benefit) => (
            <li key={benefit.title} className="flex items-start">
              <svg
                className="w-5 h-5 text-status-success mr-3 mt-0.5 flex-shrink-0"
                fill="currentColor"
                viewBox="0 0 20 20"
              >
                <path
                  fillRule="evenodd"
                  d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                  clipRule="evenodd"
                />
              </svg>
              <div>
                <span className="font-medium text-foreground">
                  {benefit.title}
                </span>
                <p className="text-sm text-muted-foreground">{benefit.description}</p>
              </div>
            </li>
          ))}
        </ul>
      </div>

      {/* Connect button */}
      <div className="flex flex-col items-center space-y-4">
        <button
          onClick={handleConnectXero}
          disabled={isLoading}
          className="w-full sm:w-auto px-8 py-4 bg-[#13B5EA] text-white rounded-lg font-medium hover:bg-[#0E9AC7] transition-colors flex items-center justify-center disabled:opacity-50"
        >
          {isLoading ? (
            <>
              <svg
                className="animate-spin -ml-1 mr-2 h-5 w-5"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                />
              </svg>
              Connecting...
            </>
          ) : (
            <>
              <svg
                className="w-6 h-6 mr-2"
                viewBox="0 0 24 24"
                fill="currentColor"
              >
                <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm6.066 9.645c.183 4.04-2.83 8.544-8.164 8.544A8.127 8.127 0 015.5 16.898a5.778 5.778 0 004.252-1.189 2.879 2.879 0 01-2.684-1.995 2.88 2.88 0 001.298-.049c-1.381-.278-2.335-1.522-2.304-2.853.388.215.83.344 1.301.359a2.877 2.877 0 01-.889-3.835 8.153 8.153 0 005.92 3.001 2.876 2.876 0 014.895-2.62 5.73 5.73 0 001.824-.697 2.884 2.884 0 01-1.264 1.589 5.73 5.73 0 001.649-.453 5.765 5.765 0 01-1.432 1.489z" />
              </svg>
              Connect Xero
            </>
          )}
        </button>

        <button
          onClick={() => setShowSkipModal(true)}
          className="text-sm text-muted-foreground hover:text-foreground"
        >
          Skip for now
        </button>
      </div>

      {/* Skip confirmation modal */}
      {showSkipModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-card rounded-xl p-6 max-w-md mx-4">
            <h3 className="text-lg font-semibold text-foreground">
              Skip Xero connection?
            </h3>
            <p className="mt-2 text-muted-foreground">
              You can still use Clairo, but you will not be able to import clients
              or sync financial data automatically. You can connect Xero later
              from Settings.
            </p>
            <div className="mt-6 flex space-x-4">
              <button
                onClick={() => setShowSkipModal(false)}
                className="flex-1 px-4 py-2 border border-border rounded-lg text-foreground hover:bg-muted"
              >
                Cancel
              </button>
              <button
                onClick={handleSkip}
                className="flex-1 px-4 py-2 bg-muted-foreground text-background rounded-lg hover:bg-muted-foreground/90"
              >
                Skip anyway
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
