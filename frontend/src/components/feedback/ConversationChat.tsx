'use client';

import { useAuth } from '@clerk/nextjs';
import { Mic, Send, Loader2 } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Textarea } from '@/components/ui/textarea';
import { sendMessage, sendVoiceMessage, getConversation } from '@/lib/api/feedback';
import { formatRelativeTime } from '@/lib/formatters';
import { cn } from '@/lib/utils';
import type {
  FeedbackMessage,
  ConversationTurnResponse,
} from '@/types/feedback';

interface ConversationChatProps {
  submissionId: string;
  initialMessages?: FeedbackMessage[];
  onBriefReady: (
    briefData: Record<string, unknown>,
    briefMarkdown: string
  ) => void;
}

export function ConversationChat({
  submissionId,
  initialMessages,
  onBriefReady,
}: ConversationChatProps) {
  const { getToken } = useAuth();
  const [messages, setMessages] = useState<FeedbackMessage[]>(
    initialMessages ?? []
  );
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Auto-scroll to bottom on new messages
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading, scrollToBottom]);

  // Fetch conversation on mount if no initial messages
  useEffect(() => {
    if (initialMessages && initialMessages.length > 0) return;

    async function fetchMessages() {
      try {
        const token = await getToken();
        if (!token) return;
        const res = await getConversation(token, submissionId);
        setMessages(res.messages);
      } catch {
        // Silent fail on initial load — messages may not exist yet
      }
    }

    fetchMessages();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [submissionId]);

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = 'auto';
    textarea.style.height = `${Math.min(textarea.scrollHeight, 160)}px`;
  }, [input]);

  // Handle brief ready from a turn response
  const handleTurnResponse = useCallback(
    (response: ConversationTurnResponse) => {
      setMessages((prev) => [
        ...prev,
        response.user_message,
        response.assistant_message,
      ]);

      if (response.brief_ready && response.brief_data) {
        onBriefReady(
          response.brief_data,
          response.brief_markdown ?? ''
        );
      }
    },
    [onBriefReady]
  );

  // Send text message
  const handleSend = useCallback(async () => {
    const content = input.trim();
    if (!content || isLoading) return;

    setInput('');
    setError(null);
    setIsLoading(true);

    try {
      const token = await getToken();
      if (!token) throw new Error('Not authenticated');

      const response = await sendMessage(token, submissionId, content);
      handleTurnResponse(response);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to send message'
      );
    } finally {
      setIsLoading(false);
    }
  }, [input, isLoading, getToken, submissionId, handleTurnResponse]);

  // Send voice message via file upload
  const handleVoiceUpload = useCallback(
    async (file: File) => {
      setError(null);
      setIsLoading(true);

      try {
        const token = await getToken();
        if (!token) throw new Error('Not authenticated');

        const response = await sendVoiceMessage(token, submissionId, file);
        handleTurnResponse(response);
      } catch (err) {
        setError(
          err instanceof Error ? err.message : 'Failed to send voice message'
        );
      } finally {
        setIsLoading(false);
      }
    },
    [getToken, submissionId, handleTurnResponse]
  );

  // Handle keyboard shortcut
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend]
  );

  // Filter out system messages for display
  const displayMessages = messages.filter((m) => m.role !== 'system');

  return (
    <Card className="flex flex-col h-full">
      {/* Messages area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {displayMessages.length === 0 && !isLoading && (
          <p className="text-center text-sm text-muted-foreground py-8">
            No messages yet. Start the conversation below.
          </p>
        )}

        {displayMessages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}

        {isLoading && <TypingIndicator />}

        <div ref={messagesEndRef} />
      </div>

      {/* Error display */}
      {error && (
        <div className="px-4 pb-2">
          <p className="text-sm text-destructive">{error}</p>
        </div>
      )}

      {/* Input area */}
      <div className="border-t p-4 space-y-2">
        <div className="flex items-end gap-2">
          <Textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type your response..."
            disabled={isLoading}
            rows={1}
            className="min-h-[40px] max-h-[160px] resize-none"
          />
          <Button
            size="icon"
            onClick={handleSend}
            disabled={!input.trim() || isLoading}
          >
            {isLoading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </Button>
        </div>

        {/* Voice upload */}
        <input
          ref={fileInputRef}
          type="file"
          accept="audio/*"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) {
              handleVoiceUpload(file);
              e.target.value = '';
            }
          }}
        />
        <Button
          variant="ghost"
          size="sm"
          className="text-muted-foreground"
          disabled={isLoading}
          onClick={() => fileInputRef.current?.click()}
        >
          <Mic className="h-3.5 w-3.5 mr-1.5" />
          Record follow-up
        </Button>
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function MessageBubble({ message }: { message: FeedbackMessage }) {
  const isUser = message.role === 'user';
  const isTranscript = message.content_type === 'transcript';

  return (
    <div
      className={cn('flex', isUser ? 'justify-end' : 'justify-start')}
    >
      <div
        className={cn(
          'max-w-[80%] rounded-lg px-3 py-2 text-sm',
          isUser
            ? 'bg-primary text-primary-foreground'
            : 'bg-muted text-foreground'
        )}
      >
        {isTranscript && (
          <Badge
            variant="outline"
            className={cn(
              'mb-1.5 text-[10px] px-1.5 py-0',
              isUser
                ? 'border-primary-foreground/30 text-primary-foreground/80'
                : 'border-border'
            )}
          >
            Voice
          </Badge>
        )}
        <p className="whitespace-pre-wrap leading-relaxed">
          {message.content}
        </p>
        <span
          className={cn(
            'block text-[10px] mt-1 tabular-nums',
            isUser
              ? 'text-primary-foreground/60 text-right'
              : 'text-muted-foreground'
          )}
        >
          {formatRelativeTime(message.created_at)}
        </span>
      </div>
    </div>
  );
}

function TypingIndicator() {
  return (
    <div className="flex justify-start">
      <div className="bg-muted rounded-lg px-4 py-3">
        <div className="flex items-center gap-1">
          <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground/60 animate-bounce [animation-delay:0ms]" />
          <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground/60 animate-bounce [animation-delay:150ms]" />
          <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground/60 animate-bounce [animation-delay:300ms]" />
        </div>
      </div>
    </div>
  );
}
