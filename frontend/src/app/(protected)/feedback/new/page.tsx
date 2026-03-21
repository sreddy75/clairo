'use client';

import { useAuth } from '@clerk/nextjs';
import { ArrowLeft, Bug, Lightbulb, Loader2 } from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useCallback, useState } from 'react';

import { AudioRecorder } from '@/components/feedback/AudioRecorder';
import { BriefPreview } from '@/components/feedback/BriefPreview';
import { ConversationChat } from '@/components/feedback/ConversationChat';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { confirmBrief, createSubmission } from '@/lib/api/feedback';
import { cn } from '@/lib/utils';
import type { FeedbackMessage, SubmissionType } from '@/types/feedback';

type Step = 'select-type' | 'record' | 'conversation';

const TYPE_OPTIONS: {
  value: SubmissionType;
  label: string;
  description: string;
  icon: typeof Lightbulb;
}[] = [
  {
    value: 'feature_request',
    label: 'Feature Request',
    description:
      'Suggest a new feature, workflow improvement, or product idea',
    icon: Lightbulb,
  },
  {
    value: 'bug_enhancement',
    label: 'Bug / Enhancement',
    description:
      'Report an issue, incorrect behaviour, or suggest an enhancement',
    icon: Bug,
  },
];

export default function NewFeedbackPage() {
  const router = useRouter();
  const { getToken } = useAuth();

  const [step, setStep] = useState<Step>('select-type');
  const [selectedType, setSelectedType] = useState<SubmissionType | null>(null);
  const [submissionId, setSubmissionId] = useState<string | null>(null);
  const [initialMessages, setInitialMessages] = useState<FeedbackMessage[]>([]);
  const [briefData, setBriefData] = useState<{
    data: Record<string, unknown>;
    markdown: string;
  } | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isConfirming, setIsConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // ---------------------------------------------------------------------------
  // Step 1: Select type
  // ---------------------------------------------------------------------------
  const handleSelectType = useCallback((type: SubmissionType) => {
    setSelectedType(type);
    setError(null);
    setStep('record');
  }, []);

  // ---------------------------------------------------------------------------
  // Step 2: Audio ready -> create submission
  // ---------------------------------------------------------------------------
  const handleAudioReady = useCallback(
    async (file: File) => {
      if (!selectedType) return;

      setError(null);
      setIsSubmitting(true);

      try {
        const token = await getToken();
        if (!token) throw new Error('Authentication required');

        const submission = await createSubmission(token, selectedType, file);
        setSubmissionId(submission.id);

        // The initial transcript message comes back on the submission;
        // the ConversationChat component will fetch conversation on mount.
        setInitialMessages([]);
        setStep('conversation');
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : 'Failed to create submission. Please try again.'
        );
      } finally {
        setIsSubmitting(false);
      }
    },
    [selectedType, getToken]
  );

  // ---------------------------------------------------------------------------
  // Step 3: Brief ready
  // ---------------------------------------------------------------------------
  const handleBriefReady = useCallback(
    (data: Record<string, unknown>, markdown: string) => {
      setBriefData({ data, markdown });
    },
    []
  );

  const handleConfirmBrief = useCallback(async (revisions?: string) => {
    if (!submissionId) return;

    setError(null);
    setIsConfirming(true);

    try {
      const token = await getToken();
      if (!token) throw new Error('Authentication required');

      await confirmBrief(token, submissionId, revisions);
      router.push('/feedback');
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Failed to confirm brief. Please try again.'
      );
    } finally {
      setIsConfirming(false);
    }
  }, [submissionId, getToken, router]);

  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------
  const selectedTypeLabel =
    TYPE_OPTIONS.find((t) => t.value === selectedType)?.label ?? '';

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------
  return (
    <div className="space-y-5">
      {/* Page header */}
      <div className="flex items-center gap-3">
        <Link href="/feedback">
          <Button variant="ghost" size="icon" className="h-8 w-8">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <h1 className="text-xl font-semibold tracking-tight">New Feedback</h1>
      </div>

      {/* Error alert */}
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* ------------------------------------------------------------------ */}
      {/* Step 1: Select type                                                */}
      {/* ------------------------------------------------------------------ */}
      {step === 'select-type' && (
        <div className="grid gap-4 sm:grid-cols-2">
          {TYPE_OPTIONS.map((option) => {
            const Icon = option.icon;
            return (
              <button
                key={option.value}
                type="button"
                onClick={() => handleSelectType(option.value)}
                className="text-left"
              >
                <Card
                  className={cn(
                    'cursor-pointer transition-colors',
                    'hover:border-primary/50 hover:bg-accent/50'
                  )}
                >
                  <CardHeader>
                    <div className="flex items-center gap-3">
                      <div className="rounded-lg bg-primary/10 p-2.5">
                        <Icon className="h-5 w-5 text-primary" />
                      </div>
                      <CardTitle className="text-base">
                        {option.label}
                      </CardTitle>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <CardDescription>{option.description}</CardDescription>
                  </CardContent>
                </Card>
              </button>
            );
          })}
        </div>
      )}

      {/* ------------------------------------------------------------------ */}
      {/* Step 2: Record audio                                               */}
      {/* ------------------------------------------------------------------ */}
      {step === 'record' && (
        <div className="space-y-5">
          <Badge variant="secondary">{selectedTypeLabel}</Badge>

          {isSubmitting ? (
            <Card className="p-6">
              <div className="flex flex-col items-center gap-4">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                <p className="text-sm font-medium text-muted-foreground">
                  Transcribing your recording...
                </p>
              </div>
            </Card>
          ) : (
            <AudioRecorder
              onAudioReady={handleAudioReady}
              disabled={isSubmitting}
            />
          )}
        </div>
      )}

      {/* ------------------------------------------------------------------ */}
      {/* Step 3: Conversation + Brief                                       */}
      {/* ------------------------------------------------------------------ */}
      {step === 'conversation' && submissionId && (
        <div className="space-y-5">
          <Badge variant="secondary">{selectedTypeLabel}</Badge>

          <ConversationChat
            submissionId={submissionId}
            initialMessages={initialMessages}
            onBriefReady={handleBriefReady}
          />

          {briefData && (
            <div className="space-y-4">
              <BriefPreview
                briefData={briefData.data}
                briefMarkdown={briefData.markdown}
                onConfirm={async (revisions) => {
                  await handleConfirmBrief(revisions);
                }}
                isLoading={isConfirming}
              />

              <div className="flex justify-end hidden">
                <Button
                  onClick={() => handleConfirmBrief()}
                  disabled={isConfirming}
                  className="gap-2"
                >
                  {isConfirming && (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  )}
                  Confirm & Submit
                </Button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
