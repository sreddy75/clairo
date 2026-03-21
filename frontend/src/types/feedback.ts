export type SubmissionType = 'feature_request' | 'bug_enhancement';
export type SubmissionStatus = 'draft' | 'new' | 'in_review' | 'planned' | 'in_progress' | 'done';
export type Severity = 'low' | 'medium' | 'high' | 'critical';
export type MessageRole = 'system' | 'user' | 'assistant';
export type ContentType = 'text' | 'transcript';

export interface FeedbackSubmission {
  id: string;
  tenant_id: string;
  submitter_id: string;
  submitter_name: string;
  title: string | null;
  type: SubmissionType;
  status: SubmissionStatus;
  severity: Severity | null;
  conversation_complete: boolean;
  has_brief: boolean;
  created_at: string;
  updated_at: string;
}

export interface SubmissionDetail extends FeedbackSubmission {
  transcript: string | null;
  brief_data: Record<string, unknown> | null;
  brief_markdown: string | null;
  audio_duration_seconds: number | null;
  message_count: number;
  comment_count: number;
}

export interface SubmissionListResponse {
  items: FeedbackSubmission[];
  total: number;
  limit: number;
  offset: number;
}

export interface FeedbackMessage {
  id: string;
  role: MessageRole;
  content: string;
  content_type: ContentType;
  created_at: string;
}

export interface ConversationResponse {
  messages: FeedbackMessage[];
}

export interface ConversationTurnResponse {
  user_message: FeedbackMessage;
  assistant_message: FeedbackMessage;
  brief_ready: boolean;
  brief_data: Record<string, unknown> | null;
  brief_markdown: string | null;
}

export interface VoiceConversationTurnResponse extends ConversationTurnResponse {
  transcript: string;
}

export interface FeedbackComment {
  id: string;
  author_id: string;
  author_name: string;
  content: string;
  created_at: string;
}

export interface FeedbackStats {
  total: number;
  by_status: Record<SubmissionStatus, number>;
  by_type: Record<SubmissionType, number>;
}

export interface SubmissionListParams {
  status?: SubmissionStatus;
  type?: SubmissionType;
  mine_only?: boolean;
  limit?: number;
  offset?: number;
}
