#!/bin/bash
# Generate PWA icons from SVG source
# Requires: Inkscape or ImageMagick with librsvg
#
# Usage: ./scripts/generate-pwa-icons.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ICONS_DIR="$PROJECT_DIR/public/icons"
SOURCE_SVG="$ICONS_DIR/icon.svg"

# Icon sizes for PWA
SIZES=(72 96 128 144 152 192 384 512)

echo "Generating PWA icons from $SOURCE_SVG"

# Check if source SVG exists
if [ ! -f "$SOURCE_SVG" ]; then
    echo "Error: Source SVG not found at $SOURCE_SVG"
    exit 1
fi

# Try using Inkscape first (better quality)
if command -v inkscape &> /dev/null; then
    echo "Using Inkscape for conversion..."
    for size in "${SIZES[@]}"; do
        echo "  Generating icon-${size}.png"
        inkscape "$SOURCE_SVG" -w "$size" -h "$size" -o "$ICONS_DIR/icon-${size}.png" 2>/dev/null
    done

    # Generate maskable icons (with safe zone padding)
    for size in 192 512; do
        echo "  Generating icon-maskable-${size}.png"
        inkscape "$SOURCE_SVG" -w "$size" -h "$size" -o "$ICONS_DIR/icon-maskable-${size}.png" 2>/dev/null
    done

# Fallback to ImageMagick
elif command -v convert &> /dev/null; then
    echo "Using ImageMagick for conversion..."
    for size in "${SIZES[@]}"; do
        echo "  Generating icon-${size}.png"
        convert -background none -resize "${size}x${size}" "$SOURCE_SVG" "$ICONS_DIR/icon-${size}.png"
    done

    for size in 192 512; do
        echo "  Generating icon-maskable-${size}.png"
        convert -background none -resize "${size}x${size}" "$SOURCE_SVG" "$ICONS_DIR/icon-maskable-${size}.png"
    done

# No conversion tool available
else
    echo "Warning: Neither Inkscape nor ImageMagick found."
    echo "Please install one of them to generate PNG icons:"
    echo "  macOS: brew install inkscape"
    echo "  Ubuntu: sudo apt install inkscape"
    echo ""
    echo "Or use an online tool like https://realfavicongenerator.net/"
    exit 1
fi

# Generate shortcut icon
if [ -f "$ICONS_DIR/icon-96.png" ]; then
    cp "$ICONS_DIR/icon-96.png" "$ICONS_DIR/shortcut-requests.png"
    echo "  Created shortcut icon"
fi

echo "Done! Icons generated in $ICONS_DIR"
ls -la "$ICONS_DIR"/*.png 2>/dev/null || echo "No PNG files generated"
