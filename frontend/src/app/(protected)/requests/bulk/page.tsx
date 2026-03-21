'use client';

import { useQuery } from '@tanstack/react-query';
import { ArrowLeft } from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';

import { BulkRequestWizard } from '@/components/requests/BulkRequestWizard';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { useRequestsApi } from '@/lib/api/requests';
import { useXeroApi } from '@/lib/api/xero';

export default function BulkRequestPage() {
  const router = useRouter();
  const requestsApi = useRequestsApi();
  const xeroApi = useXeroApi();

  // Fetch clients (Xero connections)
  const { data: clientsData, isLoading: isLoadingClients } = useQuery({
    queryKey: ['xero-connections'],
    queryFn: () => xeroApi.getConnections(),
  });

  // Fetch templates
  const { data: templatesData, isLoading: isLoadingTemplates } = useQuery({
    queryKey: ['request-templates'],
    queryFn: () => requestsApi.templates.list(),
  });

  const isLoading = isLoadingClients || isLoadingTemplates;

  // Transform clients for the wizard
  const clients = (clientsData?.connections || []).map((conn) => ({
    id: conn.id,
    name: conn.organisation_name || 'Unknown Organization',
    email: conn.primary_contact_email ?? undefined,
    status: conn.status,
  }));

  const templates = templatesData?.templates || [];

  if (isLoading) {
    return (
      <div className="container max-w-4xl py-8">
        <div className="space-y-4">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-4 w-96" />
          <div className="mt-8">
            <Skeleton className="h-16 w-full" />
          </div>
          <div className="mt-8 space-y-4">
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-64 w-full" />
          </div>
        </div>
      </div>
    );
  }

  if (clients.length === 0) {
    return (
      <div className="container max-w-4xl py-8">
        <div className="text-center py-12">
          <h2 className="text-xl font-semibold mb-2">No Clients Available</h2>
          <p className="text-muted-foreground mb-4">
            Connect some Xero organizations first to send bulk document requests.
          </p>
          <Button asChild>
            <Link href="/settings/integrations">Connect Xero</Link>
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="container max-w-4xl py-8">
      <div className="mb-8">
        <Button variant="ghost" size="sm" asChild className="mb-4">
          <Link href="/requests">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Requests
          </Link>
        </Button>
        <h1 className="text-2xl font-bold">Bulk Document Request</h1>
        <p className="text-muted-foreground">
          Send a document request to multiple clients at once
        </p>
      </div>

      <BulkRequestWizard
        clients={clients}
        templates={templates}
        onSuccess={() => router.push('/requests')}
        onCancel={() => router.back()}
      />
    </div>
  );
}
