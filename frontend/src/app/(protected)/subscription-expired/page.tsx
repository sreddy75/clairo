'use client';

import { CreditCard, Download, XCircle } from 'lucide-react';
import Link from 'next/link';

import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';

export default function SubscriptionExpiredPage() {
  return (
    <div className="flex items-center justify-center min-h-[70vh]">
      <Card className="max-w-md w-full shadow-sm">
        <CardContent className="p-8 text-center space-y-6">
          <div className="mx-auto w-16 h-16 bg-red-50 rounded-full flex items-center justify-center">
            <XCircle className="h-8 w-8 text-red-500" />
          </div>

          <div className="space-y-2">
            <h1 className="text-xl font-semibold text-foreground">
              Your subscription has ended
            </h1>
            <p className="text-sm text-muted-foreground">
              Your Clairo subscription is no longer active. Resubscribe to regain full
              access to your practice data and tools.
            </p>
          </div>

          <div className="space-y-3">
            <Button className="w-full" size="lg" asChild>
              <Link href="/settings/billing">
                <CreditCard className="h-4 w-4 mr-2" />
                Resubscribe — $299/month
              </Link>
            </Button>

            <p className="text-xs text-muted-foreground">
              Your data is safe. Resubscribing restores full access immediately.
            </p>
          </div>

          <div className="border-t pt-4">
            <Button variant="ghost" size="sm" className="text-muted-foreground" asChild>
              <Link href="/settings/billing/history">
                <Download className="h-3.5 w-3.5 mr-1.5" />
                View billing history
              </Link>
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
