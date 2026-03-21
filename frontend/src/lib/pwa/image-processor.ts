/**
 * Image Processing Utilities
 *
 * Handles:
 * - Image compression
 * - EXIF orientation correction
 * - Image resizing
 *
 * Spec: 032-pwa-mobile-document-capture
 */

// =============================================================================
// Types
// =============================================================================

export interface ImageProcessingOptions {
  /** Maximum width in pixels */
  maxWidth?: number;
  /** Maximum height in pixels */
  maxHeight?: number;
  /** JPEG quality (0-1) */
  quality?: number;
  /** Output MIME type */
  mimeType?: 'image/jpeg' | 'image/png' | 'image/webp';
  /** Whether to fix EXIF orientation */
  fixOrientation?: boolean;
}

export interface ProcessedImage {
  /** Processed image blob */
  blob: Blob;
  /** Original width */
  originalWidth: number;
  /** Original height */
  originalHeight: number;
  /** Processed width */
  width: number;
  /** Processed height */
  height: number;
  /** Original size in bytes */
  originalSize: number;
  /** Processed size in bytes */
  size: number;
  /** Compression ratio */
  compressionRatio: number;
}

// =============================================================================
// EXIF Orientation
// =============================================================================

/**
 * Get EXIF orientation from image file.
 * Returns 1-8 orientation value, or 1 if not found.
 */
export async function getExifOrientation(file: Blob): Promise<number> {
  return new Promise((resolve) => {
    const reader = new FileReader();

    reader.onload = (e) => {
      const view = new DataView(e.target?.result as ArrayBuffer);

      // Check for JPEG magic bytes
      if (view.getUint16(0, false) !== 0xffd8) {
        resolve(1);
        return;
      }

      const length = view.byteLength;
      let offset = 2;

      while (offset < length) {
        // Check for valid JPEG marker
        if (view.getUint8(offset) !== 0xff) {
          resolve(1);
          return;
        }

        const marker = view.getUint8(offset + 1);

        // APP1 marker (EXIF data)
        if (marker === 0xe1) {
          const exifOffset = offset + 4;

          // Check for "Exif" identifier
          if (
            view.getUint32(exifOffset, false) !== 0x45786966 ||
            view.getUint16(exifOffset + 4, false) !== 0x0000
          ) {
            resolve(1);
            return;
          }

          const tiffOffset = exifOffset + 6;
          const littleEndian = view.getUint16(tiffOffset, false) === 0x4949;
          const ifdOffset = view.getUint32(tiffOffset + 4, littleEndian);
          const tags = view.getUint16(tiffOffset + ifdOffset, littleEndian);

          for (let i = 0; i < tags; i++) {
            const tagOffset = tiffOffset + ifdOffset + 2 + i * 12;
            const tag = view.getUint16(tagOffset, littleEndian);

            // Orientation tag
            if (tag === 0x0112) {
              const orientation = view.getUint16(tagOffset + 8, littleEndian);
              resolve(orientation);
              return;
            }
          }

          resolve(1);
          return;
        } else if (marker === 0xd9) {
          // End of image
          break;
        } else {
          // Skip to next marker
          offset += 2 + view.getUint16(offset + 2, false);
        }
      }

      resolve(1);
    };

    reader.onerror = () => resolve(1);
    reader.readAsArrayBuffer(file.slice(0, 65536)); // Only read first 64KB
  });
}

/**
 * Get canvas transformation for EXIF orientation.
 */
function getOrientationTransform(
  orientation: number,
  width: number,
  height: number
): {
  width: number;
  height: number;
  transform: (ctx: CanvasRenderingContext2D) => void;
} {
  switch (orientation) {
    case 2: // Horizontal flip
      return {
        width,
        height,
        transform: (ctx) => {
          ctx.translate(width, 0);
          ctx.scale(-1, 1);
        },
      };
    case 3: // 180° rotation
      return {
        width,
        height,
        transform: (ctx) => {
          ctx.translate(width, height);
          ctx.rotate(Math.PI);
        },
      };
    case 4: // Vertical flip
      return {
        width,
        height,
        transform: (ctx) => {
          ctx.translate(0, height);
          ctx.scale(1, -1);
        },
      };
    case 5: // 90° CW + horizontal flip
      return {
        width: height,
        height: width,
        transform: (ctx) => {
          ctx.rotate(Math.PI / 2);
          ctx.scale(1, -1);
        },
      };
    case 6: // 90° CW
      return {
        width: height,
        height: width,
        transform: (ctx) => {
          ctx.translate(height, 0);
          ctx.rotate(Math.PI / 2);
        },
      };
    case 7: // 90° CCW + horizontal flip
      return {
        width: height,
        height: width,
        transform: (ctx) => {
          ctx.translate(height, width);
          ctx.rotate(Math.PI / 2);
          ctx.translate(0, -height);
          ctx.scale(-1, 1);
        },
      };
    case 8: // 90° CCW
      return {
        width: height,
        height: width,
        transform: (ctx) => {
          ctx.translate(0, width);
          ctx.rotate(-Math.PI / 2);
        },
      };
    default: // Normal orientation
      return {
        width,
        height,
        transform: () => {},
      };
  }
}

// =============================================================================
// Image Processing
// =============================================================================

/**
 * Load an image from a blob.
 */
async function loadImage(blob: Blob): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error('Failed to load image'));
    img.src = URL.createObjectURL(blob);
  });
}

/**
 * Calculate scaled dimensions while maintaining aspect ratio.
 */
function calculateScaledDimensions(
  width: number,
  height: number,
  maxWidth: number,
  maxHeight: number
): { width: number; height: number; scale: number } {
  let scale = 1;

  if (width > maxWidth) {
    scale = maxWidth / width;
  }

  if (height * scale > maxHeight) {
    scale = maxHeight / height;
  }

  return {
    width: Math.round(width * scale),
    height: Math.round(height * scale),
    scale,
  };
}

/**
 * Compress and optionally resize an image.
 */
export async function compressImage(
  blob: Blob,
  options: ImageProcessingOptions = {}
): Promise<ProcessedImage> {
  const {
    maxWidth = 1920,
    maxHeight = 1920,
    quality = 0.85,
    mimeType = 'image/jpeg',
    fixOrientation = true,
  } = options;

  const originalSize = blob.size;

  // Load image
  const img = await loadImage(blob);
  const originalWidth = img.width;
  const originalHeight = img.height;

  // Get EXIF orientation
  let orientation = 1;
  if (fixOrientation) {
    orientation = await getExifOrientation(blob);
  }

  // Get transformation for orientation
  const transform = getOrientationTransform(
    orientation,
    originalWidth,
    originalHeight
  );

  // Calculate output dimensions
  const scaled = calculateScaledDimensions(
    transform.width,
    transform.height,
    maxWidth,
    maxHeight
  );

  // Create canvas
  const canvas = document.createElement('canvas');
  canvas.width = scaled.width;
  canvas.height = scaled.height;

  const ctx = canvas.getContext('2d');
  if (!ctx) {
    throw new Error('Could not get canvas context');
  }

  // Apply scaling
  ctx.scale(scaled.scale, scaled.scale);

  // Apply orientation transform
  transform.transform(ctx);

  // Draw image
  ctx.drawImage(img, 0, 0, originalWidth, originalHeight);

  // Clean up
  URL.revokeObjectURL(img.src);

  // Convert to blob
  const processedBlob = await new Promise<Blob>((resolve, reject) => {
    canvas.toBlob(
      (blob) => {
        if (blob) {
          resolve(blob);
        } else {
          reject(new Error('Failed to create blob'));
        }
      },
      mimeType,
      quality
    );
  });

  return {
    blob: processedBlob,
    originalWidth,
    originalHeight,
    width: scaled.width,
    height: scaled.height,
    originalSize,
    size: processedBlob.size,
    compressionRatio: originalSize / processedBlob.size,
  };
}

/**
 * Resize an image to specific dimensions.
 */
export async function resizeImage(
  blob: Blob,
  width: number,
  height: number,
  options: Omit<ImageProcessingOptions, 'maxWidth' | 'maxHeight'> = {}
): Promise<Blob> {
  const result = await compressImage(blob, {
    ...options,
    maxWidth: width,
    maxHeight: height,
  });
  return result.blob;
}

/**
 * Create a thumbnail from an image.
 */
export async function createThumbnail(
  blob: Blob,
  size: number = 200
): Promise<Blob> {
  return resizeImage(blob, size, size, {
    quality: 0.7,
    mimeType: 'image/jpeg',
  });
}

/**
 * Get image dimensions from a blob.
 */
export async function getImageDimensions(
  blob: Blob
): Promise<{ width: number; height: number }> {
  const img = await loadImage(blob);
  const { width, height } = img;
  URL.revokeObjectURL(img.src);
  return { width, height };
}

/**
 * Check if a blob is a valid image.
 */
export async function isValidImage(blob: Blob): Promise<boolean> {
  try {
    const img = await loadImage(blob);
    URL.revokeObjectURL(img.src);
    return img.width > 0 && img.height > 0;
  } catch {
    return false;
  }
}
