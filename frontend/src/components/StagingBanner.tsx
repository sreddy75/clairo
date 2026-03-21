"use client";

/**
 * Staging Environment Banner
 *
 * Displays a prominent banner when the app is running in staging environment.
 * This helps testers distinguish staging from production.
 */

export function StagingBanner() {
  const isStaging = process.env.NEXT_PUBLIC_ENVIRONMENT === "staging";

  if (!isStaging) {
    return null;
  }

  return (
    <div className="fixed top-0 left-0 right-0 z-[9999] bg-amber-500 text-amber-950 text-center py-1 text-sm font-medium">
      <span className="inline-flex items-center gap-2">
        <span className="inline-block w-2 h-2 bg-amber-950 rounded-full animate-pulse" />
        STAGING ENVIRONMENT - Not for production use
      </span>
    </div>
  );
}
