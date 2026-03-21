'use client';

/**
 * A2UI ExportButton Component
 * Button for exporting data in various formats
 */

import { Download, FileSpreadsheet, FileText, Loader2 } from 'lucide-react';
import { useState } from 'react';

import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { useA2UIAction } from '@/lib/a2ui/context';
import type { ActionConfig } from '@/lib/a2ui/types';
import { cn } from '@/lib/utils';


// =============================================================================
// Types
// =============================================================================

interface A2UIExportButtonProps {
  id: string;
  label?: string;
  formats?: ('csv' | 'pdf' | 'xlsx')[];
  dataBinding?: string;
  onExport?: ActionConfig;
  onAction?: (action: ActionConfig) => Promise<void>;
}

// =============================================================================
// Format Icons
// =============================================================================

const formatIcons: Record<string, React.ReactNode> = {
  csv: <FileSpreadsheet className="h-4 w-4" />,
  xlsx: <FileSpreadsheet className="h-4 w-4" />,
  pdf: <FileText className="h-4 w-4" />,
  json: <FileText className="h-4 w-4" />,
};

const formatLabels: Record<string, string> = {
  csv: 'CSV Spreadsheet',
  xlsx: 'Excel Spreadsheet',
  pdf: 'PDF Document',
  json: 'JSON Data',
};

// =============================================================================
// Component
// =============================================================================

export function ExportButton({
  id,
  label = 'Export',
  formats = ['csv', 'xlsx'],
  onExport,
  onAction,
}: A2UIExportButtonProps) {
  const [isExporting, setIsExporting] = useState(false);
  const [exportingFormat, setExportingFormat] = useState<string | null>(null);
  const contextAction = useA2UIAction();
  const handleAction = onAction || contextAction;

  const handleExport = async (format: string) => {
    if (!onExport) return;

    setIsExporting(true);
    setExportingFormat(format);

    try {
      await handleAction({
        ...onExport,
        payload: { ...onExport.payload, format },
      });
    } finally {
      setIsExporting(false);
      setExportingFormat(null);
    }
  };

  const outlineClassName = cn(
    'gap-2',
    'border-border text-foreground hover:bg-muted'
  );

  // Single format - just a button
  if (formats.length === 1) {
    const format = formats[0] as 'csv' | 'pdf' | 'xlsx';
    return (
      <Button
        id={id}
        variant="outline"
        onClick={() => handleExport(format)}
        disabled={isExporting}
        className={outlineClassName}
      >
        {isExporting ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          formatIcons[format] || <Download className="h-4 w-4" />
        )}
        {label}
      </Button>
    );
  }

  // Multiple formats - dropdown
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button id={id} variant="outline" disabled={isExporting} className={outlineClassName}>
          {isExporting ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Download className="h-4 w-4" />
          )}
          {label}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        {formats.map((format) => (
          <DropdownMenuItem
            key={format}
            onClick={() => handleExport(format)}
            disabled={isExporting && exportingFormat === format}
            className="gap-2"
          >
            {exportingFormat === format ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              formatIcons[format] || <Download className="h-4 w-4" />
            )}
            {formatLabels[format] || format.toUpperCase()}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
