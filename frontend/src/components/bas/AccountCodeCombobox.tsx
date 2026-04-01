'use client';

import { Check, ChevronsUpDown } from 'lucide-react';
import { useEffect, useState } from 'react';

import { Button } from '@/components/ui/button';
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import type { XeroAccountOption } from '@/lib/bas';
import { listXeroAccounts } from '@/lib/bas';
import { cn } from '@/lib/utils';

interface AccountCodeComboboxProps {
  connectionId: string;
  getToken: () => Promise<string | null>;
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  placeholder?: string;
  className?: string;
}

/**
 * Searchable combobox for selecting a Xero account code.
 * Fetches the chart of accounts once on first open and caches it locally.
 */
export function AccountCodeCombobox({
  connectionId,
  getToken,
  value,
  onChange,
  disabled = false,
  placeholder = 'Account...',
  className,
}: AccountCodeComboboxProps) {
  const [open, setOpen] = useState(false);
  const [accounts, setAccounts] = useState<XeroAccountOption[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (!open || loaded) return;
    let cancelled = false;
    (async () => {
      const token = await getToken();
      if (!token || cancelled) return;
      try {
        const data = await listXeroAccounts(token, connectionId);
        if (!cancelled) {
          setAccounts(data.sort((a, b) => a.account_code.localeCompare(b.account_code)));
          setLoaded(true);
        }
      } catch {
        // silent — combobox degrades to showing nothing
      }
    })();
    return () => { cancelled = true; };
  }, [open, loaded, connectionId, getToken]);

  const selected = accounts.find((a) => a.account_code === value);
  const displayLabel = selected
    ? `${selected.account_code} · ${selected.account_name}`
    : value || placeholder;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          disabled={disabled}
          className={cn(
            'h-6 text-xs px-2 justify-between font-normal',
            !value && 'text-muted-foreground',
            className,
          )}
        >
          <span className="truncate">{displayLabel}</span>
          <ChevronsUpDown className="ml-1 w-3 h-3 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-72 p-0" align="start">
        <Command>
          <CommandInput placeholder="Search code or name..." className="h-8 text-xs" />
          <CommandList>
            <CommandEmpty className="py-4 text-xs text-center text-muted-foreground">
              {loaded ? 'No accounts found.' : 'Loading…'}
            </CommandEmpty>
            {accounts.length > 0 && (
              <CommandGroup>
                {accounts.map((account) => (
                  <CommandItem
                    key={account.account_code}
                    value={`${account.account_code} ${account.account_name}`}
                    onSelect={() => {
                      onChange(account.account_code === value ? '' : account.account_code);
                      setOpen(false);
                    }}
                    className="text-xs"
                  >
                    <Check
                      className={cn(
                        'mr-2 w-3 h-3',
                        value === account.account_code ? 'opacity-100' : 'opacity-0',
                      )}
                    />
                    <span className="font-mono mr-2 text-muted-foreground w-12 shrink-0">
                      {account.account_code}
                    </span>
                    <span className="truncate">{account.account_name}</span>
                  </CommandItem>
                ))}
              </CommandGroup>
            )}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
