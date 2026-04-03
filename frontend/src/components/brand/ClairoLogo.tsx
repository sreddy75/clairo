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
  sm: { icon: 24, text: 'text-lg' },
  md: { icon: 32, text: 'text-xl' },
  lg: { icon: 48, text: 'text-2xl' },
  xl: { icon: 64, text: 'text-3xl' },
};

/**
 * Clairo brand logo — overlapping circles representing
 * data + compliance + strategy converging into clarity
 */
export function ClairoLogo({ size = 'md', showText = true, variant = 'light', className = '' }: ClairoLogoProps) {
  const { icon: iconSize, text: textSize } = sizes[size];

  return (
    <div className={cn('flex items-center gap-2', className)}>
      <Image
        src="/logos/clairo-logo-new.png"
        alt="Clairo"
        width={iconSize}
        height={iconSize}
        className="flex-shrink-0 rounded-sm"
        priority
      />
      {showText && (
        <span className={cn(
          'font-bold',
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
export function ClairoIcon({ size = 32, className = '' }: { size?: number; className?: string }) {
  return (
    <Image
      src="/logos/clairo-logo-new.png"
      alt="Clairo"
      width={size}
      height={size}
      className={cn('rounded-sm', className)}
    />
  );
}

/**
 * Animated logo for thinking/loading states in chat
 */
export function ClairoThinking({ size = 48, className = '' }: { size?: number; className?: string }) {
  return (
    <video
      src="/logos/clairo-animate.mp4"
      width={size}
      height={size}
      autoPlay
      loop
      muted
      playsInline
      className={cn('rounded-sm', className)}
    />
  );
}

export default ClairoLogo;
