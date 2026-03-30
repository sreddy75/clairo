'use client';

/**
 * A2UI CameraCapture Component
 * Mobile-first camera capture for document scanning
 */

import { Camera, Check, RotateCcw, X } from 'lucide-react';
import { useCallback, useRef, useState } from 'react';

import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { useA2UIAction } from '@/lib/a2ui/context';
import type { ActionConfig, CameraCaptureProps } from '@/lib/a2ui/types';


// =============================================================================
// Types
// =============================================================================

interface A2UICameraCaptureProps extends CameraCaptureProps {
  id: string;
  dataBinding?: string;
  onAction?: (action: ActionConfig) => Promise<void>;
}

// =============================================================================
// Component
// =============================================================================

export function CameraCapture({
  id,
  mode = 'photo',
  multiPage = false,
  hint,
  onCapture,
  onAction,
}: A2UICameraCaptureProps) {
  const [isCapturing, setIsCapturing] = useState(false);
  const [capturedImages, setCapturedImages] = useState<string[]>([]);
  const [previewImage, setPreviewImage] = useState<string | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const contextAction = useA2UIAction();
  const handleAction = onAction || contextAction;

  const startCamera = useCallback(async () => {
    try {
      const constraints: MediaStreamConstraints = {
        video: {
          facingMode: 'environment', // Prefer back camera
          width: { ideal: 1920 },
          height: { ideal: 1080 },
        },
      };

      const stream = await navigator.mediaDevices.getUserMedia(constraints);
      streamRef.current = stream;

      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }

      setIsCapturing(true);
    } catch {
      console.error('Failed to access camera');
      // Fall back to file input
    }
  }, []);

  const stopCamera = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    setIsCapturing(false);
  }, []);

  const captureImage = useCallback(() => {
    if (!videoRef.current || !canvasRef.current) return;

    const video = videoRef.current;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');

    if (!ctx) return;

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    ctx.drawImage(video, 0, 0);

    const imageData = canvas.toDataURL('image/jpeg', 0.9);
    setPreviewImage(imageData);
  }, []);

  const confirmCapture = useCallback(async () => {
    if (!previewImage) return;

    if (multiPage) {
      setCapturedImages((prev) => [...prev, previewImage]);
      setPreviewImage(null);
    } else {
      stopCamera();
      if (onCapture) {
        await handleAction({
          ...onCapture,
          payload: { ...onCapture.payload, image: previewImage },
        });
      }
    }
  }, [previewImage, multiPage, stopCamera, onCapture, handleAction]);

  const retakePhoto = useCallback(() => {
    setPreviewImage(null);
  }, []);

  const finishMultiPage = useCallback(async () => {
    stopCamera();
    if (onCapture) {
      await handleAction({
        ...onCapture,
        payload: { ...onCapture.payload, images: capturedImages },
      });
    }
  }, [capturedImages, stopCamera, onCapture, handleAction]);

  // Preview mode
  if (previewImage) {
    return (
      <Card id={id} className="overflow-hidden">
        <CardContent className="p-0">
          <div className="relative">
            {/* eslint-disable-next-line @next/next/no-img-element -- base64 data URI from camera capture */}
            <img
              src={previewImage}
              alt="Captured"
              className="w-full h-auto"
            />
            <div className="absolute bottom-4 left-0 right-0 flex justify-center gap-4">
              <Button
                variant="destructive"
                size="lg"
                onClick={retakePhoto}
                className="rounded-full"
              >
                <RotateCcw className="h-5 w-5 mr-2" />
                Retake
              </Button>
              <Button
                size="lg"
                onClick={confirmCapture}
                className="rounded-full"
              >
                <Check className="h-5 w-5 mr-2" />
                {multiPage ? 'Add Page' : 'Use Photo'}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  // Camera mode
  if (isCapturing) {
    return (
      <Card id={id} className="overflow-hidden">
        <CardContent className="p-0">
          <div className="relative bg-black">
            <video
              ref={videoRef}
              autoPlay
              playsInline
              muted
              className="w-full h-auto"
            />
            <canvas ref={canvasRef} className="hidden" />

            {/* Document overlay guide for document mode */}
            {mode === 'document' && (
              <div className="absolute inset-8 border-2 border-white/50 rounded-lg pointer-events-none">
                <div className="absolute -top-6 left-1/2 -translate-x-1/2 text-white/70 text-sm">
                  Align document within frame
                </div>
              </div>
            )}

            {/* Controls */}
            <div className="absolute bottom-4 left-0 right-0 flex justify-center gap-4">
              <Button
                variant="outline"
                size="icon"
                onClick={stopCamera}
                className="rounded-full bg-white/20 border-white/30"
              >
                <X className="h-5 w-5 text-white" />
              </Button>
              <Button
                size="lg"
                onClick={captureImage}
                className="rounded-full h-16 w-16 bg-white text-black hover:bg-white/90"
              >
                <Camera className="h-8 w-8" />
              </Button>
              {multiPage && capturedImages.length > 0 && (
                <Button
                  variant="default"
                  onClick={finishMultiPage}
                  className="rounded-full"
                >
                  Done ({capturedImages.length})
                </Button>
              )}
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  // Initial state - capture button
  return (
    <Card id={id}>
      <CardContent className="p-6">
        <div className="flex flex-col items-center gap-4 text-center">
          <div className="rounded-full bg-primary/10 p-4">
            <Camera className="h-8 w-8 text-primary" />
          </div>
          <div>
            <h3 className="font-semibold">
              {mode === 'document' ? 'Scan Document' : 'Take Photo'}
            </h3>
            {hint && (
              <p className="text-sm text-muted-foreground mt-1">{hint}</p>
            )}
          </div>

          <div className="flex gap-2">
            <Button onClick={startCamera} size="lg">
              <Camera className="h-4 w-4 mr-2" />
              Open Camera
            </Button>
          </div>

          {multiPage && capturedImages.length > 0 && (
            <div className="flex gap-2 mt-4 overflow-x-auto max-w-full">
              {capturedImages.map((img, index) => (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  key={index}
                  src={img}
                  alt={`Page ${index + 1}`}
                  className="h-16 w-auto rounded border"
                />
              ))}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
