/**
 * Product tour steps configuration for react-joyride.
 *
 * Spec 021: Onboarding Flow - Interactive Product Tour
 */

import type { Step } from 'react-joyride';

export const TOUR_STEPS: Step[] = [
  {
    target: '[data-tour="dashboard-header"]',
    content:
      'Welcome to Clairo! This is your dashboard where you can see an overview of all your clients and their BAS status.',
    title: 'Dashboard Overview',
    disableBeacon: true,
    placement: 'bottom',
  },
  {
    target: '[data-tour="client-list"]',
    content:
      'Your clients are listed here. You can see their BAS due dates, data quality scores, and current status at a glance.',
    title: 'Client List',
    placement: 'right',
  },
  {
    target: '[data-tour="bas-workflow"]',
    content:
      'Click on a client to open their BAS workflow. Clairo guides you through preparation, review, and lodgement.',
    title: 'BAS Workflow',
    placement: 'bottom',
  },
  {
    target: '[data-tour="quality-score"]',
    content:
      'Data quality scores help you identify issues before they become problems. Higher scores mean fewer potential ATO queries.',
    title: 'Data Quality Scoring',
    placement: 'left',
  },
  {
    target: '[data-tour="ai-insights"]',
    content:
      'AI-powered insights automatically detect anomalies, suggest corrections, and provide compliance recommendations.',
    title: 'AI Insights',
    placement: 'bottom',
  },
  {
    target: '[data-tour="settings-menu"]',
    content:
      'Access your settings, manage your Xero connection, update billing, and customize your workspace.',
    title: 'Settings',
    placement: 'left',
  },
];

// Mapping for tour step IDs to display names
export const TOUR_STEP_NAMES: Record<number, string> = {
  0: 'Dashboard',
  1: 'Clients',
  2: 'BAS Workflow',
  3: 'Data Quality',
  4: 'AI Insights',
  5: 'Settings',
};
