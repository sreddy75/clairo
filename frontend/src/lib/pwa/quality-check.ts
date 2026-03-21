/**
 * Document Quality Check Utilities
 *
 * Analyzes image quality for blur, brightness, and contrast.
 *
 * Spec: 032-pwa-mobile-document-capture
 */

// =============================================================================
// Types
// =============================================================================

export interface QualityResult {
  /** Overall quality score (0-100) */
  score: number;
  /** Individual quality checks */
  checks: {
    blur: QualityCheck;
    brightness: QualityCheck;
    contrast: QualityCheck;
  };
  /** List of issues found */
  issues: string[];
  /** Whether quality is acceptable */
  isAcceptable: boolean;
}

export interface QualityCheck {
  /** Check passed */
  passed: boolean;
  /** Measured value */
  value: number;
  /** Human-readable message */
  message: string;
}

export interface QualityThresholds {
  /** Minimum Laplacian variance for blur detection */
  minBlurScore: number;
  /** Minimum brightness (0-255) */
  minBrightness: number;
  /** Maximum brightness (0-255) */
  maxBrightness: number;
  /** Minimum contrast (standard deviation) */
  minContrast: number;
}

// =============================================================================
// Default Thresholds
// =============================================================================

export const DEFAULT_THRESHOLDS: QualityThresholds = {
  minBlurScore: 100, // Laplacian variance threshold
  minBrightness: 40, // Too dark below this
  maxBrightness: 220, // Too bright above this
  minContrast: 30, // Low contrast below this
};

// =============================================================================
// Quality Analysis
// =============================================================================

/**
 * Analyze image quality.
 */
export async function analyzeImageQuality(
  imageBlob: Blob,
  thresholds: QualityThresholds = DEFAULT_THRESHOLDS
): Promise<QualityResult> {
  const imageData = await getImageData(imageBlob);

  // Run quality checks
  const blur = checkBlur(imageData, thresholds.minBlurScore);
  const brightness = checkBrightness(
    imageData,
    thresholds.minBrightness,
    thresholds.maxBrightness
  );
  const contrast = checkContrast(imageData, thresholds.minContrast);

  // Collect issues
  const issues: string[] = [];
  if (!blur.passed) issues.push(blur.message);
  if (!brightness.passed) issues.push(brightness.message);
  if (!contrast.passed) issues.push(contrast.message);

  // Calculate overall score
  const blurScore = blur.passed ? 100 : Math.min(100, (blur.value / thresholds.minBlurScore) * 100);
  const brightnessScore = brightness.passed ? 100 : 70;
  const contrastScore = contrast.passed ? 100 : Math.min(100, (contrast.value / thresholds.minContrast) * 100);

  const score = Math.round((blurScore + brightnessScore + contrastScore) / 3);

  return {
    score,
    checks: { blur, brightness, contrast },
    issues,
    isAcceptable: issues.length === 0,
  };
}

/**
 * Quick quality check (blur only - for real-time feedback).
 */
export async function quickBlurCheck(
  imageBlob: Blob,
  threshold: number = DEFAULT_THRESHOLDS.minBlurScore
): Promise<{ isBlurry: boolean; score: number }> {
  const imageData = await getImageData(imageBlob, 300); // Smaller image for speed
  const blur = checkBlur(imageData, threshold);

  return {
    isBlurry: !blur.passed,
    score: blur.value,
  };
}

// =============================================================================
// Helper Functions
// =============================================================================

/**
 * Get ImageData from a blob.
 */
async function getImageData(
  blob: Blob,
  maxSize: number = 800
): Promise<ImageData> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(blob);
    const img = new Image();

    img.onload = () => {
      // Calculate scaled dimensions
      let width = img.width;
      let height = img.height;

      if (width > maxSize || height > maxSize) {
        const scale = maxSize / Math.max(width, height);
        width = Math.round(width * scale);
        height = Math.round(height * scale);
      }

      // Draw to canvas
      const canvas = document.createElement('canvas');
      canvas.width = width;
      canvas.height = height;

      const ctx = canvas.getContext('2d');
      if (!ctx) {
        reject(new Error('Could not get canvas context'));
        return;
      }

      ctx.drawImage(img, 0, 0, width, height);
      const imageData = ctx.getImageData(0, 0, width, height);

      URL.revokeObjectURL(url);
      resolve(imageData);
    };

    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error('Failed to load image'));
    };

    img.src = url;
  });
}

/**
 * Check for blur using Laplacian variance.
 */
function checkBlur(imageData: ImageData, threshold: number): QualityCheck {
  const { data, width, height } = imageData;

  // Convert to grayscale
  const gray = new Float32Array(width * height);
  for (let i = 0; i < gray.length; i++) {
    const r = data[i * 4] ?? 0;
    const g = data[i * 4 + 1] ?? 0;
    const b = data[i * 4 + 2] ?? 0;
    gray[i] = 0.299 * r + 0.587 * g + 0.114 * b;
  }

  // Apply Laplacian kernel
  const laplacian: number[] = [];
  for (let y = 1; y < height - 1; y++) {
    for (let x = 1; x < width - 1; x++) {
      const idx = y * width + x;
      const value =
        (gray[idx - width] ?? 0) +
        (gray[idx - 1] ?? 0) +
        (gray[idx + 1] ?? 0) +
        (gray[idx + width] ?? 0) -
        4 * (gray[idx] ?? 0);
      laplacian.push(value);
    }
  }

  // Calculate variance
  const mean = laplacian.reduce((a, b) => a + b, 0) / laplacian.length;
  const variance =
    laplacian.reduce((sum, val) => sum + Math.pow(val - mean, 2), 0) /
    laplacian.length;

  const passed = variance >= threshold;

  return {
    passed,
    value: Math.round(variance),
    message: passed ? 'Image is sharp' : 'Image appears blurry',
  };
}

/**
 * Check brightness level.
 */
function checkBrightness(
  imageData: ImageData,
  minBrightness: number,
  maxBrightness: number
): QualityCheck {
  const { data } = imageData;

  // Calculate average brightness
  let total = 0;
  const pixelCount = data.length / 4;

  for (let i = 0; i < data.length; i += 4) {
    const r = data[i] ?? 0;
    const g = data[i + 1] ?? 0;
    const b = data[i + 2] ?? 0;
    total += 0.299 * r + 0.587 * g + 0.114 * b;
  }

  const avgBrightness = total / pixelCount;

  let passed = true;
  let message = 'Brightness is good';

  if (avgBrightness < minBrightness) {
    passed = false;
    message = 'Image is too dark';
  } else if (avgBrightness > maxBrightness) {
    passed = false;
    message = 'Image is too bright';
  }

  return {
    passed,
    value: Math.round(avgBrightness),
    message,
  };
}

/**
 * Check contrast level using standard deviation.
 */
function checkContrast(imageData: ImageData, threshold: number): QualityCheck {
  const { data } = imageData;

  // Calculate brightness values
  const brightness: number[] = [];
  for (let i = 0; i < data.length; i += 4) {
    const r = data[i] ?? 0;
    const g = data[i + 1] ?? 0;
    const b = data[i + 2] ?? 0;
    brightness.push(0.299 * r + 0.587 * g + 0.114 * b);
  }

  // Calculate standard deviation
  const mean = brightness.reduce((a, b) => a + b, 0) / brightness.length;
  const variance =
    brightness.reduce((sum, val) => sum + Math.pow(val - mean, 2), 0) /
    brightness.length;
  const stdDev = Math.sqrt(variance);

  const passed = stdDev >= threshold;

  return {
    passed,
    value: Math.round(stdDev),
    message: passed ? 'Contrast is good' : 'Image has low contrast',
  };
}
