/**
 * Camera Hook
 *
 * Provides camera access and photo capture functionality.
 *
 * Spec: 032-pwa-mobile-document-capture
 */

'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

export type CameraFacing = 'user' | 'environment';

export interface CameraState {
  /** Whether camera is supported */
  isSupported: boolean;
  /** Whether camera is currently active */
  isActive: boolean;
  /** Whether camera is loading */
  isLoading: boolean;
  /** Current camera facing mode */
  facing: CameraFacing;
  /** Error message if any */
  error: string | null;
  /** Available camera devices */
  devices: MediaDeviceInfo[];
  /** Current device ID */
  currentDeviceId: string | null;
  /** Whether flash is available */
  hasFlash: boolean;
  /** Whether flash is enabled */
  flashEnabled: boolean;
}

export interface CameraHook extends CameraState {
  /** Reference to attach to video element */
  videoRef: React.RefObject<HTMLVideoElement>;
  /** Start camera stream */
  startCamera: (facing?: CameraFacing) => Promise<boolean>;
  /** Stop camera stream */
  stopCamera: () => void;
  /** Switch between front/back camera */
  switchCamera: () => Promise<boolean>;
  /** Capture a photo */
  capturePhoto: () => Promise<Blob | null>;
  /** Toggle flash */
  toggleFlash: () => Promise<boolean>;
  /** Get available cameras */
  getCameras: () => Promise<MediaDeviceInfo[]>;
}

/**
 * Hook for camera access and photo capture.
 */
export function useCamera(): CameraHook {
  const videoRef = useRef<HTMLVideoElement>(null!);
  const streamRef = useRef<MediaStream | null>(null);
  const trackRef = useRef<MediaStreamTrack | null>(null);

  const [state, setState] = useState<CameraState>({
    isSupported: false,
    isActive: false,
    isLoading: false,
    facing: 'environment',
    error: null,
    devices: [],
    currentDeviceId: null,
    hasFlash: false,
    flashEnabled: false,
  });

  // Check camera support on mount
  useEffect(() => {
    const isSupported =
      typeof navigator !== 'undefined' &&
      'mediaDevices' in navigator &&
      'getUserMedia' in navigator.mediaDevices;

    setState((prev) => ({ ...prev, isSupported }));

    // Get available cameras
    if (isSupported) {
      getCamerasInternal().then((devices) => {
        setState((prev) => ({ ...prev, devices }));
      });
    }

    // Cleanup on unmount
    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
      }
    };
  }, []);

  /**
   * Get available camera devices.
   */
  const getCamerasInternal = async (): Promise<MediaDeviceInfo[]> => {
    try {
      // Request permission first to enumerate devices
      await navigator.mediaDevices.getUserMedia({ video: true });
      const devices = await navigator.mediaDevices.enumerateDevices();
      return devices.filter((device) => device.kind === 'videoinput');
    } catch {
      return [];
    }
  };

  const getCameras = useCallback(async (): Promise<MediaDeviceInfo[]> => {
    const devices = await getCamerasInternal();
    setState((prev) => ({ ...prev, devices }));
    return devices;
  }, []);

  /**
   * Start camera stream.
   */
  const startCamera = useCallback(
    async (facing: CameraFacing = 'environment'): Promise<boolean> => {
      if (!state.isSupported) {
        setState((prev) => ({
          ...prev,
          error: 'Camera not supported in this browser',
        }));
        return false;
      }

      setState((prev) => ({ ...prev, isLoading: true, error: null }));

      try {
        // Stop existing stream
        if (streamRef.current) {
          streamRef.current.getTracks().forEach((track) => track.stop());
        }

        const constraints: MediaStreamConstraints = {
          video: {
            facingMode: facing,
            width: { ideal: 1920 },
            height: { ideal: 1080 },
          },
          audio: false,
        };

        const stream = await navigator.mediaDevices.getUserMedia(constraints);
        streamRef.current = stream;

        const videoTrack = stream.getVideoTracks()[0];
        if (!videoTrack) {
          throw new Error('No video track available');
        }
        trackRef.current = videoTrack;

        // Get device ID
        const settings = videoTrack.getSettings();
        const currentDeviceId = settings.deviceId || null;

        // Check for flash (torch) capability
        let hasFlash = false;
        try {
          const capabilities = videoTrack.getCapabilities?.() as MediaTrackCapabilities & { torch?: boolean };
          hasFlash = capabilities?.torch === true;
        } catch {
          // Torch not supported
        }

        // Attach to video element
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          await videoRef.current.play();
        }

        setState((prev) => ({
          ...prev,
          isActive: true,
          isLoading: false,
          facing,
          currentDeviceId,
          hasFlash,
          flashEnabled: false,
          error: null,
        }));

        return true;
      } catch (err) {
        const error = err as Error;
        let message = 'Failed to access camera';

        if (error.name === 'NotAllowedError') {
          message = 'Camera permission denied. Please enable camera access.';
        } else if (error.name === 'NotFoundError') {
          message = 'No camera found on this device.';
        } else if (error.name === 'NotReadableError') {
          message = 'Camera is in use by another application.';
        } else if (error.name === 'OverconstrainedError') {
          message = 'Camera does not support the requested resolution.';
        }

        setState((prev) => ({
          ...prev,
          isLoading: false,
          error: message,
        }));

        console.error('[Camera] Start failed:', error);
        return false;
      }
    },
    [state.isSupported]
  );

  /**
   * Stop camera stream.
   */
  const stopCamera = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }

    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }

    trackRef.current = null;

    setState((prev) => ({
      ...prev,
      isActive: false,
      currentDeviceId: null,
      hasFlash: false,
      flashEnabled: false,
    }));
  }, []);

  /**
   * Switch between front and back camera.
   */
  const switchCamera = useCallback(async (): Promise<boolean> => {
    const newFacing = state.facing === 'environment' ? 'user' : 'environment';
    return startCamera(newFacing);
  }, [state.facing, startCamera]);

  /**
   * Capture a photo from the video stream.
   */
  const capturePhoto = useCallback(async (): Promise<Blob | null> => {
    if (!videoRef.current || !state.isActive) {
      return null;
    }

    try {
      const video = videoRef.current;
      const canvas = document.createElement('canvas');
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;

      const ctx = canvas.getContext('2d');
      if (!ctx) {
        throw new Error('Could not get canvas context');
      }

      // Draw video frame to canvas
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

      // Convert to blob
      return new Promise<Blob | null>((resolve) => {
        canvas.toBlob(
          (blob) => {
            resolve(blob);
          },
          'image/jpeg',
          0.9
        );
      });
    } catch (err) {
      console.error('[Camera] Capture failed:', err);
      setState((prev) => ({
        ...prev,
        error: 'Failed to capture photo',
      }));
      return null;
    }
  }, [state.isActive]);

  /**
   * Toggle flash/torch.
   */
  const toggleFlash = useCallback(async (): Promise<boolean> => {
    if (!trackRef.current || !state.hasFlash) {
      return false;
    }

    try {
      const newState = !state.flashEnabled;
      await trackRef.current.applyConstraints({
        // @ts-expect-error - torch is not in the TypeScript types
        advanced: [{ torch: newState }],
      });

      setState((prev) => ({ ...prev, flashEnabled: newState }));
      return true;
    } catch (err) {
      console.error('[Camera] Toggle flash failed:', err);
      return false;
    }
  }, [state.hasFlash, state.flashEnabled]);

  return {
    ...state,
    videoRef,
    startCamera,
    stopCamera,
    switchCamera,
    capturePhoto,
    toggleFlash,
    getCameras,
  };
}
