'use client';

import { useAuth } from '@clerk/nextjs';
import { useCallback, useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { chatStream, listMessages } from '@/lib/api/tax-planning';
import { cn } from '@/lib/utils';
import type { CitationVerification, TaxPlanMessage, TaxScenario } from '@/types/tax-planning';

import { CitationBadge } from './CitationBadge';

interface ScenarioChatProps {
  planId: string;
  disabled?: boolean;
  onScenarioCreated?: (scenario: TaxScenario) => void;
}

export function ScenarioChat({ planId, disabled, onScenarioCreated }: ScenarioChatProps) {
  const { getToken } = useAuth();
  const [messages, setMessages] = useState<TaxPlanMessage[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [streamingContent, setStreamingContent] = useState('');
  const [thinkingText, setThinkingText] = useState('');
  const pendingVerificationRef = useRef<CitationVerification | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

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

  const handleSend = async () => {
    if (!input.trim() || isLoading || disabled) return;

    const userMessage = input.trim();
    setInput('');
    setIsLoading(true);
    setStreamingContent('');
    setThinkingText('');

    // Add user message optimistically
    const tempUserMsg: TaxPlanMessage = {
      id: `temp-${Date.now()}`,
      role: 'user',
      content: userMessage,
      scenario_ids: [],
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempUserMsg]);

    try {
      const token = await getToken();
      if (!token) return;

      let fullContent = '';

      for await (const event of chatStream(token, planId, userMessage)) {
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
    <Card className="flex flex-col h-[700px]">
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

          {/* Thinking indicator */}
          {thinkingText && (
            <div className="flex justify-start">
              <div className="max-w-[85%] rounded-lg bg-muted/30 px-3 py-2 text-sm text-muted-foreground italic">
                {thinkingText}
              </div>
            </div>
          )}

          {/* Loading dots */}
          {isLoading && !streamingContent && !thinkingText && (
            <div className="flex justify-start">
              <div className="rounded-lg bg-muted/30 px-3 py-2">
                <div className="flex gap-1">
                  <div className="h-2 w-2 rounded-full bg-muted-foreground/40 animate-bounce" style={{ animationDelay: '0ms' }} />
                  <div className="h-2 w-2 rounded-full bg-muted-foreground/40 animate-bounce" style={{ animationDelay: '150ms' }} />
                  <div className="h-2 w-2 rounded-full bg-muted-foreground/40 animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="border-t p-3">
          <div className="flex gap-2">
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
              disabled={!input.trim() || isLoading || disabled}
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
