'use client';

/**
 * A2UI FileUpload Component
 * File upload with drag and drop support
 */

import { AlertCircle, CheckCircle2, File, Upload, X } from 'lucide-react';
import { useCallback, useRef, useState } from 'react';

import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { useA2UIAction } from '@/lib/a2ui/context';
import type { ActionConfig, FileUploadProps } from '@/lib/a2ui/types';
import { cn } from '@/lib/utils';


// =============================================================================
// Types
// =============================================================================

interface A2UIFileUploadProps extends FileUploadProps {
  id: string;
  dataBinding?: string;
  onAction?: (action: ActionConfig) => Promise<void>;
}

interface UploadedFile {
  file: File;
  progress: number;
  status: 'pending' | 'uploading' | 'complete' | 'error';
  error?: string;
}

// =============================================================================
// Helpers
// =============================================================================

function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

// =============================================================================
// Component
// =============================================================================

export function FileUpload({
  id,
  accept = ['image/*', 'application/pdf'],
  maxSize = 10 * 1024 * 1024, // 10MB default
  multiple = false,
  onUpload,
  onAction,
}: A2UIFileUploadProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);
  const contextAction = useA2UIAction();
  const handleAction = onAction || contextAction;

  const validateFile = useCallback(
    (file: File): string | null => {
      // Check file size
      if (maxSize && file.size > maxSize) {
        return `File too large. Max size is ${formatFileSize(maxSize)}`;
      }

      // Check file type
      if (accept && accept.length > 0) {
        const isValid = accept.some((type) => {
          if (type.endsWith('/*')) {
            const category = type.split('/')[0];
            return file.type.startsWith(category + '/');
          }
          return file.type === type;
        });
        if (!isValid) {
          return 'File type not accepted';
        }
      }

      return null;
    },
    [accept, maxSize]
  );

  const handleFiles = useCallback(
    async (fileList: FileList) => {
      const newFiles: UploadedFile[] = [];

      for (let i = 0; i < fileList.length; i++) {
        const file = fileList[i];
        if (!file) continue;
        const error = validateFile(file);

        newFiles.push({
          file,
          progress: error ? 0 : 100, // Simulate instant upload for demo
          status: error ? 'error' : 'complete',
          error: error || undefined,
        });
      }

      if (!multiple) {
        setFiles(newFiles.slice(0, 1));
      } else {
        setFiles((prev) => [...prev, ...newFiles]);
      }

      // Trigger onUpload action for successful files
      const successfulFiles = newFiles.filter((f) => f.status === 'complete');
      if (successfulFiles.length > 0 && onUpload) {
        await handleAction({
          ...onUpload,
          payload: {
            ...onUpload.payload,
            files: successfulFiles.map((f) => ({
              name: f.file.name,
              size: f.file.size,
              type: f.file.type,
            })),
          },
        });
      }
    },
    [validateFile, multiple, onUpload, handleAction]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      handleFiles(e.dataTransfer.files);
    },
    [handleFiles]
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      if (e.target.files) {
        handleFiles(e.target.files);
      }
    },
    [handleFiles]
  );

  const removeFile = useCallback((index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const openFilePicker = useCallback(() => {
    inputRef.current?.click();
  }, []);

  return (
    <Card id={id}>
      <CardContent className="p-6">
        {/* Drop zone */}
        <div
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onClick={openFilePicker}
          className={cn(
            'border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors',
            isDragging
              ? 'border-primary bg-primary/5'
              : 'border-muted-foreground/25 hover:border-primary/50 hover:bg-muted/50'
          )}
        >
          <input
            ref={inputRef}
            type="file"
            accept={accept?.join(',')}
            multiple={multiple}
            onChange={handleInputChange}
            className="hidden"
          />

          <div className="flex flex-col items-center gap-4">
            <div
              className={cn(
                'rounded-full p-4 transition-colors',
                isDragging ? 'bg-primary/20' : 'bg-muted'
              )}
            >
              <Upload
                className={cn(
                  'h-8 w-8 transition-colors',
                  isDragging ? 'text-primary' : 'text-muted-foreground'
                )}
              />
            </div>
            <div>
              <p className="font-medium">
                {isDragging ? 'Drop files here' : 'Drag & drop files here'}
              </p>
              <p className="text-sm text-muted-foreground mt-1">
                or click to browse
              </p>
            </div>
            <p className="text-xs text-muted-foreground">
              {accept?.join(', ')} • Max {formatFileSize(maxSize || 10485760)}
            </p>
          </div>
        </div>

        {/* File list */}
        {files.length > 0 && (
          <div className="mt-4 space-y-2">
            {files.map((uploadedFile, index) => (
              <div
                key={index}
                className={cn(
                  'flex items-center gap-3 p-3 rounded-lg border',
                  uploadedFile.status === 'error'
                    ? 'border-destructive/50 bg-destructive/5'
                    : 'border-border'
                )}
              >
                <div
                  className={cn(
                    'rounded-full p-2',
                    uploadedFile.status === 'error'
                      ? 'bg-destructive/10'
                      : uploadedFile.status === 'complete'
                        ? 'bg-status-success/10'
                        : 'bg-muted'
                  )}
                >
                  {uploadedFile.status === 'error' ? (
                    <AlertCircle className="h-4 w-4 text-destructive" />
                  ) : uploadedFile.status === 'complete' ? (
                    <CheckCircle2 className="h-4 w-4 text-status-success" />
                  ) : (
                    <File className="h-4 w-4 text-muted-foreground" />
                  )}
                </div>

                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">
                    {uploadedFile.file.name}
                  </p>
                  {uploadedFile.error ? (
                    <p className="text-xs text-destructive">
                      {uploadedFile.error}
                    </p>
                  ) : (
                    <p className="text-xs text-muted-foreground">
                      {formatFileSize(uploadedFile.file.size)}
                    </p>
                  )}
                  {uploadedFile.status === 'uploading' && (
                    <Progress value={uploadedFile.progress} className="mt-1 h-1" />
                  )}
                </div>

                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8"
                  onClick={(e) => {
                    e.stopPropagation();
                    removeFile(index);
                  }}
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
