const withPWA = require('next-pwa')({
  dest: 'public',
  scope: '/portal',
  sw: 'portal-sw.js',
  register: true,
  skipWaiting: true,
  disable: process.env.NODE_ENV === 'development',
  buildExcludes: [/middleware-manifest\.json$/],
  runtimeCaching: [
    {
      // Cache portal pages with stale-while-revalidate
      urlPattern: /^https?:\/\/.*\/portal(?:\/.*)?$/,
      handler: 'StaleWhileRevalidate',
      options: {
        cacheName: 'portal-pages',
        expiration: {
          maxEntries: 32,
          maxAgeSeconds: 24 * 60 * 60, // 24 hours
        },
      },
    },
    {
      // Cache portal API requests with network-first strategy
      urlPattern: /^https?:\/\/.*\/api\/v1\/portal\/.*/,
      handler: 'NetworkFirst',
      options: {
        cacheName: 'portal-api',
        networkTimeoutSeconds: 10,
        expiration: {
          maxEntries: 50,
          maxAgeSeconds: 24 * 60 * 60,
        },
        cacheableResponse: {
          statuses: [0, 200],
        },
      },
    },
    {
      // Cache static assets
      urlPattern: /\.(?:js|css|woff2?|png|jpg|jpeg|gif|svg|ico)$/i,
      handler: 'CacheFirst',
      options: {
        cacheName: 'static-assets',
        expiration: {
          maxEntries: 100,
          maxAgeSeconds: 30 * 24 * 60 * 60, // 30 days
        },
      },
    },
    {
      // Don't cache document upload API
      urlPattern: /^https?:\/\/.*\/api\/v1\/portal\/documents\/upload.*/,
      handler: 'NetworkOnly',
    },
  ],
});

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Enable React Strict Mode for better development experience
  reactStrictMode: true,

  // Output standalone for Docker deployment
  output: 'standalone',

  // Configure allowed image domains (add as needed)
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: '**.clairo.com.au',
      },
      {
        protocol: 'https',
        hostname: '**.clairo.ai',
      },
    ],
  },

  // Environment variables available to the browser
  env: {
    NEXT_PUBLIC_APP_NAME: 'Clairo',
    NEXT_PUBLIC_APP_VERSION: '0.1.0',
  },

  // Proxy API requests to backend.
  // BACKEND_INTERNAL_URL bypasses Cloudflare (direct Railway URL) for server-side rewrites.
  // Falls back to NEXT_PUBLIC_API_URL, then localhost for development.
  async rewrites() {
    const apiUrl = process.env.BACKEND_INTERNAL_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    return [
      {
        source: '/api/:path*',
        destination: `${apiUrl}/api/:path*`,
      },
    ];
  },

  // Security headers
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          {
            key: 'X-Frame-Options',
            value: 'DENY',
          },
          {
            key: 'X-Content-Type-Options',
            value: 'nosniff',
          },
          {
            key: 'Referrer-Policy',
            value: 'origin-when-cross-origin',
          },
        ],
      },
    ];
  },
};

module.exports = withPWA(nextConfig);
