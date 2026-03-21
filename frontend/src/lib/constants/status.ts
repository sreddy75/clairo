/**
 * Shared status configurations for Clairo.
 * ALWAYS import from here — never define status configs locally.
 *
 * Uses StatusDot pattern: small colored dot + label text.
 * Color has meaning: green=good, amber=attention, red=urgent, neutral=inactive.
 */

// ─── Shared Interface ───────────────────────────────────────────────────────

export interface StatusConfig {
  label: string;
  dotColor: string;
  textColor: string;
}

export function getStatusByKey<K extends string>(
  config: Record<K, StatusConfig>,
  key: string,
  fallbackKey: K
): StatusConfig {
  return config[key as K] ?? config[fallbackKey];
}

// ─── BAS Status ─────────────────────────────────────────────────────────────

export type BASStatusKey = 'ready' | 'needs_review' | 'no_activity' | 'missing_data';

export const BAS_STATUS_CONFIG: Record<BASStatusKey, StatusConfig> = {
  ready: {
    label: 'Ready',
    dotColor: 'bg-status-success',
    textColor: 'text-status-success',
  },
  needs_review: {
    label: 'Needs Review',
    dotColor: 'bg-status-warning',
    textColor: 'text-status-warning',
  },
  no_activity: {
    label: 'No Activity',
    dotColor: 'bg-status-neutral',
    textColor: 'text-muted-foreground',
  },
  missing_data: {
    label: 'Missing Data',
    dotColor: 'bg-status-danger',
    textColor: 'text-status-danger',
  },
};

export function getStatusConfig(status: string): StatusConfig {
  return getStatusByKey(BAS_STATUS_CONFIG, status, 'no_activity');
}

// ─── Lodgement Session Status ───────────────────────────────────────────────

export type LodgementStatusKey = 'draft' | 'in_progress' | 'ready_for_review' | 'approved' | 'lodged';

export const LODGEMENT_STATUS_CONFIG: Record<LodgementStatusKey, StatusConfig> = {
  draft: {
    label: 'Draft',
    dotColor: 'bg-status-neutral',
    textColor: 'text-muted-foreground',
  },
  in_progress: {
    label: 'In Progress',
    dotColor: 'bg-status-info',
    textColor: 'text-status-info',
  },
  ready_for_review: {
    label: 'Ready for Review',
    dotColor: 'bg-status-warning',
    textColor: 'text-status-warning',
  },
  approved: {
    label: 'Approved',
    dotColor: 'bg-status-success',
    textColor: 'text-status-success',
  },
  lodged: {
    label: 'Lodged',
    dotColor: 'bg-status-success',
    textColor: 'text-status-success',
  },
};

export function getLodgementStatusConfig(status: string): StatusConfig {
  return getStatusByKey(LODGEMENT_STATUS_CONFIG, status, 'draft');
}

// ─── Urgency ────────────────────────────────────────────────────────────────

export type UrgencyKey = 'overdue' | 'critical' | 'warning' | 'normal';

export const URGENCY_CONFIG: Record<UrgencyKey, StatusConfig> = {
  overdue: {
    label: 'Overdue',
    dotColor: 'bg-status-danger',
    textColor: 'text-status-danger',
  },
  critical: {
    label: 'Critical',
    dotColor: 'bg-status-warning',
    textColor: 'text-status-warning',
  },
  warning: {
    label: 'Warning',
    dotColor: 'bg-status-warning',
    textColor: 'text-status-warning',
  },
  normal: {
    label: 'Normal',
    dotColor: 'bg-status-neutral',
    textColor: 'text-muted-foreground',
  },
};

export function getUrgencyConfig(urgency: string): StatusConfig {
  return getStatusByKey(URGENCY_CONFIG, urgency, 'normal');
}

// ─── Priority ───────────────────────────────────────────────────────────────

export type PriorityKey = 'urgent' | 'high' | 'medium' | 'low';

export const PRIORITY_CONFIG: Record<PriorityKey, StatusConfig> = {
  urgent: {
    label: 'Urgent',
    dotColor: 'bg-status-danger',
    textColor: 'text-status-danger',
  },
  high: {
    label: 'High',
    dotColor: 'bg-status-danger',
    textColor: 'text-status-danger',
  },
  medium: {
    label: 'Medium',
    dotColor: 'bg-status-warning',
    textColor: 'text-status-warning',
  },
  low: {
    label: 'Low',
    dotColor: 'bg-status-neutral',
    textColor: 'text-muted-foreground',
  },
};

export function getPriorityConfig(priority: string): StatusConfig {
  return getStatusByKey(PRIORITY_CONFIG, priority, 'low');
}

// ─── Action Item Status ─────────────────────────────────────────────────────

export type ActionItemStatusKey = 'pending' | 'in_progress' | 'completed' | 'cancelled';

export const ACTION_ITEM_STATUS_CONFIG: Record<ActionItemStatusKey, StatusConfig> = {
  pending: {
    label: 'Pending',
    dotColor: 'bg-status-neutral',
    textColor: 'text-muted-foreground',
  },
  in_progress: {
    label: 'In Progress',
    dotColor: 'bg-status-info',
    textColor: 'text-status-info',
  },
  completed: {
    label: 'Completed',
    dotColor: 'bg-status-success',
    textColor: 'text-status-success',
  },
  cancelled: {
    label: 'Cancelled',
    dotColor: 'bg-status-neutral',
    textColor: 'text-muted-foreground',
  },
};

export function getActionItemStatusConfig(status: string): StatusConfig {
  return getStatusByKey(ACTION_ITEM_STATUS_CONFIG, status, 'pending');
}

// ─── Feedback Submission Status ─────────────────────────────────────────────

export type FeedbackStatusKey = 'draft' | 'new' | 'in_review' | 'planned' | 'in_progress' | 'done';

export const FEEDBACK_STATUS_CONFIG: Record<FeedbackStatusKey, StatusConfig> = {
  draft: {
    label: 'Draft',
    dotColor: 'bg-status-neutral',
    textColor: 'text-muted-foreground',
  },
  new: {
    label: 'New',
    dotColor: 'bg-primary',
    textColor: 'text-primary',
  },
  in_review: {
    label: 'In Review',
    dotColor: 'bg-status-warning',
    textColor: 'text-status-warning',
  },
  planned: {
    label: 'Planned',
    dotColor: 'bg-status-warning',
    textColor: 'text-status-warning',
  },
  in_progress: {
    label: 'In Progress',
    dotColor: 'bg-status-info',
    textColor: 'text-status-info',
  },
  done: {
    label: 'Done',
    dotColor: 'bg-status-success',
    textColor: 'text-status-success',
  },
};

export function getFeedbackStatusConfig(status: string): StatusConfig {
  return getStatusByKey(FEEDBACK_STATUS_CONFIG, status, 'draft');
}

// ─── Feedback Submission Type ───────────────────────────────────────────────

export type FeedbackTypeKey = 'feature_request' | 'bug_enhancement';

export const FEEDBACK_TYPE_CONFIG: Record<FeedbackTypeKey, StatusConfig> = {
  feature_request: {
    label: 'Feature Request',
    dotColor: 'bg-primary',
    textColor: 'text-primary',
  },
  bug_enhancement: {
    label: 'Bug / Enhancement',
    dotColor: 'bg-status-info',
    textColor: 'text-status-info',
  },
};

export function getFeedbackTypeConfig(type: string): StatusConfig {
  return getStatusByKey(FEEDBACK_TYPE_CONFIG, type, 'feature_request');
}

// ─── Feedback Severity ──────────────────────────────────────────────────────

export type FeedbackSeverityKey = 'low' | 'medium' | 'high' | 'critical';

export const FEEDBACK_SEVERITY_CONFIG: Record<FeedbackSeverityKey, StatusConfig> = {
  low: {
    label: 'Low',
    dotColor: 'bg-status-neutral',
    textColor: 'text-muted-foreground',
  },
  medium: {
    label: 'Medium',
    dotColor: 'bg-status-warning',
    textColor: 'text-status-warning',
  },
  high: {
    label: 'High',
    dotColor: 'bg-orange-500',
    textColor: 'text-orange-600',
  },
  critical: {
    label: 'Critical',
    dotColor: 'bg-status-danger',
    textColor: 'text-status-danger',
  },
};

export function getFeedbackSeverityConfig(severity: string): StatusConfig {
  return getStatusByKey(FEEDBACK_SEVERITY_CONFIG, severity, 'medium');
}
