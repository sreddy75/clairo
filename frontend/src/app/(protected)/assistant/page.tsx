'use client';

/**
 * AI Knowledge Assistant - Redesigned
 *
 * Professional "Command Center" aesthetic for Australian accountants.
 * Features a bold split-screen for General vs Client-specific queries.
 */

import { useAuth, useUser } from '@clerk/nextjs';
import {
  AlertCircle,
  ArrowRight,
  BookOpen,
  Building2,
  Check,
  ChevronLeft,
  ChevronRight,
  Clock,
  Copy,
  DollarSign,
  ExternalLink,
  FileText,
  History,
  ListTodo,
  Loader2,
  Mail,
  MessageSquare,
  Paperclip,
  RefreshCw,
  Search,
  Send,
  Shield,
  Sparkles,
  Trash2,
  TrendingUp,
  X,
  Zap,
} from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';

import {
  ConfidenceIndicator,
  EscalationBanner,
  PerspectiveBadgeList,
} from '@/components/assistant/PerspectiveBadges';
import { DataFreshnessIndicator } from '@/components/insights/DataFreshnessIndicator';
import { ConfidenceBadge } from '@/components/knowledge/confidence-badge';
import { DomainSelector } from '@/components/knowledge/domain-selector';
import { EnhancedCitationPanel } from '@/components/knowledge/enhanced-citation-panel';
import type { Citation as EnhancedCitation } from '@/components/knowledge/enhanced-citation-panel';
import { SupersessionBanner } from '@/components/knowledge/supersession-banner';
import { A2UIRenderer } from '@/lib/a2ui/renderer';
import type { A2UIMessage } from '@/lib/a2ui/types';
import { enrichAIContentForExport } from '@/lib/ai-export-utils';
import { agentChatStream, type AgentStreamEvent } from '@/lib/api/agents';
import {
  deleteConversation,
  getClientProfile,
  getConversation,
  getConversationsWithClients,
  searchClients,
  type ClientProfileResponse,
  type ClientSearchResult,
} from '@/lib/api/knowledge';
import type { Perspective } from '@/types/agents';
import { PERSPECTIVE_CONFIG, parsePerspectiveSections } from '@/types/agents';
import type {
  Citation,
  ConversationClientSummary,
  ConversationListItem,
} from '@/types/knowledge';

// =============================================================================
// Types
// =============================================================================

interface DisplayMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
  isStreaming?: boolean;
  perspectivesUsed?: Perspective[];
  confidence?: number;
  escalationRequired?: boolean;
  escalationReason?: string | null;
  processingTimeMs?: number;
  dataFreshness?: string | null;
  /** A2UI message for rich UI components */
  a2uiMessage?: A2UIMessage;
  /** Knowledge confidence tier from spec 045 (high/medium/low) */
  knowledgeConfidence?: 'high' | 'medium' | 'low';
  /** Knowledge confidence numeric score (0-1) */
  knowledgeConfidenceScore?: number;
  /** Warnings about superseded content */
  supersededWarnings?: string[];
  /** Attribution text for legislation/ATO sources */
  attribution?: string | null;
  /** Auto-detected specialist domain */
  domainDetected?: string | null;
  /** Classified query type */
  queryType?: string | null;
}

// =============================================================================
// Example Questions
// =============================================================================

const GENERAL_EXAMPLES = [
  { q: 'Client has mixed supplies — how do I apportion GST credits between taxable and input-taxed sales?', icon: DollarSign },
  { q: 'What are the CGT implications if my client transfers a business asset into a discretionary trust?', icon: Shield },
  { q: 'Client\'s wages just crossed $750K — walk me through payroll tax registration obligations by state', icon: FileText },
  { q: 'How should I structure motor vehicle expenses to maximise deductions — logbook vs cents-per-km?', icon: TrendingUp },
];

const CLIENT_EXAMPLES = [
  { q: 'Review the BAS position — cross-check GST, PAYG, and data quality before I lodge', icon: Shield },
  { q: 'Prepare advisory talking points for my next client meeting based on their financial trends', icon: Zap },
  { q: 'Flag any unusual journal entries, expense spikes, or reconciliation gaps I should investigate', icon: TrendingUp },
  { q: 'What proactive tax planning opportunities should I raise with this client before EOFY?', icon: DollarSign },
];

// =============================================================================
// Client Context Help Categories
// =============================================================================

const CLIENT_CONTEXT_HELP = {
  intro: 'The AI has access to this client\'s financial data from Xero.',
  categories: [
    { id: 'tax', icon: FileText, title: 'Tax & Deductions', color: 'text-primary bg-primary/10', questions: ['What are the biggest expense categories?', 'Which expenses might be disallowed?', 'What home office deductions apply?'] },
    { id: 'cashflow', icon: TrendingUp, title: 'Cash Flow', color: 'text-status-success bg-status-success/10', questions: ['How is cash flow looking?', 'Who are the top overdue debtors?', 'Show revenue vs expenses trend'] },
    { id: 'gst', icon: DollarSign, title: 'GST & BAS', color: 'text-status-warning bg-status-warning/10', questions: ['What\'s the GST liability?', 'Calculate 1A and 1B for BAS', 'Any GST adjustments needed?'] },
    { id: 'compliance', icon: Shield, title: 'Compliance', color: 'text-status-info bg-status-info/10', questions: ['Total PAYG withheld?', 'Are super contributions current?', 'Any overdue lodgements?'] },
  ],
};

// =============================================================================
// Utility Functions
// =============================================================================

function formatRelativeDate(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  if (diffDays === 0) return 'Today';
  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString('en-AU', { month: 'short', day: 'numeric' });
}

// =============================================================================
// Main Component
// =============================================================================

export default function AssistantPage() {
  const { getToken } = useAuth();
  const { user } = useUser();

  // Conversation state
  const [conversations, setConversations] = useState<ConversationListItem[]>([]);
  const [clients, setClients] = useState<ConversationClientSummary[]>([]);
  const [loadingConversations, setLoadingConversations] = useState(true);
  const [loadingConversation, setLoadingConversation] = useState(false);

  // Current conversation
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [selectedClient, setSelectedClient] = useState<ClientSearchResult | null>(null);
  const [clientProfile, setClientProfile] = useState<ClientProfileResponse | null>(null);
  const [isRefreshingProfile, setIsRefreshingProfile] = useState(false);

  // UI state
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [thinkingStatus, setThinkingStatus] = useState<string | null>(null);
  const [detectedPerspectives, setDetectedPerspectives] = useState<string[]>([]);

  // Panels & Mode
  const [showHistory, setShowHistory] = useState(false);
  const [showClientSearch, setShowClientSearch] = useState(false);
  const [showClientHelp, setShowClientHelp] = useState(false);
  const [generalModeActive, setGeneralModeActive] = useState(false);

  // Knowledge domain selector (spec 045)
  const [selectedDomain, setSelectedDomain] = useState<string | null>(null);

  // File attachment
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  // Refs
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Task creation state
  const [showTaskModal, setShowTaskModal] = useState(false);
  const [taskContent, setTaskContent] = useState('');

  const userId = user?.id || 'anonymous';

  // Task creation handler - opens the action items page with pre-filled content
  const handleCreateTask = useCallback((content: string) => {
    // Store content and open modal
    setTaskContent(content);
    setShowTaskModal(true);
  }, []);

  // ==========================================================================
  // Data Loading
  // ==========================================================================

  const loadConversations = useCallback(async () => {
    if (!user?.id) return;
    setLoadingConversations(true);
    try {
      const token = await getToken();
      if (!token) return;
      const data = await getConversationsWithClients(token, user.id);
      setConversations(data.conversations);
      setClients(data.clients);
    } catch (err) {
      console.error('Failed to load conversations:', err);
    } finally {
      setLoadingConversations(false);
    }
  }, [getToken, user?.id]);

  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  const loadClientProfile = useCallback(async (client: ClientSearchResult) => {
    try {
      const token = await getToken();
      if (!token) return;
      const profile = await getClientProfile(token, client.id);
      setClientProfile(profile);
    } catch (err) {
      console.error('Failed to load client profile:', err);
      setClientProfile(null);
    }
  }, [getToken]);

  const refreshClientProfile = useCallback(async () => {
    if (!selectedClient) return;
    setIsRefreshingProfile(true);
    await loadClientProfile(selectedClient);
    setIsRefreshingProfile(false);
  }, [selectedClient, loadClientProfile]);

  // ==========================================================================
  // Scroll & Input
  // ==========================================================================

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  useEffect(() => {
    if (isStreaming) {
      const interval = setInterval(scrollToBottom, 500);
      return () => clearInterval(interval);
    }
    return undefined;
  }, [isStreaming, scrollToBottom]);

  useEffect(() => {
    const textarea = inputRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      textarea.style.height = `${Math.min(textarea.scrollHeight, 120)}px`;
    }
  }, [input]);

  // ==========================================================================
  // Conversation Handling
  // ==========================================================================

  const loadConversation = async (convId: string) => {
    setLoadingConversation(true);
    setError(null);
    setShowHistory(false);
    try {
      const token = await getToken();
      if (!token) throw new Error('Not authenticated');

      const conv = await getConversation(token, userId, convId);
      setConversationId(convId);
      setMessages(conv.messages.map((m) => ({
        id: m.id,
        role: m.role,
        content: m.content,
        citations: m.citations || undefined,
      })));

      const convData = conversations.find((c) => c.id === convId);
      if (convData?.client_id && convData?.client_name) {
        setSelectedClient({
          id: convData.client_id,
          name: convData.client_name,
          abn: null,
          connection_id: convData.client_id,
          organization_name: null,
          is_active: true,
        });
        const profile = await getClientProfile(token, convData.client_id);
        setClientProfile(profile);
      } else {
        setSelectedClient(null);
        setClientProfile(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load conversation');
    } finally {
      setLoadingConversation(false);
    }
  };

  const handleDeleteConversation = async (convId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm('Delete this conversation?')) return;
    try {
      const token = await getToken();
      if (!token) throw new Error('Not authenticated');
      await deleteConversation(token, userId, convId);
      setConversations((prev) => prev.filter((c) => c.id !== convId));
      if (conversationId === convId) startNewConversation();
    } catch (err) {
      console.error('Failed to delete conversation:', err);
    }
  };

  const startNewConversation = (client?: ClientSearchResult) => {
    setConversationId(null);
    setMessages([]);
    setError(null);
    setShowHistory(false);
    setShowClientSearch(false);
    setGeneralModeActive(false);
    setSelectedDomain(null);
    if (client) {
      setSelectedClient(client);
      loadClientProfile(client);
    } else {
      setSelectedClient(null);
      setClientProfile(null);
    }
  };

  const startGeneralChat = () => {
    startNewConversation();
    setGeneralModeActive(true);
  };

  const startClientChat = () => {
    setShowClientSearch(true);
  };

  // ==========================================================================
  // Chat Handling
  // ==========================================================================

  const handleSubmit = async (query?: string) => {
    const messageText = query || input.trim();
    if ((!messageText && !selectedFile) || isStreaming) return;

    const fileToSend = selectedFile;
    setError(null);
    setInput('');
    setSelectedFile(null);
    setIsStreaming(true);
    setThinkingStatus('Starting analysis...');
    setDetectedPerspectives([]);

    const userMessage: DisplayMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: messageText,
    };

    const assistantId = `assistant-${Date.now()}`;
    const assistantMessage: DisplayMessage = {
      id: assistantId,
      role: 'assistant',
      content: '',
      isStreaming: true,
    };

    setMessages((prev) => [...prev, userMessage, assistantMessage]);

    try {
      const token = await getToken();
      if (!token) throw new Error('Not authenticated');

      let finalContent = '';
      let finalMetadata: Partial<AgentStreamEvent> = {};
      let a2uiMessage: A2UIMessage | undefined;

      for await (const event of agentChatStream(token, {
        query: messageText,
        connection_id: selectedClient?.connection_id || null,
        conversation_id: conversationId || null,
        domain: selectedDomain,
      }, fileToSend)) {
        switch (event.type) {
          case 'thinking':
            setThinkingStatus(event.message || 'Processing...');
            break;
          case 'perspectives':
            setDetectedPerspectives(event.perspectives || []);
            setThinkingStatus(event.message || 'Analyzing...');
            break;
          case 'response':
            finalContent = event.content || '';
            // Capture A2UI message from response event
            if (event.a2ui_message) {
              a2uiMessage = event.a2ui_message as A2UIMessage;
            }
            setThinkingStatus(null);
            break;
          case 'metadata':
            finalMetadata = event;
            // Also check metadata for A2UI message (fallback)
            if (event.a2ui_message && !a2uiMessage) {
              a2uiMessage = event.a2ui_message as A2UIMessage;
            }
            if (event.conversation_id) {
              setConversationId(event.conversation_id);
            }
            break;
          case 'done':
            if (event.conversation_id) {
              setConversationId(event.conversation_id);
            }
            break;
          case 'error':
            throw new Error(event.message || 'Stream error');
        }
      }

      const citations: Citation[] = (finalMetadata.citations || []).map((c, i) => ({
        number: i + 1,
        title: c.title || c.source,
        url: c.url || '',
        source_type: c.source,
        effective_date: c.effective_date || null,
        text_preview: c.text_preview || c.section || '',
        score: c.score,
      }));

      // Build enhanced citations when verification data is present (spec 045)
      const hasEnhancedCitations = (finalMetadata.citations || []).some(
        (c) => c.verified !== undefined
      );

      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? {
                ...m,
                content: finalContent,
                citations,
                isStreaming: false,
                perspectivesUsed: finalMetadata.perspectives_used as Perspective[] | undefined,
                confidence: finalMetadata.confidence,
                escalationRequired: finalMetadata.escalation_required,
                escalationReason: finalMetadata.escalation_reason,
                processingTimeMs: finalMetadata.processing_time_ms,
                dataFreshness: (finalMetadata as Record<string, unknown>).data_freshness as string | null | undefined,
                a2uiMessage,
                // Knowledge-specific fields (spec 045)
                knowledgeConfidence: finalMetadata.knowledge_confidence,
                knowledgeConfidenceScore: finalMetadata.knowledge_confidence_score,
                supersededWarnings: finalMetadata.superseded_warnings,
                attribution: finalMetadata.attribution,
                domainDetected: finalMetadata.domain_detected,
                queryType: finalMetadata.query_type,
                // Upgrade citations with enhanced fields when available
                ...(hasEnhancedCitations && {
                  citations: (finalMetadata.citations || []).map((c, i) => ({
                    number: i + 1,
                    title: c.title || c.source,
                    url: c.url || '',
                    source_type: c.source,
                    effective_date: c.effective_date || null,
                    text_preview: c.text_preview || c.section || '',
                    score: c.score,
                    verified: c.verified,
                    section_ref: c.section_ref,
                  })),
                }),
              }
            : m
        )
      );

      loadConversations();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to get response');
      setMessages((prev) => prev.filter((m) => m.id !== assistantId));
    } finally {
      setIsStreaming(false);
      setThinkingStatus(null);
      setDetectedPerspectives([]);
      inputRef.current?.focus();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  // Determine if we're in initial mode selection (no messages, no client selected)
  const showModeSelection = messages.length === 0 && !selectedClient && !showClientSearch && !generalModeActive;

  // ==========================================================================
  // Render
  // ==========================================================================

  return (
    <div className="h-[calc(100vh-4rem)] flex flex-col bg-background -m-6 overflow-hidden">
      {/* Compact Header Bar */}
      <header className="flex-shrink-0 h-12 border-b border-border bg-card flex items-center justify-between px-4">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-blue-600 to-blue-700 flex items-center justify-center shadow-sm">
              <Sparkles className="h-4 w-4 text-white" />
            </div>
            <h1 className="text-sm font-semibold text-foreground">AI Assistant</h1>
          </div>

          {/* Mode Indicator */}
          {(selectedClient || messages.length > 0) && (
            <div className="flex items-center gap-2 pl-3 border-l border-border">
              {selectedClient ? (
                <span className="flex items-center gap-1.5 px-2 py-0.5 bg-primary/10 text-primary rounded text-xs font-medium">
                  <Building2 className="h-3 w-3" />
                  {selectedClient.name}
                </span>
              ) : (
                <span className="flex items-center gap-1.5 px-2 py-0.5 bg-muted text-muted-foreground rounded text-xs font-medium">
                  <BookOpen className="h-3 w-3" />
                  General
                </span>
              )}
            </div>
          )}
        </div>

        <div className="flex items-center gap-1">
          {/* History Toggle */}
          <button
            onClick={() => setShowHistory(!showHistory)}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 text-xs rounded-lg transition-colors ${
              showHistory ? 'bg-primary/10 text-primary' : 'text-muted-foreground hover:bg-muted'
            }`}
          >
            <History className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">History</span>
            {conversations.length > 0 && (
              <span className="px-1 py-0.5 text-[10px] bg-muted text-muted-foreground rounded">
                {conversations.length}
              </span>
            )}
          </button>

          {/* New Chat - only show when in a conversation */}
          {(messages.length > 0 || selectedClient) && (
            <button
              onClick={() => startNewConversation()}
              className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium text-primary-foreground bg-primary hover:bg-primary/90 rounded-lg transition-colors"
            >
              <Zap className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">New</span>
            </button>
          )}
        </div>
      </header>

      {/* Main Content Area */}
      <div className="flex-1 flex overflow-hidden">
        {/* History Sidebar (conditional) */}
        {showHistory && (
          <aside className="w-72 border-r border-border bg-card flex flex-col flex-shrink-0">
            <div className="flex items-center justify-between px-4 py-3 border-b border-border">
              <h2 className="text-sm font-semibold text-foreground">Conversations</h2>
              <button onClick={() => setShowHistory(false)} className="p-1 hover:bg-muted rounded">
                <ChevronLeft className="h-4 w-4 text-muted-foreground" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto">
              {loadingConversations ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                </div>
              ) : conversations.length === 0 ? (
                <div className="px-4 py-12 text-center">
                  <MessageSquare className="h-8 w-8 text-muted-foreground/30 mx-auto mb-2" />
                  <p className="text-sm text-muted-foreground">No conversations yet</p>
                </div>
              ) : (
                <div className="py-1">
                  {conversations.map((conv) => (
                    <button
                      key={conv.id}
                      onClick={() => loadConversation(conv.id)}
                      className={`w-full group flex items-start gap-2.5 px-3 py-2.5 text-left transition-all hover:bg-muted ${
                        conversationId === conv.id ? 'bg-primary/10 border-l-2 border-primary' : 'border-l-2 border-transparent'
                      }`}
                    >
                      {conv.client_id ? (
                        <div className="w-6 h-6 rounded bg-primary/10 flex items-center justify-center flex-shrink-0">
                          <Building2 className="h-3 w-3 text-primary" />
                        </div>
                      ) : (
                        <div className="w-6 h-6 rounded bg-muted flex items-center justify-center flex-shrink-0">
                          <BookOpen className="h-3 w-3 text-muted-foreground" />
                        </div>
                      )}
                      <div className="flex-1 min-w-0">
                        {conv.client_name && (
                          <span className="text-[10px] font-medium text-primary uppercase tracking-wide">{conv.client_name}</span>
                        )}
                        <p className="text-xs font-medium text-foreground truncate leading-tight">{conv.title}</p>
                        <p className="text-[10px] text-muted-foreground">{formatRelativeDate(conv.updated_at)}</p>
                      </div>
                      <button
                        onClick={(e) => handleDeleteConversation(conv.id, e)}
                        className="opacity-0 group-hover:opacity-100 p-1 hover:bg-muted rounded"
                      >
                        <Trash2 className="h-3 w-3 text-muted-foreground hover:text-status-danger" />
                      </button>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </aside>
        )}

        {/* Main Chat Area */}
        <main className="flex-1 flex flex-col overflow-hidden">
          {/* Client Context Bar */}
          {selectedClient && (
            <div className="flex-shrink-0 border-b border-border bg-muted/50">
              <div className="px-6 py-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center">
                      <Building2 className="h-4 w-4 text-primary" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-foreground text-sm">{selectedClient.name}</span>
                        {clientProfile?.profile.gst_registered && (
                          <span className="px-1.5 py-0.5 text-[10px] font-medium bg-primary/10 text-primary rounded">GST</span>
                        )}
                      </div>
                      <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        {selectedClient.abn && <span>ABN: {selectedClient.abn}</span>}
                        {clientProfile?.data_freshness && (
                          <span className="flex items-center gap-1">
                            <Clock className="h-3 w-3" />
                            {formatRelativeDate(clientProfile.data_freshness)}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => setShowClientHelp(!showClientHelp)}
                      className={`p-1.5 rounded-lg transition-colors text-xs ${showClientHelp ? 'bg-primary/10 text-primary' : 'hover:bg-muted text-muted-foreground'}`}
                    >
                      Quick questions
                    </button>
                    <button
                      onClick={refreshClientProfile}
                      disabled={isRefreshingProfile}
                      className="p-1.5 hover:bg-muted rounded-lg text-muted-foreground disabled:opacity-50"
                    >
                      <RefreshCw className={`h-4 w-4 ${isRefreshingProfile ? 'animate-spin' : ''}`} />
                    </button>
                    <button
                      onClick={() => startNewConversation()}
                      className="px-2 py-1 text-xs text-muted-foreground hover:text-foreground hover:bg-muted rounded"
                    >
                      Switch
                    </button>
                  </div>
                </div>

                {/* Quick Questions Dropdown */}
                {showClientHelp && (
                  <div className="mt-3 p-3 bg-card rounded-lg border border-border shadow-sm">
                    <p className="text-xs text-muted-foreground mb-3">{CLIENT_CONTEXT_HELP.intro}</p>
                    <div className="grid grid-cols-2 gap-2">
                      {CLIENT_CONTEXT_HELP.categories.map((cat) => {
                        const Icon = cat.icon;
                        return (
                          <div key={cat.id} className="space-y-1">
                            <div className={`flex items-center gap-1.5 ${cat.color} px-2 py-1 rounded text-xs font-medium`}>
                              <Icon className="h-3 w-3" />
                              {cat.title}
                            </div>
                            {cat.questions.slice(0, 2).map((q, i) => (
                              <button
                                key={i}
                                onClick={() => { handleSubmit(q); setShowClientHelp(false); }}
                                className="block w-full text-left text-xs text-muted-foreground hover:text-primary pl-2 truncate"
                              >
                                {q}
                              </button>
                            ))}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Chat Content */}
          <div className="flex-1 overflow-y-auto">
            {loadingConversation ? (
              <div className="flex items-center justify-center h-full">
                <Loader2 className="h-6 w-6 animate-spin text-primary" />
              </div>
            ) : showModeSelection ? (
              /* ============================================================
                 MODE SELECTION - The Hero Moment
                 Bold split-screen choice between General and Client
                 ============================================================ */
              <div className="h-full flex flex-col">
                {/* Hero Section */}
                <div className="flex-1 flex items-center justify-center p-6">
                  <div className="w-full max-w-4xl">
                    {/* Title */}
                    <div className="text-center mb-10">
                      <div className="inline-flex items-center gap-2 px-3 py-1.5 bg-primary/10 text-primary rounded-full text-xs font-medium mb-4">
                        <Sparkles className="h-3.5 w-3.5" />
                        AI-Powered Knowledge Base
                      </div>
                      <h2 className="text-3xl font-bold text-foreground tracking-tight mb-2">
                        What would you like to ask?
                      </h2>
                      <p className="text-muted-foreground text-base">
                        Choose your query mode to get started
                      </p>
                    </div>

                    {/* Two Cards Side by Side */}
                    <div className="grid md:grid-cols-2 gap-6">
                      {/* General Query Card */}
                      <button
                        onClick={startGeneralChat}
                        className="group relative bg-card rounded-2xl border-2 border-border hover:border-primary p-8 text-left transition-all duration-200 hover:shadow-lg hover:shadow-primary/10"
                      >
                        {/* Icon */}
                        <div className="w-14 h-14 rounded-2xl bg-muted group-hover:bg-primary/10 flex items-center justify-center mb-5 transition-colors">
                          <BookOpen className="h-7 w-7 text-muted-foreground group-hover:text-primary transition-colors" />
                        </div>

                        {/* Content */}
                        <h3 className="text-xl font-bold text-foreground mb-2">General Question</h3>
                        <p className="text-muted-foreground text-sm mb-6 leading-relaxed">
                          Ask about Australian tax law, GST rules, BAS requirements, PAYG, and compliance guidelines.
                        </p>

                        {/* Example Questions */}
                        <div className="space-y-2">
                          <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">Example questions</p>
                          {GENERAL_EXAMPLES.slice(0, 3).map((ex, i) => (
                            <div key={i} className="flex items-center gap-2 text-xs text-muted-foreground">
                              <ChevronRight className="h-3 w-3 text-muted-foreground" />
                              <span className="truncate">{ex.q}</span>
                            </div>
                          ))}
                        </div>

                        {/* Arrow indicator */}
                        <div className="absolute bottom-6 right-6 w-10 h-10 rounded-full bg-muted group-hover:bg-primary flex items-center justify-center transition-colors">
                          <ArrowRight className="h-5 w-5 text-muted-foreground group-hover:text-white transition-colors" />
                        </div>
                      </button>

                      {/* Client-Specific Card */}
                      <button
                        onClick={startClientChat}
                        className="group relative bg-card rounded-2xl border-2 border-border hover:border-primary p-8 text-left transition-all duration-200 hover:shadow-lg hover:shadow-primary/10"
                      >
                        {/* Icon */}
                        <div className="w-14 h-14 rounded-2xl bg-muted group-hover:bg-primary/10 flex items-center justify-center mb-5 transition-colors">
                          <Building2 className="h-7 w-7 text-muted-foreground group-hover:text-primary transition-colors" />
                        </div>

                        {/* Content */}
                        <h3 className="text-xl font-bold text-foreground mb-2">Client-Specific</h3>
                        <p className="text-muted-foreground text-sm mb-6 leading-relaxed">
                          Ask questions about a specific client&apos;s finances, with access to their Xero data.
                        </p>

                        {/* Example Questions */}
                        <div className="space-y-2">
                          <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">Example questions</p>
                          {CLIENT_EXAMPLES.slice(0, 3).map((ex, i) => (
                            <div key={i} className="flex items-center gap-2 text-xs text-muted-foreground">
                              <ChevronRight className="h-3 w-3 text-muted-foreground" />
                              <span className="truncate">{ex.q}</span>
                            </div>
                          ))}
                        </div>

                        {/* Arrow indicator */}
                        <div className="absolute bottom-6 right-6 w-10 h-10 rounded-full bg-muted group-hover:bg-primary flex items-center justify-center transition-colors">
                          <ArrowRight className="h-5 w-5 text-muted-foreground group-hover:text-white transition-colors" />
                        </div>

                        {/* Badge */}
                        <div className="absolute top-6 right-6 px-2 py-1 bg-primary/10 text-primary text-[10px] font-semibold rounded uppercase tracking-wider">
                          Xero Data
                        </div>
                      </button>
                    </div>

                    {/* Recent Clients Quick Access */}
                    {clients.length > 0 && (
                      <div className="mt-8 text-center">
                        <p className="text-xs text-muted-foreground mb-3">Or quick start with a recent client:</p>
                        <div className="flex flex-wrap justify-center gap-2">
                          {clients.slice(0, 5).map((client) => (
                            <button
                              key={client.client_id}
                              onClick={async () => {
                                const token = await getToken();
                                if (!token) return;
                                const results = await searchClients(token, client.client_name, 1);
                                if (results.results[0]) startNewConversation(results.results[0]);
                              }}
                              className="flex items-center gap-1.5 px-3 py-1.5 bg-card border border-border hover:border-primary hover:bg-primary/10 text-foreground hover:text-primary rounded-lg text-xs font-medium transition-colors"
                            >
                              <Building2 className="h-3 w-3" />
                              {client.client_name}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ) : showClientSearch ? (
              /* ============================================================
                 CLIENT SEARCH INTERFACE
                 ============================================================ */
              <div className="h-full flex items-center justify-center p-6">
                <div className="w-full max-w-md">
                  <button
                    onClick={() => setShowClientSearch(false)}
                    className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-6"
                  >
                    <ChevronLeft className="h-4 w-4" />
                    Back to selection
                  </button>

                  <div className="bg-card rounded-2xl border border-border p-6 shadow-sm">
                    <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center mb-4">
                      <Building2 className="h-6 w-6 text-primary" />
                    </div>
                    <h3 className="text-lg font-bold text-foreground mb-1">Select a Client</h3>
                    <p className="text-sm text-muted-foreground mb-6">Search for the client you want to ask about</p>

                    <ClientSearchInput
                      getToken={getToken}
                      onSelectClient={(client) => startNewConversation(client)}
                    />
                  </div>
                </div>
              </div>
            ) : messages.length === 0 && generalModeActive && !selectedClient ? (
              /* ============================================================
                 GENERAL MODE - EMPTY STATE WITH SUGGESTIONS
                 ============================================================ */
              <div className="h-full flex items-center justify-center p-6">
                <div className="text-center max-w-lg">
                  <div className="w-16 h-16 rounded-2xl bg-muted flex items-center justify-center mx-auto mb-6">
                    <BookOpen className="h-8 w-8 text-muted-foreground" />
                  </div>
                  <h2 className="text-2xl font-bold text-foreground mb-2">
                    General Tax &amp; Compliance
                  </h2>
                  <p className="text-muted-foreground mb-8">
                    Ask about Australian tax law, GST rules, BAS requirements, PAYG, and compliance guidelines.
                  </p>

                  <div className="flex flex-wrap justify-center gap-2">
                    {GENERAL_EXAMPLES.map((ex, idx) => {
                      const Icon = ex.icon;
                      return (
                        <button
                          key={idx}
                          onClick={() => handleSubmit(ex.q)}
                          disabled={isStreaming}
                          className="flex items-center gap-2 px-4 py-2.5 text-sm text-muted-foreground bg-card border border-border rounded-xl hover:border-primary hover:text-primary hover:bg-primary/10 transition-all disabled:opacity-50"
                        >
                          <Icon className="h-4 w-4" />
                          {ex.q}
                        </button>
                      );
                    })}
                  </div>
                </div>
              </div>
            ) : messages.length === 0 && selectedClient ? (
              /* ============================================================
                 CLIENT SELECTED - EMPTY STATE WITH SUGGESTIONS
                 ============================================================ */
              <div className="h-full flex items-center justify-center p-6">
                <div className="text-center max-w-lg">
                  <div className="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center mx-auto mb-6">
                    <Building2 className="h-8 w-8 text-primary" />
                  </div>
                  <h2 className="text-2xl font-bold text-foreground mb-2">
                    Ask about {selectedClient.name}
                  </h2>
                  <p className="text-muted-foreground mb-8">
                    I have access to this client&apos;s financial data and can help with tax analysis, compliance checks, and financial insights.
                  </p>

                  <div className="flex flex-wrap justify-center gap-2">
                    {CLIENT_EXAMPLES.map((ex, idx) => {
                      const Icon = ex.icon;
                      return (
                        <button
                          key={idx}
                          onClick={() => handleSubmit(ex.q)}
                          disabled={isStreaming}
                          className="flex items-center gap-2 px-4 py-2.5 text-sm text-muted-foreground bg-card border border-border rounded-xl hover:border-primary hover:text-primary hover:bg-primary/10 transition-all disabled:opacity-50"
                        >
                          <Icon className="h-4 w-4" />
                          {ex.q}
                        </button>
                      );
                    })}
                  </div>
                </div>
              </div>
            ) : (
              /* ============================================================
                 MESSAGES VIEW
                 ============================================================ */
              <div className="max-w-4xl mx-auto px-6 py-6">
                <div className="space-y-6 pb-32">
                  {messages.map((msg) => (
                    msg.isStreaming && !msg.content ? null : (
                      <MessageBubble
                        key={msg.id}
                        message={msg}
                        clientEmail={undefined}
                        clientName={selectedClient?.name}
                        onCreateTask={handleCreateTask}
                      />
                    )
                  ))}

                  {/* Thinking Indicator with Animation */}
                  {thinkingStatus && (
                    <ThinkingIndicator
                      status={thinkingStatus}
                      perspectives={detectedPerspectives}
                    />
                  )}

                  {/* Error */}
                  {error && (
                    <div className="px-4 py-3 bg-status-danger/10 border border-status-danger/30 rounded-xl text-sm text-status-danger flex items-center gap-2">
                      <AlertCircle className="h-4 w-4" />
                      {error}
                    </div>
                  )}

                  <div ref={messagesEndRef} />
                </div>
              </div>
            )}
          </div>

          {/* Floating Input - Only show when not in mode selection */}
          {!showModeSelection && !showClientSearch && (
            <div className="flex-shrink-0 border-t border-border bg-card px-4 py-3">
              <div className="max-w-4xl mx-auto">
                {/* Domain Selector - shown in general mode (no client selected) */}
                {!selectedClient && (
                  <DomainSelectorWrapper
                    selectedDomain={selectedDomain}
                    onSelect={setSelectedDomain}
                    getToken={getToken}
                  />
                )}
                {selectedFile && (
                  <div className="mb-2">
                    <div className="inline-flex items-center gap-2 rounded-lg bg-muted/50 px-3 py-1.5 text-xs">
                      <FileText className="h-3.5 w-3.5 text-muted-foreground" />
                      <span className="max-w-[200px] truncate">{selectedFile.name}</span>
                      <span className="text-muted-foreground">
                        {selectedFile.size < 1024 * 1024
                          ? `${(selectedFile.size / 1024).toFixed(0)}KB`
                          : `${(selectedFile.size / (1024 * 1024)).toFixed(1)}MB`}
                      </span>
                      <button onClick={() => setSelectedFile(null)} className="ml-1 rounded-sm hover:bg-muted">
                        <X className="h-3 w-3" />
                      </button>
                    </div>
                  </div>
                )}
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".png,.jpg,.jpeg,.webp,.gif,.pdf,.csv,.xlsx,.txt"
                  className="hidden"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) {
                      if (f.size > 10 * 1024 * 1024) { alert('File too large. Maximum is 10MB.'); return; }
                      setSelectedFile(f);
                    }
                    e.target.value = '';
                  }}
                />
                <div className="flex items-end gap-3">
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    disabled={isStreaming}
                    className="flex-shrink-0 w-12 h-12 border border-border rounded-xl hover:bg-muted disabled:opacity-40 disabled:cursor-not-allowed transition-colors flex items-center justify-center"
                    title="Attach file (image, PDF, Excel, CSV)"
                  >
                    <Paperclip className="h-5 w-5 text-muted-foreground" />
                  </button>
                  <div className="flex-1 relative">
                    <textarea
                      ref={inputRef}
                      value={input}
                      onChange={(e) => setInput(e.target.value)}
                      onKeyDown={handleKeyDown}
                      placeholder={selectedClient ? `Ask about ${selectedClient.name}...` : 'Ask about tax, GST, BAS, compliance...'}
                      rows={1}
                      className="w-full px-4 py-3 bg-background border border-border rounded-xl resize-none focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary text-foreground placeholder:text-muted-foreground text-sm"
                      style={{ minHeight: '48px', maxHeight: '120px' }}
                      disabled={isStreaming}
                    />
                  </div>
                  <button
                    onClick={() => handleSubmit()}
                    disabled={(!input.trim() && !selectedFile) || isStreaming}
                    className="flex-shrink-0 w-12 h-12 bg-primary text-primary-foreground rounded-xl hover:bg-primary/90 disabled:opacity-40 disabled:cursor-not-allowed transition-colors flex items-center justify-center shadow-sm"
                  >
                    {isStreaming ? (
                      <Loader2 className="h-5 w-5 animate-spin" />
                    ) : (
                      <Send className="h-5 w-5" />
                    )}
                  </button>
                </div>
                <p className="mt-2 text-center text-[10px] text-muted-foreground">
                  Enter to send · Shift+Enter for new line
                </p>
              </div>
            </div>
          )}
        </main>
      </div>

      {/* Task Creation Modal */}
      {showTaskModal && (
        <TaskCreationModal
          content={taskContent}
          clientName={selectedClient?.name || null}
          onClose={() => setShowTaskModal(false)}
          getToken={getToken}
        />
      )}
    </div>
  );
}

// =============================================================================
// Client Search Input Component
// =============================================================================

function ClientSearchInput({
  getToken,
  onSelectClient,
}: {
  getToken: () => Promise<string | null>;
  onSelectClient: (client: ClientSearchResult) => void;
}) {
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<ClientSearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);

  const handleSearch = useCallback(async (query: string) => {
    setSearchQuery(query);
    if (query.length < 1) {
      setSearchResults([]);
      return;
    }
    setIsSearching(true);
    try {
      const token = await getToken();
      if (!token) return;
      const data = await searchClients(token, query, 8);
      setSearchResults(data.results);
    } catch {
      setSearchResults([]);
    } finally {
      setIsSearching(false);
    }
  }, [getToken]);

  return (
    <div className="space-y-4">
      <div className="relative">
        <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => handleSearch(e.target.value)}
          placeholder="Search clients by name..."
          className="w-full pl-11 pr-4 py-3 bg-background border border-border rounded-xl focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary text-sm text-foreground placeholder:text-muted-foreground"
          autoFocus
        />
        {isSearching && <Loader2 className="absolute right-4 top-1/2 -translate-y-1/2 w-4 h-4 animate-spin text-muted-foreground" />}
      </div>

      <div className="max-h-64 overflow-y-auto">
        {searchResults.length === 0 ? (
          <p className="text-center text-muted-foreground text-sm py-8">
            {searchQuery ? 'No clients found' : 'Start typing to search'}
          </p>
        ) : (
          <div className="space-y-1">
            {searchResults.map((client) => (
              <button
                key={client.id}
                onClick={() => onSelectClient(client)}
                className="w-full flex items-center gap-3 p-3 hover:bg-muted rounded-xl text-left transition-colors"
              >
                <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center flex-shrink-0">
                  <Building2 className="w-5 h-5 text-primary" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-foreground truncate text-sm">{client.name}</p>
                  {client.abn && <p className="text-xs text-muted-foreground">ABN: {client.abn}</p>}
                </div>
                <ChevronRight className="h-4 w-4 text-muted-foreground" />
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// =============================================================================
// Message Bubble
// =============================================================================

interface MessageBubbleProps {
  message: DisplayMessage;
  clientEmail?: string | null;
  clientName?: string | null;
  onCreateTask?: (content: string) => void;
}

function MessageBubble({ message, clientEmail, clientName, onCreateTask }: MessageBubbleProps) {
  const isUser = message.role === 'user';
  const perspectiveSections = !isUser ? parsePerspectiveSections(message.content) : [];
  const hasPerspectiveSections = perspectiveSections.length > 0;
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(async () => {
    try {
      const enriched = enrichAIContentForExport(message.content, {
        dataFreshness: message.dataFreshness,
        confidence: message.confidence,
        isEscalated: message.escalationRequired,
        escalationReason: message.escalationReason,
      });
      await navigator.clipboard.writeText(enriched);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  }, [message.content, message.dataFreshness, message.confidence, message.escalationRequired, message.escalationReason]);

  const handleEmail = useCallback(() => {
    const subject = clientName
      ? `Clairo Analysis: ${clientName}`
      : 'Clairo Analysis';
    const enriched = enrichAIContentForExport(message.content, {
      dataFreshness: message.dataFreshness,
      confidence: message.confidence,
      isEscalated: message.escalationRequired,
      escalationReason: message.escalationReason,
    });
    const body = encodeURIComponent(
      `Hi,\n\nPlease find the analysis from Clairo below:\n\n${enriched}`
    );
    const mailto = clientEmail
      ? `mailto:${clientEmail}?subject=${encodeURIComponent(subject)}&body=${body}`
      : `mailto:?subject=${encodeURIComponent(subject)}&body=${body}`;
    window.open(mailto, '_blank');
  }, [message.content, message.dataFreshness, message.confidence, message.escalationRequired, message.escalationReason, clientEmail, clientName]);

  const handleCreateTask = useCallback(() => {
    if (onCreateTask) {
      onCreateTask(message.content);
    }
  }, [message.content, onCreateTask]);

  return (
    <div className={`${isUser ? 'flex justify-end' : ''}`}>
      <div className={`${isUser ? 'max-w-[80%]' : 'max-w-none'}`}>
        {/* Supersession Banner (spec 045) */}
        {!isUser && message.supersededWarnings && message.supersededWarnings.length > 0 && !message.isStreaming && (
          <div className="mb-3">
            <SupersessionBanner warnings={message.supersededWarnings} />
          </div>
        )}

        {/* Escalation Banner */}
        {!isUser && message.escalationRequired && !message.isStreaming && (
          <div className="mb-3">
            <EscalationBanner reason={message.escalationReason || null} />
          </div>
        )}

        {/* Perspective Badges */}
        {!isUser && message.perspectivesUsed && message.perspectivesUsed.length > 0 && !message.isStreaming && (
          <div className="mb-2">
            <PerspectiveBadgeList perspectives={message.perspectivesUsed} size="sm" />
          </div>
        )}

        {isUser ? (
          <div className="bg-primary text-primary-foreground px-5 py-3 rounded-2xl rounded-br-md shadow-sm">
            <p className="text-[15px] leading-relaxed">{message.content}</p>
          </div>
        ) : (
          <div className="space-y-4 group relative">
            {hasPerspectiveSections ? (
              <div className="space-y-4">
                {perspectiveSections.map((section, idx) => {
                  const config = PERSPECTIVE_CONFIG[section.perspective];
                  return (
                    <div key={idx}>
                      <div className={`inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-medium ${config.bgColor} ${config.color} mb-2`}>
                        {config.label}
                      </div>
                      <div className="prose prose-sm max-w-none [&_p]:text-foreground [&_p]:leading-relaxed [&_p]:mb-3 [&_strong]:text-foreground [&_ul]:my-2 [&_ol]:my-2 [&_li]:mb-1">
                        <MarkdownContent content={section.content} />
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="prose prose-sm max-w-none [&_p]:text-foreground [&_p]:leading-relaxed [&_p]:mb-3 [&_strong]:text-foreground [&_ul]:my-2 [&_ol]:my-2 [&_li]:mb-1 [&_h1]:text-lg [&_h1]:font-semibold [&_h1]:mt-4 [&_h2]:text-base [&_h2]:font-semibold [&_h2]:mt-3 [&_h3]:text-sm [&_h3]:font-medium [&_h3]:mt-2">
                <MarkdownContent content={message.content} />
              </div>
            )}

            {/* Response Actions - Always visible with subtle styling */}
            {!message.isStreaming && (
              <div className="flex items-center gap-1 pt-3 mt-3 border-t border-border">
                <button
                  onClick={handleCopy}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-muted-foreground hover:text-primary hover:bg-primary/10 rounded-lg transition-all"
                  title="Copy to clipboard"
                >
                  {copied ? (
                    <>
                      <Check className="h-3.5 w-3.5 text-status-success" />
                      <span className="text-status-success">Copied!</span>
                    </>
                  ) : (
                    <>
                      <Copy className="h-3.5 w-3.5" />
                      <span>Copy</span>
                    </>
                  )}
                </button>
                <button
                  onClick={handleEmail}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-muted-foreground hover:text-primary hover:bg-primary/10 rounded-lg transition-all"
                  title={clientEmail ? `Email to ${clientEmail}` : 'Send via email'}
                >
                  <Mail className="h-3.5 w-3.5" />
                  <span>Email</span>
                </button>
                {onCreateTask && (
                  <button
                    onClick={handleCreateTask}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-muted-foreground hover:text-primary hover:bg-primary/10 rounded-lg transition-all"
                    title="Add as task"
                  >
                    <ListTodo className="h-3.5 w-3.5" />
                    <span>Add Task</span>
                  </button>
                )}
              </div>
            )}

            {/* A2UI Rich Components */}
            {message.a2uiMessage && !message.isStreaming && (
              <div className="mt-4 p-4 bg-background rounded-xl border border-border">
                <A2UIRenderer
                  message={message.a2uiMessage}
                  className="gap-3"
                  actionHandlers={{
                    navigate: (target) => {
                      window.location.href = target;
                    },
                  }}
                />
              </div>
            )}

            {/* Citations - use EnhancedCitationPanel when verified data is present, otherwise fall back to standard CitationsPanel */}
            {message.citations && message.citations.length > 0 && !message.isStreaming && (
              (() => {
                const hasVerifiedField = message.citations.some(
                  (c) => (c as unknown as Record<string, unknown>).verified !== undefined
                );
                if (hasVerifiedField) {
                  // Map to EnhancedCitation format
                  const enhancedCitations: EnhancedCitation[] = message.citations.map((c) => {
                    const raw = c as unknown as Record<string, unknown>;
                    return {
                      number: c.number,
                      title: c.title,
                      url: c.url,
                      source_type: c.source_type,
                      section_ref: (raw.section_ref as string | null) ?? null,
                      effective_date: c.effective_date,
                      text_preview: c.text_preview,
                      score: c.score,
                      verified: (raw.verified as boolean) ?? false,
                    };
                  });
                  return <EnhancedCitationPanel citations={enhancedCitations} />;
                }
                return <CitationsPanel citations={message.citations} />;
              })()
            )}

            {/* Attribution text (spec 045) */}
            {message.attribution && !message.isStreaming && (
              <p className="text-[10px] text-muted-foreground italic mt-2 leading-relaxed">
                {message.attribution}
              </p>
            )}

            {/* Data Freshness */}
            {message.dataFreshness && !message.isStreaming && (
              <DataFreshnessIndicator lastSyncDate={message.dataFreshness} />
            )}

            {/* Meta Info - show knowledge confidence badge (spec 045) or existing confidence indicator */}
            {!message.isStreaming && (message.knowledgeConfidence || message.confidence !== undefined) && (
              <div className="flex items-center gap-4 text-xs text-muted-foreground">
                {message.knowledgeConfidence ? (
                  <ConfidenceBadge
                    confidence={message.knowledgeConfidence}
                    score={message.knowledgeConfidenceScore}
                  />
                ) : message.confidence !== undefined ? (
                  <ConfidenceIndicator confidence={message.confidence} showLabel size="sm" />
                ) : null}
                {message.processingTimeMs && (
                  <span>{(message.processingTimeMs / 1000).toFixed(1)}s</span>
                )}
                {message.domainDetected && (
                  <span className="text-primary">
                    {message.domainDetected}
                  </span>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// =============================================================================
// Task Creation Modal (Simplified)
// =============================================================================

interface TaskCreationModalProps {
  content: string;
  clientName: string | null;
  onClose: () => void;
  getToken: () => Promise<string | null>;
}

function TaskCreationModal({ content, clientName, onClose, getToken }: TaskCreationModalProps) {
  const [title, setTitle] = useState(() => {
    // Extract first meaningful sentence as title
    const firstLine = content.split('\n')[0]?.replace(/^\[.*?\]\s*/, '') || '';
    return firstLine.length > 100 ? firstLine.substring(0, 100) + '...' : firstLine;
  });
  const [priority, setPriority] = useState<'urgent' | 'high' | 'medium' | 'low'>('medium');
  const [dueDate, setDueDate] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;

    setIsSubmitting(true);
    setError(null);

    try {
      const token = await getToken();
      if (!token) {
        setError('Not authenticated');
        return;
      }

      // Import dynamically to avoid circular deps
      const { createActionItem } = await import('@/lib/api/action-items');

      await createActionItem(token, {
        title: title.trim(),
        description: content,
        notes: clientName ? `From AI Assistant - Client: ${clientName}` : 'From AI Assistant',
        priority,
        due_date: dueDate || undefined,
      });

      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create task');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />

      {/* Modal */}
      <div className="relative w-full max-w-lg rounded-xl bg-card p-6 shadow-xl mx-4 border border-border">
        <div className="mb-4 flex items-start justify-between">
          <div>
            <h2 className="text-lg font-semibold text-foreground">Create Action Item</h2>
            <p className="text-sm text-muted-foreground">Save this response as a task for follow-up</p>
          </div>
          <button onClick={onClose} className="p-1 rounded hover:bg-muted">
            <span className="sr-only">Close</span>
            <svg className="h-5 w-5 text-muted-foreground" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Title */}
          <div>
            <label className="block text-sm font-medium text-foreground mb-1">
              Title <span className="text-status-danger">*</span>
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Task title..."
              className="w-full px-3 py-2 border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary bg-card text-foreground placeholder:text-muted-foreground"
              required
            />
          </div>

          {/* Priority & Due Date */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-foreground mb-1">Priority</label>
              <select
                value={priority}
                onChange={(e) => setPriority(e.target.value as typeof priority)}
                className="w-full px-3 py-2 border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary bg-card text-foreground"
              >
                <option value="urgent">🔴 Urgent</option>
                <option value="high">🟠 High</option>
                <option value="medium">🟡 Medium</option>
                <option value="low">🟢 Low</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-foreground mb-1">Due Date</label>
              <input
                type="date"
                value={dueDate}
                onChange={(e) => setDueDate(e.target.value)}
                className="w-full px-3 py-2 border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary bg-card text-foreground"
              />
            </div>
          </div>

          {/* Preview of content */}
          <div>
            <label className="block text-sm font-medium text-foreground mb-1">Response Content</label>
            <div className="w-full px-3 py-2 border border-border rounded-lg bg-background text-sm text-muted-foreground max-h-32 overflow-y-auto">
              {content.length > 300 ? content.substring(0, 300) + '...' : content}
            </div>
            <p className="text-xs text-muted-foreground mt-1">Full response will be saved as the task description</p>
          </div>

          {/* Error */}
          {error && (
            <div className="p-3 text-sm text-status-danger bg-status-danger/10 border border-status-danger/30 rounded-lg">
              {error}
            </div>
          )}

          {/* Actions */}
          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-foreground border border-border rounded-lg hover:bg-muted"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting || !title.trim()}
              className="px-4 py-2 text-sm font-medium text-primary-foreground bg-primary rounded-lg hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Creating...
                </>
              ) : (
                'Create Task'
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// =============================================================================
// Markdown Content
// =============================================================================

function MarkdownContent({ content }: { content: string }) {
  const formatInline = (text: string): string => {
    return text
      .replace(/\*\*(.+?)\*\*/g, '<strong class="font-semibold text-foreground">$1</strong>')
      .replace(/\[(\d+)\]/g, '<span class="inline-flex items-center justify-center min-w-[1.25rem] h-5 px-1 text-xs bg-primary/10 text-primary rounded font-medium mx-0.5">$1</span>');
  };

  const renderMarkdown = (text: string) => {
    const lines = text.split('\n');
    const elements: React.ReactNode[] = [];
    let listItems: string[] = [];
    let listType: 'ul' | 'ol' | null = null;

    const flushList = () => {
      if (listItems.length > 0 && listType) {
        const ListTag = listType;
        elements.push(
          <ListTag key={elements.length} className={`${listType === 'ol' ? 'list-decimal' : 'list-disc'} ml-5 my-2 space-y-1 text-foreground`}>
            {listItems.map((item, i) => (
              <li key={i} className="text-[15px]" dangerouslySetInnerHTML={{ __html: formatInline(item) }} />
            ))}
          </ListTag>
        );
        listItems = [];
        listType = null;
      }
    };

    lines.forEach((line, index) => {
      if (line.startsWith('### ')) {
        flushList();
        elements.push(<h3 key={index} className="text-base font-medium text-foreground mt-4 mb-2" dangerouslySetInnerHTML={{ __html: formatInline(line.slice(4)) }} />);
        return;
      }
      if (line.startsWith('## ')) {
        flushList();
        elements.push(<h2 key={index} className="text-lg font-semibold text-foreground mt-4 mb-2" dangerouslySetInnerHTML={{ __html: formatInline(line.slice(3)) }} />);
        return;
      }
      if (line.startsWith('# ')) {
        flushList();
        elements.push(<h1 key={index} className="text-xl font-semibold text-foreground mt-4 mb-2" dangerouslySetInnerHTML={{ __html: formatInline(line.slice(2)) }} />);
        return;
      }

      const bulletMatch = line.match(/^[-*]\s+(.+)/);
      const numberedMatch = line.match(/^\d+\.\s+(.+)/);

      if (bulletMatch) {
        if (listType !== 'ul') { flushList(); listType = 'ul'; }
        listItems.push(bulletMatch[1] ?? '');
        return;
      }
      if (numberedMatch) {
        if (listType !== 'ol') { flushList(); listType = 'ol'; }
        listItems.push(numberedMatch[1] ?? '');
        return;
      }

      flushList();
      if (line.trim()) {
        elements.push(<p key={index} className="text-[15px] leading-relaxed my-2 text-foreground" dangerouslySetInnerHTML={{ __html: formatInline(line) }} />);
      }
    });

    flushList();
    return elements;
  };

  return <div className="text-foreground">{renderMarkdown(content)}</div>;
}

// =============================================================================
// Thinking Indicator with Animation
// =============================================================================

function ThinkingIndicator({
  status,
  perspectives,
}: {
  status: string;
  perspectives: string[];
}) {
  const [displayedStatus, setDisplayedStatus] = useState(status);
  const [isTransitioning, setIsTransitioning] = useState(false);

  useEffect(() => {
    if (status !== displayedStatus) {
      setIsTransitioning(true);
      // Short delay for fade out, then update text
      const timeout = setTimeout(() => {
        setDisplayedStatus(status);
        setIsTransitioning(false);
      }, 150);
      return () => clearTimeout(timeout);
    }
    return undefined;
  }, [status, displayedStatus]);

  return (
    <div className="flex items-start gap-3 p-4 bg-primary/5 rounded-xl border border-primary/20">
      {/* Animated dots */}
      <div className="flex gap-1 pt-0.5">
        <span
          className="w-2 h-2 bg-primary rounded-full animate-pulse"
          style={{ animationDelay: '0ms', animationDuration: '1s' }}
        />
        <span
          className="w-2 h-2 bg-primary/70 rounded-full animate-pulse"
          style={{ animationDelay: '200ms', animationDuration: '1s' }}
        />
        <span
          className="w-2 h-2 bg-primary/30 rounded-full animate-pulse"
          style={{ animationDelay: '400ms', animationDuration: '1s' }}
        />
      </div>

      <div className="flex-1 min-w-0">
        {/* Status text with fade transition */}
        <div
          className={`text-sm font-medium text-foreground transition-opacity duration-150 ${
            isTransitioning ? 'opacity-0' : 'opacity-100'
          }`}
        >
          {displayedStatus}
        </div>

        {/* Perspective badges */}
        {perspectives.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mt-2">
            {perspectives.map((p) => {
              const config = PERSPECTIVE_CONFIG[p as Perspective];
              if (!config) return null;
              return (
                <span
                  key={p}
                  className={`px-2 py-0.5 text-xs font-medium rounded-full ${config.bgColor} ${config.color} animate-fadeIn`}
                  style={{
                    animation: 'fadeIn 0.3s ease-out forwards',
                  }}
                >
                  {config.label}
                </span>
              );
            })}
          </div>
        )}
      </div>

      {/* Spinning loader on the right */}
      <Loader2 className="h-4 w-4 text-primary animate-spin flex-shrink-0" />
    </div>
  );
}

// =============================================================================
// Domain Selector Wrapper
// Handles async token retrieval for the DomainSelector component
// =============================================================================

function DomainSelectorWrapper({
  selectedDomain,
  onSelect,
  getToken,
}: {
  selectedDomain: string | null;
  onSelect: (slug: string | null) => void;
  getToken: () => Promise<string | null>;
}) {
  const [token, setToken] = useState<string | null>(null);

  useEffect(() => {
    getToken().then((t) => setToken(t));
  }, [getToken]);

  if (!token) return null;

  return (
    <div className="mb-3">
      <DomainSelector
        selectedDomain={selectedDomain}
        onSelect={onSelect}
        token={token}
        className="pb-1"
      />
    </div>
  );
}

// =============================================================================
// Citations Panel
// =============================================================================

function CitationsPanel({ citations }: { citations: Citation[] }) {
  const [expanded, setExpanded] = useState(false);
  const displayCitations = expanded ? citations : citations.slice(0, 2);

  const formatSourceType = (type: string): string => {
    const map: Record<string, string> = { ato_web: 'ATO', legislation: 'Legislation', austlii: 'AustLII', business_gov: 'Business.gov' };
    return map[type] || type.replace(/_/g, ' ');
  };

  return (
    <div className="pt-4 border-t border-border">
      <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
        Sources ({citations.length})
      </p>
      <div className="space-y-2">
        {displayCitations.map((citation) => (
          <a
            key={citation.number}
            href={citation.url || '#'}
            target="_blank"
            rel="noopener noreferrer"
            className="group flex items-start gap-2 p-2 bg-background hover:bg-muted border border-border hover:border-primary/30 rounded-lg transition-all text-sm"
          >
            <span className="w-5 h-5 rounded bg-primary/10 text-primary text-xs font-medium flex items-center justify-center flex-shrink-0">
              {citation.number}
            </span>
            <div className="flex-1 min-w-0">
              <p className="font-medium text-foreground truncate group-hover:text-primary">{citation.title || 'Source'}</p>
              <p className="text-xs text-muted-foreground">{formatSourceType(citation.source_type)} · {Math.round(citation.score * 100)}% match</p>
            </div>
            <ExternalLink className="w-3.5 h-3.5 text-muted-foreground/30 group-hover:text-primary flex-shrink-0" />
          </a>
        ))}
      </div>
      {citations.length > 2 && (
        <button onClick={() => setExpanded(!expanded)} className="mt-2 text-xs text-primary hover:text-primary/80 font-medium">
          {expanded ? 'Show less' : `+${citations.length - 2} more`}
        </button>
      )}
    </div>
  );
}
