# Research: PWA & Mobile + Document Capture

**Feature**: 032-pwa-mobile-document-capture
**Research Date**: January 2026

---

## 1. PWA Framework Options

### Decision: next-pwa with Workbox

**Rationale**: Official support for Next.js, actively maintained, Workbox integration provides production-ready caching strategies.

### Alternatives Considered

| Option | Pros | Cons | Verdict |
|--------|------|------|---------|
| next-pwa | Official, Workbox built-in, zero-config | Less control over SW | **SELECTED** |
| serwist | Modern next-pwa fork | Newer, less community | Consider for future |
| Manual Workbox | Full control | More setup work | Too complex |
| Custom SW | Complete flexibility | Must handle all edge cases | Not worth effort |

### next-pwa Configuration

```javascript
// next.config.js
const withPWA = require('next-pwa')({
  dest: 'public',
  scope: '/portal',
  sw: 'portal-sw.js',
  register: true,
  skipWaiting: true,
  disable: process.env.NODE_ENV === 'development',
  runtimeCaching: [
    {
      urlPattern: /^https:\/\/api\.clairo\.com\.au\/.*$/,
      handler: 'NetworkFirst',
      options: {
        cacheName: 'api-cache',
        expiration: { maxEntries: 50, maxAgeSeconds: 24 * 60 * 60 }
      }
    }
  ]
});

module.exports = withPWA({
  // Next.js config
});
```

### iOS PWA Limitations (2026)

- No background sync (must use periodic sync workaround)
- Push notifications require iOS 16.4+ in standalone mode
- No BadgeAPI support
- Storage quota varies by device
- Must use Apple-specific meta tags

```html
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<link rel="apple-touch-icon" href="/icons/apple-touch-icon.png">
```

---

## 2. Push Notification Service

### Decision: Firebase Cloud Messaging (FCM)

**Rationale**: Free tier sufficient for client portal use, cross-platform support, reliable delivery infrastructure.

### Alternatives Considered

| Option | Pros | Cons | Verdict |
|--------|------|------|---------|
| Firebase (FCM) | Free, cross-platform, reliable | Google ecosystem | **SELECTED** |
| OneSignal | Easy setup, analytics | Paid for features | Overkill |
| Pusher | Real-time features | Pricing | Already have WS |
| Custom VAPID | Full control | Must manage infra | Too complex |
| AWS SNS | AWS ecosystem | Pricing model | Less suited |

### FCM Integration

```typescript
// Backend: firebase-admin
import * as admin from 'firebase-admin';

admin.initializeApp({
  credential: admin.credential.cert(serviceAccount)
});

async function sendPushNotification(
  tokens: string[],
  notification: { title: string; body: string },
  data: Record<string, string>
) {
  const message = {
    notification,
    data,
    tokens,
    webpush: {
      fcmOptions: {
        link: data.link
      }
    }
  };

  const response = await admin.messaging().sendEachForMulticast(message);
  return response;
}
```

```typescript
// Frontend: firebase/messaging
import { getMessaging, getToken, onMessage } from 'firebase/messaging';

async function subscribeToPush() {
  const messaging = getMessaging();
  const token = await getToken(messaging, {
    vapidKey: process.env.NEXT_PUBLIC_VAPID_KEY
  });

  // Send token to backend
  await fetch('/api/portal/push/subscribe', {
    method: 'POST',
    body: JSON.stringify({ token })
  });

  // Handle foreground messages
  onMessage(messaging, (payload) => {
    showNotificationToast(payload);
  });
}
```

### VAPID Key Generation

```bash
# Generate VAPID keys
npx web-push generate-vapid-keys

# Output:
# Public Key: BEl62iUYgU...
# Private Key: 7L7VLd...
```

---

## 3. IndexedDB Strategy

### Decision: idb-keyval for simple storage, idb for complex queries

**Rationale**: idb-keyval is tiny (600 bytes) for simple key-value, idb provides full IndexedDB when needed.

### Storage Structure

```typescript
import { openDB, DBSchema } from 'idb';

interface ClairoDB extends DBSchema {
  'upload-queue': {
    key: string;
    value: UploadQueueItem;
    indexes: {
      'by-status': string;
      'by-request': string;
    };
  };
  'cached-requests': {
    key: string;
    value: CachedRequest;
    indexes: {
      'by-cached-at': number;
    };
  };
  'push-subscription': {
    key: 'current';
    value: PushSubscription;
  };
}

async function initDB() {
  return openDB<ClairoDB>('clairo-portal', 1, {
    upgrade(db) {
      // Upload queue store
      const uploadStore = db.createObjectStore('upload-queue', { keyPath: 'id' });
      uploadStore.createIndex('by-status', 'status');
      uploadStore.createIndex('by-request', 'requestId');

      // Cached requests store
      const requestStore = db.createObjectStore('cached-requests', { keyPath: 'id' });
      requestStore.createIndex('by-cached-at', 'cachedAt');

      // Push subscription store
      db.createObjectStore('push-subscription');
    }
  });
}
```

### Storage Limits

| Browser | Default Quota | Notes |
|---------|---------------|-------|
| Chrome | 60% of disk | Persistent if granted |
| Firefox | 50% of disk | Evicted under pressure |
| Safari | ~1GB | Evicted after 7 days inactivity |
| Safari iOS | ~50MB per origin | Very limited |

### Quota Management

```typescript
async function checkStorageQuota() {
  if ('storage' in navigator && 'estimate' in navigator.storage) {
    const { usage, quota } = await navigator.storage.estimate();
    const percentUsed = (usage / quota * 100).toFixed(2);

    if (percentUsed > 80) {
      await cleanupOldEntries();
    }

    return { usage, quota, percentUsed };
  }
  return null;
}

async function cleanupOldEntries() {
  const db = await initDB();
  const oneWeekAgo = Date.now() - 7 * 24 * 60 * 60 * 1000;

  // Remove old cached requests
  const oldRequests = await db.getAllFromIndex(
    'cached-requests',
    'by-cached-at',
    IDBKeyRange.upperBound(oneWeekAgo)
  );

  for (const request of oldRequests) {
    await db.delete('cached-requests', request.id);
  }

  // Remove completed uploads
  const completed = await db.getAllFromIndex(
    'upload-queue',
    'by-status',
    'completed'
  );

  for (const item of completed) {
    await db.delete('upload-queue', item.id);
  }
}
```

---

## 4. Camera Integration

### Decision: MediaDevices API with Canvas processing

**Rationale**: Native browser APIs, no external dependencies, good cross-browser support.

### Camera Access Pattern

```typescript
interface CameraConfig {
  facingMode: 'user' | 'environment';
  width: { ideal: number };
  height: { ideal: number };
}

async function openCamera(config: CameraConfig): Promise<MediaStream> {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: {
        facingMode: config.facingMode,
        width: config.width,
        height: config.height
      },
      audio: false
    });
    return stream;
  } catch (error) {
    if (error.name === 'NotAllowedError') {
      throw new Error('Camera permission denied');
    }
    if (error.name === 'NotFoundError') {
      throw new Error('No camera found');
    }
    throw error;
  }
}

async function captureFrame(video: HTMLVideoElement): Promise<Blob> {
  const canvas = document.createElement('canvas');
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;

  const ctx = canvas.getContext('2d');
  ctx.drawImage(video, 0, 0);

  return new Promise((resolve) => {
    canvas.toBlob(resolve, 'image/jpeg', 0.85);
  });
}
```

### EXIF Orientation Handling

```typescript
async function getExifOrientation(file: Blob): Promise<number> {
  const buffer = await file.slice(0, 65536).arrayBuffer();
  const view = new DataView(buffer);

  if (view.getUint16(0, false) !== 0xFFD8) return 1; // Not JPEG

  let offset = 2;
  while (offset < view.byteLength) {
    const marker = view.getUint16(offset, false);
    offset += 2;

    if (marker === 0xFFE1) { // APP1 (EXIF)
      const exifLength = view.getUint16(offset, false);
      const exifData = new DataView(buffer, offset + 2, exifLength - 2);

      // Parse TIFF header and find orientation tag
      // ... (detailed parsing)
      return orientation;
    }

    offset += view.getUint16(offset, false);
  }

  return 1; // Default: no rotation
}

function rotateCanvas(
  canvas: HTMLCanvasElement,
  ctx: CanvasRenderingContext2D,
  orientation: number
): void {
  const { width, height } = canvas;

  switch (orientation) {
    case 3: // 180°
      ctx.rotate(Math.PI);
      ctx.translate(-width, -height);
      break;
    case 6: // 90° CW
      canvas.width = height;
      canvas.height = width;
      ctx.rotate(Math.PI / 2);
      ctx.translate(0, -height);
      break;
    case 8: // 90° CCW
      canvas.width = height;
      canvas.height = width;
      ctx.rotate(-Math.PI / 2);
      ctx.translate(-width, 0);
      break;
  }
}
```

---

## 5. Image Compression

### Decision: Canvas-based compression with quality iteration

**Rationale**: No external dependencies, good quality control, works in all browsers.

### Compression Algorithm

```typescript
interface CompressionResult {
  blob: Blob;
  width: number;
  height: number;
  originalSize: number;
  compressedSize: number;
}

async function compressImage(
  file: Blob,
  maxWidth: number = 2000,
  maxSizeKB: number = 2048
): Promise<CompressionResult> {
  const img = await createImageBitmap(file);
  const originalSize = file.size;

  // Calculate new dimensions
  let { width, height } = img;
  if (width > maxWidth) {
    height = (height / width) * maxWidth;
    width = maxWidth;
  }

  // Create canvas
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(img, 0, 0, width, height);

  // Iterative quality reduction
  let quality = 0.92;
  let blob: Blob;

  do {
    blob = await new Promise<Blob>((resolve) => {
      canvas.toBlob(resolve, 'image/jpeg', quality);
    });
    quality -= 0.05;
  } while (blob.size > maxSizeKB * 1024 && quality > 0.5);

  return {
    blob,
    width,
    height,
    originalSize,
    compressedSize: blob.size
  };
}
```

### Quality Check Implementation

```typescript
interface QualityResult {
  isBlurry: boolean;
  isDark: boolean;
  isLowRes: boolean;
  blurScore: number;
  brightness: number;
  resolution: { width: number; height: number };
  suggestions: string[];
}

async function checkImageQuality(image: ImageData): Promise<QualityResult> {
  const { width, height, data } = image;
  const suggestions: string[] = [];

  // Resolution check
  const isLowRes = width < 1000;
  if (isLowRes) {
    suggestions.push('Move closer to the document for better quality');
  }

  // Brightness check (average luminance)
  let totalBrightness = 0;
  for (let i = 0; i < data.length; i += 4) {
    const r = data[i];
    const g = data[i + 1];
    const b = data[i + 2];
    totalBrightness += (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  }
  const brightness = totalBrightness / (width * height);
  const isDark = brightness < 0.2;
  if (isDark) {
    suggestions.push('Add more light to the document');
  }

  // Blur detection (Laplacian variance)
  const blurScore = calculateLaplacianVariance(image);
  const isBlurry = blurScore < 100;
  if (isBlurry) {
    suggestions.push('Hold the camera steady and ensure focus');
  }

  return {
    isBlurry,
    isDark,
    isLowRes,
    blurScore,
    brightness,
    resolution: { width, height },
    suggestions
  };
}

function calculateLaplacianVariance(image: ImageData): number {
  const { width, height, data } = image;
  const grayscale = new Float32Array(width * height);

  // Convert to grayscale
  for (let i = 0; i < data.length; i += 4) {
    const idx = i / 4;
    grayscale[idx] = 0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2];
  }

  // Apply Laplacian kernel
  let variance = 0;
  for (let y = 1; y < height - 1; y++) {
    for (let x = 1; x < width - 1; x++) {
      const idx = y * width + x;
      const laplacian =
        -grayscale[idx - width] +
        -grayscale[idx - 1] +
        4 * grayscale[idx] +
        -grayscale[idx + 1] +
        -grayscale[idx + width];
      variance += laplacian * laplacian;
    }
  }

  return variance / ((width - 2) * (height - 2));
}
```

---

## 6. PDF Generation

### Decision: jsPDF for client-side PDF creation

**Rationale**: Mature library, no server dependency, good image support, reasonable file sizes.

### Multi-Page PDF Generation

```typescript
import { jsPDF } from 'jspdf';

interface PageImage {
  id: string;
  blob: Blob;
  width: number;
  height: number;
}

async function generatePDF(pages: PageImage[], filename: string): Promise<Blob> {
  // A4 dimensions in mm
  const A4_WIDTH = 210;
  const A4_HEIGHT = 297;

  const pdf = new jsPDF({
    orientation: 'portrait',
    unit: 'mm',
    format: 'a4'
  });

  for (let i = 0; i < pages.length; i++) {
    if (i > 0) {
      pdf.addPage();
    }

    const page = pages[i];
    const imageData = await blobToDataURL(page.blob);

    // Calculate dimensions to fit A4
    const aspectRatio = page.width / page.height;
    let imgWidth = A4_WIDTH - 20; // 10mm margins
    let imgHeight = imgWidth / aspectRatio;

    if (imgHeight > A4_HEIGHT - 20) {
      imgHeight = A4_HEIGHT - 20;
      imgWidth = imgHeight * aspectRatio;
    }

    // Center on page
    const x = (A4_WIDTH - imgWidth) / 2;
    const y = (A4_HEIGHT - imgHeight) / 2;

    pdf.addImage(imageData, 'JPEG', x, y, imgWidth, imgHeight);
  }

  return pdf.output('blob');
}

async function blobToDataURL(blob: Blob): Promise<string> {
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onloadend = () => resolve(reader.result as string);
    reader.readAsDataURL(blob);
  });
}
```

### PDF Size Optimization

```typescript
async function optimizePDF(pages: PageImage[]): Promise<PageImage[]> {
  const optimized: PageImage[] = [];

  for (const page of pages) {
    // Target: 150 DPI for A4 width = ~1240px
    const targetWidth = 1240;

    if (page.width > targetWidth) {
      const compressed = await compressImage(page.blob, targetWidth, 500);
      optimized.push({
        ...page,
        blob: compressed.blob,
        width: compressed.width,
        height: compressed.height
      });
    } else {
      optimized.push(page);
    }
  }

  return optimized;
}
```

---

## 7. Background Sync

### Decision: Background Sync API with Service Worker

**Rationale**: Native browser API, handles network restoration automatically, works in background.

### Implementation

```typescript
// In service worker
self.addEventListener('sync', (event: SyncEvent) => {
  if (event.tag === 'upload-queue') {
    event.waitUntil(processUploadQueue());
  }
});

// In main app
async function queueUpload(item: UploadQueueItem): Promise<void> {
  const db = await initDB();
  await db.put('upload-queue', item);

  // Request background sync
  const registration = await navigator.serviceWorker.ready;
  await registration.sync.register('upload-queue');
}
```

### Periodic Sync (iOS Workaround)

```typescript
// For iOS which doesn't support background sync
self.addEventListener('periodicsync', (event: PeriodicSyncEvent) => {
  if (event.tag === 'check-queue') {
    event.waitUntil(processUploadQueue());
  }
});

// Request periodic sync (if supported)
async function setupPeriodicSync(): Promise<void> {
  const registration = await navigator.serviceWorker.ready;

  if ('periodicSync' in registration) {
    const status = await navigator.permissions.query({
      name: 'periodic-background-sync' as PermissionName
    });

    if (status.state === 'granted') {
      await registration.periodicSync.register('check-queue', {
        minInterval: 60 * 60 * 1000 // 1 hour
      });
    }
  }
}
```

---

## 8. WebAuthn Integration

### Decision: WebAuthn with platform authenticator

**Rationale**: Native biometric support, secure credential storage, no password needed.

### Registration Flow

```typescript
async function registerBiometric(userId: string): Promise<void> {
  const challenge = await fetch('/api/portal/webauthn/register/challenge')
    .then(r => r.json());

  const credential = await navigator.credentials.create({
    publicKey: {
      challenge: base64ToBuffer(challenge.challenge),
      rp: {
        name: 'Clairo',
        id: 'clairo.ai'
      },
      user: {
        id: base64ToBuffer(userId),
        name: 'Client',
        displayName: 'Clairo Client'
      },
      pubKeyCredParams: [
        { alg: -7, type: 'public-key' },  // ES256
        { alg: -257, type: 'public-key' } // RS256
      ],
      authenticatorSelection: {
        authenticatorAttachment: 'platform',
        userVerification: 'required',
        residentKey: 'preferred'
      },
      timeout: 60000
    }
  });

  await fetch('/api/portal/webauthn/register/verify', {
    method: 'POST',
    body: JSON.stringify({
      id: credential.id,
      response: {
        clientDataJSON: bufferToBase64(credential.response.clientDataJSON),
        attestationObject: bufferToBase64(credential.response.attestationObject)
      }
    })
  });
}
```

### Authentication Flow

```typescript
async function authenticateWithBiometric(): Promise<string> {
  const challenge = await fetch('/api/portal/webauthn/auth/challenge')
    .then(r => r.json());

  const credential = await navigator.credentials.get({
    publicKey: {
      challenge: base64ToBuffer(challenge.challenge),
      rpId: 'clairo.ai',
      userVerification: 'required',
      timeout: 60000
    }
  });

  const response = await fetch('/api/portal/webauthn/auth/verify', {
    method: 'POST',
    body: JSON.stringify({
      id: credential.id,
      response: {
        clientDataJSON: bufferToBase64(credential.response.clientDataJSON),
        authenticatorData: bufferToBase64(credential.response.authenticatorData),
        signature: bufferToBase64(credential.response.signature)
      }
    })
  });

  return response.json().token;
}
```

---

## 9. Service Worker Update Strategy

### Decision: Prompt user with skipWaiting

**Rationale**: Balance between immediate updates and not disrupting user mid-action.

### Update Flow

```typescript
// In main app
navigator.serviceWorker.addEventListener('controllerchange', () => {
  // New service worker activated, reload to get new version
  window.location.reload();
});

// Check for updates periodically
setInterval(async () => {
  const registration = await navigator.serviceWorker.getRegistration();
  await registration?.update();
}, 60 * 60 * 1000); // Every hour

// Show update prompt
navigator.serviceWorker.addEventListener('message', (event) => {
  if (event.data.type === 'SW_UPDATE_AVAILABLE') {
    showUpdatePrompt({
      onAccept: () => {
        // Tell waiting SW to skip waiting
        navigator.serviceWorker.controller?.postMessage({ type: 'SKIP_WAITING' });
      }
    });
  }
});
```

```typescript
// In service worker
self.addEventListener('install', (event) => {
  // Notify clients of update
  self.clients.matchAll().then((clients) => {
    clients.forEach((client) => {
      client.postMessage({ type: 'SW_UPDATE_AVAILABLE' });
    });
  });
});

self.addEventListener('message', (event) => {
  if (event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});
```

---

## 10. Analytics Implementation

### Decision: Custom events to existing analytics

**Rationale**: Extend existing analytics setup, no additional dependencies.

### PWA-Specific Events

```typescript
interface PWAAnalyticsEvents {
  // Installation
  pwa_install_prompt_shown: { source: string };
  pwa_installed: { source: string };
  pwa_install_dismissed: {};

  // Push
  push_permission_prompted: {};
  push_permission_granted: {};
  push_permission_denied: {};
  push_received: { type: string };
  push_clicked: { type: string };

  // Offline
  offline_mode_entered: {};
  offline_queue_item_added: { requestId: string };
  offline_queue_processed: { count: number; success: number };

  // Camera
  camera_opened: { source: 'request' | 'general' };
  camera_captured: { quality: 'good' | 'warning' };
  camera_retake: { reason: string };

  // Multi-page
  multipage_started: {};
  multipage_page_added: { pageNumber: number };
  multipage_completed: { pageCount: number };
}

function trackPWAEvent<K extends keyof PWAAnalyticsEvents>(
  event: K,
  data: PWAAnalyticsEvents[K]
): void {
  // Send to existing analytics
  analytics.track(event, {
    ...data,
    platform: 'pwa',
    isStandalone: window.matchMedia('(display-mode: standalone)').matches
  });
}
```

---

## Summary

| Decision | Choice | Key Rationale |
|----------|--------|---------------|
| PWA Framework | next-pwa + Workbox | Official Next.js support |
| Push Service | Firebase Cloud Messaging | Free, cross-platform |
| IndexedDB | idb-keyval + idb | Lightweight, type-safe |
| Camera | MediaDevices API | Native, no dependencies |
| Compression | Canvas API | Browser-native |
| PDF | jsPDF | Client-side, no server |
| Sync | Background Sync API | Browser-native |
| Biometric | WebAuthn | Secure, cross-platform |
