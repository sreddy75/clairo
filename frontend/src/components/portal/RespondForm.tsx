'use client';

import { zodResolver } from '@hookform/resolvers/zod';
import { Loader2, Send, Upload, X, FileText } from 'lucide-react';
import { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { useForm } from 'react-hook-form';
import * as z from 'zod';

import { Button } from '@/components/ui/button';
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import { Textarea } from '@/components/ui/textarea';
import { useToast } from '@/hooks/use-toast';
import { portalApi } from '@/lib/api/portal';
import { cn } from '@/lib/utils';

const formSchema = z.object({
  message: z.string().max(2000, 'Message cannot exceed 2000 characters').optional(),
});

type FormValues = z.infer<typeof formSchema>;

interface RespondFormProps {
  requestId: string;
  onSuccess?: () => void;
}

interface UploadedFile {
  id: string;
  filename: string;
  size: number;
}

export function RespondForm({ requestId, onSuccess }: RespondFormProps) {
  const { toast } = useToast();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      message: '',
    },
  });

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    if (acceptedFiles.length === 0) return;

    setIsUploading(true);

    for (const file of acceptedFiles) {
      try {
        const formData = new FormData();
        formData.append('file', file);

        const result = await portalApi.documents.upload(file);

        setUploadedFiles((prev) => [
          ...prev,
          {
            id: result.id,
            filename: result.filename,
            size: result.file_size,
          },
        ]);

        toast({
          title: 'File uploaded',
          description: `${file.name} uploaded successfully`,
        });
      } catch {
        toast({
          title: 'Upload failed',
          description: `Failed to upload ${file.name}`,
          variant: 'destructive',
        });
      }
    }

    setIsUploading(false);
  }, [toast]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'image/*': ['.png', '.jpg', '.jpeg', '.gif'],
      'application/msword': ['.doc'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'application/vnd.ms-excel': ['.xls'],
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
    },
    maxSize: 50 * 1024 * 1024, // 50MB
    disabled: isUploading || isSubmitting,
  });

  const removeFile = (fileId: string) => {
    setUploadedFiles((prev) => prev.filter((f) => f.id !== fileId));
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const handleSubmit = async (values: FormValues) => {
    if (!values.message && uploadedFiles.length === 0) {
      toast({
        title: 'Nothing to submit',
        description: 'Please add a message or upload at least one document.',
        variant: 'destructive',
      });
      return;
    }

    setIsSubmitting(true);

    try {
      await portalApi.requests.respond(requestId, {
        message: values.message || undefined,
        document_ids: uploadedFiles.map((f) => f.id),
      });

      toast({
        title: 'Response submitted',
        description: 'Your response has been sent successfully.',
      });

      form.reset();
      setUploadedFiles([]);
      onSuccess?.();
    } catch (error) {
      toast({
        title: 'Error',
        description:
          error instanceof Error ? error.message : 'Failed to submit response',
        variant: 'destructive',
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-4">
        <FormField
          control={form.control}
          name="message"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Message (Optional)</FormLabel>
              <FormControl>
                <Textarea
                  placeholder="Add a message for your accountant..."
                  className="min-h-[100px] resize-none"
                  {...field}
                />
              </FormControl>
              <FormDescription>
                Include any notes or questions for your accountant.
              </FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />

        {/* Document Upload Area */}
        <div className="space-y-3">
          <label className="text-sm font-medium">Attach Documents</label>
          <div
            {...getRootProps()}
            className={cn(
              'border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors',
              isDragActive
                ? 'border-primary bg-primary/5'
                : 'border-muted-foreground/25 hover:border-primary/50',
              (isUploading || isSubmitting) && 'opacity-50 cursor-not-allowed'
            )}
          >
            <input {...getInputProps()} />
            {isUploading ? (
              <>
                <Loader2 className="mx-auto h-8 w-8 text-muted-foreground mb-2 animate-spin" />
                <p className="text-sm text-muted-foreground">Uploading...</p>
              </>
            ) : isDragActive ? (
              <>
                <Upload className="mx-auto h-8 w-8 text-primary mb-2" />
                <p className="text-sm text-primary font-medium">Drop files here</p>
              </>
            ) : (
              <>
                <Upload className="mx-auto h-8 w-8 text-muted-foreground mb-2" />
                <p className="text-sm text-muted-foreground">
                  Drag & drop files here, or click to select
                </p>
                <p className="text-xs text-muted-foreground mt-1">
                  PDF, Word, Excel, or images up to 50MB
                </p>
              </>
            )}
          </div>

          {/* Uploaded Files List */}
          {uploadedFiles.length > 0 && (
            <div className="space-y-2">
              {uploadedFiles.map((file) => (
                <div
                  key={file.id}
                  className="flex items-center justify-between p-3 bg-muted/50 rounded-lg"
                >
                  <div className="flex items-center gap-3">
                    <FileText className="h-5 w-5 text-muted-foreground" />
                    <div>
                      <p className="text-sm font-medium truncate max-w-[200px]">
                        {file.filename}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {formatFileSize(file.size)}
                      </p>
                    </div>
                  </div>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => removeFile(file.id)}
                    disabled={isSubmitting}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="flex justify-end gap-3">
          <Button
            type="button"
            variant="outline"
            onClick={() => {
              form.reset();
              setUploadedFiles([]);
            }}
            disabled={isSubmitting}
          >
            Clear
          </Button>
          <Button type="submit" disabled={isSubmitting || isUploading}>
            {isSubmitting ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Send className="mr-2 h-4 w-4" />
            )}
            Submit Response
          </Button>
        </div>
      </form>
    </Form>
  );
}

export default RespondForm;
