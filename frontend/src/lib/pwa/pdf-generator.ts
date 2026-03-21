/**
 * PDF Generator Utility
 *
 * Creates PDF documents from captured images.
 *
 * Spec: 032-pwa-mobile-document-capture
 */

import { jsPDF } from 'jspdf';

// =============================================================================
// Types
// =============================================================================

export interface PageData {
  id: string;
  imageData: ArrayBuffer;
  order: number;
  width?: number;
  height?: number;
}

export interface PDFGeneratorOptions {
  /** PDF title (metadata) */
  title?: string;
  /** PDF author (metadata) */
  author?: string;
  /** Image quality (0-1) */
  quality?: number;
  /** Page orientation */
  orientation?: 'portrait' | 'landscape' | 'auto';
  /** Page size */
  pageSize?: 'a4' | 'letter' | 'legal';
  /** Margin in mm */
  margin?: number;
}

export interface GeneratedPDF {
  /** PDF blob */
  blob: Blob;
  /** Suggested filename */
  filename: string;
  /** Number of pages */
  pageCount: number;
  /** Total size in bytes */
  size: number;
}

// =============================================================================
// PDF Generation
// =============================================================================

/**
 * Generate a PDF from an array of page images.
 */
export async function generatePDF(
  pages: PageData[],
  options: PDFGeneratorOptions = {}
): Promise<GeneratedPDF> {
  const {
    title = 'Scanned Document',
    author = 'Clairo Portal',
    quality: _quality = 0.85,
    orientation = 'auto',
    pageSize = 'a4',
    margin = 10,
  } = options;

  // Sort pages by order
  const sortedPages = [...pages].sort((a, b) => a.order - b.order);

  const firstPage = sortedPages[0];
  if (!firstPage) {
    throw new Error('No pages to generate PDF');
  }

  // Get page dimensions in mm
  const pageDimensions = getPageDimensions(pageSize);

  // Create PDF - first page orientation
  const firstImage = await loadImageFromArrayBuffer(firstPage.imageData);
  const firstOrientation = getPageOrientation(
    firstImage.width,
    firstImage.height,
    orientation
  );

  const pdf = new jsPDF({
    orientation: firstOrientation,
    unit: 'mm',
    format: pageSize,
  });

  // Set metadata
  pdf.setProperties({
    title,
    author,
    creator: 'Clairo PWA',
  });

  // Add each page
  for (let i = 0; i < sortedPages.length; i++) {
    const page = sortedPages[i];
    if (!page) continue;
    const image = await loadImageFromArrayBuffer(page.imageData);

    // Add new page (except for first)
    if (i > 0) {
      const pageOrientation = getPageOrientation(
        image.width,
        image.height,
        orientation
      );
      pdf.addPage(pageSize, pageOrientation);
    }

    // Calculate image placement
    const currentOrientation = i === 0 ? firstOrientation : getPageOrientation(
      image.width,
      image.height,
      orientation
    );

    const pageWidth = currentOrientation === 'landscape'
      ? pageDimensions.height
      : pageDimensions.width;
    const pageHeight = currentOrientation === 'landscape'
      ? pageDimensions.width
      : pageDimensions.height;

    const availableWidth = pageWidth - margin * 2;
    const availableHeight = pageHeight - margin * 2;

    const placement = calculateImagePlacement(
      image.width,
      image.height,
      availableWidth,
      availableHeight
    );

    // Add image to page
    pdf.addImage(
      image.dataUrl,
      'JPEG',
      margin + placement.x,
      margin + placement.y,
      placement.width,
      placement.height,
      undefined,
      'FAST'
    );
  }

  // Generate blob
  const blob = pdf.output('blob');

  return {
    blob,
    filename: generateFilename(title),
    pageCount: sortedPages.length,
    size: blob.size,
  };
}

/**
 * Generate a PDF from a single image.
 */
export async function generateSinglePagePDF(
  imageBlob: Blob,
  options: PDFGeneratorOptions = {}
): Promise<GeneratedPDF> {
  const buffer = await imageBlob.arrayBuffer();
  const page: PageData = {
    id: 'single',
    imageData: buffer,
    order: 0,
  };

  return generatePDF([page], options);
}

// =============================================================================
// Helper Functions
// =============================================================================

/**
 * Load an image from ArrayBuffer and get data URL.
 */
async function loadImageFromArrayBuffer(
  buffer: ArrayBuffer
): Promise<{ dataUrl: string; width: number; height: number }> {
  return new Promise((resolve, reject) => {
    const blob = new Blob([buffer], { type: 'image/jpeg' });
    const url = URL.createObjectURL(blob);
    const img = new Image();

    img.onload = () => {
      // Create canvas to get data URL
      const canvas = document.createElement('canvas');
      canvas.width = img.width;
      canvas.height = img.height;

      const ctx = canvas.getContext('2d');
      if (!ctx) {
        reject(new Error('Could not get canvas context'));
        return;
      }

      ctx.drawImage(img, 0, 0);
      const dataUrl = canvas.toDataURL('image/jpeg', 0.85);

      URL.revokeObjectURL(url);
      resolve({
        dataUrl,
        width: img.width,
        height: img.height,
      });
    };

    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error('Failed to load image'));
    };

    img.src = url;
  });
}

/**
 * Get page dimensions for a page size.
 */
function getPageDimensions(pageSize: string): { width: number; height: number } {
  switch (pageSize) {
    case 'letter':
      return { width: 215.9, height: 279.4 };
    case 'legal':
      return { width: 215.9, height: 355.6 };
    case 'a4':
    default:
      return { width: 210, height: 297 };
  }
}

/**
 * Determine page orientation based on image aspect ratio.
 */
function getPageOrientation(
  imageWidth: number,
  imageHeight: number,
  preference: 'portrait' | 'landscape' | 'auto'
): 'portrait' | 'landscape' {
  if (preference !== 'auto') {
    return preference;
  }

  // Use landscape if image is wider than tall
  return imageWidth > imageHeight ? 'landscape' : 'portrait';
}

/**
 * Calculate image placement to fit within available space.
 */
function calculateImagePlacement(
  imageWidth: number,
  imageHeight: number,
  availableWidth: number,
  availableHeight: number
): { x: number; y: number; width: number; height: number } {
  const imageRatio = imageWidth / imageHeight;
  const availableRatio = availableWidth / availableHeight;

  let width: number;
  let height: number;

  if (imageRatio > availableRatio) {
    // Image is wider - fit to width
    width = availableWidth;
    height = availableWidth / imageRatio;
  } else {
    // Image is taller - fit to height
    height = availableHeight;
    width = availableHeight * imageRatio;
  }

  // Center the image
  const x = (availableWidth - width) / 2;
  const y = (availableHeight - height) / 2;

  return { x, y, width, height };
}

/**
 * Generate a filename for the PDF.
 */
export function generateFilename(title?: string): string {
  const now = new Date();
  const date = now.toISOString().split('T')[0] ?? 'unknown';
  const time = (now.toTimeString().split(' ')[0] ?? '00-00-00').replace(/:/g, '-');

  if (title) {
    // Sanitize title for filename
    const sanitized = title
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '')
      .substring(0, 50);

    return `${sanitized}-${date}.pdf`;
  }

  return `scan-${date}-${time}.pdf`;
}
