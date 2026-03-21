'use client';

/**
 * SubmissionDetail
 *
 * Wide dialog for viewing a full feedback submission: metadata sidebar,
 * brief, transcript, conversation history, and team notes.
 * Follows the InsightDetailPanel two-zone layout pattern.
 */

import { useAuth } from '@clerk/nextjs';
import {
  Calendar,
  ChevronDown,
  ChevronRight,
  Clock,
  Copy,
  Download,
  FileText,
  Hash,
  Loader2,
  MessageSquare,
  User,
} from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog';
import { Separator } from '@/components/ui/separator';
import { Textarea } from '@/components/ui/textarea';
import {
  getSubmission,
  getConversation,
  exportBrief,
  listComments,
  addComment,
} from '@/lib/api/feedback';
import { formatDate, formatRelativeTime } from '@/lib/formatters';
import { cn } from '@/lib/utils';
import type {
  SubmissionDetail as SubmissionDetailType,
  FeedbackMessage,
  FeedbackComment,
} from '@/types/feedback';

interface SubmissionDetailProps {
  submissionId: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const TYPE_BADGE: Record<string, { label: string; className: string }> = {
  feature_request: {
    label: 'Feature Request',
    className: 'bg-primary/10 text-primary ring-1 ring-primary/20',
  },
  bug_enhancement: {
    label: 'Bug / Enhancement',
    className: 'bg-status-warning/10 text-status-warning ring-1 ring-status-warning/20',
  },
};

const STATUS_BADGE: Record<string, { label: string; className: string }> = {
  draft: { label: 'Draft', className: 'bg-muted text-muted-foreground' },
  new: { label: 'New', className: 'bg-primary/10 text-primary ring-1 ring-primary/20' },
  in_review: {
    label: 'In Review',
    className: 'bg-status-warning/10 text-status-warning ring-1 ring-status-warning/20',
  },
  planned: {
    label: 'Planned',
    className: 'bg-accent/10 text-accent-foreground ring-1 ring-accent/20',
  },
  in_progress: {
    label: 'In Progress',
    className: 'bg-primary/10 text-primary ring-1 ring-primary/20',
  },
  done: {
    label: 'Done',
    className: 'bg-status-success/10 text-status-success ring-1 ring-status-success/20',
  },
};

const SEVERITY_BADGE: Record<string, { label: string; className: string }> = {
  low: { label: 'Low', className: 'bg-muted text-muted-foreground' },
  medium: {
    label: 'Medium',
    className: 'bg-status-warning/10 text-status-warning ring-1 ring-status-warning/20',
  },
  high: {
    label: 'High',
    className: 'bg-status-danger/10 text-status-danger ring-1 ring-status-danger/20',
  },
  critical: {
    label: 'Critical',
    className: 'bg-status-danger/15 text-status-danger ring-1 ring-status-danger/30 font-semibold',
  },
};

function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

export function SubmissionDetail({ submissionId, open, onOpenChange }: SubmissionDetailProps) {
  const { getToken } = useAuth();

  const [submission, setSubmission] = useState<SubmissionDetailType | null>(null);
  const [messages, setMessages] = useState<FeedbackMessage[]>([]);
  const [comments, setComments] = useState<FeedbackComment[]>([]);
  const [loading, setLoading] = useState(false);
  const [newComment, setNewComment] = useState('');
  const [addingComment, setAddingComment] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [copied, setCopied] = useState(false);
  const [showTranscript, setShowTranscript] = useState(false);
  const [showConversation, setShowConversation] = useState(false);
  const [showExportMenu, setShowExportMenu] = useState(false);

  const loadData = useCallback(async () => {
    if (!submissionId) return;
    setLoading(true);
    try {
      const token = await getToken();
      if (!token) return;

      const [detail, convo, commentsRes] = await Promise.all([
        getSubmission(token, submissionId),
        getConversation(token, submissionId),
        listComments(token, submissionId),
      ]);

      setSubmission(detail);
      setMessages(convo.messages);
      setComments(commentsRes.items);
    } catch {
      // Errors handled silently — the UI shows empty state
    } finally {
      setLoading(false);
    }
  }, [submissionId, getToken]);

  useEffect(() => {
    if (open && submissionId) {
      loadData();
    }
    if (!open) {
      setSubmission(null);
      setMessages([]);
      setComments([]);
      setNewComment('');
      setShowTranscript(false);
      setShowConversation(false);
      setShowExportMenu(false);
    }
  }, [open, submissionId, loadData]);

  const handleExportDownload = useCallback(async () => {
    if (!submissionId) return;
    setExporting(true);
    try {
      const token = await getToken();
      if (!token) return;

      const text = await exportBrief(token, submissionId);
      const blob = new Blob([text], { type: 'text/markdown' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${submission?.title ?? 'submission'}-brief.md`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch {
      // Download failed silently
    } finally {
      setExporting(false);
      setShowExportMenu(false);
    }
  }, [submissionId, submission?.title, getToken]);

  const handleExportCopy = useCallback(async () => {
    if (!submissionId) return;
    setExporting(true);
    try {
      const token = await getToken();
      if (!token) return;

      const text = await exportBrief(token, submissionId);
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Copy failed silently
    } finally {
      setExporting(false);
      setShowExportMenu(false);
    }
  }, [submissionId, getToken]);

  const handleAddComment = useCallback(async () => {
    if (!submissionId || !newComment.trim()) return;
    setAddingComment(true);
    try {
      const token = await getToken();
      if (!token) return;

      const comment = await addComment(token, submissionId, newComment.trim());
      setComments((prev) => [...prev, comment]);
      setNewComment('');
    } catch {
      // Comment add failed silently
    } finally {
      setAddingComment(false);
    }
  }, [submissionId, newComment, getToken]);

  const typeBadge = submission ? TYPE_BADGE[submission.type] : null;
  const statusBadge = submission ? STATUS_BADGE[submission.status] : null;
  const severityBadge = submission?.severity ? SEVERITY_BADGE[submission.severity] : null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className={cn(
          'max-w-4xl w-[95vw] p-0 gap-0 overflow-hidden',
          'bg-card border-border',
          'max-h-[90vh] flex flex-col',
        )}
      >
        {/* Accessibility title */}
        <DialogTitle className="sr-only">
          {submission?.title ?? 'Submission Detail'}
        </DialogTitle>

        {loading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
          </div>
        ) : !submission ? (
          <div className="flex items-center justify-center py-20">
            <p className="text-sm text-muted-foreground">Submission not found</p>
          </div>
        ) : (
          <>
            {/* Header */}
            <div className="px-6 pt-5 pb-4 border-b border-border shrink-0">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  {/* Badge row */}
                  <div className="flex items-center gap-2 flex-wrap mb-2.5">
                    {typeBadge && (
                      <span className={cn('px-2.5 py-0.5 rounded-md text-xs font-medium', typeBadge.className)}>
                        {typeBadge.label}
                      </span>
                    )}
                    {statusBadge && (
                      <span className={cn('px-2.5 py-0.5 rounded-md text-xs font-medium', statusBadge.className)}>
                        {statusBadge.label}
                      </span>
                    )}
                    {severityBadge && (
                      <span className={cn('px-2.5 py-0.5 rounded-md text-xs font-medium', severityBadge.className)}>
                        {severityBadge.label}
                      </span>
                    )}
                  </div>

                  {/* Title */}
                  <h2 className="text-xl font-semibold text-foreground leading-tight tracking-tight">
                    {submission.title ?? 'Untitled'}
                  </h2>
                </div>
              </div>
            </div>

            {/* Body — scrollable */}
            <div className="flex-1 overflow-y-auto min-h-0">
              <div className="flex flex-col lg:flex-row">
                {/* Metadata sidebar */}
                <aside className="lg:w-64 shrink-0 border-b lg:border-b-0 lg:border-r border-border p-5 space-y-4 bg-muted/50">
                  {/* Submitter */}
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1.5">
                      Submitter
                    </p>
                    <div className="flex items-center gap-1.5 text-xs text-foreground">
                      <User className="w-3 h-3 text-muted-foreground" />
                      {submission.submitter_name}
                    </div>
                  </div>

                  {/* Created */}
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1.5">
                      Created
                    </p>
                    <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                      <Calendar className="w-3 h-3" />
                      {formatDate(submission.created_at)}
                    </div>
                  </div>

                  {/* Last Updated */}
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1.5">
                      Last Updated
                    </p>
                    <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                      <Clock className="w-3 h-3" />
                      {formatRelativeTime(submission.updated_at)}
                    </div>
                  </div>

                  {/* Audio Duration */}
                  {submission.audio_duration_seconds != null && (
                    <div>
                      <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1.5">
                        Audio Duration
                      </p>
                      <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                        <Clock className="w-3 h-3" />
                        {formatDuration(submission.audio_duration_seconds)}
                      </div>
                    </div>
                  )}

                  {/* Message Count */}
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1.5">
                      Messages
                    </p>
                    <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                      <MessageSquare className="w-3 h-3" />
                      {submission.message_count}
                    </div>
                  </div>

                  {/* Comment Count */}
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1.5">
                      Notes
                    </p>
                    <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                      <Hash className="w-3 h-3" />
                      {submission.comment_count}
                    </div>
                  </div>
                </aside>

                {/* Main content area */}
                <main className="flex-1 min-w-0 p-6 space-y-6">
                  {/* Brief section */}
                  {submission.brief_markdown && (
                    <div>
                      <div className="flex items-center gap-2 mb-3">
                        <FileText className="w-4 h-4 text-muted-foreground" />
                        <h3 className="text-sm font-semibold text-foreground">Brief</h3>
                      </div>
                      <div className="rounded-lg border border-border bg-muted/30 p-4">
                        <div className="text-sm text-foreground whitespace-pre-wrap leading-relaxed">
                          {submission.brief_markdown}
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Transcript section — collapsible */}
                  {submission.transcript && (
                    <div>
                      <button
                        onClick={() => setShowTranscript((prev) => !prev)}
                        className="flex items-center gap-2 text-sm font-semibold text-foreground hover:text-primary transition-colors"
                      >
                        {showTranscript ? (
                          <ChevronDown className="w-4 h-4" />
                        ) : (
                          <ChevronRight className="w-4 h-4" />
                        )}
                        Original Transcript
                      </button>
                      {showTranscript && (
                        <div className="mt-3 rounded-lg border border-border bg-muted/30 p-4">
                          <div className="text-sm text-muted-foreground whitespace-pre-wrap leading-relaxed">
                            {submission.transcript}
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Conversation section — collapsible */}
                  {messages.length > 0 && (
                    <div>
                      <button
                        onClick={() => setShowConversation((prev) => !prev)}
                        className="flex items-center gap-2 text-sm font-semibold text-foreground hover:text-primary transition-colors"
                      >
                        {showConversation ? (
                          <ChevronDown className="w-4 h-4" />
                        ) : (
                          <ChevronRight className="w-4 h-4" />
                        )}
                        Conversation ({messages.length} messages)
                      </button>
                      {showConversation && (
                        <div className="mt-3 space-y-3">
                          {messages.map((msg) => (
                            <div
                              key={msg.id}
                              className={cn(
                                'rounded-lg border border-border p-3',
                                msg.role === 'assistant' && 'bg-muted/30',
                                msg.role === 'user' && 'bg-card',
                                msg.role === 'system' && 'bg-muted/50',
                              )}
                            >
                              <div className="flex items-center gap-2 mb-1.5">
                                <Badge variant="outline" className="text-[10px] font-medium">
                                  {msg.role === 'assistant' ? 'AI' : msg.role === 'user' ? 'User' : 'System'}
                                </Badge>
                                {msg.content_type === 'transcript' && (
                                  <Badge variant="outline" className="text-[10px] font-medium text-muted-foreground">
                                    Voice
                                  </Badge>
                                )}
                                <span className="text-[10px] text-muted-foreground ml-auto tabular-nums">
                                  {formatRelativeTime(msg.created_at)}
                                </span>
                              </div>
                              <p className="text-sm text-foreground whitespace-pre-wrap leading-relaxed">
                                {msg.content}
                              </p>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  <Separator />

                  {/* Team Notes (Comments) */}
                  <div>
                    <h3 className="text-sm font-semibold text-foreground mb-3">Team Notes</h3>

                    {comments.length > 0 ? (
                      <div className="space-y-3 mb-4">
                        {comments.map((comment) => (
                          <div key={comment.id} className="rounded-lg border border-border p-3 bg-card">
                            <div className="flex items-center gap-2 mb-1.5">
                              <span className="text-xs font-medium text-foreground">
                                {comment.author_name}
                              </span>
                              <span className="text-[10px] text-muted-foreground ml-auto tabular-nums">
                                {formatRelativeTime(comment.created_at)}
                              </span>
                            </div>
                            <p className="text-sm text-foreground whitespace-pre-wrap">
                              {comment.content}
                            </p>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-sm text-muted-foreground mb-4">No notes yet.</p>
                    )}

                    {/* Add comment */}
                    <div className="flex gap-2">
                      <Textarea
                        placeholder="Add a note..."
                        value={newComment}
                        onChange={(e) => setNewComment(e.target.value)}
                        className="flex-1 min-h-[60px] text-sm resize-none"
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                            handleAddComment();
                          }
                        }}
                      />
                      <Button
                        size="sm"
                        onClick={handleAddComment}
                        disabled={addingComment || !newComment.trim()}
                        className="self-end"
                      >
                        {addingComment ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          'Add Note'
                        )}
                      </Button>
                    </div>
                  </div>
                </main>
              </div>
            </div>

            {/* Footer — export actions */}
            {submission.has_brief && (
              <div className="shrink-0 border-t border-border bg-muted px-6 py-3">
                <div className="flex items-center justify-end">
                  <div className="relative">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setShowExportMenu((prev) => !prev)}
                      disabled={exporting}
                      className="inline-flex items-center gap-2"
                    >
                      {exporting ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <Download className="w-4 h-4" />
                      )}
                      Export for Spec
                      <ChevronDown className="w-3 h-3" />
                    </Button>

                    {showExportMenu && (
                      <div className="absolute right-0 bottom-full mb-1 w-48 rounded-lg border border-border bg-card shadow-lg py-1 z-50">
                        <button
                          onClick={handleExportDownload}
                          className="w-full flex items-center gap-2 px-3 py-2 text-sm text-foreground hover:bg-muted transition-colors"
                        >
                          <Download className="w-4 h-4 text-muted-foreground" />
                          Download as .md
                        </button>
                        <button
                          onClick={handleExportCopy}
                          className="w-full flex items-center gap-2 px-3 py-2 text-sm text-foreground hover:bg-muted transition-colors"
                        >
                          <Copy className="w-4 h-4 text-muted-foreground" />
                          {copied ? 'Copied!' : 'Copy to clipboard'}
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
