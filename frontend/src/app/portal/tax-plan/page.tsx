'use client';

/**
 * Client Portal — Tax Plan View
 *
 * Shows the shared tax plan summary with implementation checklist.
 * Clients can mark items as done and ask questions.
 */

import { useEffect, useState } from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';

interface PortalTaxPlan {
  plan_id: string;
  client_name: string;
  financial_year: string;
  client_summary: string;
  total_estimated_saving: number;
  implementation_items: {
    id: string;
    title: string;
    estimated_saving?: number;
    deadline?: string;
    status: string;
  }[];
  shared_at: string;
  practice_name: string;
}

export default function PortalTaxPlanPage() {
  const [plan, setPlan] = useState<PortalTaxPlan | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const response = await fetch('/api/v1/client-portal/tax-plan', {
          credentials: 'include',
        });
        if (!response.ok) {
          if (response.status === 404) {
            setPlan(null);
            return;
          }
          throw new Error('Failed to load tax plan');
        }
        const data = await response.json();
        setPlan(data);
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to load');
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <p className="text-muted-foreground">Loading your tax plan...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 text-red-600">{error}</div>
    );
  }

  if (!plan) {
    return (
      <div className="flex items-center justify-center py-16">
        <p className="text-muted-foreground">
          No tax plan has been shared with you yet. Your accountant will share one when ready.
        </p>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6 p-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold">Your Tax Plan — FY {plan.financial_year}</h1>
        <p className="text-sm text-muted-foreground">
          Prepared by {plan.practice_name}
        </p>
      </div>

      {/* Savings hero */}
      {plan.total_estimated_saving > 0 && (
        <Card>
          <CardContent className="pt-6 text-center">
            <p className="text-sm text-muted-foreground">Potential Tax Savings</p>
            <p className="text-3xl font-bold text-emerald-600">
              ${plan.total_estimated_saving.toLocaleString()}
            </p>
          </CardContent>
        </Card>
      )}

      {/* Summary */}
      {plan.client_summary && (
        <Card>
          <CardContent className="pt-4 prose prose-sm dark:prose-invert max-w-none">
            <pre className="whitespace-pre-wrap text-sm font-sans">{plan.client_summary}</pre>
          </CardContent>
        </Card>
      )}

      {/* Implementation Checklist */}
      {plan.implementation_items.length > 0 && (
        <Card>
          <CardContent className="pt-4">
            <h2 className="text-lg font-semibold mb-3">Recommended Actions</h2>
            <div className="space-y-3">
              {plan.implementation_items.map((item) => (
                <div
                  key={item.id}
                  className="flex items-center justify-between rounded-md border p-3"
                >
                  <div className="flex items-center gap-3">
                    <input
                      type="checkbox"
                      checked={item.status === 'completed'}
                      onChange={async () => {
                        const newStatus = item.status === 'completed' ? 'pending' : 'completed';
                        await fetch(`/api/v1/client-portal/tax-plan/items/${item.id}`, {
                          method: 'PATCH',
                          headers: { 'Content-Type': 'application/json' },
                          credentials: 'include',
                          body: JSON.stringify({ status: newStatus }),
                        });
                        setPlan((prev) => {
                          if (!prev) return prev;
                          return {
                            ...prev,
                            implementation_items: prev.implementation_items.map((i) =>
                              i.id === item.id ? { ...i, status: newStatus } : i,
                            ),
                          };
                        });
                      }}
                      className="h-4 w-4 rounded border-gray-300"
                    />
                    <div>
                      <p className="text-sm font-medium">{item.title}</p>
                      {item.deadline && (
                        <p className="text-xs text-muted-foreground">
                          Complete by {new Date(item.deadline).toLocaleDateString()}
                        </p>
                      )}
                    </div>
                  </div>
                  {item.estimated_saving && (
                    <Badge variant="outline" className="text-emerald-600">
                      Save ${item.estimated_saving.toLocaleString()}
                    </Badge>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Ask a question */}
      <Card>
        <CardContent className="pt-4">
          <h2 className="text-lg font-semibold mb-2">Have Questions?</h2>
          <p className="text-sm text-muted-foreground mb-3">
            If you have questions about any of these recommendations, your accountant is here to help.
          </p>
          <Button
            variant="outline"
            onClick={() => {
              const question = prompt('What would you like to ask your accountant?');
              if (question) {
                fetch('/api/v1/client-portal/tax-plan/question', {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  credentials: 'include',
                  body: JSON.stringify({ question }),
                }).then(() => {
                  alert('Your question has been sent to your accountant!');
                });
              }
            }}
          >
            Ask a Question
          </Button>
        </CardContent>
      </Card>

      <p className="text-xs text-center text-muted-foreground">
        All figures are estimates only. Professional advice should be sought for implementation.
      </p>
    </div>
  );
}
