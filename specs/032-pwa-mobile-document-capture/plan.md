# Implementation Plan: PWA & Mobile + Document Capture

**Feature**: 032-pwa-mobile-document-capture
**Status**: PLANNING
**Branch**: `032-pwa-mobile-document-capture`

---

## Technical Context

### Existing Infrastructure

| Component | Current State | Spec 032 Impact |
|-----------|---------------|-----------------|
| Frontend Framework | Next.js 14 App Router | Add PWA configuration |
| Portal Auth | Magic link JWT (Spec 030) | Add WebAuthn support |
| Document Upload | S3 presigned URLs | Add offline queue |
| Notifications | Email via Resend | Add push notifications |
| Database | PostgreSQL | Add push subscriptions |

### Technology Choices

| Component | Choice | Rationale |
|-----------|--------|-----------|
| PWA Framework | next-pwa + Workbox | Official Next.js PWA support |
| Push Service | Firebase Cloud Messaging | Cross-platform, free tier |
| IndexedDB | idb-keyval | Simple key-value, small bundle |
| PDF Generation | jsPDF + html2canvas | No backend dependency |
| Camera API | MediaDevices.getUserMedia | Native browser API |
| Image Processing | Browser Canvas API | No external library |

---

## Constitution Check

### Pre-Design Gates

| Gate | Status | Notes |
|------|--------|-------|
| Follows modular structure | PASS | New pwa/ module in frontend |
| Multi-tenant compatible | PASS | Push subs tied to client_id |
| Audit-first design | PASS | Install/permission events logged |
| Repository pattern | PASS | Push subscription repository |

### Standards Applied

- TypeScript strict mode for all PWA code
- Zod schemas for service worker messages
- Error boundaries for offline fallbacks
- Progressive enhancement (works without SW)

---

## Architecture

### Frontend Structure

```
frontend/src/
├── app/
│   └── portal/
│       ├── manifest.json          # PWA manifest
│       ├── sw.ts                  # Service worker entry
│       └── ...existing pages
│
├── components/
│   └── pwa/
│       ├── InstallPrompt.tsx      # Add to home screen
│       ├── OfflineIndicator.tsx   # Offline status
│       ├── QueueStatus.tsx        # Upload queue
│       └── CameraCapture.tsx      # Document capture
│
├── hooks/
│   ├── useServiceWorker.ts        # SW registration
│   ├── usePushNotifications.ts    # Push API wrapper
│   ├── useOfflineQueue.ts         # IndexedDB queue
│   ├── useCamera.ts               # Camera capture
│   └── useNetworkStatus.ts        # Online/offline
│
├── lib/
│   └── pwa/
│       ├── sw-utils.ts            # Service worker utilities
│       ├── cache-strategies.ts    # Workbox strategies
│       ├── indexed-db.ts          # IndexedDB wrapper
│       ├── image-processor.ts     # Compression/rotation
│       └── pdf-generator.ts       # Multi-page PDF
│
└── workers/
    └── service-worker.ts          # Compiled SW
```

### Backend Structure

```
backend/app/modules/
└── notifications/
    ├── push/
    │   ├── __init__.py
    │   ├── models.py              # PushSubscription model
    │   ├── schemas.py             # Subscription DTOs
    │   ├── repository.py          # Subscription storage
    │   ├── service.py             # FCM integration
    │   └── router.py              # Push endpoints
    │
    └── ...existing notification code
```

---

## Service Worker Strategy

### Caching Strategy

| Route Pattern | Strategy | Cache Name |
|---------------|----------|------------|
| /portal/_next/static/* | CacheFirst | static-v1 |
| /portal/api/requests | NetworkFirst | api-v1 |
| /portal/api/documents | NetworkOnly | - |
| /portal/* (pages) | StaleWhileRevalidate | pages-v1 |

### Background Sync

```typescript
// Service worker handles failed uploads
self.addEventListener('sync', (event) => {
  if (event.tag === 'upload-queue') {
    event.waitUntil(processUploadQueue());
  }
});

// Queue structure in IndexedDB
interface QueuedUpload {
  id: string;
  requestId: string;
  file: Blob;
  filename: string;
  mimeType: string;
  createdAt: Date;
  retryCount: number;
  status: 'queued' | 'uploading' | 'failed';
}
```

---

## Push Notification Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                          Backend                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  DocumentRequestService              PushNotificationService         │
│  ┌────────────────────┐             ┌─────────────────────┐         │
│  │ create_request()   │────────────►│ send_notification() │         │
│  └────────────────────┘             └──────────┬──────────┘         │
│                                                 │                    │
│                                                 ▼                    │
│                                     ┌─────────────────────┐         │
│                                     │ PushSubscriptionRepo │         │
│                                     │ get_by_client_id()  │         │
│                                     └──────────┬──────────┘         │
│                                                 │                    │
│                                                 ▼                    │
│                                     ┌─────────────────────┐         │
│                                     │ Firebase Admin SDK  │         │
│                                     │ send_multicast()    │         │
│                                     └──────────┬──────────┘         │
│                                                 │                    │
└─────────────────────────────────────────────────┼────────────────────┘
                                                  │
                                                  ▼
                                     ┌─────────────────────┐
                                     │ Firebase Cloud      │
                                     │ Messaging (FCM)     │
                                     └──────────┬──────────┘
                                                │
                    ┌───────────────────────────┼───────────────────────┐
                    │                           │                       │
                    ▼                           ▼                       ▼
            ┌──────────────┐          ┌──────────────┐         ┌──────────────┐
            │ iOS Safari   │          │ Chrome       │         │ Firefox      │
            │ Push Service │          │ Push Service │         │ Push Service │
            └──────────────┘          └──────────────┘         └──────────────┘
```

---

## Document Capture Pipeline

```
┌────────────────────────────────────────────────────────────────┐
│                    CameraCapture Component                      │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. Open Camera                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ navigator.mediaDevices.getUserMedia({                    │   │
│  │   video: { facingMode: 'environment', width: 1920 }     │   │
│  │ })                                                       │   │
│  └─────────────────────────────────────────────────────────┘   │
│                           │                                     │
│                           ▼                                     │
│  2. Capture Frame                                               │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ canvas.drawImage(video, 0, 0)                           │   │
│  │ canvas.toBlob(callback, 'image/jpeg', 0.85)             │   │
│  └─────────────────────────────────────────────────────────┘   │
│                           │                                     │
│                           ▼                                     │
│  3. Process Image                                               │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ - Read EXIF orientation                                  │   │
│  │ - Rotate canvas if needed                                │   │
│  │ - Scale to max 2000px width                              │   │
│  │ - Compress to <2MB                                       │   │
│  └─────────────────────────────────────────────────────────┘   │
│                           │                                     │
│                           ▼                                     │
│  4. Quality Check                                               │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ - Resolution check (≥1000px)                             │   │
│  │ - Blur detection (edge analysis)                         │   │
│  │ - Brightness check (histogram)                           │   │
│  └─────────────────────────────────────────────────────────┘   │
│                           │                                     │
│              ┌────────────┴────────────┐                       │
│              ▼                         ▼                       │
│    [Single Page]              [Multi-Page]                     │
│         │                          │                           │
│         ▼                          ▼                           │
│  ┌──────────────┐         ┌──────────────┐                     │
│  │ Direct Upload│         │ Store to IDB │                     │
│  │ to S3        │         │ Add More     │                     │
│  └──────────────┘         └──────┬───────┘                     │
│                                  │                              │
│                                  ▼                              │
│                         ┌──────────────┐                        │
│                         │ Generate PDF │                        │
│                         │ (jsPDF)      │                        │
│                         └──────┬───────┘                        │
│                                │                                │
│                                ▼                                │
│                         ┌──────────────┐                        │
│                         │ Upload PDF   │                        │
│                         └──────────────┘                        │
└────────────────────────────────────────────────────────────────┘
```

---

## Offline Queue Design

### IndexedDB Schema

```typescript
// Database: clairo-portal
// Store: upload-queue

interface UploadQueueItem {
  id: string;                    // UUID
  requestId: string;             // Document request ID
  clientId: string;              // Client ID
  fileName: string;              // Original filename
  mimeType: string;              // image/jpeg or application/pdf
  fileData: ArrayBuffer;         // File content
  fileSize: number;              // Size in bytes
  status: 'queued' | 'uploading' | 'failed' | 'completed';
  retryCount: number;            // Max 3 retries
  createdAt: number;             // Timestamp
  lastAttempt: number | null;    // Last upload attempt
  errorMessage: string | null;   // Last error
}

// Store: cached-requests
interface CachedRequest {
  id: string;                    // Request ID
  data: DocumentRequest;         // Full request object
  cachedAt: number;              // Timestamp
}
```

### Queue Processing

```typescript
async function processUploadQueue() {
  const db = await openDB('clairo-portal');
  const items = await db.getAllFromIndex('upload-queue', 'status', 'queued');

  for (const item of items) {
    if (item.retryCount >= 3) {
      item.status = 'failed';
      await db.put('upload-queue', item);
      continue;
    }

    try {
      item.status = 'uploading';
      item.lastAttempt = Date.now();
      await db.put('upload-queue', item);

      // Get presigned URL
      const { uploadUrl } = await fetch(`/api/portal/requests/${item.requestId}/upload-url`, {
        method: 'POST',
        body: JSON.stringify({ filename: item.fileName, mimeType: item.mimeType })
      }).then(r => r.json());

      // Upload to S3
      await fetch(uploadUrl, {
        method: 'PUT',
        body: item.fileData,
        headers: { 'Content-Type': item.mimeType }
      });

      item.status = 'completed';
      await db.put('upload-queue', item);

      // Notify user
      self.registration.showNotification('Upload Complete', {
        body: `${item.fileName} uploaded successfully`,
        icon: '/icons/success.png'
      });

    } catch (error) {
      item.retryCount++;
      item.status = 'queued';
      item.errorMessage = error.message;
      await db.put('upload-queue', item);
    }
  }
}
```

---

## PWA Manifest

```json
{
  "name": "Clairo Client Portal",
  "short_name": "Clairo",
  "description": "Respond to your accountant's document requests",
  "start_url": "/portal",
  "display": "standalone",
  "background_color": "#0f172a",
  "theme_color": "#3b82f6",
  "orientation": "portrait-primary",
  "icons": [
    {
      "src": "/icons/icon-72.png",
      "sizes": "72x72",
      "type": "image/png"
    },
    {
      "src": "/icons/icon-192.png",
      "sizes": "192x192",
      "type": "image/png",
      "purpose": "any maskable"
    },
    {
      "src": "/icons/icon-512.png",
      "sizes": "512x512",
      "type": "image/png",
      "purpose": "any maskable"
    }
  ],
  "screenshots": [
    {
      "src": "/screenshots/dashboard.png",
      "sizes": "1080x1920",
      "type": "image/png",
      "form_factor": "narrow"
    }
  ],
  "categories": ["business", "finance"],
  "lang": "en-AU"
}
```

---

## API Endpoints

### Push Subscription

```yaml
POST /api/portal/push/subscribe
  - Register push subscription
  - Body: { endpoint, keys: { p256dh, auth } }

DELETE /api/portal/push/unsubscribe
  - Remove push subscription

GET /api/portal/push/vapid-key
  - Get VAPID public key for subscription
```

### Upload Queue Status

```yaml
GET /api/portal/uploads/queue
  - Get queued uploads for current client

DELETE /api/portal/uploads/queue/{id}
  - Cancel queued upload
```

### Installation Tracking

```yaml
POST /api/portal/analytics/install
  - Track PWA installation event
  - Body: { installed: boolean }

POST /api/portal/analytics/permission
  - Track push permission grant
  - Body: { granted: boolean }
```

---

## Implementation Phases

### Phase 1: PWA Foundation (Days 1-2)

1. Configure next-pwa
2. Create manifest.json
3. Set up service worker with Workbox
4. Implement cache strategies
5. Add install prompt component

### Phase 2: Push Notifications (Days 2-3)

1. Set up Firebase project
2. Create push subscription model
3. Implement subscription endpoints
4. Add push notification service
5. Integrate with document request creation

### Phase 3: Offline Support (Days 3-4)

1. Implement IndexedDB wrapper
2. Create upload queue
3. Add background sync
4. Build offline indicator
5. Cache API responses

### Phase 4: Camera & Capture (Days 4-5)

1. Build camera capture component
2. Implement image processing
3. Add quality checks
4. Create multi-page scanner
5. Integrate PDF generation

### Phase 5: Polish & Analytics (Days 5-7)

1. Add biometric authentication
2. Create settings page
3. Implement installation tracking
4. Test across devices
5. Performance optimization

---

## Testing Strategy

### Unit Tests

- Image processor functions
- PDF generation
- IndexedDB operations
- Push subscription serialization

### Integration Tests

- Service worker registration
- Push notification delivery
- Offline queue processing
- Camera permissions flow

### E2E Tests

- Install PWA flow
- Enable notifications flow
- Capture and upload document
- Offline queue sync

### Device Testing

| Device | Browser | Priority |
|--------|---------|----------|
| iPhone 14 | Safari | P1 |
| Samsung S23 | Chrome | P1 |
| Pixel 7 | Chrome | P1 |
| iPad | Safari | P2 |
| MacBook | Chrome | P2 |

---

## Environment Variables

```bash
# Firebase
NEXT_PUBLIC_FIREBASE_API_KEY=...
NEXT_PUBLIC_FIREBASE_PROJECT_ID=...
NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID=...
FIREBASE_SERVICE_ACCOUNT=...

# VAPID Keys
VAPID_PUBLIC_KEY=...
VAPID_PRIVATE_KEY=...
VAPID_SUBJECT=mailto:support@clairo.ai
```

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| iOS PWA limitations | Medium | Document limitations, test thoroughly |
| Push delivery failures | Medium | Email fallback for critical notifications |
| IndexedDB quota | Low | Monitor usage, clean old entries |
| Camera permission denied | Low | Clear instructions, file picker fallback |
| Service worker update | Medium | Skipwaiting prompt, version tracking |

---

## Success Criteria

| Criteria | Target |
|----------|--------|
| PWA Lighthouse score | >90 |
| Offline functionality | Works without network |
| Push delivery rate | >95% |
| Camera launch time | <500ms |
| Queue sync success | >99% |
