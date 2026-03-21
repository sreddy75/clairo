/**
 * Tests for UpgradePrompt component.
 *
 * Tests feature gating UI components.
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { UpgradePrompt, withFeatureGate } from '@/components/billing/UpgradePrompt';

describe('UpgradePrompt component', () => {
  describe('card variant (default)', () => {
    it('should render feature name', () => {
      render(
        <UpgradePrompt
          feature="custom_triggers"
          requiredTier="professional"
          currentTier="starter"
        />
      );

      expect(screen.getByText('Custom Triggers Locked')).toBeInTheDocument();
    });

    it('should show required tier message', () => {
      render(
        <UpgradePrompt
          feature="custom_triggers"
          requiredTier="professional"
          currentTier="starter"
        />
      );

      expect(
        screen.getByText(/Custom Triggers is available on Professional plan/)
      ).toBeInTheDocument();
    });

    it('should show current tier badge', () => {
      render(
        <UpgradePrompt
          feature="api_access"
          requiredTier="growth"
          currentTier="professional"
        />
      );

      expect(screen.getByText('Professional')).toBeInTheDocument();
    });

    it('should render upgrade button with correct tier', () => {
      render(
        <UpgradePrompt
          feature="api_access"
          requiredTier="growth"
          currentTier="starter"
        />
      );

      expect(screen.getByRole('link', { name: /Upgrade to Growth/i })).toBeInTheDocument();
    });

    it('should link to pricing page', () => {
      render(
        <UpgradePrompt
          feature="client_portal"
          requiredTier="professional"
          currentTier="starter"
        />
      );

      const link = screen.getByRole('link', { name: /Upgrade to Professional/i });
      expect(link).toHaveAttribute('href', '/pricing');
    });
  });

  describe('inline variant', () => {
    it('should render inline message', () => {
      render(
        <UpgradePrompt
          feature="magic_zone"
          requiredTier="professional"
          currentTier="starter"
          variant="inline"
        />
      );

      expect(
        screen.getByText(/Magic Zone is available on Professional plan/)
      ).toBeInTheDocument();
    });

    it('should show inline upgrade link', () => {
      render(
        <UpgradePrompt
          feature="magic_zone"
          requiredTier="professional"
          currentTier="starter"
          variant="inline"
        />
      );

      expect(screen.getByRole('link', { name: /Upgrade/i })).toBeInTheDocument();
    });
  });

  describe('banner variant', () => {
    it('should render banner style', () => {
      render(
        <UpgradePrompt
          feature="knowledge_base"
          requiredTier="professional"
          currentTier="starter"
          variant="banner"
        />
      );

      expect(
        screen.getByText(/Knowledge Base is available on Professional plan/)
      ).toBeInTheDocument();
      expect(screen.getByRole('link', { name: /Upgrade/i })).toBeInTheDocument();
    });
  });

  describe('custom message', () => {
    it('should display custom message when provided', () => {
      const customMessage = 'Please upgrade to access this premium feature.';
      render(
        <UpgradePrompt
          feature="api_access"
          requiredTier="growth"
          currentTier="starter"
          message={customMessage}
        />
      );

      expect(screen.getByText(customMessage)).toBeInTheDocument();
    });
  });

  describe('callback handling', () => {
    it('should call onUpgrade callback when clicked', async () => {
      const onUpgrade = vi.fn();
      const user = userEvent.setup();

      render(
        <UpgradePrompt
          feature="custom_triggers"
          requiredTier="professional"
          currentTier="starter"
          onUpgrade={onUpgrade}
        />
      );

      const link = screen.getByRole('link', { name: /Upgrade to Professional/i });
      await user.click(link);

      expect(onUpgrade).toHaveBeenCalled();
    });
  });

  describe('custom className', () => {
    it('should apply custom className', () => {
      const { container } = render(
        <UpgradePrompt
          feature="api_access"
          requiredTier="growth"
          currentTier="starter"
          className="my-custom-class"
        />
      );

      expect(container.firstChild).toHaveClass('my-custom-class');
    });
  });
});

describe('withFeatureGate HOC', () => {
  const MockComponent = () => <div data-testid="protected-content">Protected Content</div>;

  it('should render wrapped component when tier is sufficient', () => {
    const GatedComponent = withFeatureGate(MockComponent, {
      feature: 'client_portal',
      requiredTier: 'professional',
    });

    render(<GatedComponent currentTier="professional" />);

    expect(screen.getByTestId('protected-content')).toBeInTheDocument();
  });

  it('should show upgrade prompt when tier is insufficient', () => {
    const GatedComponent = withFeatureGate(MockComponent, {
      feature: 'client_portal',
      requiredTier: 'professional',
    });

    render(<GatedComponent currentTier="starter" />);

    expect(screen.queryByTestId('protected-content')).not.toBeInTheDocument();
    expect(screen.getByText('Client Portal Locked')).toBeInTheDocument();
  });

  it('should allow higher tier than required', () => {
    const GatedComponent = withFeatureGate(MockComponent, {
      feature: 'client_portal',
      requiredTier: 'professional',
    });

    render(<GatedComponent currentTier="enterprise" />);

    expect(screen.getByTestId('protected-content')).toBeInTheDocument();
  });

  it('should block growth-only feature for professional', () => {
    const GatedComponent = withFeatureGate(MockComponent, {
      feature: 'api_access',
      requiredTier: 'growth',
    });

    render(<GatedComponent currentTier="professional" />);

    expect(screen.queryByTestId('protected-content')).not.toBeInTheDocument();
    expect(screen.getByText('API Access Locked')).toBeInTheDocument();
  });
});
