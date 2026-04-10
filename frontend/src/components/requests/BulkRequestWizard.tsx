'use client';

import { zodResolver } from '@hookform/resolvers/zod';
import { addDays, format } from 'date-fns';
import {
  AlertCircle,
  CalendarIcon,
  Check,
  ChevronLeft,
  ChevronRight,
  Loader2,
  Send,
  Users,
} from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useCallback, useState } from 'react';
import { useForm } from 'react-hook-form';
import * as z from 'zod';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Calendar } from '@/components/ui/calendar';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import { Input } from '@/components/ui/input';
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
import { Textarea } from '@/components/ui/textarea';
import { useToast } from '@/hooks/use-toast';
import {
  type BulkRequestPreview,
  type DocumentRequestTemplate,
  useRequestsApi,
} from '@/lib/api/requests';
import { cn } from '@/lib/utils';

// ============================================================================
// Types
// ============================================================================

interface Client {
  id: string;
  name: string;
  email?: string;
  status?: string;
}

interface BulkRequestWizardProps {
  clients: Client[];
  templates: DocumentRequestTemplate[];
  onSuccess?: () => void;
  onCancel?: () => void;
}

// ============================================================================
// Form Schema
// ============================================================================

const formSchema = z.object({
  connection_ids: z.array(z.string()).min(1, 'Select at least one client'),
  template_id: z.string().optional(),
  title: z.string().min(1, 'Title is required').max(200),
  description: z.string().min(1, 'Description is required'),
  due_date: z.date().optional(),
  priority: z.enum(['low', 'normal', 'high', 'urgent']),
});

type FormValues = z.infer<typeof formSchema>;

const PRIORITY_OPTIONS = [
  { value: 'low', label: 'Low', color: 'bg-muted text-foreground' },
  { value: 'normal', label: 'Normal', color: 'bg-status-info/10 text-status-info' },
  { value: 'high', label: 'High', color: 'bg-orange-100 text-orange-800' },
  { value: 'urgent', label: 'Urgent', color: 'bg-red-100 text-red-800' },
];

const STEPS = [
  { id: 1, name: 'Select Clients', description: 'Choose recipients' },
  { id: 2, name: 'Configure Request', description: 'Set up details' },
  { id: 3, name: 'Review & Send', description: 'Confirm and send' },
];

// ============================================================================
// Component
// ============================================================================

export function BulkRequestWizard({
  clients,
  templates,
  onSuccess,
  onCancel,
}: BulkRequestWizardProps) {
  const router = useRouter();
  const api = useRequestsApi();
  const { toast } = useToast();

  const [currentStep, setCurrentStep] = useState(1);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isPreviewing, setIsPreviewing] = useState(false);
  const [preview, setPreview] = useState<BulkRequestPreview | null>(null);
  const [searchQuery, setSearchQuery] = useState('');

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      connection_ids: [],
      template_id: undefined,
      title: '',
      description: '',
      due_date: addDays(new Date(), 7),
      priority: 'normal',
    },
  });

  const selectedClients = form.watch('connection_ids');
  const selectedTemplateId = form.watch('template_id');

  // Filter clients by search
  const filteredClients = clients.filter((client) =>
    client.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Get selected template
  const selectedTemplate = templates.find((t) => t.id === selectedTemplateId);

  // Handle template selection
  const handleTemplateSelect = useCallback(
    (templateId: string | undefined) => {
      form.setValue('template_id', templateId);
      if (templateId) {
        const template = templates.find((t) => t.id === templateId);
        if (template) {
          form.setValue('title', template.name);
          form.setValue('description', template.description_template);
          form.setValue('priority', template.default_priority);
          if (template.default_due_days) {
            form.setValue('due_date', addDays(new Date(), template.default_due_days));
          }
        }
      }
    },
    [form, templates]
  );

  // Handle select all
  const handleSelectAll = () => {
    const allIds = filteredClients.map((c) => c.id);
    form.setValue('connection_ids', allIds);
  };

  // Handle deselect all
  const handleDeselectAll = () => {
    form.setValue('connection_ids', []);
  };

  // Toggle client selection
  const toggleClient = (clientId: string) => {
    const current = form.getValues('connection_ids');
    if (current.includes(clientId)) {
      form.setValue(
        'connection_ids',
        current.filter((id) => id !== clientId)
      );
    } else {
      form.setValue('connection_ids', [...current, clientId]);
    }
  };

  // Navigate steps
  const nextStep = async () => {
    if (currentStep === 1) {
      const valid = await form.trigger('connection_ids');
      if (!valid) return;
    } else if (currentStep === 2) {
      const valid = await form.trigger(['title', 'description', 'priority']);
      if (!valid) return;

      // Preview the request
      await loadPreview();
    }
    setCurrentStep((s) => Math.min(s + 1, 3));
  };

  const prevStep = () => {
    setCurrentStep((s) => Math.max(s - 1, 1));
  };

  // Load preview
  const loadPreview = async () => {
    setIsPreviewing(true);
    try {
      const values = form.getValues();
      const previewData = await api.bulkRequests.preview({
        connection_ids: values.connection_ids,
        template_id: values.template_id,
        title: values.title,
        description: values.description,
        due_date: values.due_date ? format(values.due_date, 'yyyy-MM-dd') : undefined,
      });
      setPreview(previewData);
    } catch (error) {
      toast({
        title: 'Preview failed',
        description: error instanceof Error ? error.message : 'Could not load preview',
        variant: 'destructive',
      });
    } finally {
      setIsPreviewing(false);
    }
  };

  // Submit bulk request
  const handleSubmit = async () => {
    const values = form.getValues();
    setIsSubmitting(true);

    try {
      await api.bulkRequests.create({
        connection_ids: values.connection_ids,
        template_id: values.template_id,
        title: values.title,
        description: values.description,
        priority: values.priority,
        due_date: values.due_date ? format(values.due_date, 'yyyy-MM-dd') : undefined,
      });

      toast({
        title: 'Bulk request sent',
        description: `Document requests have been sent to ${values.connection_ids.length} clients`,
      });

      onSuccess?.();
      router.push('/requests');
    } catch (error) {
      toast({
        title: 'Error',
        description: error instanceof Error ? error.message : 'Failed to send bulk request',
        variant: 'destructive',
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  // ============================================================================
  // Render Steps
  // ============================================================================

  const renderStepIndicator = () => (
    <nav aria-label="Progress" className="mb-8">
      <ol className="flex items-center justify-center">
        {STEPS.map((step, index) => (
          <li
            key={step.id}
            className={cn('flex items-center', index !== STEPS.length - 1 && 'flex-1')}
          >
            <div className="flex flex-col items-center">
              <div
                className={cn(
                  'flex h-10 w-10 items-center justify-center rounded-full border-2 transition-colors',
                  currentStep > step.id
                    ? 'border-primary bg-primary text-primary-foreground'
                    : currentStep === step.id
                      ? 'border-primary bg-background text-primary'
                      : 'border-muted bg-background text-muted-foreground'
                )}
              >
                {currentStep > step.id ? (
                  <Check className="h-5 w-5" />
                ) : (
                  <span className="text-sm font-medium">{step.id}</span>
                )}
              </div>
              <div className="mt-2 text-center">
                <p
                  className={cn(
                    'text-sm font-medium',
                    currentStep >= step.id ? 'text-foreground' : 'text-muted-foreground'
                  )}
                >
                  {step.name}
                </p>
                <p className="text-xs text-muted-foreground hidden sm:block">
                  {step.description}
                </p>
              </div>
            </div>
            {index !== STEPS.length - 1 && (
              <div
                className={cn(
                  'mx-4 h-0.5 w-full min-w-[60px] transition-colors',
                  currentStep > step.id ? 'bg-primary' : 'bg-muted'
                )}
              />
            )}
          </li>
        ))}
      </ol>
    </nav>
  );

  const renderStep1 = () => (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-medium">Select Clients</h3>
          <p className="text-sm text-muted-foreground">
            Choose which clients should receive this document request
          </p>
        </div>
        <Badge variant="outline" className="text-sm">
          <Users className="mr-1 h-3 w-3" />
          {selectedClients.length} selected
        </Badge>
      </div>

      <div className="flex items-center gap-2">
        <Input
          placeholder="Search clients..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="max-w-xs"
        />
        <Button variant="outline" size="sm" onClick={handleSelectAll}>
          Select All
        </Button>
        <Button variant="outline" size="sm" onClick={handleDeselectAll}>
          Deselect All
        </Button>
      </div>

      <div className="border rounded-lg max-h-[400px] overflow-y-auto">
        {filteredClients.length === 0 ? (
          <div className="p-8 text-center text-muted-foreground">
            No clients found
          </div>
        ) : (
          <div className="divide-y">
            {filteredClients.map((client) => (
              <label
                key={client.id}
                className={cn(
                  'flex items-center gap-3 p-3 cursor-pointer hover:bg-muted/50 transition-colors',
                  selectedClients.includes(client.id) && 'bg-muted/30'
                )}
              >
                <Checkbox
                  checked={selectedClients.includes(client.id)}
                  onCheckedChange={() => toggleClient(client.id)}
                />
                <div className="flex-1 min-w-0">
                  <p className="font-medium truncate">{client.name}</p>
                  {client.email && (
                    <p className="text-sm text-muted-foreground truncate">
                      {client.email}
                    </p>
                  )}
                </div>
                {client.status && (
                  <Badge variant="outline" className="text-xs">
                    {client.status}
                  </Badge>
                )}
              </label>
            ))}
          </div>
        )}
      </div>

      {form.formState.errors.connection_ids && (
        <p className="text-sm text-destructive">
          {form.formState.errors.connection_ids.message}
        </p>
      )}
    </div>
  );

  const renderStep2 = () => (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-medium">Configure Request</h3>
        <p className="text-sm text-muted-foreground">
          Set up the document request details
        </p>
      </div>

      {/* Template Selection */}
      {templates.length > 0 && (
        <div className="space-y-3">
          <FormLabel>Use Template (Optional)</FormLabel>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {templates.slice(0, 6).map((template) => (
              <Card
                key={template.id}
                className={cn(
                  'cursor-pointer transition-all hover:border-primary/50',
                  selectedTemplateId === template.id && 'border-primary ring-1 ring-primary'
                )}
                onClick={() =>
                  handleTemplateSelect(
                    selectedTemplateId === template.id ? undefined : template.id
                  )
                }
              >
                <CardHeader className="p-3">
                  <CardTitle className="text-sm flex items-center gap-2">
                    {template.icon && <span>{template.icon}</span>}
                    {template.name}
                  </CardTitle>
                  <CardDescription className="text-xs line-clamp-2">
                    {template.description_template}
                  </CardDescription>
                </CardHeader>
              </Card>
            ))}
          </div>
        </div>
      )}

      <Form {...form}>
        <div className="space-y-4">
          <FormField
            control={form.control}
            name="title"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Title</FormLabel>
                <FormControl>
                  <Input placeholder="e.g., Q3 Bank Statements Required" {...field} />
                </FormControl>
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
                    placeholder="Describe what documents you need..."
                    className="min-h-[100px]"
                    {...field}
                  />
                </FormControl>
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
                          {field.value ? format(field.value, 'PPP') : <span>Pick a date</span>}
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
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="priority"
              render={({ field }) => (
                <FormItem>
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
                          <Badge variant="outline" className={option.color}>
                            {option.label}
                          </Badge>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />
          </div>
        </div>
      </Form>
    </div>
  );

  const renderStep3 = () => (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-medium">Review & Send</h3>
        <p className="text-sm text-muted-foreground">
          Confirm the details before sending
        </p>
      </div>

      {isPreviewing ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : preview ? (
        <div className="space-y-4">
          {/* Preview Stats */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <Card>
              <CardHeader className="pb-2">
                <CardDescription>Total Clients</CardDescription>
                <CardTitle className="text-2xl">{preview.total_clients}</CardTitle>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardDescription>Valid</CardDescription>
                <CardTitle className="text-2xl text-green-600">
                  {preview.valid_clients}
                </CardTitle>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardDescription>Issues</CardDescription>
                <CardTitle className="text-2xl text-orange-600">
                  {preview.invalid_clients}
                </CardTitle>
              </CardHeader>
            </Card>
          </div>

          {/* Issues Alert */}
          {preview.issues.length > 0 && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertTitle>Some clients have issues</AlertTitle>
              <AlertDescription>
                <ul className="mt-2 list-disc list-inside">
                  {preview.issues.slice(0, 3).map((issue, i) => (
                    <li key={i} className="text-sm">
                      {issue.issue}
                    </li>
                  ))}
                  {preview.issues.length > 3 && (
                    <li className="text-sm">
                      ...and {preview.issues.length - 3} more
                    </li>
                  )}
                </ul>
              </AlertDescription>
            </Alert>
          )}

          {/* Request Summary */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Request Summary</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Title</span>
                <span className="font-medium">{form.getValues('title')}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Priority</span>
                <Badge
                  variant="outline"
                  className={
                    PRIORITY_OPTIONS.find((p) => p.value === form.getValues('priority'))
                      ?.color
                  }
                >
                  {form.getValues('priority')}
                </Badge>
              </div>
              {form.getValues('due_date') && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Due Date</span>
                  <span className="font-medium">
                    {format(form.getValues('due_date')!, 'PPP')}
                  </span>
                </div>
              )}
              {selectedTemplate && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Template</span>
                  <span className="font-medium">{selectedTemplate.name}</span>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Description Preview */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Message Preview</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground whitespace-pre-wrap">
                {form.getValues('description')}
              </p>
            </CardContent>
          </Card>
        </div>
      ) : (
        <Alert>
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Preview unavailable</AlertTitle>
          <AlertDescription>
            Could not load preview. You can still send the request.
          </AlertDescription>
        </Alert>
      )}
    </div>
  );

  // ============================================================================
  // Main Render
  // ============================================================================

  return (
    <div className="max-w-3xl mx-auto">
      {renderStepIndicator()}

      <div className="min-h-[400px]">
        {currentStep === 1 && renderStep1()}
        {currentStep === 2 && renderStep2()}
        {currentStep === 3 && renderStep3()}
      </div>

      {/* Navigation */}
      <div className="flex items-center justify-between mt-8 pt-4 border-t">
        <Button variant="outline" onClick={currentStep === 1 ? onCancel : prevStep}>
          <ChevronLeft className="mr-2 h-4 w-4" />
          {currentStep === 1 ? 'Cancel' : 'Back'}
        </Button>

        {currentStep < 3 ? (
          <Button onClick={nextStep} disabled={isPreviewing}>
            {isPreviewing ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : null}
            Next
            <ChevronRight className="ml-2 h-4 w-4" />
          </Button>
        ) : (
          <Button onClick={handleSubmit} disabled={isSubmitting}>
            {isSubmitting ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Send className="mr-2 h-4 w-4" />
            )}
            Send to {selectedClients.length} Clients
          </Button>
        )}
      </div>
    </div>
  );
}

export default BulkRequestWizard;
