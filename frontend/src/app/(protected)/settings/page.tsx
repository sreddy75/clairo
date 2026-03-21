'use client';

import { Link2, Shield, User, Building2, CreditCard } from 'lucide-react';
import Link from 'next/link';

const settingsCategories = [
  {
    name: 'Integrations',
    description: 'Connect your accounting software like Xero or MYOB',
    href: '/settings/integrations',
    icon: Link2,
  },
  {
    name: 'Practice',
    description: 'Manage your practice settings and branding',
    href: '/settings/practice',
    icon: Building2,
  },
  {
    name: 'Account',
    description: 'Update your personal account settings',
    href: '/settings/account',
    icon: User,
  },
  {
    name: 'Security',
    description: 'Manage passwords, MFA, and security settings',
    href: '/settings/security',
    icon: Shield,
  },
  {
    name: 'Billing',
    description: 'Manage your subscription and payment methods',
    href: '/settings/billing',
    icon: CreditCard,
  },
];

/**
 * Settings Overview Page
 * Displays navigation cards to different settings sections.
 */
export default function SettingsPage() {
  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-8">
        <h1 className="text-xl font-bold text-foreground">Settings</h1>
        <p className="text-muted-foreground mt-1">
          Manage your practice, integrations, and account settings.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {settingsCategories.map((category) => {
          const Icon = category.icon;
          return (
            <Link
              key={category.name}
              href={category.href}
              className="bg-card rounded-xl border border-border p-6 hover:border-primary hover:shadow-md transition-all"
            >
              <div className="flex items-start gap-4">
                <div className="w-10 h-10 bg-primary/10 rounded-lg flex items-center justify-center flex-shrink-0">
                  <Icon className="w-5 h-5 text-primary" />
                </div>
                <div>
                  <h2 className="text-lg font-semibold text-foreground">
                    {category.name}
                  </h2>
                  <p className="text-sm text-muted-foreground mt-1">
                    {category.description}
                  </p>
                </div>
              </div>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
