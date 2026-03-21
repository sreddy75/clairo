'use client';

import { useAuth, useUser } from '@clerk/nextjs';
import { useRouter } from 'next/navigation';
import { useState } from 'react';

import { apiClient } from '@/lib/api-client';

export default function CreateAccountPage() {
  const router = useRouter();
  const { getToken } = useAuth();
  const { user } = useUser();
  const [practiceName, setPracticeName] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!practiceName.trim()) return;

    setIsSubmitting(true);
    setError(null);

    try {
      const token = await getToken();
      if (!token) throw new Error('Authentication required');

      const response = await apiClient.post('/api/v1/auth/register', {
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          tenant_name: practiceName.trim(),
        }),
      });

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        // If user already registered (conflict), just proceed
        if (response.status === 409) {
          router.push('/onboarding/tier-selection');
          return;
        }
        throw new Error(data.detail || data.error?.message || 'Failed to create account');
      }

      // Account created — proceed to tier selection
      router.push('/onboarding/tier-selection');
    } catch (err) {
      console.error('Failed to create account:', err);
      setError(
        err instanceof Error
          ? err.message
          : 'Failed to create account. Please try again.'
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="max-w-lg mx-auto space-y-8">
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
              d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"
            />
          </svg>
        </div>
        <h1 className="text-3xl font-bold text-foreground">
          Set up your practice
        </h1>
        <p className="mt-2 text-lg text-muted-foreground">
          Welcome{user?.firstName ? `, ${user.firstName}` : ''}! Tell us about your practice.
        </p>
      </div>

      {/* Error banner */}
      {error && (
        <div className="bg-status-danger/10 border border-status-danger/20 rounded-lg p-4 text-center">
          <p className="text-status-danger">{error}</p>
        </div>
      )}

      {/* Form */}
      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="bg-card rounded-xl border border-border p-6 space-y-4">
          <div>
            <label
              htmlFor="practiceName"
              className="block text-sm font-medium text-foreground mb-1"
            >
              Practice / Organisation Name
            </label>
            <input
              id="practiceName"
              type="text"
              value={practiceName}
              onChange={(e) => setPracticeName(e.target.value)}
              placeholder="e.g. Smith & Partners Accounting"
              className="w-full px-4 py-3 rounded-lg border border-border bg-background text-foreground placeholder:text-muted-foreground focus:ring-2 focus:ring-primary/20 focus:border-primary transition-colors"
              required
              autoFocus
              minLength={2}
              maxLength={255}
            />
            <p className="mt-1.5 text-sm text-muted-foreground">
              This is the name of your accounting practice or firm.
            </p>
          </div>
        </div>

        <button
          type="submit"
          disabled={isSubmitting || !practiceName.trim()}
          className="w-full px-6 py-3 bg-primary text-primary-foreground rounded-lg font-medium hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center"
        >
          {isSubmitting ? (
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
              Creating your account...
            </>
          ) : (
            'Continue'
          )}
        </button>
      </form>
    </div>
  );
}
