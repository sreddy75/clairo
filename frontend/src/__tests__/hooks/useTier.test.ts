/**
 * Tests for useTier hook.
 *
 * Tests tier-based feature access functionality.
 */

import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useTier } from '@/hooks/useTier';
import { getFeatures } from '@/lib/api/billing';
import type { AIInsightsLevel, FeaturesResponse } from '@/types/billing';

// Mock the API module
vi.mock('@/lib/api/billing', () => ({
  getFeatures: vi.fn(),
}));

const mockGetFeatures = vi.mocked(getFeatures);

describe('useTier hook', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('initial state', () => {
    it('should start with loading state', () => {
      mockGetFeatures.mockImplementation(() => new Promise(() => {})); // Never resolves

      const { result } = renderHook(() => useTier());

      expect(result.current.isLoading).toBe(true);
      expect(result.current.tier).toBeNull();
      expect(result.current.error).toBeNull();
    });
  });

  describe('successful data fetch', () => {
    const mockProfessionalFeatures: FeaturesResponse = {
      tier: 'professional',
      features: {
        max_clients: 100,
        ai_insights: 'full' as AIInsightsLevel,
        client_portal: true,
        custom_triggers: true,
        api_access: false,
        knowledge_base: true,
        magic_zone: true,
      },
      can_access: {
        ai_insights: true,
        client_portal: true,
        custom_triggers: true,
        api_access: false,
        knowledge_base: true,
        magic_zone: true,
      },
    };

    it('should load tier information', async () => {
      mockGetFeatures.mockResolvedValue(mockProfessionalFeatures);

      const { result } = renderHook(() => useTier());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.tier).toBe('professional');
      expect(result.current.error).toBeNull();
    });

    it('should provide canAccess function', async () => {
      mockGetFeatures.mockResolvedValue(mockProfessionalFeatures);

      const { result } = renderHook(() => useTier());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.canAccess('client_portal')).toBe(true);
      expect(result.current.canAccess('api_access')).toBe(false);
      expect(result.current.canAccess('custom_triggers')).toBe(true);
    });

    it('should return false for unknown features', async () => {
      mockGetFeatures.mockResolvedValue(mockProfessionalFeatures);

      const { result } = renderHook(() => useTier());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.canAccess('unknown_feature')).toBe(false);
    });
  });

  describe('starter tier restrictions', () => {
    const mockStarterFeatures: FeaturesResponse = {
      tier: 'starter',
      features: {
        max_clients: 25,
        ai_insights: 'basic' as AIInsightsLevel,
        client_portal: false,
        custom_triggers: false,
        api_access: false,
        knowledge_base: false,
        magic_zone: false,
      },
      can_access: {
        ai_insights: true,
        client_portal: false,
        custom_triggers: false,
        api_access: false,
        knowledge_base: false,
        magic_zone: false,
      },
    };

    it('should show restricted features for starter tier', async () => {
      mockGetFeatures.mockResolvedValue(mockStarterFeatures);

      const { result } = renderHook(() => useTier());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.tier).toBe('starter');
      expect(result.current.canAccess('client_portal')).toBe(false);
      expect(result.current.canAccess('custom_triggers')).toBe(false);
      expect(result.current.canAccess('magic_zone')).toBe(false);
    });
  });

  describe('getMinimumTier', () => {
    const mockFeatures: FeaturesResponse = {
      tier: 'starter',
      features: {
        max_clients: 25,
        ai_insights: 'basic' as AIInsightsLevel,
        client_portal: false,
        custom_triggers: false,
        api_access: false,
        knowledge_base: false,
        magic_zone: false,
      },
      can_access: {},
    };

    it('should return correct minimum tier for features', async () => {
      mockGetFeatures.mockResolvedValue(mockFeatures);

      const { result } = renderHook(() => useTier());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.getMinimumTier('client_portal')).toBe('professional');
      expect(result.current.getMinimumTier('api_access')).toBe('growth');
      expect(result.current.getMinimumTier('ai_insights')).toBe('starter');
    });

    it('should default to professional for unknown features', async () => {
      mockGetFeatures.mockResolvedValue(mockFeatures);

      const { result } = renderHook(() => useTier());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.getMinimumTier('unknown_feature')).toBe('professional');
    });
  });

  describe('isUpgrade', () => {
    const mockProfessionalFeatures: FeaturesResponse = {
      tier: 'professional',
      features: {
        max_clients: 100,
        ai_insights: 'full' as AIInsightsLevel,
        client_portal: true,
        custom_triggers: true,
        api_access: false,
        knowledge_base: true,
        magic_zone: true,
      },
      can_access: {},
    };

    it('should correctly identify upgrades', async () => {
      mockGetFeatures.mockResolvedValue(mockProfessionalFeatures);

      const { result } = renderHook(() => useTier());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.isUpgrade('growth')).toBe(true);
      expect(result.current.isUpgrade('enterprise')).toBe(true);
      expect(result.current.isUpgrade('starter')).toBe(false);
      expect(result.current.isUpgrade('professional')).toBe(false);
    });
  });

  describe('error handling', () => {
    it('should handle API errors gracefully', async () => {
      mockGetFeatures.mockRejectedValue(new Error('API Error'));

      const { result } = renderHook(() => useTier());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.error).toBe('Failed to load tier information');
      expect(result.current.tier).toBeNull();
    });
  });

  describe('refresh functionality', () => {
    it('should refresh tier information', async () => {
      const initialFeatures: FeaturesResponse = {
        tier: 'starter',
        features: {
          max_clients: 25,
          ai_insights: 'basic' as AIInsightsLevel,
          client_portal: false,
          custom_triggers: false,
          api_access: false,
          knowledge_base: false,
          magic_zone: false,
        },
        can_access: { client_portal: false },
      };

      const updatedFeatures: FeaturesResponse = {
        tier: 'professional',
        features: {
          max_clients: 100,
          ai_insights: 'full' as AIInsightsLevel,
          client_portal: true,
          custom_triggers: true,
          api_access: false,
          knowledge_base: true,
          magic_zone: true,
        },
        can_access: { client_portal: true },
      };

      mockGetFeatures.mockResolvedValueOnce(initialFeatures);

      const { result } = renderHook(() => useTier());

      await waitFor(() => {
        expect(result.current.tier).toBe('starter');
      });

      mockGetFeatures.mockResolvedValueOnce(updatedFeatures);

      await act(async () => {
        await result.current.refresh();
      });

      expect(result.current.tier).toBe('professional');
      expect(result.current.canAccess('client_portal')).toBe(true);
    });
  });
});
