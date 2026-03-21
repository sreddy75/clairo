/**
 * Product tour component using react-joyride.
 *
 * Spec 021: Onboarding Flow - Interactive Product Tour
 */

'use client';

import dynamic from 'next/dynamic';
import { useCallback, useState } from 'react';
import type { CallBackProps, Status } from 'react-joyride';

import { TOUR_STEPS } from './tourSteps';

// Dynamically import Joyride to avoid SSR issues
const Joyride = dynamic(() => import('react-joyride'), { ssr: false });

interface ProductTourProps {
  run: boolean;
  onTourEnd: (data: { action: string }) => void;
}

export function ProductTour({ run, onTourEnd }: ProductTourProps) {
  const [stepIndex, setStepIndex] = useState(0);

  const handleJoyrideCallback = useCallback((data: CallBackProps) => {
    const { status, action, index, type } = data;

    // Handle step navigation
    if (type === 'step:after' && action === 'next') {
      setStepIndex(index + 1);
    } else if (type === 'step:after' && action === 'prev') {
      setStepIndex(index - 1);
    }

    // Handle tour completion or skip
    const finishedStatuses: Status[] = ['finished', 'skipped'];
    if (finishedStatuses.includes(status)) {
      setStepIndex(0);
      onTourEnd({ action: status === 'skipped' ? 'skip' : 'finish' });
    }

    // Handle close (X button)
    if (action === 'close') {
      setStepIndex(0);
      onTourEnd({ action: 'close' });
    }
  }, [onTourEnd]);

  return (
    <Joyride
      steps={TOUR_STEPS}
      run={run}
      stepIndex={stepIndex}
      callback={handleJoyrideCallback}
      continuous
      showProgress
      showSkipButton
      scrollToFirstStep
      disableCloseOnEsc={false}
      disableOverlayClose={false}
      spotlightClicks={false}
      styles={{
        options: {
          arrowColor: 'hsl(0, 0%, 100%)',
          backgroundColor: 'hsl(0, 0%, 100%)',
          overlayColor: 'rgba(0, 0, 0, 0.5)',
          primaryColor: 'hsl(12, 80%, 55%)',
          spotlightShadow: '0 0 15px rgba(0, 0, 0, 0.3)',
          textColor: 'hsl(222, 47%, 11%)',
          width: 380,
          zIndex: 10000,
        },
        tooltip: {
          borderRadius: 12,
          padding: '20px 24px',
        },
        tooltipTitle: {
          fontSize: 18,
          fontWeight: 600,
          marginBottom: 8,
        },
        tooltipContent: {
          fontSize: 14,
          lineHeight: 1.6,
          padding: '8px 0',
        },
        buttonNext: {
          backgroundColor: 'hsl(12, 80%, 55%)',
          borderRadius: 8,
          fontSize: 14,
          fontWeight: 500,
          padding: '10px 20px',
        },
        buttonBack: {
          color: 'hsl(220, 10%, 46%)',
          fontSize: 14,
          fontWeight: 500,
          marginRight: 8,
        },
        buttonSkip: {
          color: 'hsl(220, 10%, 46%)',
          fontSize: 14,
        },
        buttonClose: {
          color: 'hsl(220, 10%, 46%)',
          padding: 8,
        },
        spotlight: {
          borderRadius: 8,
        },
      }}
      locale={{
        back: 'Back',
        close: 'Close',
        last: 'Got it!',
        next: 'Next',
        skip: 'Skip tour',
        open: 'Open tour',
      }}
      floaterProps={{
        disableAnimation: false,
      }}
    />
  );
}
