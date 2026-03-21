'use client';

import { Loader2, X } from 'lucide-react';
import { useEffect, useState } from 'react';

import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import {
  COLLECTION_NAMES,
  SOURCE_TYPES,
  type KnowledgeSource,
  type KnowledgeSourceCreate,
  type KnowledgeSourceType,
} from '@/types/knowledge';

interface SourceFormModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: KnowledgeSourceCreate) => Promise<void>;
  source?: KnowledgeSource | null;
  isSubmitting: boolean;
}

export function SourceFormModal({
  isOpen,
  onClose,
  onSubmit,
  source,
  isSubmitting,
}: SourceFormModalProps) {
  const [formData, setFormData] = useState<KnowledgeSourceCreate>({
    name: '',
    source_type: 'ato_rss',
    base_url: '',
    collection_name: 'compliance_knowledge',
    scrape_config: {},
    is_active: true,
  });
  const [scrapeConfigJson, setScrapeConfigJson] = useState('{}');
  const [jsonError, setJsonError] = useState<string | null>(null);

  const isEdit = !!source;

  useEffect(() => {
    if (source) {
      setFormData({
        name: source.name,
        source_type: source.source_type,
        base_url: source.base_url,
        collection_name: source.collection_name,
        scrape_config: source.scrape_config,
        is_active: source.is_active,
      });
      setScrapeConfigJson(JSON.stringify(source.scrape_config, null, 2));
    } else {
      setFormData({
        name: '',
        source_type: 'ato_rss',
        base_url: '',
        collection_name: 'compliance_knowledge',
        scrape_config: {},
        is_active: true,
      });
      setScrapeConfigJson('{}');
    }
    setJsonError(null);
  }, [source, isOpen]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    try {
      const config = JSON.parse(scrapeConfigJson);
      await onSubmit({
        ...formData,
        scrape_config: config,
      });
      onClose();
    } catch (err) {
      if (err instanceof SyntaxError) {
        setJsonError('Invalid JSON format');
      }
    }
  };

  const handleJsonChange = (value: string) => {
    setScrapeConfigJson(value);
    try {
      JSON.parse(value);
      setJsonError(null);
    } catch {
      setJsonError('Invalid JSON format');
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />

      <div className="relative bg-card rounded-2xl shadow-lg w-full max-w-lg mx-4 max-h-[90vh] overflow-hidden border border-border">
        {/* Header */}
        <div className="px-6 py-4 bg-muted border-b border-border">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-foreground">
              {isEdit ? 'Edit Source' : 'Add Knowledge Source'}
            </h2>
            <Button variant="ghost" size="icon" className="h-8 w-8" onClick={onClose}>
              <X className="w-5 h-5" />
            </Button>
          </div>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4 overflow-y-auto max-h-[calc(90vh-140px)]">
          <div>
            <label className="block text-xs font-medium uppercase tracking-wide text-muted-foreground mb-1.5">
              Source Name
            </label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              placeholder="e.g., ATO GST Rulings"
              required
              className="w-full px-3 py-2.5 border border-input rounded-lg bg-background text-foreground placeholder:text-muted-foreground focus:ring-2 focus:ring-ring focus:border-ring outline-none transition-shadow"
            />
          </div>

          <div>
            <label className="block text-xs font-medium uppercase tracking-wide text-muted-foreground mb-1.5">
              Source Type
            </label>
            <select
              value={formData.source_type}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  source_type: e.target.value as KnowledgeSourceType,
                })
              }
              disabled={isEdit}
              className="w-full px-3 py-2.5 border border-input rounded-lg bg-background text-foreground focus:ring-2 focus:ring-ring focus:border-ring outline-none transition-shadow disabled:bg-muted disabled:text-muted-foreground"
            >
              {SOURCE_TYPES.map((type) => (
                <option key={type.value} value={type.value}>
                  {type.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium uppercase tracking-wide text-muted-foreground mb-1.5">
              Base URL
            </label>
            <input
              type="url"
              value={formData.base_url}
              onChange={(e) => setFormData({ ...formData, base_url: e.target.value })}
              placeholder="https://www.ato.gov.au/rss/rulings.xml"
              required
              disabled={isEdit}
              className="w-full px-3 py-2.5 border border-input rounded-lg bg-background text-foreground placeholder:text-muted-foreground focus:ring-2 focus:ring-ring focus:border-ring outline-none transition-shadow disabled:bg-muted disabled:text-muted-foreground font-mono text-sm"
            />
          </div>

          <div>
            <label className="block text-xs font-medium uppercase tracking-wide text-muted-foreground mb-1.5">
              Target Collection
            </label>
            <select
              value={formData.collection_name}
              onChange={(e) =>
                setFormData({ ...formData, collection_name: e.target.value })
              }
              disabled={isEdit}
              className="w-full px-3 py-2.5 border border-input rounded-lg bg-background text-foreground focus:ring-2 focus:ring-ring focus:border-ring outline-none transition-shadow disabled:bg-muted disabled:text-muted-foreground"
            >
              {COLLECTION_NAMES.map((name) => (
                <option key={name} value={name}>
                  {name.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium uppercase tracking-wide text-muted-foreground mb-1.5">
              Scrape Configuration{' '}
              <span className="font-normal text-muted-foreground/60">(JSON)</span>
            </label>
            <textarea
              value={scrapeConfigJson}
              onChange={(e) => handleJsonChange(e.target.value)}
              rows={4}
              className={cn(
                'w-full px-3 py-2.5 border rounded-lg bg-background text-foreground focus:ring-2 focus:ring-ring focus:border-ring outline-none transition-shadow font-mono text-sm',
                jsonError ? 'border-destructive' : 'border-input'
              )}
            />
            {jsonError && (
              <p className="text-destructive text-xs mt-1">{jsonError}</p>
            )}
          </div>

          <div className="flex items-center gap-3">
            <input
              type="checkbox"
              id="is_active"
              checked={formData.is_active}
              onChange={(e) =>
                setFormData({ ...formData, is_active: e.target.checked })
              }
              className="w-4 h-4 text-primary border-input rounded focus:ring-ring"
            />
            <label htmlFor="is_active" className="text-sm text-muted-foreground">
              Source is active and will be included in scheduled ingestion
            </label>
          </div>
        </form>

        {/* Footer */}
        <div className="px-6 py-4 bg-muted border-t border-border flex justify-end gap-3">
          <Button
            variant="outline"
            onClick={onClose}
            disabled={isSubmitting}
          >
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={isSubmitting || !!jsonError}
          >
            {isSubmitting && <Loader2 className="mr-2 w-4 h-4 animate-spin" />}
            {isEdit ? 'Save Changes' : 'Create Source'}
          </Button>
        </div>
      </div>
    </div>
  );
}
