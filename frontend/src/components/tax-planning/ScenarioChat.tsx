'use client';

import { useAuth } from '@clerk/nextjs';
import { FileText, Paperclip, X } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { chatStream, listMessages } from '@/lib/api/tax-planning';
import { cn } from '@/lib/utils';
import type { ChatAttachment, CitationVerification, TaxPlanMessage, TaxScenario } from '@/types/tax-planning';

import { CitationBadge } from './CitationBadge';

const ACCEPTED_FILE_TYPES = [
  'image/png',
  'image/jpeg',
  'image/webp',
  'image/gif',
  'application/pdf',
  'text/csv',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  'text/plain',
].join(',');

const ACCEPTED_EXTENSIONS = '.png,.jpg,.jpeg,.webp,.gif,.pdf,.csv,.xlsx,.txt';

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)}KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
}

interface ScenarioChatProps {
  planId: string;
  disabled?: boolean;
  onScenarioCreated?: (scenario: TaxScenario) => void;
  className?: string;
}

export function ScenarioChat({ planId, disabled, onScenarioCreated, className }: ScenarioChatProps) {
  const { getToken } = useAuth();
  const [messages, setMessages] = useState<TaxPlanMessage[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [streamingContent, setStreamingContent] = useState('');
  const [thinkingText, setThinkingText] = useState('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const pendingVerificationRef = useRef<CitationVerification | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Auto-scroll to bottom
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamingContent, scrollToBottom]);

  // Load existing messages
  useEffect(() => {
    const load = async () => {
      const token = await getToken();
      if (!token || !planId) return;
      try {
        const response = await listMessages(token, planId);
        setMessages(response.items);
      } catch {
        // Silently fail — empty chat is fine
      }
    };
    load();
  }, [planId, getToken]);

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      textarea.style.height = `${Math.min(textarea.scrollHeight, 150)}px`;
    }
  }, [input]);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      if (file.size > 10 * 1024 * 1024) {
        alert('File too large. Maximum size is 10MB.');
        return;
      }
      setSelectedFile(file);
    }
    e.target.value = '';
  };

  const handleSend = async () => {
    if ((!input.trim() && !selectedFile) || isLoading || disabled) return;

    const userMessage = input.trim() || (selectedFile ? `[Attached: ${selectedFile.name}]` : '');
    const fileToSend = selectedFile;
    setInput('');
    setSelectedFile(null);
    setIsLoading(true);
    setStreamingContent('');
    setThinkingText('');

    // Build optimistic attachment info
    const attachment: ChatAttachment | undefined = fileToSend
      ? {
          filename: fileToSend.name,
          media_type: fileToSend.type,
          category: fileToSend.type.startsWith('image/') ? 'image' :
                    fileToSend.type === 'application/pdf' ? 'pdf' :
                    fileToSend.type === 'text/csv' ? 'csv' :
                    fileToSend.type.includes('spreadsheet') ? 'excel' : 'text',
          size_bytes: fileToSend.size,
        }
      : undefined;

    // Add user message optimistically
    const tempUserMsg: TaxPlanMessage = {
      id: `temp-${Date.now()}`,
      role: 'user',
      content: userMessage,
      scenario_ids: [],
      created_at: new Date().toISOString(),
      attachment,
    };
    setMessages((prev) => [...prev, tempUserMsg]);

    try {
      const token = await getToken();
      if (!token) return;

      let fullContent = '';

      for await (const event of chatStream(token, planId, userMessage, fileToSend)) {
        switch (event.type) {
          case 'thinking':
            setThinkingText(event.content || '');
            break;
          case 'content':
            fullContent += event.content || '';
            setStreamingContent(fullContent);
            setThinkingText('');
            break;
          case 'scenario':
            if (event.scenario && onScenarioCreated) {
              onScenarioCreated(event.scenario as TaxScenario);
            }
            break;
          case 'verification':
            if (event.data) {
              pendingVerificationRef.current = event.data;
            }
            break;
          case 'done':
            // Add final assistant message with verification data
            if (fullContent) {
              const assistantMsg: TaxPlanMessage = {
                id: event.message_id || `msg-${Date.now()}`,
                role: 'assistant',
                content: fullContent,
                scenario_ids: event.scenarios_created || [],
                created_at: new Date().toISOString(),
                citation_verification: pendingVerificationRef.current,
              };
              setMessages((prev) => [...prev, assistantMsg]);
              pendingVerificationRef.current = null;
            }
            setStreamingContent('');
            break;
          case 'error':
            setMessages((prev) => [
              ...prev,
              {
                id: `error-${Date.now()}`,
                role: 'assistant',
                content: `Error: ${event.error || 'Something went wrong'}`,
                scenario_ids: [],
                created_at: new Date().toISOString(),
              },
            ]);
            setStreamingContent('');
            break;
        }
      }
    } catch (e) {
      setMessages((prev) => [
        ...prev,
        {
          id: `error-${Date.now()}`,
          role: 'assistant',
          content: `Error: ${e instanceof Error ? e.message : 'Failed to get response'}`,
          scenario_ids: [],
          created_at: new Date().toISOString(),
        },
      ]);
    } finally {
      setIsLoading(false);
      setStreamingContent('');
      setThinkingText('');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <Card className={cn("flex flex-col h-[700px]", className)}>
      <CardContent className="flex flex-col flex-1 p-0 overflow-hidden">
        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {messages.length === 0 && !streamingContent && (
            <div className="flex items-center justify-center h-full">
              <p className="text-sm text-muted-foreground text-center">
                Describe a scenario to model tax strategies.
                <br />
                <span className="text-xs">
                  e.g. &quot;Client wants to prepay 6 months rent ($30K) before June 30&quot;
                </span>
              </p>
            </div>
          )}

          {messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} />
          ))}

          {/* Streaming content */}
          {streamingContent && (
            <div className="flex justify-start">
              <div className="max-w-[85%] rounded-lg bg-muted/50 px-3 py-2 text-sm whitespace-pre-wrap">
                {streamingContent}
              </div>
            </div>
          )}

          {/* Thinking indicator with animated logo */}
          {thinkingText && (
            <div className="flex justify-start">
              <div className="flex items-center gap-2 max-w-[85%] rounded-lg bg-muted/30 px-3 py-2">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src="/logos/clairo-logo-new.png" alt="" width={22} height={22} className="rounded-sm shrink-0 animate-pulse " />
                <span className="text-sm text-muted-foreground italic">{thinkingText}</span>
              </div>
            </div>
          )}

          {/* Loading indicator with animated logo */}
          {isLoading && !streamingContent && !thinkingText && (
            <div className="flex justify-start">
              <div className="flex items-center gap-2 rounded-lg bg-muted/30 px-3 py-2">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src="/logos/clairo-logo-new.png" alt="" width={22} height={22} className="rounded-sm animate-pulse " />
                <span className="text-xs text-muted-foreground">Thinking...</span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* File preview */}
        {selectedFile && (
          <div className="border-t px-3 pt-2">
            <div className="inline-flex items-center gap-2 rounded-md bg-muted/50 px-2.5 py-1.5 text-xs">
              <FileText className="h-3.5 w-3.5 text-muted-foreground" />
              <span className="max-w-[200px] truncate">{selectedFile.name}</span>
              <span className="text-muted-foreground">{formatFileSize(selectedFile.size)}</span>
              <button
                onClick={() => setSelectedFile(null)}
                className="ml-1 rounded-sm hover:bg-muted"
              >
                <X className="h-3 w-3" />
              </button>
            </div>
          </div>
        )}

        {/* Input */}
        <div className="border-t p-3">
          <div className="flex gap-2">
            <input
              ref={fileInputRef}
              type="file"
              accept={`${ACCEPTED_FILE_TYPES},${ACCEPTED_EXTENSIONS}`}
              className="hidden"
              onChange={handleFileSelect}
            />
            <Button
              variant="ghost"
              size="sm"
              className="shrink-0 px-2"
              onClick={() => fileInputRef.current?.click()}
              disabled={disabled || isLoading}
              title="Attach file (image, PDF, Excel, CSV)"
            >
              <Paperclip className="h-4 w-4" />
            </Button>
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={
                disabled
                  ? 'Load financials first to enable AI chat'
                  : 'Describe a tax scenario...'
              }
              disabled={disabled || isLoading}
              className="flex-1 resize-none rounded-md border bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring disabled:opacity-50"
              rows={1}
            />
            <Button
              onClick={handleSend}
              disabled={(!input.trim() && !selectedFile) || isLoading || disabled}
              size="sm"
            >
              Send
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function AttachmentBadge({ attachment }: { attachment: ChatAttachment }) {
  const icon = attachment.category === 'image' ? '🖼' :
               attachment.category === 'pdf' ? '📄' :
               attachment.category === 'csv' || attachment.category === 'excel' ? '📊' : '📎';

  return (
    <div className="inline-flex items-center gap-1.5 rounded bg-primary-foreground/10 px-2 py-1 text-xs mb-1">
      <span>{icon}</span>
      <span className="max-w-[180px] truncate">{attachment.filename}</span>
      <span className="text-primary-foreground/60">{formatFileSize(attachment.size_bytes)}</span>
    </div>
  );
}

function MessageBubble({ message }: { message: TaxPlanMessage }) {
  const isUser = message.role === 'user';

  return (
    <div className={cn('flex flex-col', isUser ? 'items-end' : 'items-start')}>
      <div
        className={cn(
          'max-w-[85%] rounded-lg px-3 py-2 text-sm',
          isUser
            ? 'bg-primary text-primary-foreground whitespace-pre-wrap'
            : 'bg-muted/50 prose prose-sm dark:prose-invert max-w-none prose-p:my-1 prose-headings:my-2 prose-table:my-2 prose-li:my-0.5 prose-td:px-2 prose-td:py-1 prose-th:px-2 prose-th:py-1 prose-table:text-xs',
        )}
      >
        {isUser && message.attachment && (
          <AttachmentBadge attachment={message.attachment} />
        )}
        {isUser ? (
          message.content
        ) : (
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
        )}
      </div>
      {!isUser && message.citation_verification && (
        <CitationBadge verification={message.citation_verification} />
      )}
    </div>
  );
}
