'use client';

import { useAuth, useUser } from '@clerk/nextjs';
import { UserButton } from '@clerk/nextjs';
import {
  BarChart3,
  Bell,
  Building2,
  ChevronDown,
  FileCheck,
  HelpCircle,
  LayoutGrid,
  Library,
  ListChecks,
  Menu,
  MessageSquareText,
  Mic,
  ScrollText,
  Search,
  Settings,
  ShieldCheck,
  Users,
  Zap,
} from 'lucide-react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useCallback, useEffect, useState, type ReactNode } from 'react';

import { SubscriptionBanner } from '@/components/billing/SubscriptionBanner';
import { TrialBanner } from '@/components/billing/TrialBanner';
import { ClairoLogo } from '@/components/brand';
import { CommandPalette } from '@/components/CommandPalette';
import { NotificationBell } from '@/components/NotificationBell';
import { OnboardingChecklist } from '@/components/onboarding/OnboardingChecklist';
import { ProductTour } from '@/components/onboarding/ProductTour';
import { ThemeToggle } from '@/components/theme';
import { Button } from '@/components/ui/button';
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { useChecklist } from '@/hooks/useChecklist';
import { useTour } from '@/hooks/useTour';
import { apiClient } from '@/lib/api-client';
import { cn } from '@/lib/utils';
import type { SubscriptionTier, TierFeatures } from '@/types/billing';

interface TrialStatus {
  is_trial: boolean;
  tier: SubscriptionTier;
  trial_end_date: string | null;
  days_remaining: number | null;
  price_monthly: number;
  billing_date: string | null;
}

interface ProtectedLayoutProps {
  children: ReactNode;
}

interface NavItem {
  name: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  requiredFeature?: keyof TierFeatures | 'full_ai';
  tourTarget?: string;
  badgeKey?: 'notifications' | 'actionItems';
}

// ─── Navigation Config ───────────────────────────────────────────────────────

const navigation: NavItem[] = [
  { name: 'Dashboard', href: '/dashboard', icon: LayoutGrid },
  { name: 'Clients', href: '/clients', icon: Building2 },
  { name: 'Lodgements', href: '/lodgements', icon: FileCheck },
  { name: 'AI Assistant', href: '/assistant', icon: MessageSquareText, requiredFeature: 'full_ai', tourTarget: 'ai-insights' },
  { name: 'Action Items', href: '/action-items', icon: ListChecks, requiredFeature: 'custom_triggers', badgeKey: 'actionItems' },
  { name: 'Notifications', href: '/notifications', icon: Bell, requiredFeature: 'custom_triggers', badgeKey: 'notifications' },
  { name: 'Feedback', href: '/feedback', icon: Mic },
  { name: 'Team', href: '/team', icon: Users, requiredFeature: 'client_portal' },
];

const adminNavigation: NavItem[] = [
  { name: 'Usage', href: '/admin/usage', icon: BarChart3 },
  { name: 'Knowledge Base', href: '/admin/knowledge', icon: Library },
  { name: 'Triggers', href: '/admin/triggers', icon: Zap },
  { name: 'Audit Log', href: '/admin/audit', icon: ScrollText },
  { name: 'Admin', href: '/internal/admin', icon: ShieldCheck },
];

// ─── Nav Link Component ──────────────────────────────────────────────────────

function NavLink({
  item,
  isActive,
  badgeCount,
}: {
  item: NavItem;
  isActive: boolean;
  badgeCount?: number;
}) {
  const Icon = item.icon;
  return (
    <Link
      href={item.href}
      data-tour={item.tourTarget}
      className={cn(
        'flex items-center gap-3 px-3 py-2 text-sm font-medium rounded-lg transition-colors',
        isActive
          ? 'bg-primary/10 text-primary'
          : 'text-muted-foreground hover:bg-muted hover:text-foreground'
      )}
    >
      <Icon className="w-[18px] h-[18px] flex-shrink-0" />
      <span className="truncate flex-1">{item.name}</span>
      {badgeCount != null && badgeCount > 0 && (
        <span className="flex-shrink-0 min-w-[20px] h-5 flex items-center justify-center px-1.5 text-[11px] font-semibold rounded-full bg-primary/15 text-primary tabular-nums">
          {badgeCount > 99 ? '99+' : badgeCount}
        </span>
      )}
    </Link>
  );
}

// ─── Layout ──────────────────────────────────────────────────────────────────

export default function ProtectedLayout({ children }: ProtectedLayoutProps) {
  const router = useRouter();
  const pathname = usePathname();
  const { getToken, isLoaded } = useAuth();
  const { user } = useUser();
  const [isCheckingRegistration, setIsCheckingRegistration] = useState(true);
  const [isRegistered, setIsRegistered] = useState(false);
  const [features, setFeatures] = useState<TierFeatures | null>(null);
  const [_tier, setTier] = useState<string>('starter');
  const [trialStatus, setTrialStatus] = useState<TrialStatus | null>(null);
  const [subscriptionStatus, setSubscriptionStatus] = useState<string | null>(null);
  const [_canAccess, setCanAccess] = useState(true);
  const [showHelpMenu, setShowHelpMenu] = useState(false);
  const [adminExpanded, setAdminExpanded] = useState(true);
  const [commandOpen, setCommandOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Badge counts
  const [notificationCount, setNotificationCount] = useState(0);
  const [actionItemCount, setActionItemCount] = useState(0);

  // Product tour hook
  const { shouldShowTour, isTourRunning, startTour, handleTourEnd } = useTour();

  // Onboarding checklist hook
  const {
    checklist,
    shouldShow: shouldShowChecklist,
    dismiss: dismissChecklist,
  } = useChecklist();

  // Auto-start tour when conditions are met
  useEffect(() => {
    if (shouldShowTour && !isTourRunning && isRegistered && pathname === '/dashboard') {
      const timer = setTimeout(() => {
        startTour();
      }, 1000);
      return () => clearTimeout(timer);
    }
    return undefined;
  }, [shouldShowTour, isTourRunning, isRegistered, pathname, startTour]);

  // ⌘K keyboard shortcut
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setCommandOpen((prev) => !prev);
      }
    }

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Check if user is super admin
  const isSuperAdmin = user?.publicMetadata?.role === 'super_admin';

  // Helper to check if a feature is available
  const hasFeature = (feature: keyof TierFeatures | 'full_ai'): boolean => {
    if (!features) return false;
    if (feature === 'full_ai') {
      return features.ai_insights === 'full';
    }
    const value = features[feature];
    return typeof value === 'boolean' ? value : Boolean(value);
  };

  // Fetch badge counts
  const fetchBadgeCounts = useCallback(async () => {
    try {
      const token = await getToken();
      if (!token) return;

      const [notifRes, actionRes] = await Promise.allSettled([
        apiClient.get('/api/v1/notifications/unread-count', {
          headers: { Authorization: `Bearer ${token}` },
        }),
        apiClient.get('/api/v1/action-items/stats', {
          headers: { Authorization: `Bearer ${token}` },
        }),
      ]);

      if (notifRes.status === 'fulfilled' && notifRes.value.ok) {
        const data = await notifRes.value.json();
        setNotificationCount(data.unread_count ?? 0);
      }

      if (actionRes.status === 'fulfilled' && actionRes.value.ok) {
        const data = await actionRes.value.json();
        setActionItemCount((data.pending ?? 0) + (data.in_progress ?? 0));
      }
    } catch {
      // Silently fail — badges are non-critical
    }
  }, [getToken]);

  // Poll badge counts
  useEffect(() => {
    if (!isRegistered) return;

    fetchBadgeCounts();
    const interval = setInterval(() => {
      if (!document.hidden) fetchBadgeCounts();
    }, 60000);
    return () => clearInterval(interval);
  }, [isRegistered, fetchBadgeCounts]);

  // Badge count lookup
  const getBadgeCount = (key?: 'notifications' | 'actionItems'): number | undefined => {
    if (key === 'notifications') return notificationCount;
    if (key === 'actionItems') return actionItemCount;
    return undefined;
  };

  // Single bootstrap call: auth + features + trial in one round-trip
  useEffect(() => {
    async function bootstrap() {
      if (!isLoaded) return;

      if (pathname === '/onboarding') {
        setIsCheckingRegistration(false);
        setIsRegistered(true);
        return;
      }

      try {
        const token = await getToken();
        if (!token) {
          setIsCheckingRegistration(false);
          return;
        }

        const response = await apiClient.get('/api/v1/auth/bootstrap', {
          headers: { Authorization: `Bearer ${token}` },
        });

        if (response.ok) {
          const data = await response.json();

          // Check ToS acceptance before allowing access
          const { TOS_VERSION } = await import('@/lib/constants');
          if (!data.tos_accepted_at || data.tos_version_accepted !== TOS_VERSION) {
            router.push('/accept-terms');
            return;
          }

          setIsRegistered(true);

          if (data.features) {
            setFeatures(data.features.features);
            setTier(data.features.tier);
          }

          if (data.trial_status) {
            setTrialStatus(data.trial_status);
          }

          // Subscription status for access gating
          if (data.subscription_status) {
            setSubscriptionStatus(data.subscription_status);
            // Redirect cancelled users to expired page (unless already on billing)
            if (data.subscription_status === 'cancelled' && !pathname.startsWith('/settings/billing') && pathname !== '/subscription-expired') {
              router.push('/subscription-expired');
              return;
            }
          }
          if (data.can_access !== undefined) {
            setCanAccess(data.can_access);
          }
        } else if (response.status === 404) {
          router.push('/onboarding');
          return;
        }
      } catch {
        router.push('/onboarding');
        return;
      }

      setIsCheckingRegistration(false);
    }

    bootstrap();
  }, [isLoaded, getToken, router, pathname]);

  // Close sidebar on route change (mobile)
  useEffect(() => {
    setSidebarOpen(false);
  }, [pathname]);

  // ─── Sidebar Content (shared between desktop and mobile) ─────────────────
  const renderSidebarNav = (onNavigate?: () => void) => (
    <>
      {/* Sidebar Header */}
      <div className="flex items-center gap-2.5 h-14 px-3 border-b border-border flex-shrink-0">
        <Link href="/dashboard" className="flex items-center gap-2 flex-shrink-0" onClick={onNavigate}>
          <ClairoLogo size="sm" showText={false} variant="light" className="dark:hidden" />
          <ClairoLogo size="sm" showText={false} variant="dark" className="hidden dark:flex" />
        </Link>
        <button
          onClick={() => { setCommandOpen(true); onNavigate?.(); }}
          className="flex items-center gap-2 flex-1 min-w-0 px-2.5 py-1.5 text-sm text-muted-foreground bg-muted/50 border border-border rounded-lg hover:bg-muted transition-colors"
          aria-label="Search"
        >
          <Search className="w-3.5 h-3.5 flex-shrink-0" />
          <span className="flex-1 text-left text-muted-foreground/70 text-xs truncate">Search...</span>
          <kbd className="text-[10px] font-mono text-muted-foreground/50 bg-background border border-border px-1 py-0.5 rounded">
            ⌘K
          </kbd>
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto px-3 py-2 space-y-1" data-tour="client-list">
        {navigation.map((item) => {
          const isActive = pathname.startsWith(item.href);
          const isLocked = item.requiredFeature && !hasFeature(item.requiredFeature);
          if (isLocked) return null;

          return (
            <div key={item.name} onClick={onNavigate}>
              <NavLink
                item={item}
                isActive={isActive}
                badgeCount={getBadgeCount(item.badgeKey)}
              />
            </div>
          );
        })}

        {/* Admin Section */}
        {isSuperAdmin && (
          <div className="pt-3 mt-3">
            <button
              onClick={() => setAdminExpanded(!adminExpanded)}
              className="flex items-center gap-2 w-full px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground/70 hover:text-muted-foreground transition-colors"
            >
              <ChevronDown
                className={cn(
                  'w-3 h-3 transition-transform duration-200',
                  !adminExpanded && '-rotate-90'
                )}
              />
              Admin
            </button>
            {adminExpanded && (
              <div className="mt-1 space-y-1">
                {adminNavigation.map((item) => {
                  const isActive = pathname.startsWith(item.href);
                  return (
                    <div key={item.name} onClick={onNavigate}>
                      <NavLink item={item} isActive={isActive} />
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </nav>

      {/* Onboarding Checklist */}
      {shouldShowChecklist && checklist && (
        <div className="px-4 pb-2 border-t border-border pt-3">
          <OnboardingChecklist
            checklist={checklist}
            onDismiss={dismissChecklist}
          />
        </div>
      )}

      {/* Bottom Section */}
      <div className="border-t border-border p-3 space-y-0.5">
        <div className="flex items-center gap-3 px-3 py-2 mb-1">
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-foreground truncate">
              {user?.fullName || 'My Practice'}
            </p>
            <p className="text-xs text-muted-foreground truncate">
              {user?.primaryEmailAddress?.emailAddress}
            </p>
          </div>
        </div>
        <div onClick={onNavigate}>
          <Link
            href="/settings"
            data-tour="settings-menu"
            className={cn(
              'flex items-center gap-3 px-3 py-2 text-sm font-medium rounded-lg transition-colors',
              pathname.startsWith('/settings')
                ? 'bg-primary/10 text-primary'
                : 'text-muted-foreground hover:bg-muted hover:text-foreground'
            )}
          >
            <Settings className="w-[18px] h-[18px] flex-shrink-0" />
            <span>Settings</span>
          </Link>
        </div>

        {/* Help Menu */}
        <div className="relative">
          <button
            onClick={() => setShowHelpMenu(!showHelpMenu)}
            className="flex items-center gap-3 w-full px-3 py-2 text-sm font-medium text-muted-foreground hover:bg-muted hover:text-foreground rounded-lg transition-colors"
          >
            <HelpCircle className="w-[18px] h-[18px] flex-shrink-0" />
            <span>Help &amp; Support</span>
          </button>
          {showHelpMenu && (
            <>
              <div
                className="fixed inset-0 z-40"
                onClick={() => setShowHelpMenu(false)}
              />
              <div className="absolute left-full bottom-0 ml-2 w-52 bg-card border border-border rounded-xl shadow-lg z-50 py-1 lg:block hidden">
                <button
                  onClick={() => { setShowHelpMenu(false); startTour(); onNavigate?.(); }}
                  className="w-full text-left px-4 py-2.5 text-sm text-foreground hover:bg-muted transition-colors"
                >
                  Restart Product Tour
                </button>
                <a href="mailto:support@clairo.ai" className="block px-4 py-2.5 text-sm text-foreground hover:bg-muted transition-colors">
                  Contact Support
                </a>
                <a href="/docs" className="block px-4 py-2.5 text-sm text-foreground hover:bg-muted transition-colors">
                  Documentation
                </a>
              </div>
              {/* Mobile help menu — renders inline below button instead of flyout */}
              <div className="lg:hidden w-full bg-muted/50 rounded-lg py-1 mt-1">
                <button
                  onClick={() => { setShowHelpMenu(false); startTour(); onNavigate?.(); }}
                  className="w-full text-left px-4 py-2.5 text-sm text-foreground hover:bg-muted transition-colors rounded-lg"
                >
                  Restart Product Tour
                </button>
                <a href="mailto:support@clairo.ai" className="block px-4 py-2.5 text-sm text-foreground hover:bg-muted transition-colors rounded-lg">
                  Contact Support
                </a>
                <a href="/docs" className="block px-4 py-2.5 text-sm text-foreground hover:bg-muted transition-colors rounded-lg">
                  Documentation
                </a>
              </div>
            </>
          )}
        </div>
      </div>
    </>
  );

  // ─── Skeleton ────────────────────────────────────────────────────────────

  if (isCheckingRegistration || !isRegistered) {
    return (
      <div className="min-h-screen bg-background">
        {/* Desktop skeleton sidebar */}
        <aside className="fixed inset-y-0 left-0 w-64 bg-card border-r border-border hidden lg:flex flex-col">
          <div className="flex items-center gap-2.5 h-14 px-3 border-b border-border">
            <div className="h-6 w-6 bg-muted rounded-lg animate-pulse flex-shrink-0" />
            <div className="flex-1 h-8 bg-muted rounded-lg animate-pulse" />
          </div>
          <div className="px-3 py-2 space-y-1">
            {[...Array(6)].map((_, i) => (
              <div key={i} className="h-9 bg-muted rounded-lg animate-pulse" />
            ))}
          </div>
        </aside>
        <div className="lg:pl-64">
          <header className="h-14 bg-card border-b border-border flex items-center px-4">
            {/* Mobile skeleton header */}
            <div className="lg:hidden flex items-center gap-2">
              <div className="h-8 w-8 bg-muted rounded animate-pulse" />
              <div className="h-6 w-20 bg-muted rounded animate-pulse" />
            </div>
          </header>
          <main className="p-6">
            <div className="space-y-4">
              <div className="h-8 w-48 bg-muted rounded animate-pulse" />
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                {[...Array(4)].map((_, i) => (
                  <div key={i} className="h-28 bg-card rounded-xl border border-border animate-pulse" />
                ))}
              </div>
              <div className="h-64 bg-card rounded-xl border border-border animate-pulse" />
            </div>
          </main>
        </div>
      </div>
    );
  }

  // ─── Main Layout ─────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-background">
      {/* ── Desktop Sidebar (hidden on mobile) ──────────────────────────── */}
      <aside className="fixed inset-y-0 left-0 w-64 bg-card border-r border-border hidden lg:flex flex-col z-30">
        {renderSidebarNav()}
      </aside>

      {/* ── Mobile Sidebar Drawer ───────────────────────────────────────── */}
      <Sheet open={sidebarOpen} onOpenChange={setSidebarOpen}>
        <SheetContent side="left" className="w-72 p-0 flex flex-col">
          <SheetHeader className="sr-only">
            <SheetTitle>Navigation</SheetTitle>
          </SheetHeader>
          {renderSidebarNav(() => setSidebarOpen(false))}
        </SheetContent>
      </Sheet>

      {/* ── Main Content ────────────────────────────────────────────────── */}
      <div className="lg:pl-64">
        {/* Top bar */}
        <header
          className="sticky top-0 z-20 h-14 bg-card/80 backdrop-blur-sm border-b border-border flex items-center gap-2 px-4 lg:px-6 lg:justify-end"
          data-tour="dashboard-header"
        >
          {/* Mobile: hamburger + logo */}
          <div className="flex items-center gap-2 lg:hidden">
            <Button variant="ghost" size="icon" onClick={() => setSidebarOpen(true)} aria-label="Open menu">
              <Menu className="h-5 w-5" />
            </Button>
            <Link href="/dashboard">
              <ClairoLogo size="sm" showText={false} variant="light" className="dark:hidden" />
              <ClairoLogo size="sm" showText={false} variant="dark" className="hidden dark:flex" />
            </Link>
          </div>
          {/* Right side actions */}
          <div className="flex items-center gap-2 ml-auto">
            <ThemeToggle />
            <NotificationBell />
            <UserButton
              appearance={{
                elements: {
                  avatarBox: 'w-8 h-8',
                },
              }}
              afterSignOutUrl="/"
            />
          </div>
        </header>

        {/* Subscription Status Banners */}
        {subscriptionStatus === 'suspended' && !pathname.startsWith('/settings/billing') && (
          <SubscriptionBanner status="suspended" />
        )}
        {subscriptionStatus === 'past_due' && (
          <SubscriptionBanner
            status="past_due"
            currentPeriodEnd={trialStatus?.billing_date ?? null}
          />
        )}

        {/* Trial Banner (only when not suspended/past_due) */}
        {trialStatus?.is_trial && trialStatus.days_remaining !== null && subscriptionStatus === 'trial' && (
          <div className="px-6 pt-4">
            <TrialBanner
              daysRemaining={trialStatus.days_remaining}
              tier={trialStatus.tier}
              priceMonthly={trialStatus.price_monthly}
              billingDate={
                trialStatus.billing_date
                  ? new Date(trialStatus.billing_date).toLocaleDateString(
                      'en-AU',
                      { month: 'long', day: 'numeric', year: 'numeric' }
                    )
                  : 'soon'
              }
            />
          </div>
        )}

        {/* Page content */}
        <main className="p-5" data-tour="bas-workflow">{children}</main>
      </div>

      {/* Command Palette */}
      <CommandPalette open={commandOpen} onOpenChange={setCommandOpen} />

      {/* Product Tour */}
      <ProductTour run={isTourRunning} onTourEnd={handleTourEnd} />
    </div>
  );
}
