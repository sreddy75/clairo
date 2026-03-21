/**
 * Action Items types
 */

export type ActionItemStatus = 'pending' | 'in_progress' | 'completed' | 'cancelled';

export type ActionItemPriority = 'urgent' | 'high' | 'medium' | 'low';

export interface ActionItem {
  id: string;
  tenant_id: string;
  title: string;
  description: string | null;
  notes: string | null;
  source_insight_id: string | null;
  client_id: string | null;
  client_name: string | null;
  assigned_to_user_id: string | null;
  assigned_to_name: string | null;
  assigned_by_user_id: string;
  due_date: string | null;
  priority: ActionItemPriority;
  status: ActionItemStatus;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  completed_at: string | null;
  resolution_notes: string | null;
  is_overdue: boolean;
}

export interface ActionItemCreate {
  title: string;
  description?: string | null;
  notes?: string | null;
  source_insight_id?: string | null;
  client_id?: string | null;
  client_name?: string | null;
  assigned_to_user_id?: string | null;
  assigned_to_name?: string | null;
  due_date?: string | null;
  priority?: ActionItemPriority;
}

export interface ActionItemUpdate {
  title?: string;
  description?: string | null;
  notes?: string | null;
  assigned_to_user_id?: string | null;
  assigned_to_name?: string | null;
  due_date?: string | null;
  priority?: ActionItemPriority;
  resolution_notes?: string | null;
}

export interface ActionItemListResponse {
  items: ActionItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface ActionItemStats {
  total: number;
  pending: number;
  in_progress: number;
  completed: number;
  cancelled: number;
  overdue: number;
  urgent: number;
  high: number;
  medium: number;
  low: number;
}

export interface ConvertInsightRequest {
  title?: string | null;
  description?: string | null;
  notes?: string | null;
  assigned_to_user_id?: string | null;
  assigned_to_name?: string | null;
  due_date?: string | null;
  priority?: ActionItemPriority | null;
}

// Priority configuration for UI
export const PRIORITY_CONFIG: Record<
  ActionItemPriority,
  { label: string; color: string; bgColor: string; borderColor: string }
> = {
  urgent: {
    label: 'Urgent',
    color: 'text-red-700',
    bgColor: 'bg-red-50',
    borderColor: 'border-red-200',
  },
  high: {
    label: 'High',
    color: 'text-orange-700',
    bgColor: 'bg-orange-50',
    borderColor: 'border-orange-200',
  },
  medium: {
    label: 'Medium',
    color: 'text-blue-700',
    bgColor: 'bg-blue-50',
    borderColor: 'border-blue-200',
  },
  low: {
    label: 'Low',
    color: 'text-gray-600',
    bgColor: 'bg-gray-50',
    borderColor: 'border-gray-200',
  },
};

// Status configuration for UI
export const STATUS_CONFIG: Record<
  ActionItemStatus,
  { label: string; color: string; bgColor: string }
> = {
  pending: {
    label: 'Pending',
    color: 'text-gray-700',
    bgColor: 'bg-gray-100',
  },
  in_progress: {
    label: 'In Progress',
    color: 'text-blue-700',
    bgColor: 'bg-blue-100',
  },
  completed: {
    label: 'Completed',
    color: 'text-green-700',
    bgColor: 'bg-green-100',
  },
  cancelled: {
    label: 'Cancelled',
    color: 'text-gray-500',
    bgColor: 'bg-gray-100',
  },
};
