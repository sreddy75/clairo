'use client';

import { usePathname } from 'next/navigation';

import { ClairoLogo } from '@/components/brand';
import { ThemeToggle } from '@/components/theme';

const steps = [
  { id: 'create-account', label: 'Create Account', path: '/onboarding/create-account' },
  { id: 'tier-selection', label: 'Select Plan', path: '/onboarding/tier-selection' },
  { id: 'connect-xero', label: 'Connect Xero', path: '/onboarding/connect-xero' },
  { id: 'import-clients', label: 'Import Clients', path: '/onboarding/import-clients' },
  { id: 'complete', label: 'Get Started', path: '/dashboard' },
];

export default function OnboardingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();

  // Determine current step index
  const currentStepIndex = steps.findIndex((step) =>
    pathname.startsWith(step.path)
  );

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="bg-card border-b border-border">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            {/* Logo */}
            <div className="flex items-center">
              <ClairoLogo size="md" variant="light" className="dark:hidden" />
              <ClairoLogo size="md" variant="dark" className="hidden dark:flex" />
            </div>

            {/* Progress Indicator */}
            <div className="hidden sm:flex items-center space-x-4">
              {steps.map((step, index) => (
                <div key={step.id} className="flex items-center">
                  <div
                    className={`flex items-center justify-center w-8 h-8 rounded-full text-sm font-medium ${
                      index < currentStepIndex
                        ? 'bg-primary text-primary-foreground'
                        : index === currentStepIndex
                        ? 'bg-primary text-primary-foreground ring-4 ring-primary/20'
                        : 'bg-muted text-muted-foreground'
                    }`}
                  >
                    {index < currentStepIndex ? (
                      <svg
                        className="w-5 h-5"
                        fill="currentColor"
                        viewBox="0 0 20 20"
                      >
                        <path
                          fillRule="evenodd"
                          d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                          clipRule="evenodd"
                        />
                      </svg>
                    ) : (
                      index + 1
                    )}
                  </div>
                  <span
                    className={`ml-2 text-sm ${
                      index <= currentStepIndex
                        ? 'text-foreground font-medium'
                        : 'text-muted-foreground'
                    }`}
                  >
                    {step.label}
                  </span>
                  {index < steps.length - 1 && (
                    <div
                      className={`ml-4 w-12 h-0.5 ${
                        index < currentStepIndex ? 'bg-primary' : 'bg-muted'
                      }`}
                    />
                  )}
                </div>
              ))}
            </div>

            {/* Right side: Theme toggle and mobile step indicator */}
            <div className="flex items-center gap-4">
              {/* Mobile step indicator */}
              <div className="sm:hidden text-sm text-muted-foreground">
                Step {currentStepIndex + 1} of {steps.length}
              </div>
              <ThemeToggle />
            </div>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {children}
      </main>
    </div>
  );
}
