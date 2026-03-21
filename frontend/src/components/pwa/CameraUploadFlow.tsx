/**
 * Camera Upload Flow Component
 *
 * Full camera-to-upload flow for document capture.
 *
 * Spec: 032-pwa-mobile-document-capture
 */

'use client';

import { Camera, Upload, Loader2, CheckCircle2, AlertCircle } from 'lucide-react';
import { useState, useCallback } from 'react';

import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { compressImage } from '@/lib/pwa/image-processor';
import { cn } from '@/lib/utils';

import { CameraCapture } from './CameraCapture';
import { CameraPreview } from './CameraPreview';

type FlowState = 'idle' | 'camera' | 'preview' | 'processing' | 'uploading' | 'success' | 'error';

interface CameraUploadFlowProps {
  /** Request ID to upload to */
  requestId: string;
  /** Callback after successful upload */
  onSuccess?: (documentId: string) => void;
  /** Callback when flow is cancelled */
  onCancel?: () => void;
  /** Upload function */
  uploadFile: (requestId: string, file: File, message?: string) => Promise<{ id: string }>;
  /** Custom class name */
  className?: string;
}

export function CameraUploadFlow({
  requestId,
  onSuccess,
  onCancel,
  uploadFile,
  className,
}: CameraUploadFlowProps) {
  const [state, setState] = useState<FlowState>('idle');
  const [capturedBlob, setCapturedBlob] = useState<Blob | null>(null);
  const [processedBlob, setProcessedBlob] = useState<Blob | null>(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const handleStartCamera = () => {
    setState('camera');
    setError(null);
  };

  const handleCapture = useCallback((blob: Blob) => {
    setCapturedBlob(blob);
    setState('preview');
  }, []);

  const handleRetake = useCallback(() => {
    setCapturedBlob(null);
    setProcessedBlob(null);
    setState('camera');
  }, []);

  const handleAccept = useCallback(async (blob: Blob) => {
    setState('processing');
    setError(null);

    try {
      // Compress image
      const result = await compressImage(blob, {
        maxWidth: 2048,
        maxHeight: 2048,
        quality: 0.85,
        mimeType: 'image/jpeg',
        fixOrientation: true,
      });

      setProcessedBlob(result.blob);
      console.log(
        `[Upload] Compressed: ${(blob.size / 1024).toFixed(1)}KB → ${(result.blob.size / 1024).toFixed(1)}KB (${result.compressionRatio.toFixed(1)}x)`
      );

      // Start upload
      setState('uploading');
      setUploadProgress(0);

      // Create file from blob
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
      const file = new File([result.blob], `photo-${timestamp}.jpg`, {
        type: 'image/jpeg',
      });

      // Simulate progress (actual progress would come from upload function)
      const progressInterval = setInterval(() => {
        setUploadProgress((prev) => {
          if (prev >= 90) {
            clearInterval(progressInterval);
            return prev;
          }
          return prev + 10;
        });
      }, 200);

      // Upload file
      const response = await uploadFile(requestId, file);

      clearInterval(progressInterval);
      setUploadProgress(100);

      setState('success');

      // Wait briefly to show success state
      setTimeout(() => {
        onSuccess?.(response.id);
      }, 1500);
    } catch (err) {
      console.error('[Upload] Failed:', err);
      setError(err instanceof Error ? err.message : 'Upload failed');
      setState('error');
    }
  }, [requestId, uploadFile, onSuccess]);

  const handleClose = useCallback(() => {
    setCapturedBlob(null);
    setProcessedBlob(null);
    setState('idle');
    onCancel?.();
  }, [onCancel]);

  const handleRetry = useCallback(() => {
    if (capturedBlob) {
      handleAccept(capturedBlob);
    } else {
      setState('camera');
    }
  }, [capturedBlob, handleAccept]);

  // Render based on state
  if (state === 'camera') {
    return <CameraCapture onCapture={handleCapture} onClose={handleClose} />;
  }

  if (state === 'preview' && capturedBlob) {
    return (
      <CameraPreview
        imageBlob={capturedBlob}
        onAccept={handleAccept}
        onRetake={handleRetake}
        isProcessing={false}
      />
    );
  }

  if (state === 'processing') {
    return (
      <div className="fixed inset-0 z-50 bg-black flex flex-col items-center justify-center p-6">
        <div className="text-center text-white space-y-4">
          <Loader2 className="h-12 w-12 animate-spin mx-auto text-blue-400" />
          <h2 className="text-xl font-semibold">Processing Image</h2>
          <p className="text-muted-foreground">Optimizing for upload...</p>
        </div>
      </div>
    );
  }

  if (state === 'uploading') {
    return (
      <div className="fixed inset-0 z-50 bg-black flex flex-col items-center justify-center p-6">
        <div className="text-center text-white space-y-6 w-full max-w-sm">
          <Upload className="h-12 w-12 mx-auto text-blue-400 animate-pulse" />
          <h2 className="text-xl font-semibold">Uploading</h2>
          <div className="space-y-2">
            <Progress value={uploadProgress} className="h-2" />
            <p className="text-sm text-muted-foreground">{uploadProgress}%</p>
          </div>
          {processedBlob && (
            <p className="text-xs text-muted-foreground">
              {(processedBlob.size / 1024).toFixed(1)} KB
            </p>
          )}
        </div>
      </div>
    );
  }

  if (state === 'success') {
    return (
      <div className="fixed inset-0 z-50 bg-black flex flex-col items-center justify-center p-6">
        <div className="text-center text-white space-y-4">
          <div className="mx-auto w-16 h-16 rounded-full bg-green-500/20 flex items-center justify-center">
            <CheckCircle2 className="h-8 w-8 text-green-500" />
          </div>
          <h2 className="text-xl font-semibold">Upload Complete!</h2>
          <p className="text-muted-foreground">Your document has been uploaded successfully.</p>
        </div>
      </div>
    );
  }

  if (state === 'error') {
    return (
      <div className="fixed inset-0 z-50 bg-black flex flex-col items-center justify-center p-6">
        <div className="text-center text-white space-y-4 max-w-sm">
          <div className="mx-auto w-16 h-16 rounded-full bg-red-500/20 flex items-center justify-center">
            <AlertCircle className="h-8 w-8 text-red-500" />
          </div>
          <h2 className="text-xl font-semibold">Upload Failed</h2>
          <p className="text-muted-foreground">{error || 'Something went wrong'}</p>
          <div className="pt-4 space-y-2">
            <Button onClick={handleRetry} variant="secondary" className="w-full">
              Try Again
            </Button>
            <Button onClick={handleClose} variant="ghost" className="w-full text-muted-foreground">
              Cancel
            </Button>
          </div>
        </div>
      </div>
    );
  }

  // Idle state - show "Take Photo" button
  return (
    <Button
      onClick={handleStartCamera}
      className={cn('gap-2', className)}
    >
      <Camera className="h-4 w-4" />
      Take Photo
    </Button>
  );
}

/**
 * Trigger button for camera upload flow.
 */
export function TakePhotoButton({
  onClick,
  className,
  disabled,
}: {
  onClick: () => void;
  className?: string;
  disabled?: boolean;
}) {
  return (
    <Button
      onClick={onClick}
      disabled={disabled}
      variant="default"
      className={cn('gap-2', className)}
    >
      <Camera className="h-4 w-4" />
      Take Photo
    </Button>
  );
}
