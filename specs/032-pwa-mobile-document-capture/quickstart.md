# Quickstart: PWA & Mobile + Document Capture

**Feature**: 032-pwa-mobile-document-capture
**Time to First Test**: ~2 hours

---

## Prerequisites

- Spec 030 (Client Portal) implemented
- HTTPS enabled (required for Service Workers)
- Firebase project created (for push notifications)

---

## Quick Start Steps

### 1. Install Dependencies

```bash
# Frontend PWA dependencies
cd frontend
npm install next-pwa workbox-precaching workbox-strategies
npm install idb-keyval idb
npm install jspdf

# Backend push notification dependencies
cd ../backend
uv add firebase-admin py-webauthn
```

### 2. Configure next-pwa

```javascript
// frontend/next.config.js
const withPWA = require('next-pwa')({
  dest: 'public',
  scope: '/portal',
  sw: 'portal-sw.js',
  register: true,
  skipWaiting: true,
  disable: process.env.NODE_ENV === 'development',
  runtimeCaching: [
    {
      urlPattern: /^https:\/\/api\.clairo\.com\.au\/api\/v1\/portal\/.*/,
      handler: 'NetworkFirst',
      options: {
        cacheName: 'portal-api',
        expiration: { maxEntries: 50, maxAgeSeconds: 86400 }
      }
    }
  ]
});

module.exports = withPWA({
  // existing Next.js config
});
```

### 3. Create Web Manifest

```json
// frontend/public/manifest.json
{
  "name": "Clairo Client Portal",
  "short_name": "Clairo",
  "description": "Respond to your accountant's document requests",
  "start_url": "/portal",
  "display": "standalone",
  "background_color": "#0f172a",
  "theme_color": "#3b82f6",
  "icons": [
    { "src": "/icons/icon-192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "/icons/icon-512.png", "sizes": "512x512", "type": "image/png" }
  ]
}
```

### 4. Add Manifest to Layout

```typescript
// frontend/src/app/portal/layout.tsx
import { Metadata } from 'next';

export const metadata: Metadata = {
  manifest: '/manifest.json',
  themeColor: '#3b82f6',
  appleWebApp: {
    capable: true,
    statusBarStyle: 'black-translucent',
    title: 'Clairo'
  }
};
```

### 5. Create Service Worker Hook

```typescript
// frontend/src/hooks/useServiceWorker.ts
import { useEffect, useState } from 'react';

export function useServiceWorker() {
  const [registration, setRegistration] = useState<ServiceWorkerRegistration | null>(null);
  const [updateAvailable, setUpdateAvailable] = useState(false);

  useEffect(() => {
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('/portal-sw.js', { scope: '/portal' })
        .then((reg) => {
          setRegistration(reg);
          reg.addEventListener('updatefound', () => {
            const newWorker = reg.installing;
            newWorker?.addEventListener('statechange', () => {
              if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                setUpdateAvailable(true);
              }
            });
          });
        });
    }
  }, []);

  const skipWaiting = () => {
    registration?.waiting?.postMessage({ type: 'SKIP_WAITING' });
  };

  return { registration, updateAvailable, skipWaiting };
}
```

### 6. Create Push Notification Hook

```typescript
// frontend/src/hooks/usePushNotifications.ts
import { useState, useCallback } from 'react';

export function usePushNotifications() {
  const [permission, setPermission] = useState<NotificationPermission>(
    typeof Notification !== 'undefined' ? Notification.permission : 'default'
  );

  const subscribe = useCallback(async () => {
    // Request permission
    const result = await Notification.requestPermission();
    setPermission(result);

    if (result !== 'granted') return null;

    // Get VAPID key
    const { publicKey } = await fetch('/api/portal/push/vapid-key').then(r => r.json());

    // Subscribe
    const registration = await navigator.serviceWorker.ready;
    const subscription = await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(publicKey)
    });

    // Send to server
    await fetch('/api/portal/push/subscribe', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        endpoint: subscription.endpoint,
        keys: {
          p256dh: arrayBufferToBase64(subscription.getKey('p256dh')),
          auth: arrayBufferToBase64(subscription.getKey('auth'))
        }
      })
    });

    return subscription;
  }, []);

  return { permission, subscribe };
}

function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = '='.repeat((4 - base64String.length % 4) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const rawData = window.atob(base64);
  return Uint8Array.from([...rawData].map(char => char.charCodeAt(0)));
}

function arrayBufferToBase64(buffer: ArrayBuffer | null): string {
  if (!buffer) return '';
  return btoa(String.fromCharCode(...new Uint8Array(buffer)));
}
```

### 7. Create Camera Capture Component

```typescript
// frontend/src/components/pwa/CameraCapture.tsx
'use client';

import { useRef, useState, useCallback } from 'react';
import { Camera, X, Check, RotateCcw } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface CameraCaptureProps {
  onCapture: (blob: Blob) => void;
  onClose: () => void;
}

export function CameraCapture({ onCapture, onClose }: CameraCaptureProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [capturedImage, setCapturedImage] = useState<Blob | null>(null);

  const startCamera = useCallback(async () => {
    try {
      const mediaStream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment', width: { ideal: 1920 } },
        audio: false
      });
      setStream(mediaStream);
      if (videoRef.current) {
        videoRef.current.srcObject = mediaStream;
      }
    } catch (error) {
      console.error('Camera access denied:', error);
    }
  }, []);

  const capture = useCallback(() => {
    if (!videoRef.current) return;

    const canvas = document.createElement('canvas');
    canvas.width = videoRef.current.videoWidth;
    canvas.height = videoRef.current.videoHeight;

    const ctx = canvas.getContext('2d');
    ctx?.drawImage(videoRef.current, 0, 0);

    canvas.toBlob((blob) => {
      if (blob) setCapturedImage(blob);
    }, 'image/jpeg', 0.85);
  }, []);

  const confirm = useCallback(() => {
    if (capturedImage) {
      onCapture(capturedImage);
      stream?.getTracks().forEach(track => track.stop());
    }
  }, [capturedImage, onCapture, stream]);

  const retake = useCallback(() => {
    setCapturedImage(null);
  }, []);

  // Start camera on mount
  useEffect(() => {
    startCamera();
    return () => {
      stream?.getTracks().forEach(track => track.stop());
    };
  }, [startCamera]);

  return (
    <div className="fixed inset-0 bg-black z-50 flex flex-col">
      {/* Camera preview or captured image */}
      <div className="flex-1 relative">
        {capturedImage ? (
          <img
            src={URL.createObjectURL(capturedImage)}
            alt="Captured"
            className="w-full h-full object-contain"
          />
        ) : (
          <video
            ref={videoRef}
            autoPlay
            playsInline
            className="w-full h-full object-cover"
          />
        )}
      </div>

      {/* Controls */}
      <div className="p-4 flex justify-center gap-4">
        {capturedImage ? (
          <>
            <Button variant="outline" onClick={retake}>
              <RotateCcw className="mr-2 h-4 w-4" />
              Retake
            </Button>
            <Button onClick={confirm}>
              <Check className="mr-2 h-4 w-4" />
              Use Photo
            </Button>
          </>
        ) : (
          <>
            <Button variant="outline" onClick={onClose}>
              <X className="mr-2 h-4 w-4" />
              Cancel
            </Button>
            <Button size="lg" onClick={capture}>
              <Camera className="mr-2 h-4 w-4" />
              Capture
            </Button>
          </>
        )}
      </div>
    </div>
  );
}
```

### 8. Create Backend Push Service

```python
# backend/app/modules/notifications/push/service.py
from firebase_admin import messaging
from uuid import UUID
from .repository import PushSubscriptionRepository

class PushNotificationService:
    def __init__(self, subscription_repo: PushSubscriptionRepository):
        self.subscription_repo = subscription_repo

    async def send_to_client(
        self,
        client_id: UUID,
        title: str,
        body: str,
        data: dict | None = None,
        link: str | None = None
    ) -> list[str]:
        """Send push notification to all devices for a client."""
        subscriptions = await self.subscription_repo.get_active_by_client(client_id)

        if not subscriptions:
            return []

        tokens = [sub.endpoint.split('/')[-1] for sub in subscriptions]

        message = messaging.MulticastMessage(
            notification=messaging.Notification(title=title, body=body),
            data=data or {},
            webpush=messaging.WebpushConfig(
                fcm_options=messaging.WebpushFCMOptions(link=link)
            ) if link else None,
            tokens=tokens
        )

        response = messaging.send_each_for_multicast(message)

        # Handle failures - mark subscriptions as inactive
        for idx, result in enumerate(response.responses):
            if not result.success:
                await self.subscription_repo.mark_inactive(subscriptions[idx].id)

        return [r.message_id for r in response.responses if r.success]
```

### 9. Create IndexedDB Upload Queue

```typescript
// frontend/src/lib/pwa/upload-queue.ts
import { openDB, DBSchema, IDBPDatabase } from 'idb';

interface UploadQueueItem {
  id: string;
  requestId: string;
  fileName: string;
  mimeType: string;
  fileData: ArrayBuffer;
  fileSize: number;
  status: 'queued' | 'uploading' | 'failed' | 'completed';
  retryCount: number;
  createdAt: number;
}

interface ClairoDB extends DBSchema {
  'upload-queue': {
    key: string;
    value: UploadQueueItem;
    indexes: { 'by-status': string };
  };
}

let dbPromise: Promise<IDBPDatabase<ClairoDB>> | null = null;

function getDB() {
  if (!dbPromise) {
    dbPromise = openDB<ClairoDB>('clairo-portal', 1, {
      upgrade(db) {
        const store = db.createObjectStore('upload-queue', { keyPath: 'id' });
        store.createIndex('by-status', 'status');
      }
    });
  }
  return dbPromise;
}

export async function queueUpload(
  requestId: string,
  file: Blob,
  fileName: string
): Promise<string> {
  const db = await getDB();
  const id = crypto.randomUUID();

  await db.put('upload-queue', {
    id,
    requestId,
    fileName,
    mimeType: file.type,
    fileData: await file.arrayBuffer(),
    fileSize: file.size,
    status: 'queued',
    retryCount: 0,
    createdAt: Date.now()
  });

  // Trigger background sync if available
  const registration = await navigator.serviceWorker.ready;
  await registration.sync?.register('upload-queue');

  return id;
}

export async function getQueuedUploads(): Promise<UploadQueueItem[]> {
  const db = await getDB();
  return db.getAllFromIndex('upload-queue', 'by-status', 'queued');
}

export async function processQueue(): Promise<void> {
  const items = await getQueuedUploads();

  for (const item of items) {
    await uploadItem(item);
  }
}

async function uploadItem(item: UploadQueueItem): Promise<void> {
  const db = await getDB();

  try {
    item.status = 'uploading';
    await db.put('upload-queue', item);

    // Get presigned URL
    const response = await fetch(`/api/portal/requests/${item.requestId}/upload-url`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filename: item.fileName, mimeType: item.mimeType })
    });
    const { uploadUrl } = await response.json();

    // Upload to S3
    await fetch(uploadUrl, {
      method: 'PUT',
      body: item.fileData,
      headers: { 'Content-Type': item.mimeType }
    });

    item.status = 'completed';
    await db.put('upload-queue', item);

  } catch (error) {
    item.retryCount++;
    item.status = item.retryCount >= 3 ? 'failed' : 'queued';
    await db.put('upload-queue', item);
  }
}
```

---

## Test Scenarios

### 1. PWA Installation

```gherkin
Scenario: Install PWA from portal
  Given I am a business owner on the portal
  And I have visited the portal at least twice
  When I see the "Add to Home Screen" prompt
  And I tap "Install"
  Then the app should install to my home screen
  And opening the app shows the portal without browser chrome
```

### 2. Push Notifications

```gherkin
Scenario: Receive push notification for new request
  Given I have installed the PWA
  And I have enabled push notifications
  When my accountant creates a new document request
  Then I should receive a push notification within 2 seconds
  And tapping the notification should open the request detail
```

### 3. Camera Document Capture

```gherkin
Scenario: Capture document with camera
  Given I am viewing a document request
  When I tap "Take Photo"
  Then the camera should open
  When I capture a photo
  Then I should see a preview with quality feedback
  When I tap "Use Photo"
  Then the photo should upload to the request
```

### 4. Offline Upload Queue

```gherkin
Scenario: Queue upload when offline
  Given I am viewing a document request
  And I am offline
  When I capture and submit a photo
  Then I should see "Queued for upload" message
  And the photo should be stored locally
  When I come back online
  Then the photo should automatically upload
  And I should see a success notification
```

### 5. Multi-Page Scanning

```gherkin
Scenario: Scan multi-page document
  Given I am capturing a document
  When I capture the first page
  And I tap "Add Page"
  And I capture two more pages
  Then I should see 3 page thumbnails
  When I tap "Done"
  Then a PDF should be generated with all 3 pages
  And the PDF should upload to the request
```

---

## Verification Checklist

### PWA Basics
- [ ] Manifest loads correctly (check DevTools > Application)
- [ ] Service worker registers successfully
- [ ] "Add to Home Screen" prompt appears
- [ ] App opens in standalone mode

### Push Notifications
- [ ] VAPID key endpoint returns public key
- [ ] Push subscription saves to database
- [ ] Test notification received on device
- [ ] Notification click opens correct page

### Camera Capture
- [ ] Camera permission prompt appears
- [ ] Back camera selected by default on mobile
- [ ] Image quality warnings display correctly
- [ ] Compressed image under 2MB

### Offline Support
- [ ] Dashboard loads when offline (cached)
- [ ] Upload queues correctly when offline
- [ ] Queue processes when back online
- [ ] Failed uploads retry automatically

---

## Common Issues

### 1. Service Worker Not Registering

```typescript
// Check scope is correct
navigator.serviceWorker.register('/portal-sw.js', { scope: '/portal' });

// Ensure HTTPS (required for SW)
// localhost is the exception for development
```

### 2. Push Notifications Not Working

```bash
# Verify Firebase config
NEXT_PUBLIC_FIREBASE_API_KEY=...
NEXT_PUBLIC_FIREBASE_PROJECT_ID=...
NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID=...

# Check browser console for errors
# Verify VAPID keys match frontend and backend
```

### 3. Camera Not Opening on iOS

```typescript
// iOS requires user gesture to open camera
// Ensure getUserMedia is called from button click handler
<button onClick={() => openCamera()}>Take Photo</button>
```

### 4. IndexedDB Quota Exceeded

```typescript
// Implement cleanup for old entries
async function cleanupOldUploads() {
  const db = await getDB();
  const completed = await db.getAllFromIndex('upload-queue', 'by-status', 'completed');
  const oneWeekAgo = Date.now() - 7 * 24 * 60 * 60 * 1000;

  for (const item of completed) {
    if (item.createdAt < oneWeekAgo) {
      await db.delete('upload-queue', item.id);
    }
  }
}
```

---

## Related Files

| File | Purpose |
|------|---------|
| `frontend/next.config.js` | PWA configuration |
| `frontend/public/manifest.json` | Web app manifest |
| `frontend/src/hooks/useServiceWorker.ts` | SW registration |
| `frontend/src/hooks/usePushNotifications.ts` | Push API wrapper |
| `frontend/src/lib/pwa/upload-queue.ts` | IndexedDB queue |
| `frontend/src/components/pwa/CameraCapture.tsx` | Camera component |
| `backend/app/modules/notifications/push/` | Push notification service |
