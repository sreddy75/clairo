'use client';

import Image from 'next/image';

import { cn } from '@/lib/utils';

interface ClairoLogoProps {
  size?: 'sm' | 'md' | 'lg' | 'xl';
  showText?: boolean;
  variant?: 'light' | 'dark';
  className?: string;
}

const sizes = {
  sm: { icon: 28, text: 'text-lg' },
  md: { icon: 36, text: 'text-xl' },
  lg: { icon: 52, text: 'text-2xl' },
  xl: { icon: 72, text: 'text-3xl' },
};

/**
 * Clairo brand logo — overlapping circles representing
 * data + compliance + strategy converging into clarity
 */
export function ClairoLogo({ size = 'md', showText = true, variant = 'light', className = '' }: ClairoLogoProps) {
  const { icon: iconSize, text: textSize } = sizes[size];

  return (
    <div className={cn('flex items-center gap-2.5', className)}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src="/logos/clairo-logo-new.png"
        alt="Clairo"
        width={iconSize}
        height={iconSize}
        className="flex-shrink-0 rounded-md mix-blend-multiply dark:mix-blend-normal"
      />
      {showText && (
        <span className={cn(
          'font-bold tracking-tight',
          variant === 'dark' ? 'text-white' : 'text-foreground',
          textSize
        )}>
          Clairo
        </span>
      )}
    </div>
  );
}

/**
 * Icon-only version for favicons, app icons, etc.
 */
export function ClairoIcon({ size = 36, className = '' }: { size?: number; className?: string }) {
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src="/logos/clairo-logo-new.png"
      alt="Clairo"
      width={size}
      height={size}
      className={cn('rounded-md mix-blend-multiply dark:mix-blend-normal', className)}
    />
  );
}

/**
 * Animated logo for thinking/loading states in chat.
 * Uses the MP4 animation with <img> fallback for the static logo.
 */
export function ClairoThinking({ size = 48, className = '' }: { size?: number; className?: string }) {
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src="/logos/clairo-animate.mp4"
      alt=""
      width={size}
      height={size}
      className={cn('rounded-md', className)}
      // If MP4 doesn't render as <img>, fall back to static logo with animation
      onError={(e) => {
        const el = e.currentTarget;
        el.src = '/logos/clairo-logo-new.png';
        el.classList.add('animate-pulse');
      }}
    />
  );
}

export default ClairoLogo;
