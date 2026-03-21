/**
 * Camera Preview Component
 *
 * Shows captured photo with options to use or retake.
 *
 * Spec: 032-pwa-mobile-document-capture
 */

'use client';

import { Check, X, RotateCcw, Loader2 } from 'lucide-react';
import Image from 'next/image';
import { useEffect, useState } from 'react';

import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface CameraPreviewProps {
  /** Captured image blob */
  imageBlob: Blob;
  /** Callback when photo is accepted */
  onAccept: (blob: Blob) => void;
  /** Callback when user wants to retake */
  onRetake: () => void;
  /** Whether currently processing */
  isProcessing?: boolean;
  /** Custom class name */
  className?: string;
}

export function CameraPreview({
  imageBlob,
  onAccept,
  onRetake,
  isProcessing = false,
  className,
}: CameraPreviewProps) {
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [dimensions, setDimensions] = useState<{
    width: number;
    height: number;
  } | null>(null);

  // Create object URL for preview
  useEffect(() => {
    const url = URL.createObjectURL(imageBlob);
    setImageUrl(url);

    // Get image dimensions
    const img = new window.Image();
    img.onload = () => {
      setDimensions({ width: img.width, height: img.height });
    };
    img.src = url;

    return () => {
      URL.revokeObjectURL(url);
    };
  }, [imageBlob]);

  const handleAccept = () => {
    if (!isProcessing) {
      onAccept(imageBlob);
    }
  };

  const handleRetake = () => {
    if (!isProcessing) {
      onRetake();
    }
  };

  // Format file size
  const formatSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div
      className={cn(
        'fixed inset-0 z-50 bg-black flex flex-col',
        className
      )}
    >
      {/* Header */}
      <div className="absolute top-0 left-0 right-0 z-10 p-4 flex items-center justify-between bg-gradient-to-b from-black/60 to-transparent">
        <Button
          variant="ghost"
          size="icon"
          className="text-white hover:bg-white/20"
          onClick={handleRetake}
          disabled={isProcessing}
        >
          <X className="h-6 w-6" />
        </Button>

        <div className="text-white text-sm">
          {dimensions && (
            <span className="text-white/60">
              {dimensions.width} x {dimensions.height}
            </span>
          )}
          <span className="mx-2 text-white/40">|</span>
          <span className="text-white/60">{formatSize(imageBlob.size)}</span>
        </div>
      </div>

      {/* Image preview */}
      <div className="flex-1 relative flex items-center justify-center p-4">
        {imageUrl && (
          <div className="relative max-w-full max-h-full">
            <Image
              src={imageUrl}
              alt="Captured photo"
              width={dimensions?.width || 1920}
              height={dimensions?.height || 1080}
              className="max-w-full max-h-[calc(100vh-200px)] object-contain rounded-lg"
              priority
            />
          </div>
        )}
      </div>

      {/* Footer controls */}
      <div className="absolute bottom-0 left-0 right-0 z-10 p-6 pb-safe bg-gradient-to-t from-black/60 to-transparent">
        <div className="flex items-center justify-center gap-4 max-w-sm mx-auto">
          {/* Retake button */}
          <Button
            variant="outline"
            size="lg"
            className="flex-1 bg-white/10 border-white/30 text-white hover:bg-white/20"
            onClick={handleRetake}
            disabled={isProcessing}
          >
            <RotateCcw className="h-5 w-5 mr-2" />
            Retake
          </Button>

          {/* Accept button */}
          <Button
            size="lg"
            className="flex-1 bg-green-500 hover:bg-green-600 text-white"
            onClick={handleAccept}
            disabled={isProcessing}
          >
            {isProcessing ? (
              <>
                <Loader2 className="h-5 w-5 mr-2 animate-spin" />
                Processing...
              </>
            ) : (
              <>
                <Check className="h-5 w-5 mr-2" />
                Use Photo
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}
