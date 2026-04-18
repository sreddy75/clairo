'use client';

import { useAuth, useUser } from '@clerk/nextjs';
import {
  AlertCircle,
  Database,
  Download,
  ListChecks,
  Loader2,
  Search,
} from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

import { CollectionsTab } from './components/collections-tab';
import { IngestionTab } from './components/ingestion-tab';
import { SearchTestTab } from './components/search-test-tab';
import { StrategiesTab } from './components/strategies-tab';

type TabId = 'ingestion' | 'collections' | 'search' | 'strategies';

interface Tab {
  id: TabId;
  label: string;
  icon: typeof Database;
}

const TABS: Tab[] = [
  { id: 'ingestion', label: 'Ingestion', icon: Download },
  { id: 'collections', label: 'Collections', icon: Database },
  { id: 'strategies', label: 'Strategies', icon: ListChecks },
  { id: 'search', label: 'Search Test', icon: Search },
];

/**
 * Knowledge Base Admin Page
 *
 * Super admin only - provides management interface for:
 * - Qdrant collection health and initialization
 * - Knowledge source configuration
 * - Ingestion job monitoring
 * - Search testing and verification
 */
export default function KnowledgeAdminPage() {
  const router = useRouter();
  const { isLoaded, isSignedIn } = useAuth();
  const { user } = useUser();
  const [activeTab, setActiveTab] = useState<TabId>('ingestion');
  const [isAuthorized, setIsAuthorized] = useState<boolean | null>(null);

  // Check super admin role
  useEffect(() => {
    if (!isLoaded) return;

    if (!isSignedIn) {
      router.push('/sign-in');
      return;
    }

    // Check for super_admin role in public metadata
    const role = user?.publicMetadata?.role as string | undefined;
    const isSuperAdmin = role === 'super_admin';

    if (!isSuperAdmin) {
      setIsAuthorized(false);
    } else {
      setIsAuthorized(true);
    }
  }, [isLoaded, isSignedIn, user, router]);

  // Loading state
  if (!isLoaded || isAuthorized === null) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  // Unauthorized state
  if (!isAuthorized) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <div className="max-w-md text-center">
          <div className="w-16 h-16 bg-status-danger/10 rounded-full flex items-center justify-center mx-auto">
            <AlertCircle className="w-8 h-8 text-status-danger" />
          </div>
          <h1 className="mt-6 text-xl font-bold text-foreground">
            Access Denied
          </h1>
          <p className="mt-3 text-muted-foreground">
            You don&apos;t have permission to access the Knowledge Base Admin.
            This page is restricted to super administrators only.
          </p>
          <button
            onClick={() => router.push('/dashboard')}
            className="mt-6 px-6 py-2.5 text-sm font-medium text-primary-foreground bg-primary rounded-lg hover:bg-primary/90 transition-colors"
          >
            Return to Dashboard
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* Page Header */}
      <div>
        <h1 className="text-xl font-bold text-foreground">
          Knowledge Base Admin
        </h1>
        <p className="text-muted-foreground mt-1">
          Manage knowledge sources, monitor ingestion, and test search
        </p>
      </div>

      {/* Tabs */}
      <div className="border-b border-border">
        <nav className="flex gap-6" aria-label="Tabs">
          {TABS.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-1 py-3 text-sm font-medium border-b-2 transition-colors ${
                  isActive
                    ? 'border-primary text-primary'
                    : 'border-transparent text-muted-foreground hover:text-foreground hover:border-border'
                }`}
              >
                <Icon className="w-4 h-4" />
                {tab.label}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Tab Content */}
      <div className="min-h-[400px]">
        {activeTab === 'ingestion' && <IngestionTab />}
        {activeTab === 'collections' && <CollectionsTab />}
        {activeTab === 'strategies' && <StrategiesTab />}
        {activeTab === 'search' && <SearchTestTab />}
      </div>
    </div>
  );
}
