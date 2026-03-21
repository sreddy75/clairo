'use client';

import {
  Building2,
  FileText,
  Receipt,
  Users,
  Calendar,
  UserPlus,
  Box,
  FileSignature,
  FileCheck,
  File,
  Loader2,
  Star,
  Check,
} from 'lucide-react';
import { useEffect, useState } from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  type DocumentRequestTemplate,
  useRequestsApi,
  RequestsApiError,
} from '@/lib/api/requests';
import { cn } from '@/lib/utils';

// Icon mapping for template icons
const ICON_MAP: Record<string, React.ComponentType<{ className?: string }>> = {
  'building-columns': Building2,
  'file-invoice': FileText,
  'receipt': Receipt,
  'file-check': FileCheck,
  'users': Users,
  'calendar-days': Calendar,
  'user-plus': UserPlus,
  'box': Box,
  'building-2': Building2,
  'file-signature': FileSignature,
  'file': File,
};

const PRIORITY_COLORS: Record<string, string> = {
  low: 'bg-muted text-muted-foreground',
  normal: 'bg-primary/10 text-primary',
  high: 'bg-status-warning/10 text-status-warning',
  urgent: 'bg-status-danger/10 text-status-danger',
};

interface RequestTemplateSelectorProps {
  onSelect: (template: DocumentRequestTemplate) => void;
  selectedId?: string;
  className?: string;
}

/**
 * Component for selecting document request templates.
 *
 * Displays available templates in a grid, grouped by system vs custom.
 * Allows accountants to select a template to pre-fill a new document request.
 */
export function RequestTemplateSelector({
  onSelect,
  selectedId,
  className,
}: RequestTemplateSelectorProps) {
  const api = useRequestsApi();
  const [templates, setTemplates] = useState<DocumentRequestTemplate[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchTemplates = async () => {
      try {
        const response = await api.templates.list();
        setTemplates(response.templates);
      } catch (err) {
        if (err instanceof RequestsApiError) {
          setError(err.message);
        } else {
          setError('Failed to load templates');
        }
      } finally {
        setIsLoading(false);
      }
    };

    fetchTemplates();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (isLoading) {
    return (
      <div className={cn('flex items-center justify-center py-8', className)}>
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        <span className="ml-2 text-muted-foreground">Loading templates...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className={cn('text-center py-8', className)}>
        <p className="text-status-danger">{error}</p>
        <Button
          variant="outline"
          size="sm"
          className="mt-2"
          onClick={() => window.location.reload()}
        >
          Retry
        </Button>
      </div>
    );
  }

  const systemTemplates = templates.filter((t) => t.is_system);
  const customTemplates = templates.filter((t) => !t.is_system);

  return (
    <div className={cn('space-y-6', className)}>
      {/* System Templates */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <Star className="h-4 w-4 text-status-warning" />
          <h3 className="font-medium text-sm text-muted-foreground uppercase tracking-wide">
            Standard Templates
          </h3>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {systemTemplates.map((template) => (
            <TemplateCard
              key={template.id}
              template={template}
              isSelected={selectedId === template.id}
              onClick={() => onSelect(template)}
            />
          ))}
        </div>
      </div>

      {/* Custom Templates */}
      {customTemplates.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-3">
            <FileText className="h-4 w-4 text-primary" />
            <h3 className="font-medium text-sm text-muted-foreground uppercase tracking-wide">
              Custom Templates
            </h3>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {customTemplates.map((template) => (
              <TemplateCard
                key={template.id}
                template={template}
                isSelected={selectedId === template.id}
                onClick={() => onSelect(template)}
              />
            ))}
          </div>
        </div>
      )}

      {templates.length === 0 && (
        <div className="text-center py-8 text-muted-foreground">
          <FileText className="h-12 w-12 mx-auto mb-3 opacity-50" />
          <p>No templates available</p>
        </div>
      )}
    </div>
  );
}

interface TemplateCardProps {
  template: DocumentRequestTemplate;
  isSelected: boolean;
  onClick: () => void;
}

function TemplateCard({ template, isSelected, onClick }: TemplateCardProps) {
  const IconComponent = (template.icon && ICON_MAP[template.icon]) || File;

  return (
    <Card
      className={cn(
        'cursor-pointer transition-all hover:border-primary/50 hover:shadow-md',
        isSelected && 'border-primary ring-2 ring-primary/20'
      )}
      onClick={onClick}
    >
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-md bg-muted">
              <IconComponent className="h-4 w-4" />
            </div>
            <CardTitle className="text-sm font-medium">{template.name}</CardTitle>
          </div>
          {isSelected && (
            <div className="p-1 rounded-full bg-primary text-primary-foreground">
              <Check className="h-3 w-3" />
            </div>
          )}
        </div>
      </CardHeader>
      <CardContent className="pt-0">
        <div className="flex items-center gap-2 flex-wrap">
          <Badge variant="outline" className={PRIORITY_COLORS[template.default_priority]}>
            {template.default_priority}
          </Badge>
          <span className="text-xs text-muted-foreground">
            {template.default_due_days} day{template.default_due_days !== 1 ? 's' : ''}
          </span>
          {template.is_system && (
            <Badge variant="secondary" className="text-xs">
              System
            </Badge>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

/**
 * Compact version of template selector for inline use.
 */
interface CompactTemplateSelectorProps {
  onSelect: (template: DocumentRequestTemplate) => void;
  selectedTemplate?: DocumentRequestTemplate | null;
}

export function CompactTemplateSelector({
  onSelect,
  selectedTemplate,
}: CompactTemplateSelectorProps) {
  const api = useRequestsApi();
  const [templates, setTemplates] = useState<DocumentRequestTemplate[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchTemplates = async () => {
      try {
        const response = await api.templates.list();
        setTemplates(response.templates);
      } catch {
        // Silently fail for compact version
      } finally {
        setIsLoading(false);
      }
    };

    fetchTemplates();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (isLoading) {
    return <Loader2 className="h-4 w-4 animate-spin" />;
  }

  return (
    <div className="flex flex-wrap gap-2">
      {templates.slice(0, 6).map((template) => {
        const IconComponent = (template.icon && ICON_MAP[template.icon]) || File;
        const isSelected = selectedTemplate?.id === template.id;

        return (
          <Button
            key={template.id}
            variant={isSelected ? 'default' : 'outline'}
            size="sm"
            onClick={() => onSelect(template)}
            className="gap-1"
          >
            <IconComponent className="h-3 w-3" />
            <span className="truncate max-w-[100px]">{template.name}</span>
          </Button>
        );
      })}
    </div>
  );
}

export default RequestTemplateSelector;
