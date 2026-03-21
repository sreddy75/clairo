import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * Merge class names with Tailwind CSS conflict resolution.
 *
 * Uses clsx for conditional class handling and tailwind-merge
 * to resolve Tailwind CSS class conflicts.
 *
 * @example
 * cn('px-2 py-1', 'px-4') // => 'py-1 px-4'
 * cn('text-red-500', condition && 'text-blue-500')
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// Re-export formatters for backward compatibility.
// New code should import directly from '@/lib/formatters'.
export { formatCurrency, formatDate } from './formatters';
