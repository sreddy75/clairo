'use client';

import { Check, Mic, MicOff, Pause, Play, RotateCcw, Upload } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';

import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { cn } from '@/lib/utils';

// =============================================================================
// Types
// =============================================================================

interface AudioRecorderProps {
  onAudioReady: (file: File) => void;
  maxDuration?: number; // seconds, default 300 (5 min)
  disabled?: boolean;
}

type RecorderState = 'idle' | 'recording' | 'preview';

const MAX_FILE_SIZE = 25 * 1024 * 1024; // 25MB
const ACCEPTED_TYPES = '.mp3,.m4a,.wav,.webm';

// =============================================================================
// Helpers
// =============================================================================

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
}

function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function getPreferredMimeType(): string {
  if (typeof MediaRecorder !== 'undefined') {
    if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) {
      return 'audio/webm;codecs=opus';
    }
    if (MediaRecorder.isTypeSupported('audio/webm')) {
      return 'audio/webm';
    }
    if (MediaRecorder.isTypeSupported('audio/mp4')) {
      return 'audio/mp4';
    }
  }
  return 'audio/webm';
}

function getFileExtension(mimeType: string): string {
  if (mimeType.includes('mp4')) return '.m4a';
  if (mimeType.includes('webm')) return '.webm';
  return '.webm';
}

// =============================================================================
// Component
// =============================================================================

export function AudioRecorder({
  onAudioReady,
  maxDuration = 300,
  disabled = false,
}: AudioRecorderProps) {
  const [state, setState] = useState<RecorderState>('idle');
  const [elapsed, setElapsed] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [audioDuration, setAudioDuration] = useState(0);
  const [playbackTime, setPlaybackTime] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [supportsRecording, setSupportsRecording] = useState(true);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const audioBlobRef = useRef<Blob | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Check browser support on mount
  useEffect(() => {
    if (
      typeof navigator === 'undefined' ||
      !navigator.mediaDevices ||
      !navigator.mediaDevices.getUserMedia
    ) {
      setSupportsRecording(false);
    }
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
      }
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
    };
  }, []);

  const stopStream = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
  }, []);

  const clearTimer = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  // ---- Recording ----

  const startRecording = useCallback(async () => {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const mimeType = getPreferredMimeType();
      const recorder = new MediaRecorder(stream, { mimeType });
      mediaRecorderRef.current = recorder;
      chunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          chunksRef.current.push(e.data);
        }
      };

      recorder.onstop = () => {
        const mimeBase = mimeType.split(';')[0] || 'audio/webm';
        const blob = new Blob(chunksRef.current, { type: mimeBase });
        audioBlobRef.current = blob;

        // Create audio element for preview playback
        const audio = new Audio(URL.createObjectURL(blob));
        audio.onloadedmetadata = () => {
          // Handle Infinity duration (common in WebM)
          if (Number.isFinite(audio.duration)) {
            setAudioDuration(Math.round(audio.duration));
          } else {
            setAudioDuration(elapsed);
          }
        };
        audio.onended = () => {
          setIsPlaying(false);
          setPlaybackTime(0);
        };
        audio.ontimeupdate = () => {
          setPlaybackTime(Math.round(audio.currentTime));
        };
        audioRef.current = audio;

        stopStream();
        setState('preview');
      };

      recorder.start(1000); // Collect data every second
      setState('recording');
      setElapsed(0);

      // Start elapsed timer
      timerRef.current = setInterval(() => {
        setElapsed((prev) => {
          const next = prev + 1;
          if (next >= maxDuration) {
            recorder.stop();
            clearTimer();
          }
          return next;
        });
      }, 1000);
    } catch (err) {
      stopStream();
      if (err instanceof DOMException && err.name === 'NotAllowedError') {
        setError('Microphone access denied. Please allow microphone access and try again.');
      } else {
        setError('Could not access microphone. Please check your device settings.');
      }
    }
  }, [maxDuration, stopStream, clearTimer, elapsed]);

  const stopRecording = useCallback(() => {
    clearTimer();
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      mediaRecorderRef.current.stop();
    }
  }, [clearTimer]);

  // ---- Playback ----

  const togglePlayback = useCallback(() => {
    if (!audioRef.current) return;

    if (isPlaying) {
      audioRef.current.pause();
      setIsPlaying(false);
    } else {
      audioRef.current.play();
      setIsPlaying(true);
    }
  }, [isPlaying]);

  // ---- Actions ----

  const reRecord = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      const src = audioRef.current.src;
      audioRef.current = null;
      URL.revokeObjectURL(src);
    }
    audioBlobRef.current = null;
    setIsPlaying(false);
    setPlaybackTime(0);
    setAudioDuration(0);
    setElapsed(0);
    setState('idle');
  }, []);

  const confirmRecording = useCallback(() => {
    if (!audioBlobRef.current) return;

    const mimeType = getPreferredMimeType();
    const ext = getFileExtension(mimeType);
    const file = new File(
      [audioBlobRef.current],
      `recording-${Date.now()}${ext}`,
      { type: audioBlobRef.current.type }
    );
    onAudioReady(file);
  }, [onAudioReady]);

  // ---- File upload fallback ----

  const openFilePicker = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  const handleFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      setError(null);
      const file = e.target.files?.[0];
      if (!file) return;

      if (file.size > MAX_FILE_SIZE) {
        setError(`File too large. Maximum size is ${formatFileSize(MAX_FILE_SIZE)}.`);
        // Reset input so the same file can be re-selected
        e.target.value = '';
        return;
      }

      onAudioReady(file);
      e.target.value = '';
    },
    [onAudioReady]
  );

  // =========================================================================
  // Render
  // =========================================================================

  return (
    <Card className="p-6">
      <input
        ref={fileInputRef}
        type="file"
        accept={ACCEPTED_TYPES}
        onChange={handleFileChange}
        className="hidden"
      />

      {/* Error message */}
      {error && (
        <div className="mb-4 rounded-lg bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {/* ---- Idle state ---- */}
      {state === 'idle' && (
        <div className="flex flex-col items-center gap-4">
          {supportsRecording ? (
            <>
              <Button
                size="lg"
                onClick={startRecording}
                disabled={disabled}
                className="h-16 w-16 rounded-full p-0"
              >
                <Mic className="h-7 w-7" />
              </Button>
              <p className="text-sm font-medium text-foreground">
                Tap to record
              </p>
              <p className="text-xs text-muted-foreground">
                Up to {formatTime(maxDuration)}
              </p>
              <button
                type="button"
                onClick={openFilePicker}
                disabled={disabled}
                className={cn(
                  'text-sm text-muted-foreground underline underline-offset-4 transition-colors',
                  'hover:text-foreground',
                  disabled && 'pointer-events-none opacity-50'
                )}
              >
                <span className="inline-flex items-center gap-1.5">
                  <Upload className="h-3.5 w-3.5" />
                  Upload file instead
                </span>
              </button>
            </>
          ) : (
            <>
              <div className="rounded-full bg-muted p-4">
                <MicOff className="h-8 w-8 text-muted-foreground" />
              </div>
              <p className="text-sm text-muted-foreground text-center">
                Recording is not supported in this browser.
                <br />
                Please upload an audio file instead.
              </p>
              <Button
                variant="outline"
                onClick={openFilePicker}
                disabled={disabled}
                className="gap-2"
              >
                <Upload className="h-4 w-4" />
                Upload audio file
              </Button>
              <p className="text-xs text-muted-foreground">
                MP3, M4A, WAV, or WebM ({formatFileSize(MAX_FILE_SIZE)} max)
              </p>
            </>
          )}
        </div>
      )}

      {/* ---- Recording state ---- */}
      {state === 'recording' && (
        <div className="flex flex-col items-center gap-5">
          {/* Pulsing red dot + elapsed time */}
          <div className="flex items-center gap-3">
            <span className="relative flex h-3 w-3">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-destructive opacity-75" />
              <span className="relative inline-flex h-3 w-3 rounded-full bg-destructive" />
            </span>
            <span className="font-mono text-lg tabular-nums text-foreground">
              {formatTime(elapsed)}
            </span>
          </div>

          <p className="text-xs text-muted-foreground">
            Recording... (max {formatTime(maxDuration)})
          </p>

          <Button
            variant="destructive"
            onClick={stopRecording}
            className="gap-2"
          >
            <MicOff className="h-4 w-4" />
            Stop
          </Button>
        </div>
      )}

      {/* ---- Preview state ---- */}
      {state === 'preview' && (
        <div className="flex flex-col items-center gap-5">
          {/* Playback controls + time */}
          <div className="flex items-center gap-4">
            <Button
              variant="outline"
              size="icon"
              className="h-10 w-10 rounded-full"
              onClick={togglePlayback}
            >
              {isPlaying ? (
                <Pause className="h-4 w-4" />
              ) : (
                <Play className="h-4 w-4" />
              )}
            </Button>
            <span className="font-mono text-lg tabular-nums text-foreground">
              {formatTime(playbackTime)} / {formatTime(audioDuration)}
            </span>
          </div>

          {/* Action buttons */}
          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              onClick={reRecord}
              className="gap-2"
            >
              <RotateCcw className="h-4 w-4" />
              Re-record
            </Button>
            <Button
              onClick={confirmRecording}
              className="gap-2"
            >
              <Check className="h-4 w-4" />
              Use this recording
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
}
