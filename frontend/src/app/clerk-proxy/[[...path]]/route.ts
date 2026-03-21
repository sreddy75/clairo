import https from 'node:https';

import type { NextRequest } from 'next/server';
import { NextResponse } from 'next/server';

/**
 * Clerk Frontend API reverse proxy.
 *
 * Makes Clerk API requests same-origin to avoid cross-origin cookie
 * issues. Cookies from the Clerk backend are rewritten so the browser
 * stores them on the application domain.
 *
 * Env vars:
 *   CLERK_PROXY_TARGET  – Clerk hostname to proxy to (default: clerk.clairo.com.au)
 *   CLERK_COOKIE_DOMAIN – Cookie domain to set (e.g. ".clairo.com.au").
 *                         If unset, the domain attribute is stripped so the
 *                         cookie defaults to the exact request host (works on
 *                         public-suffix domains like .vercel.app).
 */

const CLERK_HOST = (process.env.CLERK_PROXY_TARGET || 'clerk.clairo.com.au').trim();
const CLERK_COOKIE_DOMAIN = process.env.CLERK_COOKIE_DOMAIN?.trim();

function rewriteCookieDomain(cookie: string): string {
  if (!CLERK_COOKIE_DOMAIN) {
    // Strip domain attribute — cookie defaults to the exact request host
    return cookie.replace(/;\s*domain=[^;]*/gi, '');
  }
  return cookie.replace(/domain=[^;]*/gi, `domain=${CLERK_COOKIE_DOMAIN}`);
}

function proxyToClerk(
  method: string,
  path: string,
  reqHeaders: Record<string, string>,
  body: Buffer | null,
): Promise<{ status: number; headers: [string, string][]; body: Buffer }> {
  return new Promise((resolve, reject) => {
    const options: https.RequestOptions = {
      hostname: CLERK_HOST,
      port: 443,
      path,
      method,
      headers: {
        ...reqHeaders,
        host: CLERK_HOST,
      },
    };

    const proxyReq = https.request(options, (proxyRes) => {
      const chunks: Buffer[] = [];
      proxyRes.on('data', (chunk: Buffer) => chunks.push(chunk));
      proxyRes.on('end', () => {
        const responseHeaders: [string, string][] = [];
        for (const [key, value] of Object.entries(proxyRes.headers)) {
          if (!value || key === 'transfer-encoding') continue;

          if (key === 'set-cookie' && Array.isArray(value)) {
            for (const cookie of value) {
              responseHeaders.push(['set-cookie', rewriteCookieDomain(cookie)]);
            }
          } else {
            const headerValue = Array.isArray(value) ? value.join(', ') : value;
            responseHeaders.push([key, headerValue]);
          }
        }
        resolve({
          status: proxyRes.statusCode || 500,
          headers: responseHeaders,
          body: Buffer.concat(chunks),
        });
      });
    });

    proxyReq.on('error', reject);

    if (body && body.length > 0) {
      proxyReq.write(body);
    }
    proxyReq.end();
  });
}

async function handler(req: NextRequest) {
  try {
    const path = req.nextUrl.pathname.replace(/^\/clerk-proxy/, '') || '/';
    const search = req.nextUrl.search || '';
    const fullPath = `${path}${search}`;

    // Forward safe headers (skip hop-by-hop, pseudo-headers, and edge-specific)
    const forwardHeaders: Record<string, string> = {};
    const skipHeaders = new Set([
      'host', 'connection', 'transfer-encoding', 'keep-alive',
      'upgrade', 'proxy-authorization', 'proxy-connection',
    ]);
    req.headers.forEach((value, key) => {
      if (!skipHeaders.has(key) && !key.startsWith(':') && !key.startsWith('x-vercel')) {
        forwardHeaders[key] = value;
      }
    });

    // Read request body if present
    let body: Buffer | null = null;
    if (req.method !== 'GET' && req.method !== 'HEAD') {
      const arrayBuffer = await req.arrayBuffer();
      body = Buffer.from(arrayBuffer);
    }

    const result = await proxyToClerk(req.method, fullPath, forwardHeaders, body);

    // Build response with proper multi-value set-cookie support
    const res = new NextResponse(new Uint8Array(result.body), {
      status: result.status,
    });
    for (const [key, value] of result.headers) {
      res.headers.append(key, value);
    }
    return res;
  } catch (error) {
    return NextResponse.json(
      { error: 'Clerk proxy error', detail: String(error) },
      { status: 502 },
    );
  }
}

export const GET = handler;
export const POST = handler;
export const PUT = handler;
export const PATCH = handler;
export const DELETE = handler;
export const OPTIONS = handler;
