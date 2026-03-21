'use client';

/**
 * Design Preview Page
 *
 * Allows viewing alternative client detail page designs.
 * Access at: /internal/design-preview
 */

import { ArrowLeft } from 'lucide-react';
import dynamic from 'next/dynamic';
import Link from 'next/link';
import { useState } from 'react';

const ClientDetailRedesign = dynamic(
  () => import('@/components/client-detail/ClientDetailRedesign').then(mod => ({ default: mod.default })),
  { loading: () => <div className="p-8 text-center">Loading Swiss Ledger design...</div> }
);

const ClientDetailCompact = dynamic(
  () => import('@/components/client-detail/ClientDetailCompact').then(mod => ({ default: mod.default })),
  { loading: () => <div className="p-8 text-center">Loading Ledger Cards design...</div> }
);

type DesignOption = 'swiss-ledger' | 'ledger-cards';

export default function DesignPreviewPage() {
  const [selectedDesign, setSelectedDesign] = useState<DesignOption>('swiss-ledger');

  return (
    <div className="min-h-screen bg-background">
      {/* Design Selector Header */}
      <div className="bg-card border-b border-border sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Link
                href="/clients"
                className="flex items-center gap-2 text-muted-foreground hover:text-foreground"
              >
                <ArrowLeft className="w-4 h-4" />
                Back to Clients
              </Link>
              <div className="w-px h-6 bg-border" />
              <h1 className="text-lg font-semibold text-foreground">
                Client Detail Page - Design Preview
              </h1>
            </div>

            <div className="flex items-center gap-2 bg-muted p-1 rounded-lg">
              <button
                onClick={() => setSelectedDesign('swiss-ledger')}
                className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${
                  selectedDesign === 'swiss-ledger'
                    ? 'bg-card text-foreground shadow-sm'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                Swiss Ledger (Sidebar)
              </button>
              <button
                onClick={() => setSelectedDesign('ledger-cards')}
                className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${
                  selectedDesign === 'ledger-cards'
                    ? 'bg-card text-foreground shadow-sm'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                Ledger Cards (Compact)
              </button>
            </div>
          </div>

          {/* Design Description */}
          <div className="mt-2 text-sm text-muted-foreground">
            {selectedDesign === 'swiss-ledger' ? (
              <p>
                <strong>Swiss Ledger:</strong> Persistent dark sidebar with grouped navigation,
                dashboard hero with key metrics, command palette (Cmd+K) for power users.
              </p>
            ) : (
              <p>
                <strong>Ledger Cards:</strong> Compact card-based layout with primary tabs
                and dropdown groups for detailed data access.
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Design Preview */}
      <div className="relative">
        {selectedDesign === 'swiss-ledger' && <ClientDetailRedesign />}
        {selectedDesign === 'ledger-cards' && <ClientDetailCompact />}
      </div>
    </div>
  );
}
