'use client';

import { useAuth } from '@clerk/nextjs';
import {
  BarChart3,
  Bell,
  Building2,
  FileCheck,
  LayoutGrid,
  Library,
  ListChecks,
  MessageSquareText,
  Moon,
  Settings,
  ShieldCheck,
  Sun,
  Users,
  Zap,
} from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useTheme } from 'next-themes';
import { useCallback, useEffect, useState } from 'react';


import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
  CommandShortcut,
} from '@/components/ui/command';
import { apiClient } from '@/lib/api-client';

interface CommandPaletteProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

interface ClientResult {
  id: string;
  name: string;
  connection_id: string;
}

export function CommandPalette({ open, onOpenChange }: CommandPaletteProps) {
  const router = useRouter();
  const { getToken } = useAuth();
  const { theme, setTheme } = useTheme();
  const [clients, setClients] = useState<ClientResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [query, setQuery] = useState('');

  // Search clients when query changes
  useEffect(() => {
    if (!open || query.length < 2) {
      setClients([]);
      return;
    }

    const controller = new AbortController();
    const timer = setTimeout(async () => {
      setIsSearching(true);
      try {
        const token = await getToken();
        if (!token) return;

        const response = await apiClient.get(
          `/api/v1/clients?search=${encodeURIComponent(query)}&limit=5`,
          {
            headers: { Authorization: `Bearer ${token}` },
            signal: controller.signal,
          }
        );

        if (response.ok) {
          const data = await response.json();
          setClients(
            (data.clients || data.items || []).map(
              (c: { id: string; business_name?: string; name?: string; xero_connection_id?: string }) => ({
                id: c.id,
                name: c.business_name || c.name || 'Unknown',
                connection_id: c.xero_connection_id || c.id,
              })
            )
          );
        }
      } catch {
        // Ignore abort errors
      } finally {
        setIsSearching(false);
      }
    }, 300);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [query, open, getToken]);

  const runCommand = useCallback(
    (command: () => void) => {
      onOpenChange(false);
      command();
    },
    [onOpenChange]
  );

  // Reset query when dialog closes
  useEffect(() => {
    if (!open) {
      setQuery('');
      setClients([]);
    }
  }, [open]);

  return (
    <CommandDialog open={open} onOpenChange={onOpenChange}>
      <CommandInput
        placeholder="Search pages, clients, or actions..."
        value={query}
        onValueChange={setQuery}
      />
      <CommandList>
        <CommandEmpty>
          {isSearching ? 'Searching...' : 'No results found.'}
        </CommandEmpty>

        {/* Client search results */}
        {clients.length > 0 && (
          <CommandGroup heading="Clients">
            {clients.map((client) => (
              <CommandItem
                key={client.id}
                value={`client-${client.name}`}
                onSelect={() =>
                  runCommand(() =>
                    router.push(`/clients/${client.connection_id}`)
                  )
                }
              >
                <Building2 className="mr-2 h-4 w-4" />
                {client.name}
              </CommandItem>
            ))}
          </CommandGroup>
        )}

        {/* Navigation */}
        <CommandGroup heading="Pages">
          <CommandItem
            value="Dashboard"
            onSelect={() => runCommand(() => router.push('/dashboard'))}
          >
            <LayoutGrid className="mr-2 h-4 w-4" />
            Dashboard
          </CommandItem>
          <CommandItem
            value="Clients"
            onSelect={() => runCommand(() => router.push('/clients'))}
          >
            <Building2 className="mr-2 h-4 w-4" />
            Clients
          </CommandItem>
          <CommandItem
            value="Lodgements"
            onSelect={() => runCommand(() => router.push('/lodgements'))}
          >
            <FileCheck className="mr-2 h-4 w-4" />
            Lodgements
          </CommandItem>
          <CommandItem
            value="AI Assistant"
            onSelect={() => runCommand(() => router.push('/assistant'))}
          >
            <MessageSquareText className="mr-2 h-4 w-4" />
            AI Assistant
          </CommandItem>
          <CommandItem
            value="Action Items"
            onSelect={() => runCommand(() => router.push('/action-items'))}
          >
            <ListChecks className="mr-2 h-4 w-4" />
            Action Items
          </CommandItem>
          <CommandItem
            value="Notifications"
            onSelect={() => runCommand(() => router.push('/notifications'))}
          >
            <Bell className="mr-2 h-4 w-4" />
            Notifications
          </CommandItem>
          <CommandItem
            value="Team"
            onSelect={() => runCommand(() => router.push('/team'))}
          >
            <Users className="mr-2 h-4 w-4" />
            Team
          </CommandItem>
        </CommandGroup>

        <CommandSeparator />

        {/* Settings */}
        <CommandGroup heading="Settings">
          <CommandItem
            value="Settings"
            onSelect={() => runCommand(() => router.push('/settings'))}
          >
            <Settings className="mr-2 h-4 w-4" />
            Settings
          </CommandItem>
          <CommandItem
            value="Billing"
            onSelect={() =>
              runCommand(() => router.push('/settings/billing'))
            }
          >
            <Settings className="mr-2 h-4 w-4" />
            Billing
          </CommandItem>
          <CommandItem
            value="Integrations"
            onSelect={() =>
              runCommand(() => router.push('/settings/integrations'))
            }
          >
            <Settings className="mr-2 h-4 w-4" />
            Integrations
          </CommandItem>
        </CommandGroup>

        <CommandSeparator />

        {/* Actions */}
        <CommandGroup heading="Actions">
          <CommandItem
            value="Toggle theme"
            onSelect={() =>
              runCommand(() =>
                setTheme(theme === 'dark' ? 'light' : 'dark')
              )
            }
          >
            {theme === 'dark' ? (
              <Sun className="mr-2 h-4 w-4" />
            ) : (
              <Moon className="mr-2 h-4 w-4" />
            )}
            Toggle theme
            <CommandShortcut>Theme</CommandShortcut>
          </CommandItem>
        </CommandGroup>

        <CommandSeparator />

        {/* Admin */}
        <CommandGroup heading="Admin">
          <CommandItem
            value="Usage Analytics"
            onSelect={() => runCommand(() => router.push('/admin/usage'))}
          >
            <BarChart3 className="mr-2 h-4 w-4" />
            Usage Analytics
          </CommandItem>
          <CommandItem
            value="Knowledge Base"
            onSelect={() =>
              runCommand(() => router.push('/admin/knowledge'))
            }
          >
            <Library className="mr-2 h-4 w-4" />
            Knowledge Base
          </CommandItem>
          <CommandItem
            value="Triggers"
            onSelect={() =>
              runCommand(() => router.push('/admin/triggers'))
            }
          >
            <Zap className="mr-2 h-4 w-4" />
            Triggers
          </CommandItem>
          <CommandItem
            value="Admin Panel"
            onSelect={() =>
              runCommand(() => router.push('/internal/admin'))
            }
          >
            <ShieldCheck className="mr-2 h-4 w-4" />
            Admin Panel
          </CommandItem>
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}
