'use client';

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
 * Clairo brand logo - Neural network representing insights connected to clarity
 * Uses brand coral palette from design system
 */
export function ClairoLogo({ size = 'md', showText = true, variant = 'light', className = '' }: ClairoLogoProps) {
  const { icon: iconSize, text: textSize } = sizes[size];
  const uid = `clairo-${Math.random().toString(36).substr(2, 9)}`;

  return (
    <div className={cn('flex items-center gap-2', className)}>
      <svg
        width={iconSize}
        height={iconSize}
        viewBox="0 0 200 200"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="flex-shrink-0"
      >
        <defs>
          <linearGradient id={`${uid}-main`} x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="hsl(12, 80%, 55%)" />
            <stop offset="100%" stopColor="hsl(12, 80%, 40%)" />
          </linearGradient>
          <linearGradient id={`${uid}-light`} x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="hsl(12, 80%, 70%)" />
            <stop offset="100%" stopColor="hsl(12, 80%, 55%)" />
          </linearGradient>
          <radialGradient id={`${uid}-radial`} cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="hsl(12, 80%, 82%)" stopOpacity="0.3" />
            <stop offset="100%" stopColor="hsl(12, 80%, 82%)" stopOpacity="0" />
          </radialGradient>
        </defs>

        {/* Ambient glow */}
        <circle cx="100" cy="100" r="70" fill={`url(#${uid}-radial)`} />

        {/* C arc */}
        <path
          d="M130 35 A65 65 0 1 0 130 165"
          stroke={`url(#${uid}-main)`}
          strokeWidth="10"
          strokeLinecap="round"
          fill="none"
        />

        {/* Network connections */}
        <path d="M48 65 C70 75 80 90 100 100" stroke={`url(#${uid}-light)`} strokeWidth="2" fill="none" />
        <path d="M48 135 C70 125 80 110 100 100" stroke={`url(#${uid}-light)`} strokeWidth="2" fill="none" />
        <path d="M48 100 L100 100" stroke="hsl(12, 80%, 82%)" strokeWidth="1.5" fill="none" />
        <path d="M48 65 L48 135" stroke="hsl(12, 80%, 90%)" strokeWidth="1" fill="none" opacity="0.5" />

        {/* Input insight nodes */}
        <circle cx="48" cy="65" r="10" fill={`url(#${uid}-light)`} />
        <circle cx="48" cy="100" r="8" fill="hsl(12, 80%, 82%)" />
        <circle cx="48" cy="135" r="10" fill={`url(#${uid}-light)`} />

        {/* Central clarity hub */}
        <circle cx="100" cy="100" r="20" fill={`url(#${uid}-main)`} />
        <circle cx="100" cy="100" r="12" fill="white" opacity="0.15" />
        <circle cx="100" cy="100" r="6" fill="white" opacity="0.3" />

        {/* Output pulse ring */}
        <circle cx="100" cy="100" r="28" stroke={`url(#${uid}-main)`} strokeWidth="1.5" fill="none" opacity="0.4" />
      </svg>

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
    <svg
      width={size}
      height={size}
      viewBox="0 0 200 200"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      <defs>
        <linearGradient id="clairoIconMain" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="hsl(12, 80%, 55%)" />
          <stop offset="100%" stopColor="hsl(12, 80%, 40%)" />
        </linearGradient>
        <linearGradient id="clairoIconLight" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="hsl(12, 80%, 70%)" />
          <stop offset="100%" stopColor="hsl(12, 80%, 55%)" />
        </linearGradient>
        <radialGradient id="clairoIconRadial" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="hsl(12, 80%, 82%)" stopOpacity="0.3" />
          <stop offset="100%" stopColor="hsl(12, 80%, 82%)" stopOpacity="0" />
        </radialGradient>
      </defs>

      <circle cx="100" cy="100" r="70" fill="url(#clairoIconRadial)" />
      <path
        d="M130 35 A65 65 0 1 0 130 165"
        stroke="url(#clairoIconMain)"
        strokeWidth="10"
        strokeLinecap="round"
        fill="none"
      />
      <path d="M48 65 C70 75 80 90 100 100" stroke="url(#clairoIconLight)" strokeWidth="2" fill="none" />
      <path d="M48 135 C70 125 80 110 100 100" stroke="url(#clairoIconLight)" strokeWidth="2" fill="none" />
      <path d="M48 100 L100 100" stroke="hsl(12, 80%, 82%)" strokeWidth="1.5" fill="none" />
      <path d="M48 65 L48 135" stroke="hsl(12, 80%, 90%)" strokeWidth="1" fill="none" opacity="0.5" />
      <circle cx="48" cy="65" r="10" fill="url(#clairoIconLight)" />
      <circle cx="48" cy="100" r="8" fill="hsl(12, 80%, 82%)" />
      <circle cx="48" cy="135" r="10" fill="url(#clairoIconLight)" />
      <circle cx="100" cy="100" r="20" fill="url(#clairoIconMain)" />
      <circle cx="100" cy="100" r="12" fill="white" opacity="0.15" />
      <circle cx="100" cy="100" r="6" fill="white" opacity="0.3" />
      <circle cx="100" cy="100" r="28" stroke="url(#clairoIconMain)" strokeWidth="1.5" fill="none" opacity="0.4" />
    </svg>
  );
}

export default ClairoLogo;
