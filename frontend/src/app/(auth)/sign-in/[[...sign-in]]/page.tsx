import { SignIn } from '@clerk/nextjs';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Sign In',
  description: 'Sign in to your Clairo account',
};

/**
 * Sign In Page
 *
 * Uses Clerk's SignIn component for a complete authentication flow.
 * Supports email/password, social logins, and MFA if configured.
 */
export default function SignInPage() {
  return (
    <SignIn
      appearance={{
        elements: {
          rootBox: 'w-full',
          card: 'w-full shadow-xl rounded-2xl border-0',
        },
      }}
      routing="path"
      path="/sign-in"
      signUpUrl="/sign-up"
      forceRedirectUrl="/dashboard"
    />
  );
}
