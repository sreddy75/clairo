import { SignUp } from '@clerk/nextjs';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Sign Up',
  description: 'Create your Clairo account',
};

/**
 * Sign Up Page
 *
 * Uses Clerk's SignUp component for user registration.
 * After Clerk signup, users are redirected to onboarding to complete
 * their practice setup in the backend.
 */
export default function SignUpPage() {
  return (
    <SignUp
      appearance={{
        elements: {
          rootBox: 'w-full',
          card: 'w-full shadow-xl rounded-2xl border-0',
        },
      }}
      routing="path"
      path="/sign-up"
      signInUrl="/sign-in"
      forceRedirectUrl="/onboarding"
    />
  );
}
