'use client';

import { zodResolver } from '@hookform/resolvers/zod';
import { addDays, format } from 'date-fns';
import { CalendarIcon, Loader2, Send, Save } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import * as z from 'zod';

import { Button } from '@/components/ui/button';
import { Calendar } from '@/components/ui/calendar';
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { Textarea } from '@/components/ui/textarea';
import { useToast } from '@/hooks/use-toast';
import {
  type CreateDocumentRequest,
  type DocumentRequestTemplate,
  useRequestsApi,
} from '@/lib/api/requests';
import { cn } from '@/lib/utils';

import { TemplateCombobox, QuickTemplatePicks } from './TemplateCombobox';

const formSchema = z.object({
  title: z.string().min(1, 'Title is required').max(200),
  description: z.string().min(1, 'Description is required'),
  recipient_email: z.string().email('Please enter a valid email address').min(1, 'Email is required'),
  due_date: z.date().optional(),
  priority: z.enum(['low', 'normal', 'high', 'urgent']),
  period_start: z.date().optional(),
  period_end: z.date().optional(),
  auto_remind: z.boolean(),
});

type FormValues = z.infer<typeof formSchema>;

interface RequestFormProps {
  connectionId: string;
  clientName: string;
  clientEmail?: string;
  onSuccess?: () => void;
  /** If true, shows the integrated template selector. Default: true */
  showTemplateSelector?: boolean;
  /** Initial template to use (when controlled externally) */
  initialTemplate?: DocumentRequestTemplate | null;
}

const PRIORITY_OPTIONS = [
  { value: 'low', label: 'Low', description: 'No rush' },
  { value: 'normal', label: 'Normal', description: 'Standard timeline' },
  { value: 'high', label: 'High', description: 'Prioritize this request' },
  { value: 'urgent', label: 'Urgent', description: 'Needs immediate attention' },
];

export function RequestForm({
  connectionId,
  clientName,
  clientEmail = '',
  onSuccess,
  showTemplateSelector = true,
  initialTemplate = null,
}: RequestFormProps) {
  const router = useRouter();
  const api = useRequestsApi();
  const { toast } = useToast();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState<DocumentRequestTemplate | null>(
    initialTemplate
  );

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      title: '',
      description: '',
      recipient_email: clientEmail,
      due_date: addDays(new Date(), 7),
      priority: 'normal',
      auto_remind: true,
    },
  });

  // Update form values when template changes
  useEffect(() => {
    if (selectedTemplate) {
      const dueDays = selectedTemplate.default_due_days ?? 7;
      form.setValue('title', selectedTemplate.name);
      form.setValue('description', selectedTemplate.description_template);
      form.setValue('priority', selectedTemplate.default_priority as 'low' | 'normal' | 'high' | 'urgent');
      form.setValue('due_date', addDays(new Date(), dueDays));
    } else {
      // Clear form when template is deselected (keeping email)
      form.setValue('title', '');
      form.setValue('description', '');
      form.setValue('priority', 'normal');
      form.setValue('due_date', addDays(new Date(), 7));
    }
  }, [selectedTemplate, form]);

  const handleTemplateSelect = (template: DocumentRequestTemplate | null) => {
    setSelectedTemplate(template);
  };

  const handleSubmit = async (values: FormValues, sendImmediately: boolean) => {
    setIsSubmitting(true);

    try {
      const requestData: CreateDocumentRequest = {
        connection_id: connectionId,
        template_id: selectedTemplate?.id,
        title: values.title,
        description: values.description,
        recipient_email: values.recipient_email,
        due_date: values.due_date ? format(values.due_date, 'yyyy-MM-dd') : undefined,
        priority: values.priority,
        period_start: values.period_start
          ? format(values.period_start, 'yyyy-MM-dd')
          : undefined,
        period_end: values.period_end
          ? format(values.period_end, 'yyyy-MM-dd')
          : undefined,
        auto_remind: values.auto_remind,
        send_immediately: sendImmediately,
      };

      await api.requests.create(connectionId, requestData);

      toast({
        title: sendImmediately ? 'Request sent' : 'Draft saved',
        description: sendImmediately
          ? `Document request has been sent to ${clientName}`
          : 'Document request saved as draft',
      });

      onSuccess?.();
      router.push(`/clients/${connectionId}`);
    } catch (error) {
      toast({
        title: 'Error',
        description: error instanceof Error ? error.message : 'Failed to create request',
        variant: 'destructive',
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Form {...form}>
      <form className="space-y-6">
        {/* Template Selector */}
        {showTemplateSelector && (
          <div className="space-y-2">
            <Label>Template</Label>
            <TemplateCombobox
              value={selectedTemplate}
              onSelect={handleTemplateSelect}
            />
            <QuickTemplatePicks
              onSelect={handleTemplateSelect}
              selectedId={selectedTemplate?.id}
              className="mt-2"
            />
          </div>
        )}

        <FormField
          control={form.control}
          name="title"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Title</FormLabel>
              <FormControl>
                <Input placeholder="e.g., Bank Statements Required" {...field} />
              </FormControl>
              <FormDescription>
                A clear, concise title for the document request
              </FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="description"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Description</FormLabel>
              <FormControl>
                <Textarea
                  placeholder="Describe what documents you need and any specific requirements..."
                  className="min-h-[100px]"
                  {...field}
                />
              </FormControl>
              <FormDescription>
                Detailed instructions for your client
              </FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="recipient_email"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Client Email</FormLabel>
              <FormControl>
                <Input
                  type="email"
                  placeholder="client@example.com"
                  {...field}
                />
              </FormControl>
              <FormDescription>
                Email address to send the document request to
              </FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <FormField
            control={form.control}
            name="due_date"
            render={({ field }) => (
              <FormItem className="flex flex-col">
                <FormLabel>Due Date</FormLabel>
                <Popover>
                  <PopoverTrigger asChild>
                    <FormControl>
                      <Button
                        variant="outline"
                        className={cn(
                          'w-full pl-3 text-left font-normal',
                          !field.value && 'text-muted-foreground'
                        )}
                      >
                        {field.value ? (
                          format(field.value, 'PPP')
                        ) : (
                          <span>Pick a date</span>
                        )}
                        <CalendarIcon className="ml-auto h-4 w-4 opacity-50" />
                      </Button>
                    </FormControl>
                  </PopoverTrigger>
                  <PopoverContent className="w-auto p-0" align="start">
                    <Calendar
                      mode="single"
                      selected={field.value}
                      onSelect={field.onChange}
                      disabled={(date) => date < new Date()}
                      initialFocus
                    />
                  </PopoverContent>
                </Popover>
                <FormDescription>When you need the documents by</FormDescription>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="priority"
            render={({ field }) => (
              <FormItem className="flex flex-col">
                <FormLabel>Priority</FormLabel>
                <Select onValueChange={field.onChange} value={field.value}>
                  <FormControl>
                    <SelectTrigger>
                      <SelectValue placeholder="Select priority" />
                    </SelectTrigger>
                  </FormControl>
                  <SelectContent>
                    {PRIORITY_OPTIONS.map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        <div className="flex flex-col">
                          <span>{option.label}</span>
                          <span className="text-xs text-muted-foreground">
                            {option.description}
                          </span>
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <FormDescription>Urgency level for this request</FormDescription>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <FormField
            control={form.control}
            name="period_start"
            render={({ field }) => (
              <FormItem className="flex flex-col">
                <FormLabel>Period Start (Optional)</FormLabel>
                <Popover>
                  <PopoverTrigger asChild>
                    <FormControl>
                      <Button
                        variant="outline"
                        className={cn(
                          'w-full pl-3 text-left font-normal',
                          !field.value && 'text-muted-foreground'
                        )}
                      >
                        {field.value ? (
                          format(field.value, 'PPP')
                        ) : (
                          <span>Select start date</span>
                        )}
                        <CalendarIcon className="ml-auto h-4 w-4 opacity-50" />
                      </Button>
                    </FormControl>
                  </PopoverTrigger>
                  <PopoverContent className="w-auto p-0" align="start">
                    <Calendar
                      mode="single"
                      selected={field.value}
                      onSelect={field.onChange}
                      initialFocus
                    />
                  </PopoverContent>
                </Popover>
                <FormDescription>Start of document period</FormDescription>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="period_end"
            render={({ field }) => (
              <FormItem className="flex flex-col">
                <FormLabel>Period End (Optional)</FormLabel>
                <Popover>
                  <PopoverTrigger asChild>
                    <FormControl>
                      <Button
                        variant="outline"
                        className={cn(
                          'w-full pl-3 text-left font-normal',
                          !field.value && 'text-muted-foreground'
                        )}
                      >
                        {field.value ? (
                          format(field.value, 'PPP')
                        ) : (
                          <span>Select end date</span>
                        )}
                        <CalendarIcon className="ml-auto h-4 w-4 opacity-50" />
                      </Button>
                    </FormControl>
                  </PopoverTrigger>
                  <PopoverContent className="w-auto p-0" align="start">
                    <Calendar
                      mode="single"
                      selected={field.value}
                      onSelect={field.onChange}
                      initialFocus
                    />
                  </PopoverContent>
                </Popover>
                <FormDescription>End of document period</FormDescription>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>

        <FormField
          control={form.control}
          name="auto_remind"
          render={({ field }) => (
            <FormItem className="flex flex-row items-center justify-between rounded-lg border p-4">
              <div className="space-y-0.5">
                <FormLabel className="text-base">Auto Reminders</FormLabel>
                <FormDescription>
                  Automatically send reminders before and after the due date
                </FormDescription>
              </div>
              <FormControl>
                <Switch checked={field.value} onCheckedChange={field.onChange} />
              </FormControl>
            </FormItem>
          )}
        />

        <div className="flex flex-col-reverse sm:flex-row gap-3 pt-4">
          <Button
            type="button"
            variant="outline"
            onClick={() => router.back()}
            disabled={isSubmitting}
          >
            Cancel
          </Button>
          <Button
            type="button"
            variant="secondary"
            onClick={form.handleSubmit((values) => handleSubmit(values, false))}
            disabled={isSubmitting}
          >
            {isSubmitting ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Save className="mr-2 h-4 w-4" />
            )}
            Save as Draft
          </Button>
          <Button
            type="button"
            onClick={form.handleSubmit((values) => handleSubmit(values, true))}
            disabled={isSubmitting}
          >
            {isSubmitting ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Send className="mr-2 h-4 w-4" />
            )}
            Send Request
          </Button>
        </div>
      </form>
    </Form>
  );
}

export default RequestForm;
