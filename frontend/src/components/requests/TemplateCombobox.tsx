'use client';

import {
  Building2,
  FileText,
  Receipt,
  FileCheck,
  Users,
  Calendar,
  UserPlus,
  Box,
  FileSignature,
  File,
  Loader2,
  X,
} from 'lucide-react';
import { useEffect, useState } from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  type DocumentRequestTemplate,
  useRequestsApi,
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

interface TemplateComboboxProps {
  value: DocumentRequestTemplate | null;
  onSelect: (template: DocumentRequestTemplate | null) => void;
  className?: string;
}

/**
 * Compact select for choosing document request templates.
 * Features grouping by system/custom templates.
 */
export function TemplateCombobox({
  value,
  onSelect,
  className,
}: TemplateComboboxProps) {
  const api = useRequestsApi();
  const [templates, setTemplates] = useState<DocumentRequestTemplate[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchTemplates = async () => {
      try {
        const response = await api.templates.list();
        setTemplates(response.templates);
      } catch {
        // Silently fail
      } finally {
        setIsLoading(false);
      }
    };

    fetchTemplates();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const systemTemplates = templates.filter((t) => t.is_system);
  const customTemplates = templates.filter((t) => !t.is_system);

  const handleValueChange = (templateId: string) => {
    if (templateId === 'custom') {
      onSelect(null);
    } else {
      const template = templates.find((t) => t.id === templateId);
      if (template) {
        onSelect(template);
      }
    }
  };

  const IconComponent = value?.icon ? ICON_MAP[value.icon] || File : File;

  if (isLoading) {
    return (
      <div className={cn('flex items-center gap-2', className)}>
        <Button variant="outline" className="w-full justify-start" disabled>
          <Loader2 className="h-4 w-4 animate-spin mr-2" />
          Loading templates...
        </Button>
      </div>
    );
  }

  return (
    <div className={cn('flex items-center gap-2', className)}>
      <Select
        value={value?.id || 'custom'}
        onValueChange={handleValueChange}
      >
        <SelectTrigger className="w-full">
          <SelectValue>
            {value ? (
              <span className="flex items-center gap-2">
                <IconComponent className="h-4 w-4 shrink-0" />
                <span className="truncate">{value.name}</span>
                <Badge variant="secondary" className="ml-1 shrink-0 text-xs">
                  {value.default_due_days}d
                </Badge>
              </span>
            ) : (
              <span className="text-muted-foreground">
                Custom request (start from scratch)
              </span>
            )}
          </SelectValue>
        </SelectTrigger>
        <SelectContent>
          <SelectGroup>
            <SelectItem value="custom">
              <span className="flex items-center gap-2">
                <FileText className="h-4 w-4 text-muted-foreground" />
                <span>Custom Request</span>
                <span className="text-xs text-muted-foreground ml-1">
                  (start from scratch)
                </span>
              </span>
            </SelectItem>
          </SelectGroup>

          {/* System Templates */}
          {systemTemplates.length > 0 && (
            <SelectGroup>
              <SelectLabel>Standard Templates</SelectLabel>
              {systemTemplates.map((template) => {
                const Icon = (template.icon && ICON_MAP[template.icon]) || File;
                return (
                  <SelectItem key={template.id} value={template.id}>
                    <span className="flex items-center gap-2">
                      <Icon className="h-4 w-4" />
                      <span>{template.name}</span>
                      <span className="text-xs text-muted-foreground ml-1">
                        {template.default_due_days}d
                      </span>
                    </span>
                  </SelectItem>
                );
              })}
            </SelectGroup>
          )}

          {/* Custom Templates */}
          {customTemplates.length > 0 && (
            <SelectGroup>
              <SelectLabel>Your Templates</SelectLabel>
              {customTemplates.map((template) => {
                const Icon = (template.icon && ICON_MAP[template.icon]) || File;
                return (
                  <SelectItem key={template.id} value={template.id}>
                    <span className="flex items-center gap-2">
                      <Icon className="h-4 w-4" />
                      <span>{template.name}</span>
                      <span className="text-xs text-muted-foreground ml-1">
                        {template.default_due_days}d
                      </span>
                    </span>
                  </SelectItem>
                );
              })}
            </SelectGroup>
          )}
        </SelectContent>
      </Select>

      {/* Clear button when template is selected */}
      {value && (
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="shrink-0"
          onClick={() => onSelect(null)}
        >
          <X className="h-4 w-4" />
          <span className="sr-only">Clear template</span>
        </Button>
      )}
    </div>
  );
}

/**
 * Quick template picks shown as chips below the selector.
 */
interface QuickTemplatePicksProps {
  onSelect: (template: DocumentRequestTemplate) => void;
  selectedId?: string;
  className?: string;
}

export function QuickTemplatePicks({
  onSelect,
  selectedId,
  className,
}: QuickTemplatePicksProps) {
  const api = useRequestsApi();
  const [templates, setTemplates] = useState<DocumentRequestTemplate[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchTemplates = async () => {
      try {
        const response = await api.templates.list();
        // Show only first 4 system templates as quick picks
        setTemplates(response.templates.filter((t) => t.is_system).slice(0, 4));
      } catch {
        // Silently fail
      } finally {
        setIsLoading(false);
      }
    };

    fetchTemplates();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (isLoading || templates.length === 0) {
    return null;
  }

  return (
    <div className={cn('flex flex-wrap gap-1.5', className)}>
      <span className="text-xs text-muted-foreground self-center mr-1">
        Quick:
      </span>
      {templates.map((template) => {
        const Icon = (template.icon && ICON_MAP[template.icon]) || File;
        const isSelected = selectedId === template.id;

        return (
          <Button
            key={template.id}
            type="button"
            variant={isSelected ? 'secondary' : 'ghost'}
            size="sm"
            className={cn(
              'h-7 text-xs gap-1 px-2',
              isSelected && 'bg-primary/10 text-primary'
            )}
            onClick={() => onSelect(template)}
          >
            <Icon className="h-3 w-3" />
            <span className="truncate max-w-[80px]">{template.name}</span>
          </Button>
        );
      })}
    </div>
  );
}

export default TemplateCombobox;
