import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import {defineConfig} from 'vite';

export default defineConfig(() => {
  return {
    plugins: [react(), tailwindcss()],
    build: {
      // Chunking (docs/UX_SCORE_8_PROGRAM.md §W6). The single 521 kB entry chunk
      // we shipped mixed React, recharts, motion and every icon into one file,
      // so any dependency bump invalidated the whole app download. Vendor code
      // now sits in long-lived chunks and the entry stays under budget
      // (scripts/check_bundle_budget.mjs fails the build if that stops being
      // true).
      rollupOptions: {
        output: {
          manualChunks(id: string) {
            if (!id.includes('node_modules')) return undefined;
            if (id.includes('recharts') || id.includes('d3-')) return 'vendor-charts';
            if (id.includes('motion') || id.includes('framer-motion')) return 'vendor-motion';
            if (id.includes('lucide-react')) return 'vendor-icons';
            if (id.includes('@google/genai')) return 'vendor-ai';
            if (
              id.includes('/react/') ||
              id.includes('react-dom') ||
              id.includes('react-router') ||
              id.includes('scheduler')
            ) {
              return 'vendor-react';
            }
            return 'vendor';
          },
        },
      },
    },
    resolve: {
      alias: {
        '@': path.resolve(__dirname, '.'),
      },
    },
    server: {
        port: 3000, // HMR is disabled in AI Studio via DISABLE_HMR env var.
        // Do not modify—file watching is disabled to prevent flickering during agent edits.
        allowedHosts: true as const,
        hmr: process.env.DISABLE_HMR !== 'true',
        // Disable file watching when DISABLE_HMR is true to save CPU during agent edits.
        watch: process.env.DISABLE_HMR === 'true' ? undefined : {},
            proxy: {
                // Use 127.0.0.1 (IPv4) not localhost — Node resolves localhost to ::1
                // on some Windows setups, and uvicorn binds IPv4 127.0.0.1 only, which
                // made the proxy throw ECONNREFUSED and the UI show "Failed to fetch".
                // Keys starting with ^ are regexes: '/api' as a plain prefix
                // would also swallow the /api-docs frontend route (which
                // then 404'd as backend JSON). Anchored forms below match
                // only real API paths.
                '^/api/': {
                    target: 'http://127.0.0.1:8000',
                    changeOrigin: true,
                },
                '^/health': {
                    target: 'http://127.0.0.1:8000',
                    changeOrigin: true,
                },
                '^/healthz': {
                    target: 'http://127.0.0.1:8000',
                    changeOrigin: true,
                },
                '^/readyz': {
                    target: 'http://127.0.0.1:8000',
                    changeOrigin: true,
                },
                // Backend Swagger UI + OpenAPI spec for the ApiDocs page.
                // Without these, location / serves index.html and both links
                // break in dev (mirrors the nginx /docs + /openapi.json
                // locations in prod).
                '^/docs': {
                    target: 'http://127.0.0.1:8000',
                    changeOrigin: true,
                },
                '^/openapi\\.json$': {
                    target: 'http://127.0.0.1:8000',
                    changeOrigin: true,
                },
                '/video/': {
                    target: 'http://127.0.0.1:8000',
                    changeOrigin: true,
                    // Disable buffering for MJPEG streams — without this,
                    // the proxy holds the entire response in memory and the
                    // browser receives one frozen frame instead of a live stream.
                    configure: (proxy) => {
                        proxy.on('proxyRes', (proxyRes) => {
                            const contentType = proxyRes.headers['content-type'] || '';
                            if (contentType.includes('multipart')) {
                                // Force chunked transfer so frames stream in real-time
                                proxyRes.headers['cache-control'] = 'no-cache, no-store';
                                delete proxyRes.headers['content-length'];
                                delete proxyRes.headers['transfer-encoding'];
                                proxyRes.headers['transfer-encoding'] = 'chunked';
                            }
                        });
                    },
                },
                '/ws': {
                    target: 'http://127.0.0.1:8000',
                    ws: true,
                },
                '/cloud-api': {
                    target: 'http://127.0.0.1:8100',
                    changeOrigin: true,
                    // ws:true lets the cloud WebSocket (/cloud-api/cloud/ws) work
                    // through this prefix instead of needing a direct origin.
                    ws: true,
                    // Cloud core routes live under /api/cloud/... — map the UI's
                    // /cloud-api/cloud/... prefix onto that namespace.
                    rewrite: (path) => path.replace(/^\/cloud-api/, '/api'),
                    // NOTE for the cloud WS client (not yet wired up): the cloud
                    // socket has TWO alert delivery paths. Every 200 ms it sends
                    // {type:'update'} with recent_alerts — that snapshot is the
                    // GUARANTEED path. It ALSO emits {type:'alert'} the instant an
                    // alert is created, purely as an accelerator for toasts, and
                    // that same alert will normally also appear in the next
                    // update. De-duplicate on alert_id or every alert shows twice.
                },
            },
    },
  };
});
