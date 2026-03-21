# Spec 032: PWA & Mobile + Document Capture

**Status**: NOT_STARTED
**Priority**: P1
**Dependencies**: Spec 030 (Client Portal + Document Requests)
**Estimated Effort**: 1 week

---

## Overview

Transform the Clairo client portal into a Progressive Web App (PWA) with native-like mobile experience, push notifications, offline support, and camera-first document capture. This enables business owners to respond to document requests instantly from their mobile devices, even with intermittent connectivity.

### Problem Statement

Business owners receive document requests while on-the-go:
- They can't install another app just for their accountant
- Mobile web upload experience is clunky
- Taking photos of receipts requires downloading images then uploading
- Poor connectivity at job sites means failed uploads
- They miss time-sensitive requests because email goes to spam

### Solution

A PWA that:
- Installs like a native app (no app store)
- Sends push notifications for new requests
- Opens camera directly for document capture
- Queues uploads when offline
- Syncs automatically when connection restored

---

## User Stories

### US1: PWA Installation (P1)

**As a** business owner accessing the portal on mobile
**I want to** install Clairo as an app on my home screen
**So that** I can access it quickly without opening a browser

**Acceptance Criteria**:
- [ ] Service worker registered on portal pages
- [ ] Web manifest with app icon, name, theme colors
- [ ] "Add to Home Screen" prompt appears after 2 visits
- [ ] App opens in standalone mode (no browser chrome)
- [ ] Splash screen displays during app load
- [ ] Works on iOS Safari and Chrome for Android
- [ ] App icon includes Clairo branding

**Technical Notes**:
- manifest.json with display: standalone
- Service worker for caching shell
- beforeinstallprompt event handling
- iOS meta tags for standalone mode

---

### US2: Push Notifications (P1)

**As a** business owner
**I want to** receive push notifications when my accountant needs documents
**So that** I can respond immediately without checking email

**Acceptance Criteria**:
- [ ] Push permission requested after first document request viewed
- [ ] Notification sent when new document request created
- [ ] Notification sent when request marked urgent
- [ ] Notification sent 24 hours before deadline
- [ ] Notification sent when request overdue
- [ ] Clicking notification opens specific request
- [ ] Notification badge shows unread count
- [ ] User can disable notifications in settings

**Notification Types**:
| Type | Title | Body | Priority |
|------|-------|------|----------|
| new_request | "Document needed" | "{Accountant} needs: {item}" | High |
| urgent | "Urgent: Document needed" | "{item} needed by {date}" | High |
| reminder | "Reminder: {item}" | "Due in 24 hours" | Normal |
| overdue | "Overdue: {item}" | "{days} days overdue" | High |
| message | "New message" | "{Accountant}: {preview}" | Normal |

**Technical Notes**:
- Web Push API with VAPID keys
- Push subscription stored per client
- Background sync for delivery confirmation
- Firebase Cloud Messaging for cross-platform

---

### US3: Offline Request Viewing (P1)

**As a** business owner with poor connectivity
**I want to** view my pending document requests offline
**So that** I can see what's needed even without internet

**Acceptance Criteria**:
- [ ] Dashboard available offline after first visit
- [ ] Request list cached locally
- [ ] Request details cached with descriptions
- [ ] Accountant contact info available offline
- [ ] "Offline mode" indicator shown in header
- [ ] Last sync time displayed
- [ ] Automatic sync when connection restored

**Caching Strategy**:
- Cache-first for static assets
- Network-first for API data with stale fallback
- IndexedDB for structured data

---

### US4: Camera-First Upload (P1)

**As a** business owner responding to a document request
**I want to** open my camera directly from the request
**So that** I can quickly photograph and send a document

**Acceptance Criteria**:
- [ ] "Take Photo" button prominent on request detail
- [ ] Camera opens in capture mode immediately
- [ ] Preview shown after capture with retake/confirm
- [ ] Image compressed before upload (max 2MB)
- [ ] EXIF orientation corrected automatically
- [ ] Progress indicator during upload
- [ ] Success confirmation with thumbnail
- [ ] Falls back to file picker if camera unavailable

**Technical Notes**:
- MediaDevices.getUserMedia() for camera access
- Canvas for image processing/compression
- Orientation from EXIF or accelerometer
- Progressive JPEG for smaller files

---

### US5: Multi-Page Scanning (P1)

**As a** business owner photographing a multi-page document
**I want to** capture multiple pages as a single PDF
**So that** I can send complete bank statements or contracts

**Acceptance Criteria**:
- [ ] "Add Page" button after each capture
- [ ] Page count indicator (e.g., "Page 3 of 3")
- [ ] Thumbnail strip showing all pages
- [ ] Reorder pages by drag-and-drop
- [ ] Delete individual pages
- [ ] Preview full document before sending
- [ ] Generates PDF client-side
- [ ] Filename includes request name and date

**Technical Notes**:
- jsPDF for client-side PDF generation
- Canvas for image-to-PDF conversion
- IndexedDB for storing pages during capture
- Max 20 pages per document

---

### US6: Offline Upload Queue (P1)

**As a** business owner at a job site with no signal
**I want to** queue document uploads for later
**So that** I can complete my response without waiting for connection

**Acceptance Criteria**:
- [ ] Upload queued when offline
- [ ] Queue persisted to IndexedDB
- [ ] Visual indicator shows queued count
- [ ] Queue processed when online
- [ ] Retry with exponential backoff on failure
- [ ] Notification when queue processed
- [ ] User can view/cancel queued items
- [ ] Partial uploads resume (if > 1MB)

**Queue States**:
| State | Description | UI |
|-------|-------------|-----|
| queued | Waiting for connection | Gray clock icon |
| uploading | Currently uploading | Blue progress |
| failed | Upload failed | Red exclamation |
| completed | Successfully uploaded | Green check |

---

### US7: Document Quality Check (P2)

**As a** business owner taking photos of documents
**I want to** get feedback on image quality
**So that** I can retake blurry or dark photos

**Acceptance Criteria**:
- [ ] Check image resolution (min 1000px width)
- [ ] Detect blur using edge detection
- [ ] Detect low brightness
- [ ] Detect skewed orientation
- [ ] Show quality warnings before confirm
- [ ] Allow override with "Send Anyway"
- [ ] Suggestions for improvement (move closer, more light)

**Quality Thresholds**:
- Resolution: ≥1000px width
- Blur score: <30% edge pixels
- Brightness: 0.2 - 0.8 average
- Skew: <15° detected

---

### US8: App Settings (P2)

**As a** business owner using the PWA
**I want to** manage my app preferences
**So that** I can control notifications and storage

**Acceptance Criteria**:
- [ ] Toggle push notifications
- [ ] Set quiet hours (no notifications)
- [ ] View storage usage
- [ ] Clear cached data
- [ ] View offline queue status
- [ ] Toggle auto-download of request details
- [ ] About section with version info

---

### US9: Biometric Quick Access (P2)

**As a** business owner reopening the app
**I want to** authenticate with Face ID/fingerprint
**So that** I can access quickly without entering codes

**Acceptance Criteria**:
- [ ] Prompt to enable biometrics after first login
- [ ] Web Authentication API (WebAuthn) integration
- [ ] Falls back to magic link if biometric fails
- [ ] "Remember device" reduces auth prompts
- [ ] Session valid for 30 days with activity
- [ ] Lock after 5 minutes of inactivity

---

### US10: Installation Analytics (P2)

**As an** accountant
**I want to** see which clients have installed the app
**So that** I can encourage adoption

**Acceptance Criteria**:
- [ ] Track PWA installation events
- [ ] Track push notification opt-in
- [ ] Show in client profile: "App installed"
- [ ] Show in client profile: "Notifications enabled"
- [ ] Summary in dashboard: "X of Y clients have app"
- [ ] Filter clients by app installation status

---

## Non-Functional Requirements

### Performance

| Metric | Target |
|--------|--------|
| Time to interactive (offline) | <1 second |
| Time to interactive (online) | <2 seconds |
| Camera launch time | <500ms |
| Image compression time | <2 seconds |
| PDF generation (10 pages) | <5 seconds |

### Compatibility

| Platform | Version | Notes |
|----------|---------|-------|
| iOS Safari | 15+ | PWA support varies |
| Chrome Android | 90+ | Full PWA support |
| Chrome Desktop | 90+ | Install from browser |
| Firefox | 100+ | Limited PWA |
| Edge | 90+ | Full PWA support |

### Storage

| Item | Size Estimate |
|------|---------------|
| App shell | ~500KB |
| Cached API data | ~100KB per client |
| Offline queue | ~2MB per document |
| IndexedDB limit | 50MB default |

### Security

- All data encrypted at rest (IndexedDB)
- Biometric data never leaves device
- Push subscription tied to authenticated user
- Clear all data on logout
- No sensitive data in push payload

---

## Technical Architecture

### Service Worker Strategy

```
┌─────────────────────────────────────────┐
│              Service Worker              │
├─────────────────────────────────────────┤
│  ┌─────────────┐   ┌─────────────────┐  │
│  │ Cache Layer │   │ IndexedDB Store │  │
│  ├─────────────┤   ├─────────────────┤  │
│  │ Static:     │   │ Requests        │  │
│  │ - HTML/CSS  │   │ Documents       │  │
│  │ - JS/Images │   │ Upload Queue    │  │
│  │             │   │ Push Sub        │  │
│  │ API Data:   │   │                 │  │
│  │ - Dashboard │   │                 │  │
│  │ - Requests  │   │                 │  │
│  └─────────────┘   └─────────────────┘  │
├─────────────────────────────────────────┤
│  Background Sync │ Push Handler │ Fetch │
└─────────────────────────────────────────┘
```

### Document Capture Flow

```
┌─────────┐    ┌─────────────┐    ┌───────────┐
│ Camera  │───►│ Image Proc. │───►│ PDF Gen.  │
│ Capture │    │ - Compress  │    │ - Combine │
└─────────┘    │ - Rotate    │    │ - Output  │
               │ - Quality   │    └─────┬─────┘
               └─────────────┘          │
                                        ▼
                              ┌──────────────┐
                              │ Upload Queue │
                              │ (IndexedDB)  │
                              └──────┬───────┘
                                     │
                         ┌───────────┴───────────┐
                         │                       │
                    [Online]                [Offline]
                         │                       │
                         ▼                       ▼
                   ┌──────────┐          ┌────────────┐
                   │ S3 Upload│          │ Wait for   │
                   │ Direct   │          │ Connection │
                   └──────────┘          └────────────┘
```

---

## Dependencies

### On Spec 030

- Portal authentication (magic links)
- Document request API
- S3 upload infrastructure
- Client-accountant relationship

### New Dependencies

| Dependency | Purpose |
|------------|---------|
| Firebase Cloud Messaging | Push notification delivery |
| jsPDF | Client-side PDF generation |
| Workbox | Service worker utilities |
| idb-keyval | IndexedDB wrapper |

---

## Migration Notes

### Existing Portal Users

- PWA install prompt appears on existing sessions
- Push permission requested on next request view
- No data migration needed (server-side unchanged)

### Service Worker Registration

- Register on portal domain only
- Scope limited to /portal/*
- No interference with accountant app

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| PWA installation rate | >30% of active clients | Install events |
| Push opt-in rate | >50% of PWA users | Subscription count |
| Offline upload usage | >10% of uploads | Queue events |
| Response time improvement | 4 hours → 30 min | Avg time to respond |
| Camera-first usage | >60% of uploads | Upload source tracking |

---

## Out of Scope

- Native iOS/Android apps
- Barcode/QR code scanning
- OCR in-device
- Video recording
- File sharing between apps
- Widgets/complications

---

## Open Questions

1. **Push notification provider**: Firebase vs OneSignal vs custom VAPID?
2. **PDF quality**: High quality (larger) vs optimized (smaller)?
3. **Biometric timeout**: 5 minutes vs configurable?
4. **Multi-device sync**: Same client, multiple devices?

---

## References

- [Web App Manifest Spec](https://w3c.github.io/manifest/)
- [Service Worker API](https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API)
- [Push API](https://developer.mozilla.org/en-US/docs/Web/API/Push_API)
- [MediaDevices API](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices)
- [Workbox Documentation](https://developers.google.com/web/tools/workbox)
