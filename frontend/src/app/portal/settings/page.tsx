/**
 * Portal Settings Page
 *
 * Manages PWA settings: notifications, storage, offline data.
 *
 * Spec: 032-pwa-mobile-document-capture
 */

'use client';

import {
  ArrowLeft,
  Bell,
  HardDrive,
  Trash2,
  Loader2,
  WifiOff,
  RefreshCw,
} from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

import { BiometricSetup } from '@/components/pwa/BiometricSetup';
import { NotificationSettings } from '@/components/pwa/NotificationPermission';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Progress } from '@/components/ui/progress';
import { Switch } from '@/components/ui/switch';
import { useNetworkStatus } from '@/hooks/useNetworkStatus';
import { portalTokenStorage } from '@/lib/api/portal';
import { clearCachedDashboard } from '@/lib/pwa/cached-dashboard';
import { clearCachedRequests, getCacheStats } from '@/lib/pwa/cached-requests';
import {
  getSettings,
  updateSettings,
  getStorageEstimate,
  clearAllData,
  type PWASettings,
} from '@/lib/pwa/db';

export default function PortalSettingsPage() {
  const router = useRouter();
  const { isOnline } = useNetworkStatus();
  const [settings, setSettings] = useState<PWASettings | null>(null);
  const [storageUsage, setStorageUsage] = useState<{
    usage: number;
    quota: number;
    usagePercent: number;
  } | null>(null);
  const [cacheStats, setCacheStats] = useState<{
    totalRequests: number;
    lastCacheTime: number | null;
  } | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isClearingCache, setIsClearingCache] = useState(false);

  // Check auth
  useEffect(() => {
    if (!portalTokenStorage.isAuthenticated()) {
      router.push('/portal/login');
    }
  }, [router]);

  // Load settings
  useEffect(() => {
    const loadData = async () => {
      try {
        const [settingsData, storage, cache] = await Promise.all([
          getSettings(),
          getStorageEstimate(),
          getCacheStats(),
        ]);
        setSettings(settingsData);
        setStorageUsage(storage);
        setCacheStats(cache);
      } catch (err) {
        console.error('[Settings] Failed to load:', err);
      } finally {
        setIsLoading(false);
      }
    };

    loadData();
  }, []);

  const handleSettingChange = async (key: keyof PWASettings, value: boolean | string | number) => {
    if (!settings) return;

    try {
      const updated = await updateSettings({ [key]: value });
      setSettings(updated);
    } catch (err) {
      console.error('[Settings] Failed to update:', err);
    }
  };

  const handleClearCache = async () => {
    setIsClearingCache(true);
    try {
      await clearCachedRequests();
      await clearCachedDashboard();
      const [storage, cache] = await Promise.all([
        getStorageEstimate(),
        getCacheStats(),
      ]);
      setStorageUsage(storage);
      setCacheStats(cache);
    } catch (err) {
      console.error('[Settings] Failed to clear cache:', err);
    } finally {
      setIsClearingCache(false);
    }
  };

  const handleClearAllData = async () => {
    if (!confirm('This will clear all offline data including queued uploads. Continue?')) {
      return;
    }

    setIsClearingCache(true);
    try {
      await clearAllData();
      const storage = await getStorageEstimate();
      setStorageUsage(storage);
      setCacheStats({ totalRequests: 0, lastCacheTime: null });
    } catch (err) {
      console.error('[Settings] Failed to clear all data:', err);
    } finally {
      setIsClearingCache(false);
    }
  };

  // Format bytes
  const formatBytes = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
  };

  // Format date
  const formatDate = (timestamp: number): string => {
    return new Date(timestamp).toLocaleString();
  };

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="bg-card border-b">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center h-16">
            <Button variant="ghost" size="icon" asChild className="mr-3">
              <Link href="/portal/dashboard">
                <ArrowLeft className="h-5 w-5" />
              </Link>
            </Button>
            <h1 className="font-semibold text-lg">Settings</h1>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        {/* Network Status */}
        {!isOnline && (
          <Card className="border-status-warning/20 bg-status-warning/10">
            <CardContent className="flex items-center gap-3 py-4">
              <WifiOff className="h-5 w-5 text-status-warning" />
              <p className="text-status-warning">
                You&apos;re offline. Some settings may not sync.
              </p>
            </CardContent>
          </Card>
        )}

        {/* Notifications */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Bell className="h-5 w-5" />
              Notifications
            </CardTitle>
            <CardDescription>
              Manage push notification preferences
            </CardDescription>
          </CardHeader>
          <CardContent>
            <NotificationSettings />
          </CardContent>
        </Card>

        {/* Biometric Login */}
        <BiometricSetup />

        {/* Offline Settings */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <HardDrive className="h-5 w-5" />
              Offline Storage
            </CardTitle>
            <CardDescription>
              Manage cached data for offline access
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Storage usage */}
            {storageUsage && (
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Storage Used</span>
                  <span className="font-medium">
                    {formatBytes(storageUsage.usage)} / {formatBytes(storageUsage.quota)}
                  </span>
                </div>
                <Progress value={storageUsage.usagePercent} className="h-2" />
              </div>
            )}

            {/* Cache stats */}
            {cacheStats && (
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Cached Requests</span>
                  <span className="font-medium">{cacheStats.totalRequests}</span>
                </div>
                {cacheStats.lastCacheTime && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Last Sync</span>
                    <span className="font-medium">
                      {formatDate(cacheStats.lastCacheTime)}
                    </span>
                  </div>
                )}
              </div>
            )}

            {/* Auto-upload setting */}
            {settings && (
              <div className="flex items-center justify-between">
                <div>
                  <Label htmlFor="auto-upload">Auto-upload when online</Label>
                  <p className="text-sm text-muted-foreground">
                    Automatically upload queued files when connected
                  </p>
                </div>
                <Switch
                  id="auto-upload"
                  checked={settings.autoUpload}
                  onCheckedChange={(checked) => handleSettingChange('autoUpload', checked)}
                />
              </div>
            )}

            {/* Clear cache button */}
            <div className="flex gap-3">
              <Button
                variant="outline"
                className="flex-1"
                onClick={handleClearCache}
                disabled={isClearingCache}
              >
                {isClearingCache ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <RefreshCw className="h-4 w-4 mr-2" />
                )}
                Clear Cache
              </Button>
              <Button
                variant="destructive"
                className="flex-1"
                onClick={handleClearAllData}
                disabled={isClearingCache}
              >
                <Trash2 className="h-4 w-4 mr-2" />
                Clear All Data
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Image Quality Settings */}
        {settings && (
          <Card>
            <CardHeader>
              <CardTitle>Camera Settings</CardTitle>
              <CardDescription>
                Configure photo capture quality
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label>Image Quality</Label>
                <div className="flex gap-2">
                  {(['low', 'medium', 'high'] as const).map((quality) => (
                    <Button
                      key={quality}
                      variant={settings.imageQuality === quality ? 'default' : 'outline'}
                      size="sm"
                      className="flex-1 capitalize"
                      onClick={() => handleSettingChange('imageQuality', quality)}
                    >
                      {quality}
                    </Button>
                  ))}
                </div>
                <p className="text-xs text-muted-foreground">
                  {settings.imageQuality === 'high'
                    ? 'Best quality, larger file sizes'
                    : settings.imageQuality === 'medium'
                      ? 'Balanced quality and size'
                      : 'Smaller files, faster uploads'}
                </p>
              </div>
            </CardContent>
          </Card>
        )}
      </main>
    </div>
  );
}
