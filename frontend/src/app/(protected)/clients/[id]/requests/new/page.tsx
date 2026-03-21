'use client';

import { useAuth } from '@clerk/nextjs';
import { ArrowLeft, Loader2 } from 'lucide-react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useCallback, useEffect, useState } from 'react';

import { RequestForm } from '@/components/requests/RequestForm';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { apiClient } from '@/lib/api-client';

interface ClientInfo {
  id: string;
  organization_name: string;
  contact_email: string | null;
}

export default function NewRequestPage() {
  const params = useParams();
  const connectionId = params.id as string;
  const { getToken } = useAuth();

  const [client, setClient] = useState<ClientInfo | null>(null);
  const [loading, setLoading] = useState(true);

  // Fetch client info including email
  const fetchClient = useCallback(async () => {
    try {
      const token = await getToken();
      if (!token) return;

      const response = await apiClient.get(
        `/api/v1/clients/${connectionId}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      const data = await apiClient.handleResponse<ClientInfo>(response);
      setClient(data);
    } catch (err) {
      console.error('Failed to fetch client:', err);
    } finally {
      setLoading(false);
    }
  }, [connectionId, getToken]);

  useEffect(() => {
    fetchClient();
  }, [fetchClient]);

  if (loading) {
    return (
      <div className="container max-w-2xl py-6">
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      </div>
    );
  }

  return (
    <div className="container max-w-2xl py-6">
      <div className="mb-6">
        <Link href={`/clients/${connectionId}`}>
          <Button variant="ghost" size="sm" className="gap-1">
            <ArrowLeft className="h-4 w-4" />
            Back to Client
          </Button>
        </Link>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>New Document Request</CardTitle>
          <CardDescription>
            Request documents from {client?.organization_name || 'your client'}. Select a template to pre-fill the form or create a custom request.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <RequestForm
            connectionId={connectionId}
            clientName={client?.organization_name || 'Client'}
            clientEmail={client?.contact_email || ''}
          />
        </CardContent>
      </Card>
    </div>
  );
}
