/**
 * PWA Components
 *
 * Spec: 032-pwa-mobile-document-capture
 */

// Installation & Network
export { InstallPrompt } from './InstallPrompt';
export { OfflineIndicator, updateLastSync } from './OfflineIndicator';

// Notifications
export {
  NotificationPermission,
  NotificationSettings,
} from './NotificationPermission';

// Camera & Capture
export { CameraCapture } from './CameraCapture';
export { CameraPreview } from './CameraPreview';
export { CameraUploadFlow, TakePhotoButton } from './CameraUploadFlow';

// Multi-Page Scanning
export { PageThumbnailStrip } from './PageThumbnailStrip';
export { MultiPageScanner } from './MultiPageScanner';

// Upload Queue
export { QueueStatus } from './QueueStatus';

// Quality Feedback
export { QualityFeedback, QualityIndicator } from './QualityFeedback';

// Biometric Authentication
export { BiometricSetup, BiometricPrompt } from './BiometricSetup';
