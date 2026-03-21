'use client';

/**
 * Notification Bell Component
 *
 * Displays a bell icon with unread count badge and dropdown
 * showing recent notifications.
 *
 * Spec 011: Interim Lodgement - In-app deadline notifications
 */

import { useAuth } from '@clerk/nextjs';
import { Bell, CheckCheck, Clock } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useCallback, useEffect, useRef, useState } from 'react';

import { apiClient } from '@/lib/api-client';

interface Notification {
  id: string;
  notification_type: string;
  title: string;
  message: string | null;
  entity_type: string | null;
  entity_id: string | null;
  entity_context: { connection_id?: string } | null;
  is_read: boolean;
  read_at: string | null;
  created_at: string;
}

interface NotificationListResponse {
  notifications: Notification[];
  total: number;
  unread_count: number;
}

export function NotificationBell() {
  const { getToken } = useAuth();
  const router = useRouter();
  const [isOpen, setIsOpen] = useState(false);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Fetch notifications
  const fetchNotifications = useCallback(async () => {
    try {
      const token = await getToken();
      if (!token) return;

      const response = await apiClient.get(
        '/api/v1/notifications?limit=10',
        { headers: { Authorization: `Bearer ${token}` } }
      );

      if (response.ok) {
        const data: NotificationListResponse = await response.json();
        setNotifications(data.notifications);
        setUnreadCount(data.unread_count);
      }
    } catch (error) {
      console.error('Failed to fetch notifications:', error);
    }
  }, [getToken]);

  // Fetch unread count (lightweight polling)
  const fetchUnreadCount = useCallback(async () => {
    try {
      const token = await getToken();
      if (!token) return;

      const response = await apiClient.get(
        '/api/v1/notifications/unread-count',
        { headers: { Authorization: `Bearer ${token}` } }
      );

      if (response.ok) {
        const data: { unread_count: number } = await response.json();
        setUnreadCount(data.unread_count);
      }
    } catch {
      // Silently fail for polling
    }
  }, [getToken]);

  // Initial fetch and polling (skip when tab is hidden)
  useEffect(() => {
    fetchUnreadCount();

    const interval = setInterval(() => {
      if (!document.hidden) fetchUnreadCount();
    }, 60000);
    return () => clearInterval(interval);
  }, [fetchUnreadCount]);

  // Fetch full list when dropdown opens
  useEffect(() => {
    if (isOpen) {
      setIsLoading(true);
      fetchNotifications().finally(() => setIsLoading(false));
    }
  }, [isOpen, fetchNotifications]);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Mark notification as read
  const markAsRead = async (notificationId: string) => {
    try {
      const token = await getToken();
      if (!token) return;

      await apiClient.patch(
        `/api/v1/notifications/${notificationId}/read`,
        { headers: { Authorization: `Bearer ${token}` } }
      );

      setNotifications((prev) =>
        prev.map((n) =>
          n.id === notificationId ? { ...n, is_read: true } : n
        )
      );
      setUnreadCount((prev) => Math.max(0, prev - 1));
    } catch (error) {
      console.error('Failed to mark notification as read:', error);
    }
  };

  // Mark all as read
  const markAllAsRead = async () => {
    try {
      const token = await getToken();
      if (!token) return;

      await apiClient.post(
        '/api/v1/notifications/mark-all-read',
        { headers: { Authorization: `Bearer ${token}` } }
      );

      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
      setUnreadCount(0);
    } catch (error) {
      console.error('Failed to mark all as read:', error);
    }
  };

  // Handle notification click - navigate to relevant entity
  const handleNotificationClick = (notification: Notification) => {
    // Mark as read
    if (!notification.is_read) {
      markAsRead(notification.id);
    }

    // Navigate based on entity type
    if (notification.entity_type === 'bas_session' && notification.entity_context?.connection_id) {
      router.push(`/clients/${notification.entity_context.connection_id}?tab=bas`);
      setIsOpen(false);
    }
  };

  // Format relative time
  const formatRelativeTime = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString('en-AU', { day: 'numeric', month: 'short' });
  };

  // Get icon for notification type
  const getNotificationIcon = (type: string) => {
    if (type.includes('deadline') || type.includes('overdue')) {
      return <Clock className="w-4 h-4 text-status-warning" />;
    }
    return <Bell className="w-4 h-4 text-primary" />;
  };

  return (
    <div className="relative" ref={dropdownRef}>
      {/* Bell button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="relative p-2 text-muted-foreground hover:text-foreground hover:bg-muted rounded-lg transition-colors"
        aria-label="Notifications"
      >
        <Bell className="w-5 h-5" />
        {unreadCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 flex items-center justify-center min-w-[18px] h-[18px] px-1 text-[10px] font-bold text-white bg-status-danger rounded-full">
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </button>

      {/* Dropdown */}
      {isOpen && (
        <div className="absolute right-0 mt-2 w-96 bg-card rounded-xl shadow-2xl border border-border overflow-hidden z-50">
          {/* Header */}
          <div className="px-4 py-3 border-b border-border flex items-center justify-between bg-muted">
            <h3 className="font-semibold text-foreground">Notifications</h3>
            {unreadCount > 0 && (
              <button
                onClick={markAllAsRead}
                className="text-xs text-primary hover:text-primary/80 font-medium flex items-center gap-1"
              >
                <CheckCheck className="w-3.5 h-3.5" />
                Mark all read
              </button>
            )}
          </div>

          {/* Notification list */}
          <div className="max-h-[400px] overflow-y-auto">
            {isLoading ? (
              <div className="p-8 text-center text-muted-foreground">
                <div className="animate-pulse">Loading...</div>
              </div>
            ) : notifications.length === 0 ? (
              <div className="p-8 text-center">
                <Bell className="w-10 h-10 text-muted-foreground/40 mx-auto mb-2" />
                <p className="text-muted-foreground text-sm">No notifications yet</p>
              </div>
            ) : (
              <div className="divide-y divide-border">
                {notifications.map((notification) => (
                  <button
                    key={notification.id}
                    onClick={() => handleNotificationClick(notification)}
                    className={`w-full text-left px-4 py-3 hover:bg-muted transition-colors ${
                      !notification.is_read ? 'bg-primary/5' : ''
                    }`}
                  >
                    <div className="flex gap-3">
                      <div className="flex-shrink-0 mt-0.5">
                        {getNotificationIcon(notification.notification_type)}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-start justify-between gap-2">
                          <p className={`text-sm ${!notification.is_read ? 'font-semibold text-foreground' : 'text-foreground/80'}`}>
                            {notification.title}
                          </p>
                          {!notification.is_read && (
                            <span className="flex-shrink-0 w-2 h-2 mt-1.5 bg-primary rounded-full" />
                          )}
                        </div>
                        {notification.message && (
                          <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">
                            {notification.message}
                          </p>
                        )}
                        <p className="text-xs text-muted-foreground/70 mt-1">
                          {formatRelativeTime(notification.created_at)}
                        </p>
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="px-4 py-2 border-t border-border bg-muted">
            <a
              href="/notifications"
              onClick={() => setIsOpen(false)}
              className="text-xs text-primary hover:text-primary/80 font-medium"
            >
              View all notifications
            </a>
          </div>
        </div>
      )}
    </div>
  );
}

export default NotificationBell;
