/**
 * Camera Capture Component
 *
 * Full-screen camera interface for capturing photos.
 *
 * Spec: 032-pwa-mobile-document-capture
 */

'use client';

import {
  Camera,
  X,
  SwitchCamera,
  Zap,
  ZapOff,
  AlertCircle,
  Loader2,
} from 'lucide-react';
import { useEffect, useState } from 'react';

import { Button } from '@/components/ui/button';
import { useCamera } from '@/hooks/useCamera';
import { cn } from '@/lib/utils';

interface CameraCaptureProps {
  /** Callback when photo is captured */
  onCapture: (blob: Blob) => void;
  /** Callback to close camera */
  onClose: () => void;
  /** Custom class name */
  className?: string;
}

export function CameraCapture({
  onCapture,
  onClose,
  className,
}: CameraCaptureProps) {
  const {
    isSupported,
    isActive,
    isLoading,
    error,
    facing,
    hasFlash,
    flashEnabled,
    videoRef,
    startCamera,
    stopCamera,
    switchCamera,
    capturePhoto,
    toggleFlash,
  } = useCamera();

  const [isCapturing, setIsCapturing] = useState(false);
  const [showFlash, setShowFlash] = useState(false);

  // Start camera on mount
  useEffect(() => {
    startCamera();
    return () => {
      stopCamera();
    };
  }, [startCamera, stopCamera]);

  const handleCapture = async () => {
    if (isCapturing || !isActive) return;

    setIsCapturing(true);

    // Flash animation
    setShowFlash(true);
    setTimeout(() => setShowFlash(false), 100);

    try {
      const blob = await capturePhoto();
      if (blob) {
        onCapture(blob);
      }
    } finally {
      setIsCapturing(false);
    }
  };

  const handleSwitchCamera = async () => {
    await switchCamera();
  };

  const handleToggleFlash = async () => {
    await toggleFlash();
  };

  // Permission denied UI
  if (error) {
    return (
      <div
        className={cn(
          'fixed inset-0 z-50 bg-black flex flex-col items-center justify-center p-6',
          className
        )}
      >
        <div className="text-center text-white space-y-4 max-w-sm">
          <div className="mx-auto w-16 h-16 rounded-full bg-red-500/20 flex items-center justify-center">
            <AlertCircle className="h-8 w-8 text-red-500" />
          </div>
          <h2 className="text-xl font-semibold">Camera Access Required</h2>
          <p className="text-muted-foreground">{error}</p>
          <div className="pt-4 space-y-2">
            <Button onClick={() => startCamera()} variant="secondary" className="w-full">
              Try Again
            </Button>
            <Button onClick={onClose} variant="ghost" className="w-full text-muted-foreground">
              Cancel
            </Button>
          </div>
        </div>
      </div>
    );
  }

  // Not supported UI
  if (!isSupported) {
    return (
      <div
        className={cn(
          'fixed inset-0 z-50 bg-black flex flex-col items-center justify-center p-6',
          className
        )}
      >
        <div className="text-center text-white space-y-4 max-w-sm">
          <div className="mx-auto w-16 h-16 rounded-full bg-yellow-500/20 flex items-center justify-center">
            <Camera className="h-8 w-8 text-yellow-500" />
          </div>
          <h2 className="text-xl font-semibold">Camera Not Available</h2>
          <p className="text-muted-foreground">
            Your browser doesn&apos;t support camera access. Try using a different browser or device.
          </p>
          <Button onClick={onClose} variant="secondary" className="w-full">
            Close
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div
      className={cn(
        'fixed inset-0 z-50 bg-black flex flex-col',
        className
      )}
    >
      {/* Capture flash overlay */}
      {showFlash && (
        <div className="absolute inset-0 z-20 bg-white pointer-events-none" />
      )}

      {/* Header */}
      <div className="absolute top-0 left-0 right-0 z-10 p-4 flex items-center justify-between bg-gradient-to-b from-black/60 to-transparent">
        <Button
          variant="ghost"
          size="icon"
          className="text-white hover:bg-white/20"
          onClick={onClose}
        >
          <X className="h-6 w-6" />
        </Button>

        <div className="flex items-center gap-2">
          {hasFlash && (
            <Button
              variant="ghost"
              size="icon"
              className="text-white hover:bg-white/20"
              onClick={handleToggleFlash}
            >
              {flashEnabled ? (
                <Zap className="h-6 w-6 text-yellow-400" />
              ) : (
                <ZapOff className="h-6 w-6" />
              )}
            </Button>
          )}
        </div>
      </div>

      {/* Camera preview */}
      <div className="flex-1 relative overflow-hidden">
        {isLoading && (
          <div className="absolute inset-0 flex items-center justify-center bg-black">
            <Loader2 className="h-8 w-8 animate-spin text-white" />
          </div>
        )}

        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          className={cn(
            'w-full h-full object-cover',
            facing === 'user' && 'scale-x-[-1]'
          )}
        />

        {/* Guide frame */}
        <div className="absolute inset-8 border-2 border-white/30 rounded-lg pointer-events-none">
          <div className="absolute top-0 left-0 w-8 h-8 border-t-2 border-l-2 border-white rounded-tl-lg" />
          <div className="absolute top-0 right-0 w-8 h-8 border-t-2 border-r-2 border-white rounded-tr-lg" />
          <div className="absolute bottom-0 left-0 w-8 h-8 border-b-2 border-l-2 border-white rounded-bl-lg" />
          <div className="absolute bottom-0 right-0 w-8 h-8 border-b-2 border-r-2 border-white rounded-br-lg" />
        </div>
      </div>

      {/* Footer controls */}
      <div className="absolute bottom-0 left-0 right-0 z-10 p-6 pb-safe bg-gradient-to-t from-black/60 to-transparent">
        <div className="flex items-center justify-center gap-8">
          {/* Switch camera */}
          <Button
            variant="ghost"
            size="icon"
            className="text-white hover:bg-white/20 h-12 w-12"
            onClick={handleSwitchCamera}
            disabled={isLoading}
          >
            <SwitchCamera className="h-6 w-6" />
          </Button>

          {/* Capture button */}
          <button
            onClick={handleCapture}
            disabled={!isActive || isCapturing}
            className={cn(
              'w-20 h-20 rounded-full border-4 border-white flex items-center justify-center',
              'transition-transform active:scale-95',
              isCapturing && 'opacity-50'
            )}
          >
            <div
              className={cn(
                'w-16 h-16 rounded-full bg-white',
                isCapturing && 'animate-pulse'
              )}
            />
          </button>

          {/* Placeholder for symmetry */}
          <div className="h-12 w-12" />
        </div>

        <p className="text-center text-white/60 text-sm mt-4">
          Position document within the frame
        </p>
      </div>
    </div>
  );
}
