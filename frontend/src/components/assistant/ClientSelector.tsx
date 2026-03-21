'use client';

import { useAuth } from '@clerk/nextjs';
import { AlertCircle, Building2, Loader2, Search, X } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';

import {
  getClientProfile,
  searchClients,
  type ClientProfileResponse,
  type ClientSearchResult,
} from '@/lib/api/knowledge';

interface ClientSelectorProps {
  selectedClient: ClientSearchResult | null;
  onSelect: (client: ClientSearchResult | null) => void;
  onProfileLoad?: (profile: ClientProfileResponse | null) => void;
}

export default function ClientSelector({
  selectedClient,
  onSelect,
  onProfileLoad,
}: ClientSelectorProps) {
  const { getToken } = useAuth();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<ClientSearchResult[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const [profileData, setProfileData] = useState<ClientProfileResponse | null>(null);
  const [loadingProfile, setLoadingProfile] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<NodeJS.Timeout | null>(null);

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Search clients with debounce
  const search = useCallback(
    async (q: string) => {
      if (q.length < 1) {
        setResults([]);
        return;
      }

      setIsSearching(true);
      try {
        const token = await getToken();
        if (!token) return;

        const data = await searchClients(token, q, 10);
        setResults(data.results);
      } catch (err) {
        console.error('Search failed:', err);
        setResults([]);
      } finally {
        setIsSearching(false);
      }
    },
    [getToken]
  );

  // Handle input change with debounce
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setQuery(value);
    setIsOpen(true);

    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }

    debounceRef.current = setTimeout(() => {
      search(value);
    }, 200);
  };

  // Load client profile when selected
  useEffect(() => {
    const loadProfile = async () => {
      if (!selectedClient) {
        setProfileData(null);
        onProfileLoad?.(null);
        return;
      }

      setLoadingProfile(true);
      try {
        const token = await getToken();
        if (!token) return;

        const profile = await getClientProfile(token, selectedClient.id);
        setProfileData(profile);
        onProfileLoad?.(profile);
      } catch (err) {
        console.error('Failed to load profile:', err);
        setProfileData(null);
        onProfileLoad?.(null);
      } finally {
        setLoadingProfile(false);
      }
    };

    loadProfile();
  }, [selectedClient, getToken, onProfileLoad]);

  const handleSelect = (client: ClientSearchResult) => {
    onSelect(client);
    setQuery('');
    setIsOpen(false);
    setResults([]);
  };

  const handleClear = () => {
    onSelect(null);
    setProfileData(null);
    setQuery('');
    inputRef.current?.focus();
  };

  return (
    <div className="relative" ref={dropdownRef}>
      {/* Selected client display or search input */}
      {selectedClient ? (
        <div className="flex items-center gap-3 px-4 py-3 bg-card border border-border rounded-xl shadow-sm">
          <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-teal-100">
            <Building2 className="w-5 h-5 text-teal-600" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <p className="font-medium text-foreground truncate">{selectedClient.name}</p>
              {loadingProfile && <Loader2 className="w-3 h-3 animate-spin text-muted-foreground" />}
              {profileData?.is_stale && (
                <span className="flex items-center gap-1 text-xs text-amber-600">
                  <AlertCircle className="w-3 h-3" />
                  Stale data
                </span>
              )}
            </div>
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              {selectedClient.abn && <span>ABN: {selectedClient.abn}</span>}
              {profileData?.profile.gst_registered && (
                <span className="px-1.5 py-0.5 bg-teal-50 text-teal-700 rounded">GST</span>
              )}
              {profileData?.profile.revenue_bracket && (
                <span className="capitalize">{profileData.profile.revenue_bracket}</span>
              )}
            </div>
          </div>
          <button
            onClick={handleClear}
            className="p-2 hover:bg-muted rounded-lg transition-colors"
            title="Clear selection"
          >
            <X className="w-4 h-4 text-muted-foreground" />
          </button>
        </div>
      ) : (
        <div className="relative">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={handleInputChange}
            onFocus={() => query && setIsOpen(true)}
            placeholder="Search for a client by name..."
            className="w-full pl-11 pr-4 py-3 bg-card border border-border rounded-xl shadow-sm focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary text-foreground placeholder:text-muted-foreground/70"
          />
          {isSearching && (
            <Loader2 className="absolute right-4 top-1/2 -translate-y-1/2 w-4 h-4 animate-spin text-muted-foreground" />
          )}
        </div>
      )}

      {/* Search results dropdown */}
      {isOpen && !selectedClient && (
        <div className="absolute z-50 w-full mt-2 bg-card border border-border rounded-xl shadow-xl overflow-hidden">
          {results.length === 0 ? (
            <div className="px-4 py-6 text-center text-muted-foreground text-sm">
              {query ? 'No clients found' : 'Type to search clients'}
            </div>
          ) : (
            <div className="max-h-64 overflow-y-auto">
              {results.map((client) => (
                <button
                  key={client.id}
                  onClick={() => handleSelect(client)}
                  className="w-full flex items-center gap-3 px-4 py-3 hover:bg-muted transition-colors text-left border-b border-border last:border-0"
                >
                  <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-muted">
                    <Building2 className="w-4 h-4 text-muted-foreground" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-foreground truncate">{client.name}</p>
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      {client.abn && <span>ABN: {client.abn}</span>}
                      {client.organization_name && (
                        <span className="truncate">{client.organization_name}</span>
                      )}
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
