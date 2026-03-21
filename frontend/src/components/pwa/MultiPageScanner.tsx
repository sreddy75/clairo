/**
 * Multi-Page Scanner Component
 *
 * Captures multiple pages and generates a PDF.
 *
 * Spec: 032-pwa-mobile-document-capture
 */

'use client';

import {
  Camera,
  FileText,
  Plus,
  Loader2,
  CheckCircle2,
  AlertCircle,
  X,
} from 'lucide-react';
import { useState, useCallback, useEffect } from 'react';

import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { compressImage, createThumbnail } from '@/lib/pwa/image-processor';
import { generatePDF, type PageData } from '@/lib/pwa/pdf-generator';
import { cn } from '@/lib/utils';

import { CameraCapture } from './CameraCapture';
import { PageThumbnailStrip, type PageThumbnail } from './PageThumbnailStrip';

type ScannerState =
  | 'idle'
  | 'camera'
  | 'reviewing'
  | 'generating'
  | 'uploading'
  | 'success'
  | 'error';

interface CapturedPage {
  id: string;
  imageBlob: Blob;
  thumbnailUrl: string;
  order: number;
}

interface MultiPageScannerProps {
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

export function MultiPageScanner({
  requestId,
  onSuccess,
  onCancel,
  uploadFile,
  className,
}: MultiPageScannerProps) {
  const [state, setState] = useState<ScannerState>('idle');
  const [pages, setPages] = useState<CapturedPage[]>([]);
  const [selectedPageId, setSelectedPageId] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);

  // Cleanup thumbnail URLs on unmount
  useEffect(() => {
    return () => {
      pages.forEach((page) => URL.revokeObjectURL(page.thumbnailUrl));
    };
  }, [pages]);

  const handleStartCamera = () => {
    setState('camera');
    setError(null);
  };

  const handleCapture = useCallback(async (blob: Blob) => {
    try {
      // Compress image
      const compressed = await compressImage(blob, {
        maxWidth: 2048,
        maxHeight: 2048,
        quality: 0.85,
        fixOrientation: true,
      });

      // Create thumbnail
      const thumbnailBlob = await createThumbnail(compressed.blob, 150);
      const thumbnailUrl = URL.createObjectURL(thumbnailBlob);

      const newPage: CapturedPage = {
        id: crypto.randomUUID(),
        imageBlob: compressed.blob,
        thumbnailUrl,
        order: pages.length,
      };

      setPages((prev) => [...prev, newPage]);
      setState('reviewing');
    } catch (err) {
      console.error('[Scanner] Failed to process capture:', err);
      setError('Failed to process image');
      setState('error');
    }
  }, [pages.length]);

  const handleAddPage = () => {
    setState('camera');
  };

  const handleDeletePage = useCallback((id: string) => {
    setPages((prev) => {
      const page = prev.find((p) => p.id === id);
      if (page) {
        URL.revokeObjectURL(page.thumbnailUrl);
      }

      const remaining = prev.filter((p) => p.id !== id);
      // Re-order remaining pages
      return remaining.map((p, i) => ({ ...p, order: i }));
    });

    if (selectedPageId === id) {
      setSelectedPageId(null);
    }
  }, [selectedPageId]);

  const handleReorder = useCallback((reorderedPages: PageThumbnail[]) => {
    setPages((prev) => {
      return reorderedPages.map((thumbnail) => {
        const original = prev.find((p) => p.id === thumbnail.id);
        if (!original) return original!;
        return { ...original, order: thumbnail.order };
      });
    });
  }, []);

  const handleGenerateAndUpload = useCallback(async () => {
    if (pages.length === 0) return;

    setState('generating');
    setProgress(0);
    setError(null);

    try {
      // Convert pages to PageData format
      const pageDataPromises = pages.map(async (page): Promise<PageData> => ({
        id: page.id,
        imageData: await page.imageBlob.arrayBuffer(),
        order: page.order,
      }));

      const pageData = await Promise.all(pageDataPromises);
      setProgress(30);

      // Generate PDF
      const pdf = await generatePDF(pageData, {
        title: `Document ${new Date().toLocaleDateString()}`,
        orientation: 'auto',
        pageSize: 'a4',
      });

      setProgress(60);

      // Create file from blob
      const file = new File([pdf.blob], pdf.filename, {
        type: 'application/pdf',
      });

      // Upload
      setState('uploading');

      const response = await uploadFile(requestId, file);
      setProgress(100);

      setState('success');

      // Cleanup
      pages.forEach((page) => URL.revokeObjectURL(page.thumbnailUrl));

      setTimeout(() => {
        onSuccess?.(response.id);
      }, 1500);
    } catch (err) {
      console.error('[Scanner] Generate/upload failed:', err);
      setError(err instanceof Error ? err.message : 'Failed to create PDF');
      setState('error');
    }
  }, [pages, requestId, uploadFile, onSuccess]);

  const handleClose = useCallback(() => {
    pages.forEach((page) => URL.revokeObjectURL(page.thumbnailUrl));
    setPages([]);
    setState('idle');
    onCancel?.();
  }, [pages, onCancel]);

  const handleRetry = useCallback(() => {
    if (pages.length > 0) {
      setState('reviewing');
    } else {
      setState('camera');
    }
    setError(null);
  }, [pages.length]);

  // Camera state
  if (state === 'camera') {
    return (
      <CameraCapture
        onCapture={handleCapture}
        onClose={() => {
          if (pages.length > 0) {
            setState('reviewing');
          } else {
            handleClose();
          }
        }}
      />
    );
  }

  // Reviewing state
  if (state === 'reviewing') {
    const thumbnails: PageThumbnail[] = pages.map((p) => ({
      id: p.id,
      imageUrl: p.thumbnailUrl,
      order: p.order,
    }));

    return (
      <div className="fixed inset-0 z-50 bg-black flex flex-col">
        {/* Header */}
        <div className="p-4 flex items-center justify-between bg-black/80">
          <Button
            variant="ghost"
            size="icon"
            className="text-white hover:bg-white/20"
            onClick={handleClose}
          >
            <X className="h-6 w-6" />
          </Button>
          <span className="text-white font-medium">
            {pages.length} page{pages.length !== 1 ? 's' : ''}
          </span>
          <div className="w-10" />
        </div>

        {/* Pages strip */}
        <div className="bg-foreground p-4">
          <PageThumbnailStrip
            pages={thumbnails}
            selectedId={selectedPageId ?? undefined}
            onSelect={setSelectedPageId}
            onDelete={handleDeletePage}
            onReorder={handleReorder}
          />
        </div>

        {/* Preview area */}
        <div className="flex-1 flex items-center justify-center p-4">
          {selectedPageId ? (
            <div className="relative max-w-full max-h-full">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={pages.find((p) => p.id === selectedPageId)?.thumbnailUrl}
                alt="Selected page"
                className="max-w-full max-h-[50vh] object-contain rounded-lg"
              />
            </div>
          ) : (
            <div className="text-center text-muted-foreground">
              <FileText className="h-16 w-16 mx-auto mb-4 opacity-50" />
              <p>Tap a page to preview</p>
              <p className="text-sm mt-1">Drag pages to reorder</p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 bg-black/80 space-y-3">
          <div className="flex gap-3">
            <Button
              variant="outline"
              className="flex-1 bg-white/10 border-white/30 text-white"
              onClick={handleAddPage}
            >
              <Plus className="h-4 w-4 mr-2" />
              Add Page
            </Button>
            <Button
              className="flex-1 bg-green-500 hover:bg-green-600"
              onClick={handleGenerateAndUpload}
              disabled={pages.length === 0}
            >
              <FileText className="h-4 w-4 mr-2" />
              Create PDF
            </Button>
          </div>
        </div>
      </div>
    );
  }

  // Generating state
  if (state === 'generating') {
    return (
      <div className="fixed inset-0 z-50 bg-black flex flex-col items-center justify-center p-6">
        <div className="text-center text-white space-y-6 w-full max-w-sm">
          <Loader2 className="h-12 w-12 animate-spin mx-auto text-blue-400" />
          <h2 className="text-xl font-semibold">Creating PDF</h2>
          <Progress value={progress} className="h-2" />
          <p className="text-sm text-muted-foreground">
            Combining {pages.length} page{pages.length !== 1 ? 's' : ''}...
          </p>
        </div>
      </div>
    );
  }

  // Uploading state
  if (state === 'uploading') {
    return (
      <div className="fixed inset-0 z-50 bg-black flex flex-col items-center justify-center p-6">
        <div className="text-center text-white space-y-6 w-full max-w-sm">
          <FileText className="h-12 w-12 mx-auto text-blue-400 animate-pulse" />
          <h2 className="text-xl font-semibold">Uploading PDF</h2>
          <Progress value={progress} className="h-2" />
          <p className="text-sm text-muted-foreground">{progress}%</p>
        </div>
      </div>
    );
  }

  // Success state
  if (state === 'success') {
    return (
      <div className="fixed inset-0 z-50 bg-black flex flex-col items-center justify-center p-6">
        <div className="text-center text-white space-y-4">
          <div className="mx-auto w-16 h-16 rounded-full bg-green-500/20 flex items-center justify-center">
            <CheckCircle2 className="h-8 w-8 text-green-500" />
          </div>
          <h2 className="text-xl font-semibold">PDF Uploaded!</h2>
          <p className="text-muted-foreground">
            Your {pages.length}-page document has been uploaded.
          </p>
        </div>
      </div>
    );
  }

  // Error state
  if (state === 'error') {
    return (
      <div className="fixed inset-0 z-50 bg-black flex flex-col items-center justify-center p-6">
        <div className="text-center text-white space-y-4 max-w-sm">
          <div className="mx-auto w-16 h-16 rounded-full bg-red-500/20 flex items-center justify-center">
            <AlertCircle className="h-8 w-8 text-red-500" />
          </div>
          <h2 className="text-xl font-semibold">Something Went Wrong</h2>
          <p className="text-muted-foreground">{error || 'An error occurred'}</p>
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

  // Idle state - show "Scan Document" button
  return (
    <Button onClick={handleStartCamera} className={cn('gap-2', className)}>
      <Camera className="h-4 w-4" />
      Scan Document
    </Button>
  );
}
