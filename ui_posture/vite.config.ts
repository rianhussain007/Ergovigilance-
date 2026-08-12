import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import {defineConfig} from 'vite';

export default defineConfig(() => {
  return {
    plugins: [react(), tailwindcss()],
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
                '/api': {
                    target: 'http://127.0.0.1:8000',
                    changeOrigin: true,
                },
                '/video/': {
                    target: 'http://127.0.0.1:8000',
                    changeOrigin: true,
                },
                '/ws': {
                    target: 'http://127.0.0.1:8000',
                    ws: true,
                },
            },
    },
  };
});
