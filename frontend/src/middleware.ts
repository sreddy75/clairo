import { clerkMiddleware, createRouteMatcher } from '@clerk/nextjs/server';
import { NextResponse } from 'next/server';

/**
 * Routes that are publicly accessible without authentication.
 */
const isPublicRoute = createRouteMatcher([
  '/',
  '/sign-in(.*)',
  '/sign-up(.*)',
  '/invitation(.*)',
  '/pricing(.*)',
  '/portal(.*)',  // Client portal uses its own magic link auth
  '/terms',
  '/privacy',
  '/acceptable-use',
  '/api/health',
  '/api/webhooks(.*)',
]);

// Routes that require auth but not backend registration
const isOnboardingRoute = createRouteMatcher(['/onboarding(.*)', '/accept-terms']);

export default clerkMiddleware((auth, request) => {
  const { userId } = auth();

  // Allow public routes without auth
  if (isPublicRoute(request)) {
    return;
  }

  // Onboarding routes require Clerk auth but not backend registration
  if (isOnboardingRoute(request)) {
    if (!userId) {
      // Not authenticated, redirect to sign-up
      return NextResponse.redirect(new URL('/sign-up', request.url));
    }
    // Authenticated, allow access to onboarding
    return;
  }

  // Protect all other routes
  auth().protect();

  // If authenticated and on root, redirect to dashboard
  // Note: Actual onboarding check should happen in the dashboard layout
  // because middleware can't access the database
  if (userId && request.nextUrl.pathname === '/') {
    // Redirect to dashboard - the dashboard layout will check onboarding status
    return NextResponse.redirect(new URL('/dashboard', request.url));
  }

  return undefined;
});

export const config = {
  matcher: [
    // Skip Next.js internals, static files, Clerk proxy path, and backend API proxy.
    // /api/v1/* is proxied to the backend which handles its own JWT auth — running
    // Clerk middleware here adds redundant session validation + Vercel edge latency.
    '/((?!_next/static|_next/image|favicon\\.ico|clerk-proxy|api/v1/|api/health|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)',
    // Run for trpc routes only.
    '/(trpc)(.*)',
  ],
};
