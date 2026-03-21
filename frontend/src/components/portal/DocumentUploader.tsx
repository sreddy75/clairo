'use client';

import {
  AlertCircle,
  CheckCircle2,
  FileIcon,
  Loader2,
  Trash2,
  Upload,
  X,
} from 'lucide-react';
import { useCallback, useState } from 'react';
import { useDropzone, type FileRejection } from 'react-dropzone';

import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { useToast } from '@/hooks/use-toast';
import { portalApi, type UploadedDocument } from '@/lib/api/portal';
import { cn } from '@/lib/utils';

// File type configuration
const ACCEPTED_FILE_TYPES = {
  'application/pdf': ['.pdf'],
  'application/msword': ['.doc'],
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
  'application/vnd.ms-excel': ['.xls'],
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
  'text/csv': ['.csv'],
  'text/plain': ['.txt'],
  'image/png': ['.png'],
  'image/jpeg': ['.jpg', '.jpeg'],
  'image/gif': ['.gif'],
  'image/webp': ['.webp'],
};

const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50MB

interface FileUploadStatus {
  file: File;
  progress: number;
  status: 'pending' | 'uploading' | 'success' | 'error';
  error?: string;
  document?: UploadedDocument;
}

interface DocumentUploaderProps {
  onUploadComplete?: (documents: UploadedDocument[]) => void;
  onDocumentsChange?: (documentIds: string[]) => void;
  maxFiles?: number;
  documentType?: string;
  className?: string;
}

function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

function getFileIcon(_contentType: string): React.ReactNode {
  // Could be extended with specific icons per type
  return <FileIcon className="h-4 w-4" />;
}

export function DocumentUploader({
  onUploadComplete,
  onDocumentsChange,
  maxFiles = 10,
  documentType,
  className,
}: DocumentUploaderProps) {
  const { toast } = useToast();
  const [files, setFiles] = useState<FileUploadStatus[]>([]);
  const [isUploading, setIsUploading] = useState(false);

  // Handle file drop
  const onDrop = useCallback(
    async (acceptedFiles: File[], fileRejections: FileRejection[]) => {
      // Handle rejections
      if (fileRejections.length > 0) {
        const errors = fileRejections.map((rejection) => {
          const error = rejection.errors[0];
          if (!error) {
            return `${rejection.file.name}: Unknown error`;
          }
          if (error.code === 'file-too-large') {
            return `${rejection.file.name}: File is too large (max 50MB)`;
          }
          if (error.code === 'file-invalid-type') {
            return `${rejection.file.name}: Invalid file type`;
          }
          return `${rejection.file.name}: ${error.message}`;
        });

        toast({
          title: 'Some files were rejected',
          description: errors.join('\n'),
          variant: 'destructive',
        });
      }

      if (acceptedFiles.length === 0) return;

      // Check max files limit
      const currentCount = files.filter((f) => f.status === 'success').length;
      if (currentCount + acceptedFiles.length > maxFiles) {
        toast({
          title: 'Too many files',
          description: `You can only upload up to ${maxFiles} files`,
          variant: 'destructive',
        });
        return;
      }

      // Add files to state with pending status
      const newFiles: FileUploadStatus[] = acceptedFiles.map((file) => ({
        file,
        progress: 0,
        status: 'pending' as const,
      }));

      setFiles((prev) => [...prev, ...newFiles]);

      // Upload files
      setIsUploading(true);

      const uploadedDocuments: UploadedDocument[] = [];

      for (let i = 0; i < newFiles.length; i++) {
        const fileStatus = newFiles[i];
        if (!fileStatus) continue;

        // Update to uploading
        setFiles((prev) =>
          prev.map((f) =>
            f.file === fileStatus.file ? { ...f, status: 'uploading' as const } : f
          )
        );

        try {
          const document = await portalApi.documents.upload(
            fileStatus.file,
            documentType,
            (progress) => {
              setFiles((prev) =>
                prev.map((f) =>
                  f.file === fileStatus.file ? { ...f, progress } : f
                )
              );
            }
          );

          uploadedDocuments.push(document);

          setFiles((prev) =>
            prev.map((f) =>
              f.file === fileStatus.file
                ? { ...f, status: 'success' as const, progress: 100, document }
                : f
            )
          );
        } catch (error) {
          setFiles((prev) =>
            prev.map((f) =>
              f.file === fileStatus.file
                ? {
                    ...f,
                    status: 'error' as const,
                    error: error instanceof Error ? error.message : 'Upload failed',
                  }
                : f
            )
          );
        }
      }

      setIsUploading(false);

      if (uploadedDocuments.length > 0) {
        onUploadComplete?.(uploadedDocuments);

        // Update document IDs
        const allDocumentIds = files
          .filter((f) => f.status === 'success' && f.document)
          .map((f) => f.document!.id)
          .concat(uploadedDocuments.map((d) => d.id));
        onDocumentsChange?.(allDocumentIds);
      }
    },
    [files, maxFiles, documentType, toast, onUploadComplete, onDocumentsChange]
  );

  // Remove a file from the list
  const removeFile = async (fileStatus: FileUploadStatus) => {
    // If already uploaded, try to delete from server
    if (fileStatus.document) {
      try {
        await portalApi.documents.delete(fileStatus.document.id);
      } catch {
        // Ignore delete errors
      }
    }

    setFiles((prev) => prev.filter((f) => f.file !== fileStatus.file));

    // Update document IDs
    const remainingDocumentIds = files
      .filter((f) => f.status === 'success' && f.document && f.file !== fileStatus.file)
      .map((f) => f.document!.id);
    onDocumentsChange?.(remainingDocumentIds);
  };

  // Clear all files
  const clearAll = () => {
    setFiles([]);
    onDocumentsChange?.([]);
  };

  const { getRootProps, getInputProps, isDragActive, isDragReject } = useDropzone({
    onDrop,
    accept: ACCEPTED_FILE_TYPES,
    maxSize: MAX_FILE_SIZE,
    maxFiles,
    disabled: isUploading,
  });

  const successCount = files.filter((f) => f.status === 'success').length;
  const errorCount = files.filter((f) => f.status === 'error').length;

  return (
    <div className={cn('space-y-4', className)}>
      {/* Dropzone */}
      <div
        {...getRootProps()}
        className={cn(
          'border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors',
          isDragActive && !isDragReject && 'border-primary bg-primary/5',
          isDragReject && 'border-destructive bg-destructive/5',
          !isDragActive && 'border-muted-foreground/25 hover:border-muted-foreground/50',
          isUploading && 'opacity-50 cursor-not-allowed'
        )}
      >
        <input {...getInputProps()} />
        <Upload className="mx-auto h-10 w-10 text-muted-foreground mb-3" />
        {isDragActive ? (
          isDragReject ? (
            <p className="text-sm text-destructive">Some files are not allowed</p>
          ) : (
            <p className="text-sm text-primary">Drop files here...</p>
          )
        ) : (
          <>
            <p className="text-sm font-medium">
              Drag & drop files here, or click to select
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              PDF, Word, Excel, CSV, images up to 50MB
            </p>
          </>
        )}
      </div>

      {/* File List */}
      {files.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium">
              {successCount > 0 && `${successCount} uploaded`}
              {errorCount > 0 && `, ${errorCount} failed`}
            </p>
            <Button
              variant="ghost"
              size="sm"
              onClick={clearAll}
              disabled={isUploading}
            >
              Clear all
            </Button>
          </div>

          <div className="space-y-2">
            {files.map((fileStatus, index) => (
              <div
                key={`${fileStatus.file.name}-${index}`}
                className={cn(
                  'flex items-center gap-3 p-3 rounded-lg border',
                  fileStatus.status === 'error' && 'border-destructive/50 bg-destructive/5',
                  fileStatus.status === 'success' && 'border-green-500/50 bg-green-50/50'
                )}
              >
                {/* File icon */}
                <div className="flex-shrink-0">
                  {fileStatus.status === 'uploading' ? (
                    <Loader2 className="h-4 w-4 animate-spin text-primary" />
                  ) : fileStatus.status === 'success' ? (
                    <CheckCircle2 className="h-4 w-4 text-green-500" />
                  ) : fileStatus.status === 'error' ? (
                    <AlertCircle className="h-4 w-4 text-destructive" />
                  ) : (
                    getFileIcon(fileStatus.file.type)
                  )}
                </div>

                {/* File info */}
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">
                    {fileStatus.file.name}
                  </p>
                  <div className="flex items-center gap-2">
                    <p className="text-xs text-muted-foreground">
                      {formatFileSize(fileStatus.file.size)}
                    </p>
                    {fileStatus.status === 'error' && fileStatus.error && (
                      <p className="text-xs text-destructive">{fileStatus.error}</p>
                    )}
                  </div>

                  {/* Progress bar */}
                  {fileStatus.status === 'uploading' && (
                    <Progress
                      value={fileStatus.progress}
                      className="h-1 mt-2"
                    />
                  )}
                </div>

                {/* Remove button */}
                <Button
                  variant="ghost"
                  size="icon"
                  className="flex-shrink-0 h-8 w-8"
                  onClick={(e) => {
                    e.stopPropagation();
                    removeFile(fileStatus);
                  }}
                  disabled={fileStatus.status === 'uploading'}
                >
                  {fileStatus.status === 'uploading' ? (
                    <X className="h-4 w-4" />
                  ) : (
                    <Trash2 className="h-4 w-4" />
                  )}
                </Button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Error summary */}
      {errorCount > 0 && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            {errorCount} file{errorCount !== 1 ? 's' : ''} failed to upload.
            You can try uploading them again.
          </AlertDescription>
        </Alert>
      )}
    </div>
  );
}

export default DocumentUploader;
