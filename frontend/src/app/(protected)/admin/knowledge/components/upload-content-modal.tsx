'use client';

import { useAuth } from '@clerk/nextjs';
import { AlertCircle, FileText, Loader2, Upload, X } from 'lucide-react';
import { useCallback, useState } from 'react';

import {
  addManualContent,
  uploadDocument,
  type FileUploadResponse,
  type ManualContentUploadResponse,
} from '@/lib/api/knowledge';
import type { KnowledgeSource } from '@/types/knowledge';

type UploadMode = 'text' | 'file';

interface UploadContentModalProps {
  isOpen: boolean;
  onClose: () => void;
  source: KnowledgeSource;
  onSuccess: () => void;
}

const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB

export function UploadContentModal({
  isOpen,
  onClose,
  source,
  onSuccess,
}: UploadContentModalProps) {
  const { getToken } = useAuth();
  const [mode, setMode] = useState<UploadMode>('text');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Text mode state
  const [title, setTitle] = useState('');
  const [text, setText] = useState('');
  const [sourceUrl, setSourceUrl] = useState('');

  // File mode state
  const [file, setFile] = useState<File | null>(null);
  const [fileTitle, setFileTitle] = useState('');
  const [fileSourceUrl, setFileSourceUrl] = useState('');
  const [dragActive, setDragActive] = useState(false);

  const resetForm = useCallback(() => {
    setTitle('');
    setText('');
    setSourceUrl('');
    setFile(null);
    setFileTitle('');
    setFileSourceUrl('');
    setError(null);
    setSuccess(null);
  }, []);

  const handleClose = () => {
    resetForm();
    onClose();
  };

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  }, []);

  const validateFile = (f: File): string | null => {
    // Check size
    if (f.size > MAX_FILE_SIZE) {
      return 'File too large. Maximum size is 10MB.';
    }

    // Check type
    const ext = f.name.split('.').pop()?.toLowerCase();
    if (!ext || !['pdf', 'docx', 'txt'].includes(ext)) {
      return 'Unsupported file type. Please upload PDF, DOCX, or TXT files.';
    }

    return null;
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const droppedFile = e.dataTransfer.files[0];
      const validationError = validateFile(droppedFile);
      if (validationError) {
        setError(validationError);
        return;
      }
      setFile(droppedFile);
      setError(null);
    }
  }, []);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selectedFile = e.target.files[0];
      const validationError = validateFile(selectedFile);
      if (validationError) {
        setError(validationError);
        return;
      }
      setFile(selectedFile);
      setError(null);
    }
  };

  const handleSubmitText = async () => {
    if (!title.trim()) {
      setError('Please enter a title');
      return;
    }
    if (!text.trim() || text.length < 10) {
      setError('Please enter at least 10 characters of content');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const token = await getToken();
      if (!token) throw new Error('Not authenticated');

      const result: ManualContentUploadResponse = await addManualContent(
        token,
        source.id,
        {
          title: title.trim(),
          text: text.trim(),
          source_url: sourceUrl.trim() || undefined,
        }
      );

      setSuccess(result.message);
      setTimeout(() => {
        handleClose();
        onSuccess();
      }, 1500);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add content');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmitFile = async () => {
    if (!file) {
      setError('Please select a file');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const token = await getToken();
      if (!token) throw new Error('Not authenticated');

      const result: FileUploadResponse = await uploadDocument(
        token,
        source.id,
        file,
        fileTitle.trim() || undefined,
        fileSourceUrl.trim() || undefined
      );

      setSuccess(result.message);
      setTimeout(() => {
        handleClose();
        onSuccess();
      }, 1500);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to upload file');
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={handleClose}
      />

      {/* Modal */}
      <div className="relative bg-card rounded-2xl shadow-2xl w-full max-w-2xl mx-4 max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 bg-muted border-b border-border">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-primary/10 rounded-lg">
                <Upload className="w-5 h-5 text-primary" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-foreground">
                  Add Content
                </h2>
                <p className="text-sm text-muted-foreground truncate max-w-md">
                  {source.name}
                </p>
              </div>
            </div>
            <button
              onClick={handleClose}
              className="p-1 hover:bg-muted rounded-full transition-colors"
            >
              <X className="w-5 h-5 text-muted-foreground" />
            </button>
          </div>
        </div>

        {/* Mode Toggle */}
        <div className="px-6 pt-4">
          <div className="flex items-center bg-muted rounded-lg p-1">
            <button
              onClick={() => setMode('text')}
              className={`flex-1 flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                mode === 'text'
                  ? 'bg-card text-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              <FileText className="w-4 h-4" />
              Paste Text
            </button>
            <button
              onClick={() => setMode('file')}
              className={`flex-1 flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                mode === 'file'
                  ? 'bg-card text-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              <Upload className="w-4 h-4" />
              Upload File
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto max-h-[calc(90vh-280px)]">
          {/* Error Message */}
          {error && (
            <div className="mb-4 p-3 bg-status-danger/10 border border-status-danger/20 rounded-lg flex items-center gap-2 text-status-danger">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <span className="text-sm">{error}</span>
            </div>
          )}

          {/* Success Message */}
          {success && (
            <div className="mb-4 p-3 bg-status-success/10 border border-status-success/20 rounded-lg text-status-success text-sm">
              {success}
            </div>
          )}

          {mode === 'text' ? (
            /* Text Input Mode */
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-foreground mb-1">
                  Title <span className="text-status-danger">*</span>
                </label>
                <input
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="e.g., GST Registration Requirements"
                  className="w-full px-3 py-2 border border-border rounded-lg focus:ring-2 focus:ring-primary/20 focus:border-primary bg-background text-foreground"
                  disabled={loading}
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-foreground mb-1">
                  Content <span className="text-status-danger">*</span>
                </label>
                <textarea
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  placeholder="Paste or type your content here..."
                  rows={10}
                  className="w-full px-3 py-2 border border-border rounded-lg focus:ring-2 focus:ring-primary/20 focus:border-primary bg-background text-foreground resize-none font-mono text-sm"
                  disabled={loading}
                />
                <p className="mt-1 text-xs text-muted-foreground">
                  {text.length} characters
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-foreground mb-1">
                  Source URL (optional)
                </label>
                <input
                  type="url"
                  value={sourceUrl}
                  onChange={(e) => setSourceUrl(e.target.value)}
                  placeholder="https://..."
                  className="w-full px-3 py-2 border border-border rounded-lg focus:ring-2 focus:ring-primary/20 focus:border-primary bg-background text-foreground"
                  disabled={loading}
                />
              </div>
            </div>
          ) : (
            /* File Upload Mode */
            <div className="space-y-4">
              {/* Drop Zone */}
              <div
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
                className={`relative border-2 border-dashed rounded-xl p-8 text-center transition-colors ${
                  dragActive
                    ? 'border-primary bg-primary/10'
                    : file
                    ? 'border-status-success/20 bg-status-success/10'
                    : 'border-border hover:border-border'
                }`}
              >
                <input
                  type="file"
                  accept=".pdf,.docx,.txt"
                  onChange={handleFileChange}
                  className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                  disabled={loading}
                />

                {file ? (
                  <div className="flex flex-col items-center">
                    <FileText className="w-12 h-12 text-status-success mb-3" />
                    <p className="font-medium text-foreground">
                      {file.name}
                    </p>
                    <p className="text-sm text-muted-foreground">
                      {(file.size / 1024 / 1024).toFixed(2)} MB
                    </p>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setFile(null);
                      }}
                      className="mt-2 text-sm text-status-danger hover:text-status-danger"
                    >
                      Remove file
                    </button>
                  </div>
                ) : (
                  <div className="flex flex-col items-center">
                    <Upload className="w-12 h-12 text-muted-foreground mb-3" />
                    <p className="font-medium text-foreground">
                      Drop your file here, or click to browse
                    </p>
                    <p className="text-sm text-muted-foreground mt-1">
                      PDF, DOCX, or TXT (max 10MB)
                    </p>
                  </div>
                )}
              </div>

              <div>
                <label className="block text-sm font-medium text-foreground mb-1">
                  Title (optional - extracted from document if not provided)
                </label>
                <input
                  type="text"
                  value={fileTitle}
                  onChange={(e) => setFileTitle(e.target.value)}
                  placeholder="Override document title..."
                  className="w-full px-3 py-2 border border-border rounded-lg focus:ring-2 focus:ring-primary/20 focus:border-primary bg-background text-foreground"
                  disabled={loading}
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-foreground mb-1">
                  Source URL (optional)
                </label>
                <input
                  type="url"
                  value={fileSourceUrl}
                  onChange={(e) => setFileSourceUrl(e.target.value)}
                  placeholder="https://..."
                  className="w-full px-3 py-2 border border-border rounded-lg focus:ring-2 focus:ring-primary/20 focus:border-primary bg-background text-foreground"
                  disabled={loading}
                />
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 bg-muted border-t border-border flex items-center justify-end gap-3">
          <button
            type="button"
            onClick={handleClose}
            disabled={loading}
            className="px-4 py-2 text-sm font-medium text-foreground bg-card border border-border rounded-lg hover:bg-muted disabled:opacity-50 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={mode === 'text' ? handleSubmitText : handleSubmitFile}
            disabled={loading || (mode === 'text' ? !title || !text : !file)}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-primary-foreground bg-primary rounded-lg hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Processing...
              </>
            ) : (
              <>
                <Upload className="w-4 h-4" />
                {mode === 'text' ? 'Add Content' : 'Upload & Process'}
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
